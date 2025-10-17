"""
Sistema de Health Check para API

Este módulo implementa verificação de disponibilidade da API antes dos
ciclos de auto-update, evitando tentativas desnecessárias quando o site
estiver offline.
"""

import sys
import asyncio
import aiohttp
import logging
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import math

# Adiciona o diretório src ao sys.path para imports
sys.path.append(str(Path(__file__).parent.parent))


class HealthStatus(Enum):
    """Status de saúde da API"""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Resultado de uma verificação de health check"""
    url: str
    status: HealthStatus
    response_time_ms: Optional[float] = None
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @property
    def is_healthy(self) -> bool:
        """Retorna True se a API está saudável"""
        return self.status == HealthStatus.ONLINE
    
    @property
    def response_time_seconds(self) -> Optional[float]:
        """Retorna tempo de resposta em segundos"""
        if self.response_time_ms is not None:
            return self.response_time_ms / 1000.0
        return None


@dataclass
class HealthMetrics:
    """Métricas de saúde da API"""
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    last_online: Optional[str] = None
    last_offline: Optional[str] = None
    avg_response_time_ms: float = 0.0
    uptime_percentage: float = 100.0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    
    @property
    def failure_rate(self) -> float:
        """Taxa de falha em porcentagem"""
        if self.total_checks == 0:
            return 0.0
        return (self.failed_checks / self.total_checks) * 100
    
    def update_from_result(self, result: HealthCheckResult) -> None:
        """Atualiza métricas com base em um resultado"""
        self.total_checks += 1
        
        if result.is_healthy:
            self.successful_checks += 1
            self.consecutive_successes += 1
            self.consecutive_failures = 0
            self.last_online = result.timestamp
            
            # Atualizar tempo médio de resposta
            if result.response_time_ms is not None:
                if self.avg_response_time_ms == 0:
                    self.avg_response_time_ms = result.response_time_ms
                else:
                    # Média móvel simples
                    self.avg_response_time_ms = (self.avg_response_time_ms + result.response_time_ms) / 2
        else:
            self.failed_checks += 1
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            self.last_offline = result.timestamp
        
        # Recalcular uptime
        if self.total_checks > 0:
            self.uptime_percentage = (self.successful_checks / self.total_checks) * 100


class APIHealthChecker:
    """
    Verificador de saúde da API com retry automático e cache
    """
    
    def __init__(self, data_dir: Path = None):
        """
        Inicializa o health checker
        
        Args:
            data_dir: Diretório de dados (opcional)
        """
        self.data_dir = data_dir or Path("data")
        
        # Diretórios
        self.health_dir = self.data_dir / "health"
        self.health_dir.mkdir(parents=True, exist_ok=True)
        
        # Arquivos de controle
        self.metrics_file = self.health_dir / "health_metrics.json"
        self.history_file = self.health_dir / "health_history.json"
        self.config_file = self.health_dir / "health_config.json"
        
        # Configurações padrão
        self.default_config = {
            "timeout_seconds": 10,
            "max_retries": 3,
            "retry_backoff_base": 2,
            "cache_duration_minutes": 5,
            "notification_threshold_minutes": 60,
            "degraded_threshold_ms": 5000,
            "max_history_entries": 1000
        }
        
        # Logger
        self.logger = logging.getLogger("api_health_checker")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Estado interno
        self._config = self._load_config()
        self._metrics: Dict[str, HealthMetrics] = {}
        self._history: List[HealthCheckResult] = []
        self._last_check_cache: Dict[str, HealthCheckResult] = {}
        
        self._load_metrics()
        self._load_history()
    
    def _load_config(self) -> Dict[str, Any]:
        """Carrega configurações do health checker"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # Mesclar com configurações padrão
                merged_config = self.default_config.copy()
                merged_config.update(config)
                return merged_config
            else:
                # Salvar configurações padrão
                self._save_config(self.default_config)
                return self.default_config.copy()
        except Exception as e:
            self.logger.error(f"Erro ao carregar configurações: {e}")
            return self.default_config.copy()
    
    def _save_config(self, config: Dict[str, Any]) -> None:
        """Salva configurações do health checker"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Erro ao salvar configurações: {e}")
    
    def _load_metrics(self) -> None:
        """Carrega métricas de saúde"""
        try:
            if self.metrics_file.exists():
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    metrics_data = json.load(f)
                
                for url, data in metrics_data.items():
                    try:
                        self._metrics[url] = HealthMetrics(**data)
                    except Exception as e:
                        self.logger.warning(f"Erro ao carregar métricas para {url}: {e}")
        except Exception as e:
            self.logger.error(f"Erro ao carregar métricas: {e}")
    
    def _save_metrics(self) -> None:
        """Salva métricas de saúde"""
        try:
            metrics_data = {}
            for url, metrics in self._metrics.items():
                metrics_data[url] = asdict(metrics)
            
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(metrics_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Erro ao salvar métricas: {e}")
    
    def _load_history(self) -> None:
        """Carrega histórico de verificações"""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                
                for data in history_data:
                    try:
                        # Converter string de status de volta para enum
                        if 'status' in data and isinstance(data['status'], str):
                            data['status'] = HealthStatus(data['status'])
                        result = HealthCheckResult(**data)
                        self._history.append(result)
                    except Exception as e:
                        self.logger.warning(f"Erro ao carregar entrada do histórico: {e}")
                        
                # Manter apenas as últimas entradas
                max_entries = self._config.get("max_history_entries", 1000)
                if len(self._history) > max_entries:
                    self._history = self._history[-max_entries:]
                    
        except Exception as e:
            self.logger.error(f"Erro ao carregar histórico: {e}")
    
    def _save_history(self) -> None:
        """Salva histórico de verificações"""
        try:
            # Limitar histórico antes de salvar
            max_entries = self._config.get("max_history_entries", 1000)
            if len(self._history) > max_entries:
                self._history = self._history[-max_entries:]
            
            history_data = []
            for result in self._history:
                result_dict = asdict(result)
                # Converter enum para string para serialização JSON
                if isinstance(result_dict.get('status'), HealthStatus):
                    result_dict['status'] = result_dict['status'].value
                history_data.append(result_dict)
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Erro ao salvar histórico: {e}")
    
    def _is_cache_valid(self, url: str) -> bool:
        """Verifica se o cache para uma URL ainda é válido"""
        if url not in self._last_check_cache:
            return False
        
        last_result = self._last_check_cache[url]
        try:
            last_check = datetime.fromisoformat(last_result.timestamp.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            cache_duration = timedelta(minutes=self._config.get("cache_duration_minutes", 5))
            
            return (now - last_check) < cache_duration
        except Exception:
            return False
    
    async def _perform_health_check(self, url: str, timeout: float) -> HealthCheckResult:
        """
        Executa uma verificação de saúde
        
        Args:
            url: URL para verificar
            timeout: Timeout em segundos
            
        Returns:
            Resultado da verificação
        """
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session:
                async with session.get(url) as response:
                    end_time = time.time()
                    response_time_ms = (end_time - start_time) * 1000
                    
                    # Determinar status baseado no código de resposta e tempo
                    if 200 <= response.status < 300:
                        degraded_threshold = self._config.get("degraded_threshold_ms", 5000)
                        if response_time_ms > degraded_threshold:
                            status = HealthStatus.DEGRADED
                        else:
                            status = HealthStatus.ONLINE
                    else:
                        status = HealthStatus.OFFLINE
                    
                    return HealthCheckResult(
                        url=url,
                        status=status,
                        response_time_ms=response_time_ms,
                        status_code=response.status,
                        timestamp=datetime.now(timezone.utc).isoformat()
                    )
                    
        except asyncio.TimeoutError:
            return HealthCheckResult(
                url=url,
                status=HealthStatus.OFFLINE,
                error_message="Timeout na requisição",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        except Exception as e:
            return HealthCheckResult(
                url=url,
                status=HealthStatus.OFFLINE,
                error_message=str(e),
                timestamp=datetime.now(timezone.utc).isoformat()
            )
    
    async def check_health(self, url: str, use_cache: bool = True) -> HealthCheckResult:
        """
        Verifica a saúde de uma URL com retry automático
        
        Args:
            url: URL para verificar
            use_cache: Se deve usar cache
            
        Returns:
            Resultado da verificação
        """
        # Verificar cache primeiro
        if use_cache and self._is_cache_valid(url):
            cached_result = self._last_check_cache[url]
            self.logger.debug(f"Usando resultado em cache para {url}: {cached_result.status.value}")
            return cached_result
        
        timeout = self._config.get("timeout_seconds", 10)
        max_retries = self._config.get("max_retries", 3)
        backoff_base = self._config.get("retry_backoff_base", 2)
        
        last_result = None
        
        for attempt in range(max_retries + 1):
            try:
                result = await self._perform_health_check(url, timeout)
                
                if result.is_healthy or attempt == max_retries:
                    # Sucesso ou última tentativa
                    self._last_check_cache[url] = result
                    self._update_metrics(result)
                    self._add_to_history(result)
                    
                    if result.is_healthy:
                        self.logger.info(f"✅ API {url} está online (tempo: {result.response_time_ms:.1f}ms)")
                    else:
                        self.logger.warning(f"❌ API {url} está offline: {result.error_message or 'Status ' + str(result.status_code)}")
                    
                    return result
                
                last_result = result
                
                # Backoff exponencial antes do próximo retry
                if attempt < max_retries:
                    sleep_time = backoff_base ** attempt
                    self.logger.debug(f"Tentativa {attempt + 1} falhou para {url}, tentando novamente em {sleep_time}s")
                    await asyncio.sleep(sleep_time)
                    
            except Exception as e:
                self.logger.error(f"Erro na tentativa {attempt + 1} para {url}: {e}")
                if attempt == max_retries:
                    result = HealthCheckResult(
                        url=url,
                        status=HealthStatus.OFFLINE,
                        error_message=f"Falha após {max_retries + 1} tentativas: {e}",
                        timestamp=datetime.now(timezone.utc).isoformat()
                    )
                    
                    self._last_check_cache[url] = result
                    self._update_metrics(result)
                    self._add_to_history(result)
                    
                    return result
        
        # Se chegou aqui, algo deu muito errado
        return last_result or HealthCheckResult(
            url=url,
            status=HealthStatus.UNKNOWN,
            error_message="Erro desconhecido no health check",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    def _update_metrics(self, result: HealthCheckResult) -> None:
        """Atualiza métricas com base no resultado"""
        url = result.url
        
        if url not in self._metrics:
            self._metrics[url] = HealthMetrics()
        
        self._metrics[url].update_from_result(result)
        self._save_metrics()
    
    def _add_to_history(self, result: HealthCheckResult) -> None:
        """Adiciona resultado ao histórico"""
        self._history.append(result)
        
        # Manter apenas as últimas entradas
        max_entries = self._config.get("max_history_entries", 1000) 
        if len(self._history) > max_entries:
            self._history = self._history[-max_entries:]
        
        self._save_history()
    
    async def check_multiple_urls(self, urls: List[str], use_cache: bool = True) -> Dict[str, HealthCheckResult]:
        """
        Verifica múltiplas URLs em paralelo
        
        Args:
            urls: Lista de URLs para verificar
            use_cache: Se deve usar cache
            
        Returns:
            Dicionário com resultados por URL
        """
        self.logger.info(f"🔍 Verificando saúde de {len(urls)} APIs")
        
        tasks = []
        for url in urls:
            task = asyncio.create_task(self.check_health(url, use_cache))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        result_dict = {}
        online_count = 0
        
        for i, result in enumerate(results):
            url = urls[i]
            result_dict[url] = result
            
            if result.is_healthy:
                online_count += 1
        
        self.logger.info(f"📊 Resultado: {online_count}/{len(urls)} APIs online")
        
        return result_dict
    
    def get_metrics(self, url: str) -> Optional[HealthMetrics]:
        """Obtém métricas para uma URL"""
        return self._metrics.get(url)
    
    def get_all_metrics(self) -> Dict[str, HealthMetrics]:
        """Obtém todas as métricas"""
        return self._metrics.copy()
    
    def get_recent_history(self, url: str = None, limit: int = 100) -> List[HealthCheckResult]:
        """
        Obtém histórico recente de verificações
        
        Args:
            url: URL específica (opcional)
            limit: Limite de resultados
            
        Returns:
            Lista de resultados recentes
        """
        history = self._history
        
        if url:
            history = [r for r in history if r.url == url]
        
        # Retornar os mais recentes primeiro
        return list(reversed(history[-limit:]))
    
    def is_api_healthy(self, url: str) -> bool:
        """
        Verifica se uma API está saudável baseado no último check
        
        Args:
            url: URL para verificar
            
        Returns:
            True se a API está saudável
        """
        if url in self._last_check_cache:
            return self._last_check_cache[url].is_healthy
        return False
    
    def should_notify_downtime(self, url: str) -> bool:
        """
        Verifica se deve notificar sobre downtime prolongado
        
        Args:
            url: URL para verificar
            
        Returns:
            True se deve notificar
        """
        metrics = self.get_metrics(url)
        if not metrics:
            return False
        
        threshold_minutes = self._config.get("notification_threshold_minutes", 60)
        
        # Se tem muitas falhas consecutivas e a última verificação foi offline
        if (metrics.consecutive_failures >= 3 and 
            url in self._last_check_cache and 
            not self._last_check_cache[url].is_healthy):
            
            # Verificar se está offline há muito tempo
            if metrics.last_offline:
                try:
                    last_offline = datetime.fromisoformat(metrics.last_offline.replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    downtime_minutes = (now - last_offline).total_seconds() / 60
                    
                    return downtime_minutes >= threshold_minutes
                except Exception:
                    pass
        
        return False
    
    def get_config(self) -> Dict[str, Any]:
        """Obtém configuração atual"""
        return self._config.copy()
    
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """
        Atualiza configuração
        
        Args:
            new_config: Novas configurações
        """
        self._config.update(new_config)
        self._save_config(self._config)
        self.logger.info("Configuração atualizada")
    
    def clear_cache(self) -> None:
        """Limpa cache de verificações"""
        self._last_check_cache.clear()
        self.logger.info("Cache de health checks limpo")
    
    def get_uptime_summary(self, url: str, hours: int = 24) -> Dict[str, Any]:
        """
        Obtém resumo de uptime para uma URL
        
        Args:
            url: URL para analisar
            hours: Período em horas para analisar
            
        Returns:
            Resumo de uptime
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        # Filtrar histórico pelo período
        relevant_history = []
        for result in self._history:
            if result.url == url:
                try:
                    result_time = datetime.fromisoformat(result.timestamp.replace('Z', '+00:00'))
                    if result_time >= cutoff:
                        relevant_history.append(result)
                except Exception:
                    continue
        
        if not relevant_history:
            return {
                "url": url,
                "period_hours": hours,
                "total_checks": 0,
                "uptime_percentage": 0.0,
                "avg_response_time_ms": 0.0,
                "status": "no_data"
            }
        
        online_checks = sum(1 for r in relevant_history if r.is_healthy)
        total_checks = len(relevant_history)
        uptime_percentage = (online_checks / total_checks) * 100 if total_checks > 0 else 0
        
        # Calcular tempo médio de resposta
        response_times = [r.response_time_ms for r in relevant_history if r.response_time_ms is not None]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Status atual
        current_status = "unknown"
        if url in self._last_check_cache:
            current_status = self._last_check_cache[url].status.value
        
        return {
            "url": url,
            "period_hours": hours,
            "total_checks": total_checks,
            "online_checks": online_checks,
            "uptime_percentage": round(uptime_percentage, 2),
            "avg_response_time_ms": round(avg_response_time, 2),
            "current_status": current_status,
            "last_check": relevant_history[-1].timestamp if relevant_history else None
        }