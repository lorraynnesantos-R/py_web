"""
Integração do Health Checker com AutoUpdateScheduler

Este módulo integra o sistema de Health Check com o agendador de
auto-updates, verificando a saúde das APIs antes de iniciar ciclos.
"""

import sys
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

# Adiciona o diretório src ao sys.path para imports
sys.path.append(str(Path(__file__).parent.parent))

from auto_uploader.health_checker import APIHealthChecker, HealthCheckResult, HealthStatus
from auto_uploader.discord_notifier import DiscordNotifier


class HealthIntegrationManager:
    """
    Gerenciador de integração entre Health Check e Auto Update
    """
    
    def __init__(self, data_dir: Path = None):
        """
        Inicializa o gerenciador de integração
        
        Args:
            data_dir: Diretório de dados (opcional)
        """
        self.data_dir = data_dir or Path("data")
        
        # Componentes
        self.health_checker = APIHealthChecker(self.data_dir)
        self.discord_notifier = DiscordNotifier(self.data_dir)
        
        # Logger
        self.logger = logging.getLogger("health_integration")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Estado interno
        self._previous_statuses: Dict[str, HealthStatus] = {}
        self._notification_sent_for_downtime: Dict[str, bool] = {}
    
    async def check_apis_before_update(self, provider_urls: List[str], 
                                     min_healthy_percentage: float = 0.7) -> Dict[str, Any]:
        """
        Verifica APIs antes de iniciar auto-update
        
        Args:
            provider_urls: Lista de URLs dos providers
            min_healthy_percentage: Porcentagem mínima de APIs saudáveis
            
        Returns:
            Dicionário com resultado da verificação
        """
        self.logger.info(f"🔍 Verificando saúde de {len(provider_urls)} providers antes do auto-update")
        
        # Executar health checks
        results = await self.health_checker.check_multiple_urls(provider_urls, use_cache=True)
        
        # Analisar resultados
        total_apis = len(results)
        healthy_apis = sum(1 for r in results.values() if r.is_healthy)
        healthy_percentage = (healthy_apis / total_apis) * 100 if total_apis > 0 else 0
        
        # Determinar se pode prosseguir
        can_proceed = healthy_percentage >= (min_healthy_percentage * 100)
        
        # Categorizar APIs
        online_apis = []
        offline_apis = []
        degraded_apis = []
        
        for url, result in results.items():
            if result.status == HealthStatus.ONLINE:
                online_apis.append(url)
            elif result.status == HealthStatus.DEGRADED:
                degraded_apis.append(url)
            else:
                offline_apis.append(url)
        
        summary = {
            "can_proceed": can_proceed,
            "total_apis": total_apis,
            "healthy_apis": healthy_apis,
            "healthy_percentage": round(healthy_percentage, 1),
            "min_required_percentage": round(min_healthy_percentage * 100, 1),
            "online_apis": online_apis,
            "degraded_apis": degraded_apis,
            "offline_apis": offline_apis,
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Log do resultado
        if can_proceed:
            self.logger.info(f"✅ Auto-update pode prosseguir: {healthy_apis}/{total_apis} APIs saudáveis ({healthy_percentage:.1f}%)")
        else:
            self.logger.warning(f"❌ Auto-update bloqueado: apenas {healthy_apis}/{total_apis} APIs saudáveis ({healthy_percentage:.1f}% < {min_healthy_percentage * 100:.1f}%)")
        
        # Processar mudanças de status e notificações
        await self._process_status_changes(results)
        
        return summary
    
    async def _process_status_changes(self, results: Dict[str, HealthCheckResult]) -> None:
        """
        Processa mudanças de status e envia notificações
        
        Args:
            results: Resultados dos health checks
        """
        for url, result in results.items():
            current_status = result.status
            previous_status = self._previous_statuses.get(url)
            
            # Verificar mudança de status
            if previous_status and previous_status != current_status:
                self.logger.info(f"🔄 Mudança de status para {url}: {previous_status.value} → {current_status.value}")
                
                # Notificar mudança de status
                try:
                    await self.discord_notifier.notify_status_change(result, previous_status)
                except Exception as e:
                    self.logger.error(f"Erro ao notificar mudança de status para {url}: {e}")
            
            # Verificar se precisa notificar downtime prolongado
            if (not result.is_healthy and 
                self.health_checker.should_notify_downtime(url) and
                not self._notification_sent_for_downtime.get(url, False)):
                
                try:
                    metrics = self.health_checker.get_metrics(url)
                    if metrics:
                        # Calcular tempo de downtime
                        downtime_minutes = 0
                        if metrics.last_offline:
                            try:
                                last_offline = datetime.fromisoformat(metrics.last_offline.replace('Z', '+00:00'))
                                now = datetime.now(timezone.utc)
                                downtime_minutes = int((now - last_offline).total_seconds() / 60)
                            except Exception:
                                pass
                        
                        await self.discord_notifier.notify_downtime_alert(
                            url, 
                            downtime_minutes, 
                            metrics.consecutive_failures
                        )
                        
                        # Marcar como notificado para evitar spam
                        self._notification_sent_for_downtime[url] = True
                        
                except Exception as e:
                    self.logger.error(f"Erro ao notificar downtime para {url}: {e}")
            
            # Se a API voltou ao normal, limpar flag de notificação
            if result.is_healthy and url in self._notification_sent_for_downtime:
                del self._notification_sent_for_downtime[url]
            
            # Atualizar status anterior
            self._previous_statuses[url] = current_status
    
    async def get_provider_health_report(self, provider_urls: List[str]) -> Dict[str, Any]:
        """
        Gera relatório de saúde detalhado dos providers
        
        Args:
            provider_urls: Lista de URLs dos providers
            
        Returns:
            Relatório detalhado
        """
        self.logger.info("📊 Gerando relatório de saúde dos providers")
        
        # Verificar saúde atual
        current_results = await self.health_checker.check_multiple_urls(provider_urls, use_cache=False)
        
        # Coletar métricas e resumos de uptime
        provider_reports = {}
        
        for url in provider_urls:
            metrics = self.health_checker.get_metrics(url)
            uptime_24h = self.health_checker.get_uptime_summary(url, hours=24)
            uptime_7d = self.health_checker.get_uptime_summary(url, hours=168)  # 7 dias
            recent_history = self.health_checker.get_recent_history(url, limit=20)
            
            current_result = current_results.get(url)
            
            provider_reports[url] = {
                "current_status": current_result.status.value if current_result else "unknown",
                "current_response_time_ms": current_result.response_time_ms if current_result else None,
                "last_error": current_result.error_message if current_result and current_result.error_message else None,
                "metrics": {
                    "total_checks": metrics.total_checks if metrics else 0,
                    "successful_checks": metrics.successful_checks if metrics else 0,
                    "failure_rate": metrics.failure_rate if metrics else 0.0,
                    "avg_response_time_ms": metrics.avg_response_time_ms if metrics else 0.0,
                    "consecutive_failures": metrics.consecutive_failures if metrics else 0,
                    "consecutive_successes": metrics.consecutive_successes if metrics else 0
                },
                "uptime_24h": uptime_24h,
                "uptime_7d": uptime_7d,
                "recent_history": [
                    {
                        "timestamp": h.timestamp,
                        "status": h.status.value,
                        "response_time_ms": h.response_time_ms,
                        "error": h.error_message
                    }
                    for h in recent_history
                ]
            }
        
        # Estatísticas gerais
        total_providers = len(provider_urls)
        online_providers = sum(1 for r in current_results.values() if r.is_healthy)
        
        overall_uptime_24h = []
        overall_uptime_7d = []
        
        for url in provider_urls:
            uptime_24h = self.health_checker.get_uptime_summary(url, hours=24)
            uptime_7d = self.health_checker.get_uptime_summary(url, hours=168)
            
            if uptime_24h["total_checks"] > 0:
                overall_uptime_24h.append(uptime_24h["uptime_percentage"])
            if uptime_7d["total_checks"] > 0:
                overall_uptime_7d.append(uptime_7d["uptime_percentage"])
        
        avg_uptime_24h = sum(overall_uptime_24h) / len(overall_uptime_24h) if overall_uptime_24h else 0
        avg_uptime_7d = sum(overall_uptime_7d) / len(overall_uptime_7d) if overall_uptime_7d else 0
        
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_providers": total_providers,
                "online_providers": online_providers,
                "online_percentage": (online_providers / total_providers) * 100 if total_providers > 0 else 0,
                "avg_uptime_24h": round(avg_uptime_24h, 2),
                "avg_uptime_7d": round(avg_uptime_7d, 2)
            },
            "providers": provider_reports
        }
        
        return report
    
    async def monitor_providers_continuously(self, provider_urls: List[str], 
                                          check_interval_minutes: int = 15,
                                          summary_interval_hours: int = 6) -> None:
        """
        Monitora providers continuamente
        
        Args:
            provider_urls: Lista de URLs dos providers
            check_interval_minutes: Intervalo entre verificações em minutos
            summary_interval_hours: Intervalo para envio de resumos em horas
        """
        self.logger.info(f"🔄 Iniciando monitoramento contínuo de {len(provider_urls)} providers")
        self.logger.info(f"   • Verificações a cada {check_interval_minutes} minutos")
        self.logger.info(f"   • Resumos a cada {summary_interval_hours} horas")
        
        last_summary_time = datetime.now(timezone.utc)
        
        while True:
            try:
                # Executar verificações de saúde
                results = await self.health_checker.check_multiple_urls(provider_urls, use_cache=False)
                
                # Processar mudanças de status e notificações
                await self._process_status_changes(results)
                
                # Verificar se é hora de enviar resumo
                now = datetime.now(timezone.utc)
                time_since_summary = (now - last_summary_time).total_seconds() / 3600
                
                if time_since_summary >= summary_interval_hours:
                    try:
                        await self.discord_notifier.send_health_summary(results)
                        last_summary_time = now
                    except Exception as e:
                        self.logger.error(f"Erro ao enviar resumo de saúde: {e}")
                
                # Aguardar próxima verificação
                await asyncio.sleep(check_interval_minutes * 60)
                
            except KeyboardInterrupt:
                self.logger.info("Monitoramento interrompido pelo usuário")
                break
            except Exception as e:
                self.logger.error(f"Erro no monitoramento contínuo: {e}")
                await asyncio.sleep(60)  # Aguardar 1 minuto antes de tentar novamente
    
    def get_health_dashboard_data(self, provider_urls: List[str]) -> Dict[str, Any]:
        """
        Obtém dados para dashboard de saúde
        
        Args:
            provider_urls: Lista de URLs dos providers
            
        Returns:
            Dados estruturados para dashboard
        """
        dashboard_data = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "providers": []
        }
        
        for url in provider_urls:
            # Status atual (do cache)
            current_status = "unknown"
            response_time = None
            
            if url in self.health_checker._last_check_cache:
                result = self.health_checker._last_check_cache[url]
                current_status = result.status.value
                response_time = result.response_time_ms
            
            # Métricas
            metrics = self.health_checker.get_metrics(url)
            
            # Uptime recente
            uptime_24h = self.health_checker.get_uptime_summary(url, hours=24)
            
            provider_data = {
                "url": url,
                "name": url.split("//")[1].split("/")[0] if "//" in url else url,
                "current_status": current_status,
                "response_time_ms": response_time,
                "uptime_percentage_24h": uptime_24h.get("uptime_percentage", 0),
                "total_checks": metrics.total_checks if metrics else 0,
                "consecutive_failures": metrics.consecutive_failures if metrics else 0,
                "last_online": metrics.last_online if metrics else None,
                "last_offline": metrics.last_offline if metrics else None
            }
            
            dashboard_data["providers"].append(provider_data)
        
        return dashboard_data
    
    async def configure_discord_webhook(self, name: str, webhook_url: str, 
                                      username: str = "Health Monitor") -> bool:
        """
        Configura webhook do Discord
        
        Args:
            name: Nome do webhook
            webhook_url: URL do webhook
            username: Nome de usuário
            
        Returns:
            True se configurado com sucesso
        """
        try:
            self.discord_notifier.add_webhook(name, webhook_url, username)
            
            # Testar webhook
            test_result = await self.discord_notifier.test_webhook(name)
            
            if test_result:
                self.logger.info(f"✅ Webhook '{name}' configurado e testado com sucesso")
                return True
            else:
                self.logger.error(f"❌ Webhook '{name}' configurado mas falhou no teste")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro ao configurar webhook '{name}': {e}")
            return False