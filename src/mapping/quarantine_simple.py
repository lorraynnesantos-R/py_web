"""
Sistema de Quarentena Simplificado para Obras Problemáticas

Este módulo implementa o sistema automatizado de quarentena para obras
que apresentam 10 ou mais erros consecutivos, removendo-as temporariamente
da fila de auto-update até intervenção manual.
"""

from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json
import logging


@dataclass
class QuarantineEvent:
    """Evento de quarentena"""
    scan_name: str
    obra_id: int
    obra_titulo: str
    action: str  # "quarantine", "restore", "manual_restore"
    reason: str
    timestamp: str
    error_count: int = 0


@dataclass
class QuarantineStats:
    """Estatísticas do sistema de quarentena"""
    total_quarantined: int = 0
    quarantined_by_scan: Dict[str, int] = None
    last_quarantine_check: Optional[str] = None
    auto_quarantines_today: int = 0
    manual_restores_today: int = 0
    
    def __post_init__(self):
        if self.quarantined_by_scan is None:
            self.quarantined_by_scan = {}


class QuarantineManagerSimple:
    """Gerenciador simplificado do sistema de quarentena"""
    
    QUARANTINE_THRESHOLD = 10  # Erros consecutivos para quarentena automática
    
    def __init__(self, mapping_manager, data_dir: Path = None):
        """
        Inicializa o gerenciador de quarentena
        
        Args:
            mapping_manager: Instância do MappingManager
            data_dir: Diretório de dados (opcional)
        """
        self.mapping_manager = mapping_manager
        self.data_dir = data_dir or Path("data")
        self.quarantine_dir = self.data_dir / "quarantine"
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        
        # Arquivos de controle
        self.events_file = self.quarantine_dir / "events.json"
        self.stats_file = self.quarantine_dir / "stats.json"
        
        # Configura logger básico
        self.logger = logging.getLogger("quarantine")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

        self._load_stats()
    
    def _load_stats(self) -> None:
        """Carrega estatísticas de quarentena"""
        try:
            if self.stats_file.exists():
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.stats = QuarantineStats(**data)
            else:
                self.stats = QuarantineStats()
        except Exception as e:
            self.logger.error(f"Erro ao carregar estatísticas: {e}")
            self.stats = QuarantineStats()

    def _save_stats(self) -> None:
        """Salva estatísticas de quarentena"""
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(self.stats), f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Erro ao salvar estatísticas: {e}")

    def _register_event(self, event: QuarantineEvent) -> None:
        """Registra evento de quarentena"""
        try:
            events = []
            if self.events_file.exists():
                with open(self.events_file, 'r', encoding='utf-8') as f:
                    events = json.load(f)
            
            events.append(asdict(event))
            
            # Manter apenas os últimos 1000 eventos
            if len(events) > 1000:
                events = events[-1000:]
            
            with open(self.events_file, 'w', encoding='utf-8') as f:
                json.dump(events, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Erro ao registrar evento de quarentena: {e}")

    def check_and_quarantine_obras(self) -> List[Tuple[str, int]]:
        """
        Verifica todas as obras e coloca em quarentena as que atingiram o limite
        
        Returns:
            Lista de tuplas (scan_name, obra_id) das obras colocadas em quarentena
        """
        quarantined_obras = []
        now = datetime.now(timezone.utc)
        
        self.logger.info("🔍 Iniciando verificação automática de quarentena")
        
        try:
            # Obter todos os scans
            scan_names = self.mapping_manager.list_scans()
            
            for scan_name in scan_names:
                try:
                    # Carregar dados do scan
                    mapping_data = self.mapping_manager.load_mapping(scan_name)
                    if not mapping_data:
                        continue
                    
                    modified = False
                    
                    # Verificar cada obra
                    for obra in mapping_data.obras:
                        if (obra.erros_consecutivos >= self.QUARANTINE_THRESHOLD and 
                            obra.status != "quarentena"):
                            
                            # Colocar em quarentena
                            obra.status = "quarentena"
                            quarantined_obras.append((scan_name, obra.id))
                            modified = True
                            
                            # Registrar evento
                            event = QuarantineEvent(
                                scan_name=scan_name,
                                obra_id=obra.id,
                                obra_titulo=obra.titulo or "N/A",
                                action="quarantine",
                                reason=f"Quarentena automática: {obra.erros_consecutivos} erros consecutivos",
                                timestamp=now.isoformat(),
                                error_count=obra.erros_consecutivos
                            )
                            self._register_event(event)
                            
                            self.logger.warning(
                                f"🚨 Obra '{obra.titulo}' do scan '{scan_name}' "
                                f"colocada em quarentena ({obra.erros_consecutivos} erros)"
                            )
                    
                    # Salvar dados atualizados se houve mudanças
                    if modified:
                        self.mapping_manager.save_mapping(scan_name, mapping_data)
                        
                except Exception as e:
                    self.logger.error(f"Erro ao processar scan '{scan_name}': {e}")
                    continue
            
            # Atualizar estatísticas
            self.stats.last_quarantine_check = now.isoformat()
            self.stats.auto_quarantines_today += len(quarantined_obras)
            self._update_quarantine_counts()
            self._save_stats()
            
            if quarantined_obras:
                self.logger.warning(
                    f"🚨 Total de {len(quarantined_obras)} obras colocadas em quarentena"
                )
            else:
                self.logger.info("✅ Nenhuma obra precisou ser colocada em quarentena")
                
        except Exception as e:
            self.logger.error(f"Erro na verificação de quarentena: {e}")
        
        return quarantined_obras

    def restore_obra_from_quarantine(self, scan_name: str, obra_id: int, reason: str = "Restauração manual") -> bool:
        """
        Remove uma obra da quarentena
        
        Args:
            scan_name: Nome do scan
            obra_id: ID da obra
            reason: Motivo da restauração
            
        Returns:
            True se a obra foi restaurada com sucesso
        """
        try:
            # Carregar dados do scan
            mapping_data = self.mapping_manager.load_mapping(scan_name)
            if not mapping_data:
                return False
            
            # Encontrar e restaurar a obra
            obra_encontrada = False
            for obra in mapping_data.obras:
                if obra.id == obra_id and obra.status == "quarentena":
                    obra.status = "ativo"
                    obra.erros_consecutivos = 0  # Reset erros
                    obra_encontrada = True
                    
                    # Registrar evento
                    event = QuarantineEvent(
                        scan_name=scan_name,
                        obra_id=obra.id,
                        obra_titulo=obra.titulo or "N/A",
                        action="restore",
                        reason=reason,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        error_count=0
                    )
                    self._register_event(event)
                    
                    self.logger.info(f"✅ Obra '{obra.titulo}' restaurada da quarentena")
                    break
            
            if obra_encontrada:
                # Salvar dados atualizados
                self.mapping_manager.save_mapping(scan_name, mapping_data)
                
                # Atualizar estatísticas
                self.stats.manual_restores_today += 1
                self._update_quarantine_counts()
                self._save_stats()
                
                return True
            else:
                self.logger.warning(f"Obra {obra_id} não encontrada em quarentena no scan {scan_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro ao restaurar obra da quarentena: {e}")
            return False

    def get_quarantined_obras(self) -> List[Dict]:
        """
        Obtém lista de todas as obras em quarentena
        
        Returns:
            Lista de dicionários com informações das obras em quarentena
        """
        quarantined_obras = []
        
        try:
            scan_names = self.mapping_manager.list_scans()
            
            for scan_name in scan_names:
                try:
                    mapping_data = self.mapping_manager.load_mapping(scan_name)
                    if not mapping_data:
                        continue
                    
                    for obra in mapping_data.obras:
                        if obra.status == "quarentena":
                            quarantined_obras.append({
                                'scan_name': scan_name,
                                'obra_id': obra.id,
                                'titulo': obra.titulo,
                                'erros_consecutivos': obra.erros_consecutivos,
                                'ultimo_upload': obra.ultimo_upload,
                                'created_at': obra.created_at,
                                'updated_at': obra.updated_at
                            })
                            
                except Exception as e:
                    self.logger.error(f"Erro ao obter obras em quarentena do scan {scan_name}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Erro ao obter obras em quarentena: {e}")
        
        return quarantined_obras

    def _update_quarantine_counts(self) -> None:
        """Atualiza contadores de quarentena por scan"""
        try:
            quarantined_by_scan = {}
            
            scan_names = self.mapping_manager.list_scans()
            for scan_name in scan_names:
                try:
                    mapping_data = self.mapping_manager.load_mapping(scan_name)
                    if mapping_data:
                        count = sum(1 for obra in mapping_data.obras if obra.status == "quarentena")
                        if count > 0:
                            quarantined_by_scan[scan_name] = count
                except Exception as e:
                    self.logger.error(f"Erro ao contar quarentenas do scan {scan_name}: {e}")
            
            self.stats.quarantined_by_scan = quarantined_by_scan
            self.stats.total_quarantined = sum(quarantined_by_scan.values())
            
        except Exception as e:
            self.logger.error(f"Erro ao atualizar contadores de quarentena: {e}")

    def get_stats(self) -> QuarantineStats:
        """
        Obtém estatísticas atualizadas do sistema de quarentena
        
        Returns:
            Estatísticas de quarentena
        """
        self._update_quarantine_counts()
        self._save_stats()
        return self.stats

    def get_recent_events(self, limit: int = 50) -> List[QuarantineEvent]:
        """
        Obtém eventos recentes de quarentena
        
        Args:
            limit: Número máximo de eventos
            
        Returns:
            Lista de eventos recentes
        """
        try:
            if not self.events_file.exists():
                return []
            
            with open(self.events_file, 'r', encoding='utf-8') as f:
                events_data = json.load(f)
            
            # Pegar os eventos mais recentes
            recent_events = events_data[-limit:] if len(events_data) > limit else events_data
            
            # Converter de volta para objetos QuarantineEvent
            events = []
            for event_data in reversed(recent_events):  # Mais recentes primeiro
                events.append(QuarantineEvent(**event_data))
            
            return events
            
        except Exception as e:
            self.logger.error(f"Erro ao obter eventos recentes: {e}")
            return []


# Alias para compatibilidade
QuarantineManager = QuarantineManagerSimple