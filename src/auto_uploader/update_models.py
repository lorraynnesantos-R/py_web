"""
Modelos de dados para o sistema de verificação de updates

Este módulo contém as classes de dados utilizadas pelo sistema de
verificação otimizada de updates por provider.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timezone
from enum import Enum


class UpdateMethod(Enum):
    """Método utilizado para verificação de updates"""
    OPTIMIZED = "optimized"  # Usando get_update() do provider
    FALLBACK = "fallback"    # Verificação individual com getChapters()
    MIXED = "mixed"          # Combinação de ambos os métodos


@dataclass
class UpdateInfo:
    """Informação de uma obra com novos capítulos detectados"""
    obra_id: int
    titulo: str
    url_relativa: str
    novos_capitulos: List[Dict[str, Any]]
    ultimo_capitulo_local: Optional[Dict[str, Any]] = None
    timestamp_deteccao: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def __post_init__(self):
        """Validação pós-inicialização"""
        if not self.novos_capitulos:
            raise ValueError("Lista de novos capítulos não pode estar vazia")
        if self.obra_id <= 0:
            raise ValueError("ID da obra deve ser positivo")


@dataclass
class ScanUpdateResult:
    """Resultado da verificação de updates de um scan"""
    scan_name: str
    method_used: UpdateMethod
    obras_com_updates: List[UpdateInfo]
    total_obras_verificadas: int
    tempo_execucao_segundos: float
    success: bool = True
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Métricas de performance
    metricas: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Inicialização de métricas padrão"""
        if not self.metricas:
            self.metricas = {
                "requests_realizados": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "errors_encontrados": 0,
                "obras_puladas": 0,
                "provider_supports_get_update": False
            }
    
    @property
    def total_novos_capitulos(self) -> int:
        """Retorna o total de novos capítulos encontrados"""
        return sum(len(obra.novos_capitulos) for obra in self.obras_com_updates)
    
    @property
    def taxa_sucesso(self) -> float:
        """Calcula taxa de sucesso da verificação"""
        if self.total_obras_verificadas == 0:
            return 0.0
        
        obras_com_erro = self.metricas.get("errors_encontrados", 0)
        obras_verificadas_com_sucesso = self.total_obras_verificadas - obras_com_erro
        
        return (obras_verificadas_com_sucesso / self.total_obras_verificadas) * 100
    
    def add_metrica(self, chave: str, valor: Any) -> None:
        """Adiciona ou atualiza uma métrica"""
        self.metricas[chave] = valor
    
    def increment_metrica(self, chave: str, incremento: int = 1) -> None:
        """Incrementa uma métrica numérica"""
        if chave not in self.metricas:
            self.metricas[chave] = 0
        self.metricas[chave] += incremento


@dataclass
class BatchUpdateResult:
    """Resultado de uma verificação em lote de múltiplos scans"""
    scan_results: List[ScanUpdateResult]
    timestamp_inicio: str
    timestamp_fim: str
    tempo_total_segundos: float
    
    @property
    def total_obras_com_updates(self) -> int:
        """Total de obras com updates em todos os scans"""
        return sum(len(result.obras_com_updates) for result in self.scan_results)
    
    @property
    def total_novos_capitulos(self) -> int:
        """Total de novos capítulos em todos os scans"""
        return sum(result.total_novos_capitulos for result in self.scan_results)
    
    @property
    def scans_com_sucesso(self) -> int:
        """Número de scans verificados com sucesso"""
        return sum(1 for result in self.scan_results if result.success)
    
    @property
    def taxa_sucesso_geral(self) -> float:
        """Taxa de sucesso geral da verificação"""
        if not self.scan_results:
            return 0.0
        return (self.scans_com_sucesso / len(self.scan_results)) * 100
    
    def get_scans_por_metodo(self) -> Dict[UpdateMethod, int]:
        """Retorna distribuição de scans por método usado"""
        distribuicao = {method: 0 for method in UpdateMethod}
        
        for result in self.scan_results:
            distribuicao[result.method_used] += 1
            
        return distribuicao
    
    def get_scan_result(self, scan_name: str) -> Optional[ScanUpdateResult]:
        """Busca resultado de um scan específico"""
        for result in self.scan_results:
            if result.scan_name == scan_name:
                return result
        return None


@dataclass 
class UpdateCacheEntry:
    """Entrada de cache para verificação de updates"""
    scan_name: str
    obra_id: int
    ultimo_capitulo_verificado: Dict[str, Any]
    timestamp_verificacao: str
    hash_conteudo: str  # Hash do conteúdo para detectar mudanças
    
    def is_expired(self, cache_duration_minutes: int = 30) -> bool:
        """Verifica se a entrada do cache expirou"""
        try:
            timestamp = datetime.fromisoformat(self.timestamp_verificacao.replace('Z', '+00:00'))
            agora = datetime.now(timezone.utc)
            duracao = (agora - timestamp).total_seconds() / 60
            
            return duracao > cache_duration_minutes
        except (ValueError, AttributeError):
            return True  # Se não conseguir parsear, considerar expirado


@dataclass
class ProviderCapabilities:
    """Capacidades de um provider específico"""
    provider_name: str
    supports_get_update: bool
    supports_batch_check: bool = False
    max_concurrent_requests: int = 5
    rate_limit_delay: float = 1.0  # segundos entre requisições
    
    # Configurações específicas do provider
    update_page_url: Optional[str] = None
    update_page_selector: Optional[str] = None
    
    def __post_init__(self):
        """Validação de configurações"""
        if self.max_concurrent_requests <= 0:
            self.max_concurrent_requests = 1
        if self.rate_limit_delay < 0:
            self.rate_limit_delay = 0.0