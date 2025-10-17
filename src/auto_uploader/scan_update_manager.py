"""
Gerenciador de Verificação de Updates por Provider

Este módulo implementa o sistema otimizado de verificação de updates
que utiliza método get_update() nos providers quando disponível, com
fallback para verificação individual.
"""

import sys
import asyncio
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import time

# Adiciona o diretório src ao sys.path para imports
sys.path.append(str(Path(__file__).parent.parent))

from .update_models import (
    UpdateInfo, ScanUpdateResult, BatchUpdateResult, 
    UpdateMethod, UpdateCacheEntry, ProviderCapabilities
)
from mapping.mapping_manager import MappingManager


class ScanUpdateManager:
    """
    Gerenciador otimizado de verificação de updates por provider
    
    Utiliza método get_update() quando disponível no provider,
    com fallback para verificação individual.
    """
    
    def __init__(self, mapping_manager: MappingManager, data_dir: Path = None):
        """
        Inicializa o gerenciador de updates
        
        Args:
            mapping_manager: Instância do MappingManager
            data_dir: Diretório de dados (opcional)
        """
        self.mapping_manager = mapping_manager
        self.data_dir = data_dir or Path("data")
        
        # Diretórios de cache e logs
        self.cache_dir = self.data_dir / "cache" / "updates"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Arquivos de controle
        self.cache_file = self.cache_dir / "update_cache.json"
        self.capabilities_file = self.cache_dir / "provider_capabilities.json"
        self.metrics_file = self.cache_dir / "update_metrics.json"
        
        # Configurações
        self.cache_duration_minutes = 30
        self.max_concurrent_checks = 5
        self.request_delay = 1.0  # segundos entre requisições
        
        # Logger
        self.logger = logging.getLogger("scan_update_manager")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Cache em memória
        self._cache: Dict[str, UpdateCacheEntry] = {}
        self._provider_capabilities: Dict[str, ProviderCapabilities] = {}
        
        self._load_cache()
        self._load_provider_capabilities()
    
    def _load_cache(self) -> None:
        """Carrega cache de verificações anteriores"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                for key, data in cache_data.items():
                    try:
                        self._cache[key] = UpdateCacheEntry(**data)
                    except Exception as e:
                        self.logger.warning(f"Erro ao carregar entrada de cache {key}: {e}")
                        
                self.logger.info(f"Cache carregado: {len(self._cache)} entradas")
        except Exception as e:
            self.logger.error(f"Erro ao carregar cache: {e}")
            self._cache = {}
    
    def _save_cache(self) -> None:
        """Salva cache para disco"""
        try:
            # Remove entradas expiradas antes de salvar
            self._clean_expired_cache()
            
            cache_data = {}
            for key, entry in self._cache.items():
                cache_data[key] = {
                    'scan_name': entry.scan_name,
                    'obra_id': entry.obra_id,
                    'ultimo_capitulo_verificado': entry.ultimo_capitulo_verificado,
                    'timestamp_verificacao': entry.timestamp_verificacao,
                    'hash_conteudo': entry.hash_conteudo
                }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Erro ao salvar cache: {e}")
    
    def _clean_expired_cache(self) -> None:
        """Remove entradas expiradas do cache"""
        keys_to_remove = []
        for key, entry in self._cache.items():
            if entry.is_expired(self.cache_duration_minutes):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._cache[key]
        
        if keys_to_remove:
            self.logger.info(f"Removidas {len(keys_to_remove)} entradas expiradas do cache")
    
    def _load_provider_capabilities(self) -> None:
        """Carrega capacidades dos providers"""
        try:
            if self.capabilities_file.exists():
                with open(self.capabilities_file, 'r', encoding='utf-8') as f:
                    capabilities_data = json.load(f)
                
                for provider_name, data in capabilities_data.items():
                    try:
                        self._provider_capabilities[provider_name] = ProviderCapabilities(**data)
                    except Exception as e:
                        self.logger.warning(f"Erro ao carregar capacidades do provider {provider_name}: {e}")
                        
                self.logger.info(f"Capacidades carregadas para {len(self._provider_capabilities)} providers")
        except Exception as e:
            self.logger.error(f"Erro ao carregar capacidades dos providers: {e}")
            self._provider_capabilities = {}
    
    def _save_provider_capabilities(self) -> None:
        """Salva capacidades dos providers"""
        try:
            capabilities_data = {}
            for provider_name, caps in self._provider_capabilities.items():
                capabilities_data[provider_name] = {
                    'provider_name': caps.provider_name,
                    'supports_get_update': caps.supports_get_update,
                    'supports_batch_check': caps.supports_batch_check,
                    'max_concurrent_requests': caps.max_concurrent_requests,
                    'rate_limit_delay': caps.rate_limit_delay,
                    'update_page_url': caps.update_page_url,
                    'update_page_selector': caps.update_page_selector
                }
            
            with open(self.capabilities_file, 'w', encoding='utf-8') as f:
                json.dump(capabilities_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Erro ao salvar capacidades dos providers: {e}")
    
    def _get_cache_key(self, scan_name: str, obra_id: int) -> str:
        """Gera chave única para cache"""
        return f"{scan_name}:{obra_id}"
    
    def _get_content_hash(self, content: Any) -> str:
        """Gera hash do conteúdo para detectar mudanças"""
        content_str = json.dumps(content, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(content_str.encode()).hexdigest()
    
    def _detect_provider_capabilities(self, scan_name: str, provider_instance=None) -> ProviderCapabilities:
        """
        Detecta automaticamente as capacidades de um provider
        
        Args:
            scan_name: Nome do scan
            provider_instance: Instância do provider (opcional)
            
        Returns:
            Capacidades detectadas do provider
        """
        # Se já temos as capacidades em cache, retornar
        if scan_name in self._provider_capabilities:
            return self._provider_capabilities[scan_name]
        
        # Detectar capacidades do provider
        supports_get_update = False
        
        try:
            # Aqui seria feita a detecção real do provider
            # Por enquanto, assumimos que não suporta get_update()
            # Em uma implementação real, verificaríamos se o método existe
            # no provider específico do scan
            
            if provider_instance:
                supports_get_update = hasattr(provider_instance, 'get_update') and callable(getattr(provider_instance, 'get_update'))
            
        except Exception as e:
            self.logger.warning(f"Erro ao detectar capacidades do provider {scan_name}: {e}")
        
        # Criar entrada de capacidades
        capabilities = ProviderCapabilities(
            provider_name=scan_name,
            supports_get_update=supports_get_update,
            supports_batch_check=False,  # Por padrão, não suporta
            max_concurrent_requests=3,   # Valor conservador
            rate_limit_delay=1.5        # Delay conservador
        )
        
        # Cache das capacidades
        self._provider_capabilities[scan_name] = capabilities
        self._save_provider_capabilities()
        
        return capabilities
    
    def check_scan_updates_optimized(self, scan_name: str, provider_instance=None) -> ScanUpdateResult:
        """
        Verifica updates de um scan usando método otimizado quando disponível
        
        Args:
            scan_name: Nome do scan
            provider_instance: Instância do provider (opcional)
            
        Returns:
            Resultado da verificação de updates
        """
        inicio = time.time()
        
        try:
            # Carregar dados do scan
            mapping_data = self.mapping_manager.load_mapping(scan_name)
            if not mapping_data or not mapping_data.obras:
                return ScanUpdateResult(
                    scan_name=scan_name,
                    method_used=UpdateMethod.FALLBACK,
                    obras_com_updates=[],
                    total_obras_verificadas=0,
                    tempo_execucao_segundos=time.time() - inicio,
                    success=False,
                    error_message="Nenhuma obra encontrada para o scan"
                )
            
            # Detectar capacidades do provider
            capabilities = self._detect_provider_capabilities(scan_name, provider_instance)
            
            # Escolher método de verificação
            if capabilities.supports_get_update and provider_instance:
                return self._check_updates_optimized_method(scan_name, mapping_data, provider_instance, capabilities, inicio)
            else:
                return self._check_updates_fallback_method(scan_name, mapping_data, capabilities, inicio)
                
        except Exception as e:
            self.logger.error(f"Erro ao verificar updates do scan {scan_name}: {e}")
            return ScanUpdateResult(
                scan_name=scan_name,
                method_used=UpdateMethod.FALLBACK,
                obras_com_updates=[],
                total_obras_verificadas=0,
                tempo_execucao_segundos=time.time() - inicio,
                success=False,
                error_message=str(e)
            )
    
    def _check_updates_optimized_method(self, scan_name: str, mapping_data, provider_instance, capabilities: ProviderCapabilities, inicio: float) -> ScanUpdateResult:
        """
        Verifica updates usando método otimizado get_update()
        
        Args:
            scan_name: Nome do scan
            mapping_data: Dados do mapeamento
            provider_instance: Instância do provider
            capabilities: Capacidades do provider
            inicio: Timestamp de início
            
        Returns:
            Resultado da verificação otimizada
        """
        self.logger.info(f"🚀 Verificando updates do scan '{scan_name}' usando método OTIMIZADO")
        
        result = ScanUpdateResult(
            scan_name=scan_name,
            method_used=UpdateMethod.OPTIMIZED,
            obras_com_updates=[],
            total_obras_verificadas=len(mapping_data.obras),
            tempo_execucao_segundos=0
        )
        
        result.add_metrica("provider_supports_get_update", True)
        
        try:
            # Chamar método get_update() do provider
            updates_from_provider = provider_instance.get_update()
            result.increment_metrica("requests_realizados")
            
            if not updates_from_provider:
                result.success = True
                result.tempo_execucao_segundos = time.time() - inicio
                self.logger.info(f"✅ Scan '{scan_name}': Nenhum update encontrado (método otimizado)")
                return result
            
            # Mapear obras locais por URL ou título para comparação
            obras_locais = {obra.url_relativa: obra for obra in mapping_data.obras}
            
            # Processar updates encontrados
            for update_item in updates_from_provider:
                try:
                    obra_url = update_item.get('url_relativa', '')
                    obra_titulo = update_item.get('titulo', '')
                    novos_caps = update_item.get('capitulos', [])
                    
                    # Encontrar obra local correspondente
                    obra_local = obras_locais.get(obra_url)
                    if not obra_local:
                        # Tentar encontrar por título se URL não bater
                        for obra in mapping_data.obras:
                            if obra.titulo and obra.titulo.lower() == obra_titulo.lower():
                                obra_local = obra
                                break
                    
                    if obra_local and novos_caps:
                        # Verificar se realmente há novos capítulos
                        capitulos_locais = {float(cap.numero): cap for cap in obra_local.capitulos}
                        novos_capitulos_reais = []
                        
                        for cap in novos_caps:
                            cap_numero = float(cap.get('numero', 0))
                            if cap_numero not in capitulos_locais:
                                novos_capitulos_reais.append(cap)
                        
                        if novos_capitulos_reais:
                            update_info = UpdateInfo(
                                obra_id=obra_local.id,
                                titulo=obra_local.titulo or obra_titulo,
                                url_relativa=obra_local.url_relativa,
                                novos_capitulos=novos_capitulos_reais,
                                ultimo_capitulo_local=capitulos_locais.get(max(capitulos_locais.keys())) if capitulos_locais else None
                            )
                            result.obras_com_updates.append(update_info)
                            
                except Exception as e:
                    self.logger.warning(f"Erro ao processar update de obra: {e}")
                    result.increment_metrica("errors_encontrados")
            
            result.success = True
            result.tempo_execucao_segundos = time.time() - inicio
            
            self.logger.info(
                f"✅ Scan '{scan_name}' (OTIMIZADO): {len(result.obras_com_updates)} obras com updates, "
                f"{result.total_novos_capitulos} novos capítulos em {result.tempo_execucao_segundos:.1f}s"
            )
            
        except Exception as e:
            self.logger.error(f"Erro no método otimizado para scan {scan_name}: {e}")
            result.success = False
            result.error_message = str(e)
            result.tempo_execucao_segundos = time.time() - inicio
        
        return result
    
    def _check_updates_fallback_method(self, scan_name: str, mapping_data, capabilities: ProviderCapabilities, inicio: float) -> ScanUpdateResult:
        """
        Verifica updates usando método fallback (verificação individual)
        
        Args:
            scan_name: Nome do scan
            mapping_data: Dados do mapeamento
            capabilities: Capacidades do provider
            inicio: Timestamp de início
            
        Returns:
            Resultado da verificação fallback
        """
        self.logger.info(f"🔄 Verificando updates do scan '{scan_name}' usando método FALLBACK")
        
        result = ScanUpdateResult(
            scan_name=scan_name,
            method_used=UpdateMethod.FALLBACK,
            obras_com_updates=[],
            total_obras_verificadas=len(mapping_data.obras),
            tempo_execucao_segundos=0
        )
        
        result.add_metrica("provider_supports_get_update", False)
        
        try:
            # Verificar cada obra individualmente
            for obra in mapping_data.obras:
                try:
                    # Verificar cache primeiro
                    cache_key = self._get_cache_key(scan_name, obra.id)
                    cached_entry = self._cache.get(cache_key)
                    
                    if cached_entry and not cached_entry.is_expired(self.cache_duration_minutes):
                        result.increment_metrica("cache_hits")
                        continue
                    
                    result.increment_metrica("cache_misses")
                    
                    # Aqui seria feita a verificação real usando getChapters() do provider
                    # Por enquanto, simulamos que não há updates
                    # Em implementação real:
                    # novos_caps = provider_instance.getChapters(obra.url_relativa)
                    
                    result.increment_metrica("requests_realizados")
                    
                    # Delay entre requisições para respeitar rate limit
                    if capabilities.rate_limit_delay > 0:
                        time.sleep(capabilities.rate_limit_delay)
                    
                    # Simular atualização do cache
                    ultimo_cap = obra.capitulos[-1] if obra.capitulos else None
                    if ultimo_cap:
                        cache_entry = UpdateCacheEntry(
                            scan_name=scan_name,
                            obra_id=obra.id,
                            ultimo_capitulo_verificado={'numero': ultimo_cap.numero, 'status': ultimo_cap.status},
                            timestamp_verificacao=datetime.now(timezone.utc).isoformat(),
                            hash_conteudo=self._get_content_hash({'numero': ultimo_cap.numero})
                        )
                        self._cache[cache_key] = cache_entry
                    
                except Exception as e:
                    self.logger.warning(f"Erro ao verificar obra {obra.id} do scan {scan_name}: {e}")
                    result.increment_metrica("errors_encontrados")
            
            result.success = True
            result.tempo_execucao_segundos = time.time() - inicio
            
            self.logger.info(
                f"✅ Scan '{scan_name}' (FALLBACK): {len(result.obras_com_updates)} obras com updates "
                f"em {result.tempo_execucao_segundos:.1f}s"
            )
            
            # Salvar cache atualizado
            self._save_cache()
            
        except Exception as e:
            self.logger.error(f"Erro no método fallback para scan {scan_name}: {e}")
            result.success = False
            result.error_message = str(e)
            result.tempo_execucao_segundos = time.time() - inicio
        
        return result
    
    def check_multiple_scans_updates(self, scan_names: List[str], max_concurrent: int = None) -> BatchUpdateResult:
        """
        Verifica updates de múltiplos scans em paralelo
        
        Args:
            scan_names: Lista de nomes dos scans
            max_concurrent: Máximo de verificações simultâneas
            
        Returns:
            Resultado da verificação em lote
        """
        inicio = datetime.now(timezone.utc)
        max_concurrent = max_concurrent or self.max_concurrent_checks
        
        self.logger.info(f"🚀 Iniciando verificação de updates para {len(scan_names)} scans")
        
        scan_results = []
        
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            # Submeter tarefas
            future_to_scan = {
                executor.submit(self.check_scan_updates_optimized, scan_name): scan_name 
                for scan_name in scan_names
            }
            
            # Coletar resultados
            for future in as_completed(future_to_scan):
                scan_name = future_to_scan[future]
                try:
                    result = future.result()
                    scan_results.append(result)
                except Exception as e:
                    self.logger.error(f"Erro ao verificar scan {scan_name}: {e}")
                    # Criar resultado de erro
                    error_result = ScanUpdateResult(
                        scan_name=scan_name,
                        method_used=UpdateMethod.FALLBACK,
                        obras_com_updates=[],
                        total_obras_verificadas=0,
                        tempo_execucao_segundos=0,
                        success=False,
                        error_message=str(e)
                    )
                    scan_results.append(error_result)
        
        fim = datetime.now(timezone.utc)
        tempo_total = (fim - inicio).total_seconds()
        
        batch_result = BatchUpdateResult(
            scan_results=scan_results,
            timestamp_inicio=inicio.isoformat(),
            timestamp_fim=fim.isoformat(),
            tempo_total_segundos=tempo_total
        )
        
        self.logger.info(
            f"✅ Verificação em lote concluída: {batch_result.total_obras_com_updates} obras com updates, "
            f"{batch_result.total_novos_capitulos} novos capítulos em {tempo_total:.1f}s"
        )
        
        return batch_result
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache"""
        total_entries = len(self._cache)
        expired_entries = sum(1 for entry in self._cache.values() if entry.is_expired(self.cache_duration_minutes))
        
        return {
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "valid_entries": total_entries - expired_entries,
            "cache_hit_rate": "N/A",  # Seria calculado com métricas históricas
            "cache_file_size": self.cache_file.stat().st_size if self.cache_file.exists() else 0
        }
    
    def clear_cache(self) -> None:
        """Limpa todo o cache"""
        self._cache.clear()
        if self.cache_file.exists():
            self.cache_file.unlink()
        self.logger.info("Cache limpo com sucesso")