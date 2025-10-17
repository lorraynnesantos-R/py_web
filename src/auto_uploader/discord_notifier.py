"""
Sistema de notificações Discord para Health Check

Este módulo implementa notificações no Discord quando APIs ficam offline
ou retornam ao status online.
"""

import sys
import asyncio
import aiohttp
import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from enum import Enum

# Adiciona o diretório src ao sys.path para imports
sys.path.append(str(Path(__file__).parent.parent))

from auto_uploader.health_checker import HealthCheckResult, HealthStatus


class NotificationLevel(Enum):
    """Níveis de notificação"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class DiscordWebhookConfig:
    """Configuração do webhook do Discord"""
    url: str
    username: str = "Health Monitor"
    avatar_url: Optional[str] = None
    enabled: bool = True


class DiscordNotifier:
    """
    Notificador Discord para eventos de health check
    """
    
    def __init__(self, data_dir: Path = None):
        """
        Inicializa o notificador Discord
        
        Args:
            data_dir: Diretório de dados (opcional)
        """
        self.data_dir = data_dir or Path("data")
        
        # Diretórios
        self.notifications_dir = self.data_dir / "notifications"
        self.notifications_dir.mkdir(parents=True, exist_ok=True)
        
        # Arquivos de configuração
        self.webhook_config_file = self.notifications_dir / "discord_config.json"
        self.notification_history_file = self.notifications_dir / "notification_history.json"
        
        # Logger
        self.logger = logging.getLogger("discord_notifier")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Estado interno
        self._webhook_configs: Dict[str, DiscordWebhookConfig] = {}
        self._notification_history: List[Dict[str, Any]] = []
        self._last_notification_per_url: Dict[str, str] = {}  # URL -> timestamp da última notificação
        
        self._load_webhook_configs()
        self._load_notification_history()
    
    def _load_webhook_configs(self) -> None:
        """Carrega configurações dos webhooks"""
        try:
            if self.webhook_config_file.exists():
                with open(self.webhook_config_file, 'r', encoding='utf-8') as f:
                    configs_data = json.load(f)
                
                for name, config_data in configs_data.items():
                    try:
                        self._webhook_configs[name] = DiscordWebhookConfig(**config_data)
                    except Exception as e:
                        self.logger.warning(f"Erro ao carregar config webhook {name}: {e}")
            else:
                # Criar configuração padrão
                default_config = {
                    "default": {
                        "url": "",  # Usuário precisa configurar
                        "username": "Health Monitor",
                        "avatar_url": None,
                        "enabled": False  # Desabilitado até ser configurado
                    }
                }
                self._save_webhook_configs(default_config)
        except Exception as e:
            self.logger.error(f"Erro ao carregar configurações webhook: {e}")
    
    def _save_webhook_configs(self, configs_data: Dict[str, Dict[str, Any]] = None) -> None:
        """Salva configurações dos webhooks"""
        try:
            if configs_data is None:
                configs_data = {}
                for name, config in self._webhook_configs.items():
                    configs_data[name] = {
                        "url": config.url,
                        "username": config.username,
                        "avatar_url": config.avatar_url,
                        "enabled": config.enabled
                    }
            
            with open(self.webhook_config_file, 'w', encoding='utf-8') as f:
                json.dump(configs_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Erro ao salvar configurações webhook: {e}")
    
    def _load_notification_history(self) -> None:
        """Carrega histórico de notificações"""
        try:
            if self.notification_history_file.exists():
                with open(self.notification_history_file, 'r', encoding='utf-8') as f:
                    self._notification_history = json.load(f)
                
                # Manter apenas as últimas 500 notificações
                if len(self._notification_history) > 500:
                    self._notification_history = self._notification_history[-500:]
        except Exception as e:
            self.logger.error(f"Erro ao carregar histórico de notificações: {e}")
    
    def _save_notification_history(self) -> None:
        """Salva histórico de notificações"""
        try:
            # Limitar histórico antes de salvar
            if len(self._notification_history) > 500:
                self._notification_history = self._notification_history[-500:]
            
            with open(self.notification_history_file, 'w', encoding='utf-8') as f:
                json.dump(self._notification_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Erro ao salvar histórico de notificações: {e}")
    
    def add_webhook(self, name: str, url: str, username: str = "Health Monitor", 
                   avatar_url: str = None, enabled: bool = True) -> None:
        """
        Adiciona ou atualiza configuração de webhook
        
        Args:
            name: Nome identificador do webhook
            url: URL do webhook Discord
            username: Nome de usuário para as mensagens
            avatar_url: URL do avatar (opcional)
            enabled: Se o webhook está habilitado
        """
        self._webhook_configs[name] = DiscordWebhookConfig(
            url=url,
            username=username,
            avatar_url=avatar_url,
            enabled=enabled
        )
        self._save_webhook_configs()
        self.logger.info(f"Webhook '{name}' configurado")
    
    def remove_webhook(self, name: str) -> bool:
        """
        Remove configuração de webhook
        
        Args:
            name: Nome do webhook
            
        Returns:
            True se removido com sucesso
        """
        if name in self._webhook_configs:
            del self._webhook_configs[name]
            self._save_webhook_configs()
            self.logger.info(f"Webhook '{name}' removido")
            return True
        return False
    
    def list_webhooks(self) -> Dict[str, Dict[str, Any]]:
        """Lista webhooks configurados"""
        result = {}
        for name, config in self._webhook_configs.items():
            result[name] = {
                "url": config.url[:50] + "..." if len(config.url) > 50 else config.url,
                "username": config.username,
                "enabled": config.enabled
            }
        return result
    
    def _get_color_for_status(self, status: HealthStatus) -> int:
        """Obtém cor do embed baseada no status"""
        color_map = {
            HealthStatus.ONLINE: 0x00ff00,      # Verde
            HealthStatus.DEGRADED: 0xffaa00,    # Laranja  
            HealthStatus.OFFLINE: 0xff0000,     # Vermelho
            HealthStatus.UNKNOWN: 0x888888      # Cinza
        }
        return color_map.get(status, 0x888888)
    
    def _get_emoji_for_status(self, status: HealthStatus) -> str:
        """Obtém emoji para o status"""
        emoji_map = {
            HealthStatus.ONLINE: "✅",
            HealthStatus.DEGRADED: "⚠️",
            HealthStatus.OFFLINE: "❌",
            HealthStatus.UNKNOWN: "❓"
        }
        return emoji_map.get(status, "❓")
    
    def _create_health_embed(self, result: HealthCheckResult, 
                           notification_type: str) -> Dict[str, Any]:
        """
        Cria embed do Discord para notificação de saúde
        
        Args:
            result: Resultado do health check
            notification_type: Tipo de notificação (status_change, downtime_alert, etc.)
            
        Returns:
            Dicionário do embed
        """
        emoji = self._get_emoji_for_status(result.status)
        color = self._get_color_for_status(result.status)
        
        # Título baseado no tipo de notificação
        title_map = {
            "status_change": f"{emoji} Mudança de Status - API",
            "downtime_alert": "🚨 Alerta de Downtime - API",
            "recovery": "🎉 API Recuperada",
            "degraded": "⚠️ API com Performance Degradada"
        }
        
        title = title_map.get(notification_type, f"{emoji} Status da API")
        
        embed = {
            "title": title,
            "color": color,
            "timestamp": result.timestamp,
            "fields": [
                {
                    "name": "🌐 URL",
                    "value": result.url,
                    "inline": False
                },
                {
                    "name": "📊 Status",
                    "value": f"{emoji} {result.status.value.upper()}",
                    "inline": True
                }
            ]
        }
        
        # Adicionar código de status se disponível
        if result.status_code:
            embed["fields"].append({
                "name": "🔢 Código HTTP",
                "value": str(result.status_code),
                "inline": True
            })
        
        # Adicionar tempo de resposta se disponível
        if result.response_time_ms is not None:
            embed["fields"].append({
                "name": "⏱️ Tempo de Resposta",
                "value": f"{result.response_time_ms:.1f}ms",
                "inline": True
            })
        
        # Adicionar erro se houver
        if result.error_message:
            embed["fields"].append({
                "name": "❗ Erro",
                "value": result.error_message[:1000],  # Limitar tamanho
                "inline": False
            })
        
        return embed
    
    async def _send_webhook_message(self, webhook_config: DiscordWebhookConfig, 
                                   embeds: List[Dict[str, Any]], 
                                   content: str = None) -> bool:
        """
        Envia mensagem para webhook do Discord
        
        Args:
            webhook_config: Configuração do webhook
            embeds: Lista de embeds
            content: Conteúdo da mensagem (opcional)
            
        Returns:
            True se enviado com sucesso
        """
        if not webhook_config.enabled or not webhook_config.url:
            return False
        
        payload = {
            "username": webhook_config.username,
            "embeds": embeds
        }
        
        if content:
            payload["content"] = content
        
        if webhook_config.avatar_url:
            payload["avatar_url"] = webhook_config.avatar_url
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_config.url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 204:
                        return True
                    else:
                        self.logger.warning(f"Webhook retornou status {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Erro ao enviar webhook: {e}")
            return False
    
    async def notify_status_change(self, result: HealthCheckResult, 
                                 previous_status: Optional[HealthStatus] = None) -> None:
        """
        Notifica mudança de status
        
        Args:
            result: Resultado atual
            previous_status: Status anterior (opcional)
        """
        if not self._webhook_configs:
            return
        
        # Determinar tipo de notificação
        notification_type = "status_change"
        
        if previous_status:
            if previous_status != HealthStatus.ONLINE and result.status == HealthStatus.ONLINE:
                notification_type = "recovery"
            elif result.status == HealthStatus.DEGRADED:
                notification_type = "degraded"
        
        embed = self._create_health_embed(result, notification_type)
        
        # Adicionar informação do status anterior se disponível
        if previous_status:
            previous_emoji = self._get_emoji_for_status(previous_status)
            embed["fields"].insert(1, {
                "name": "📈 Status Anterior",
                "value": f"{previous_emoji} {previous_status.value.upper()}",
                "inline": True
            })
        
        # Enviar para todos os webhooks habilitados
        tasks = []
        for name, webhook_config in self._webhook_configs.items():
            if webhook_config.enabled:
                task = asyncio.create_task(
                    self._send_webhook_message(webhook_config, [embed])
                )
                tasks.append(task)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if r is True)
            self.logger.info(f"Notificação de mudança de status enviada para {success_count}/{len(tasks)} webhooks")
            
            # Registrar no histórico
            self._add_to_history({
                "type": notification_type,
                "url": result.url,
                "status": result.status.value,
                "previous_status": previous_status.value if previous_status else None,
                "timestamp": result.timestamp,
                "webhooks_sent": success_count
            })
    
    async def notify_downtime_alert(self, url: str, downtime_minutes: int, 
                                  consecutive_failures: int) -> None:
        """
        Notifica alerta de downtime prolongado
        
        Args:
            url: URL da API
            downtime_minutes: Minutos de downtime
            consecutive_failures: Falhas consecutivas
        """
        if not self._webhook_configs:
            return
        
        # Verificar se já notificou recentemente para evitar spam
        last_notification_key = f"downtime_{url}"
        now = datetime.now(timezone.utc)
        
        if last_notification_key in self._last_notification_per_url:
            try:
                last_time = datetime.fromisoformat(self._last_notification_per_url[last_notification_key])
                if (now - last_time).total_seconds() < 1800:  # 30 minutos
                    return
            except Exception:
                pass
        
        embed = {
            "title": "🚨 Alerta de Downtime Prolongado",
            "color": 0xff0000,  # Vermelho
            "timestamp": now.isoformat(),
            "fields": [
                {
                    "name": "🌐 URL",
                    "value": url,
                    "inline": False
                },
                {
                    "name": "⏰ Tempo de Downtime",
                    "value": f"{downtime_minutes} minutos",
                    "inline": True
                },
                {
                    "name": "🔢 Falhas Consecutivas",
                    "value": str(consecutive_failures),
                    "inline": True
                },
                {
                    "name": "📋 Ação Recomendada",
                    "value": "Verificar logs do servidor e conectividade de rede",
                    "inline": False
                }
            ]
        }
        
        # Enviar para todos os webhooks habilitados
        tasks = []
        for name, webhook_config in self._webhook_configs.items():
            if webhook_config.enabled:
                task = asyncio.create_task(
                    self._send_webhook_message(
                        webhook_config, 
                        [embed],
                        f"@here API {url} está offline há {downtime_minutes} minutos!"
                    )
                )
                tasks.append(task)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if r is True)
            self.logger.info(f"Alerta de downtime enviado para {success_count}/{len(tasks)} webhooks")
            
            # Atualizar timestamp da última notificação
            self._last_notification_per_url[last_notification_key] = now.isoformat()
            
            # Registrar no histórico
            self._add_to_history({
                "type": "downtime_alert",
                "url": url,
                "downtime_minutes": downtime_minutes,
                "consecutive_failures": consecutive_failures,
                "timestamp": now.isoformat(),
                "webhooks_sent": success_count
            })
    
    async def send_health_summary(self, results: Dict[str, HealthCheckResult]) -> None:
        """
        Envia resumo de saúde de múltiplas APIs
        
        Args:
            results: Dicionário com resultados por URL
        """
        if not self._webhook_configs or not results:
            return
        
        online_count = sum(1 for r in results.values() if r.is_healthy)
        total_count = len(results)
        
        # Determinar cor baseada na proporção de APIs online
        if online_count == total_count:
            color = 0x00ff00  # Verde
            status_emoji = "✅"
        elif online_count >= total_count * 0.8:
            color = 0xffaa00  # Laranja
            status_emoji = "⚠️"
        else:
            color = 0xff0000  # Vermelho
            status_emoji = "❌"
        
        embed = {
            "title": f"{status_emoji} Resumo de Saúde das APIs",
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fields": [
                {
                    "name": "📊 Status Geral",
                    "value": f"{online_count}/{total_count} APIs online ({(online_count/total_count)*100:.1f}%)",
                    "inline": False
                }
            ]
        }
        
        # Adicionar detalhes das APIs
        online_apis = []
        offline_apis = []
        degraded_apis = []
        
        for url, result in results.items():
            api_name = url.split("//")[1].split("/")[0] if "//" in url else url
            
            if result.status == HealthStatus.ONLINE:
                response_info = f" ({result.response_time_ms:.0f}ms)" if result.response_time_ms else ""
                online_apis.append(f"✅ {api_name}{response_info}")
            elif result.status == HealthStatus.DEGRADED:
                response_info = f" ({result.response_time_ms:.0f}ms)" if result.response_time_ms else ""
                degraded_apis.append(f"⚠️ {api_name}{response_info}")
            else:
                error_info = f" - {result.error_message[:50]}..." if result.error_message else ""
                offline_apis.append(f"❌ {api_name}{error_info}")
        
        if online_apis:
            embed["fields"].append({
                "name": f"✅ Online ({len(online_apis)})",
                "value": "\n".join(online_apis[:10]),  # Máximo 10
                "inline": False
            })
        
        if degraded_apis:
            embed["fields"].append({
                "name": f"⚠️ Degradadas ({len(degraded_apis)})",
                "value": "\n".join(degraded_apis[:10]),
                "inline": False
            })
        
        if offline_apis:
            embed["fields"].append({
                "name": f"❌ Offline ({len(offline_apis)})",
                "value": "\n".join(offline_apis[:10]),
                "inline": False
            })
        
        # Enviar para todos os webhooks habilitados
        tasks = []
        for name, webhook_config in self._webhook_configs.items():
            if webhook_config.enabled:
                task = asyncio.create_task(
                    self._send_webhook_message(webhook_config, [embed])
                )
                tasks.append(task)
        
        if tasks:
            results_sent = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results_sent if r is True)
            self.logger.info(f"Resumo de saúde enviado para {success_count}/{len(tasks)} webhooks")
            
            # Registrar no histórico
            self._add_to_history({
                "type": "health_summary",
                "total_apis": total_count,
                "online_apis": online_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "webhooks_sent": success_count
            })
    
    def _add_to_history(self, notification_data: Dict[str, Any]) -> None:
        """Adiciona notificação ao histórico"""
        self._notification_history.append(notification_data)
        
        # Manter apenas as últimas 500 notificações
        if len(self._notification_history) > 500:
            self._notification_history = self._notification_history[-500:]
        
        self._save_notification_history()
    
    def get_notification_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Obtém histórico de notificações
        
        Args:
            limit: Limite de notificações
            
        Returns:
            Lista com histórico das notificações
        """
        return list(reversed(self._notification_history[-limit:]))
    
    async def test_webhook(self, name: str) -> bool:
        """
        Testa um webhook específico
        
        Args:
            name: Nome do webhook
            
        Returns:
            True se o teste foi bem-sucedido
        """
        if name not in self._webhook_configs:
            self.logger.error(f"Webhook '{name}' não encontrado")
            return False
        
        webhook_config = self._webhook_configs[name]
        
        embed = {
            "title": "🧪 Teste de Webhook",
            "description": "Esta é uma mensagem de teste do Health Monitor",
            "color": 0x0099ff,  # Azul
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fields": [
                {
                    "name": "✅ Status",
                    "value": "Webhook funcionando corretamente!",
                    "inline": False
                }
            ]
        }
        
        success = await self._send_webhook_message(webhook_config, [embed])
        
        if success:
            self.logger.info(f"Teste do webhook '{name}' bem-sucedido")
        else:
            self.logger.error(f"Teste do webhook '{name}' falhou")
        
        return success