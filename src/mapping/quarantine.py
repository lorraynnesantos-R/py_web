"""
Sistema de Quarentena para Obras Problemáticas

Este módulo implementa o sistema automatizado de quarentena para obras
que apresentam 10 ou mais erros consecutivos, removendo-as temporariamente
da fila de auto-update até intervenção manual.

Classes:
    QuarantineManager: Gerenciador principal do sistema de quarentena
    QuarantineStats: Estatísticas de quarentena
    QuarantineEvent: Evento de mudança de status
"""

from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json
import logging


@dataclass
class QuarantineEvent:
    """Evento de mudança de status de quarentena"""
    obra_id: int
    scan_name: str
    action: str  # 'quarantined', 'restored', 'manual_restore'
    error_count: int
    timestamp: str
    reason: Optional[str] = None
    user: Optional[str] = None


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


class QuarantineManager:
    """
    Gerenciador do Sistema de Quarentena
    
    Responsável por:
    - Detectar obras com 10+ erros consecutivos
    - Colocar obras em quarentena automaticamente
    - Gerenciar status de quarentena
    - Fornecer interface para reativação manual
    - Manter histórico e métricas
    """
    
    QUARANTINE_THRESHOLD = 10  # Limite de erros para quarentena
    
    def __init__(self, mapping_manager, data_dir: Path = None):
        """
        Inicializa o gerenciador de quarentena
        
        Args:
            mapping_manager: Instância do MappingManager
            data_dir: Diretório de dados (padrão: data/)
        """
        self.mapping_manager = mapping_manager
        self.data_dir = data_dir or Path("data")
        self.quarantine_dir = self.data_dir / "quarantine"
        self.quarantine_dir.mkdir(exist_ok=True)
        
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
    
    def _mapping_data_to_dict(self, mapping_data) -> Dict:
        """Converte MappingData para dicionário compatível com o sistema de quarentena"""
        obras_dict = []
        for obra in mapping_data.obras:
            obra_dict = {
                'id': obra.id,
                'titulo': obra.titulo,
                'url_relativa': obra.url_relativa,
                'status': obra.status,
                'ultimo_upload': obra.ultimo_upload,
                'erros_consecutivos': obra.erros_consecutivos,
                'capitulos': [
                    {
                        'numero': cap.numero,
                        'data_upload': cap.data_upload,
                        'status': cap.status
                    } for cap in obra.capitulos
                ],
                'tags': obra.tags or [],
                'autor': obra.autor,
                'descricao': obra.descricao,
                'created_at': obra.created_at,
                'updated_at': obra.updated_at,
                'id_obra_original': obra.id_obra_original,
                'numero_pulos_config': obra.numero_pulos_config
            }
            obras_dict.append(obra_dict)
        
        return {
            'scan_info': {
                'name': mapping_data.scan_info.name,
                'base_url': mapping_data.scan_info.base_url,
                'last_check': mapping_data.scan_info.last_check,
                'active': mapping_data.scan_info.active,
                'scape_time': mapping_data.scan_info.scape_time,
                'description': mapping_data.scan_info.description
            },
            'obras': obras_dict,
            'metadata': mapping_data.metadata or {}
        }

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
            self.logger.error(f"Erro ao salvar stats de quarentena: {e}")
    
    def _log_event(self, event: QuarantineEvent) -> None:
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
        now = datetime.now(timezone.utc).isoformat()
        
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
                    scan_data = self._mapping_data_to_dict(mapping_data)
                    
                    obras_to_quarantine = []
                    
                    # Verificar cada obra
                    for obra in scan_data.get("obras", []):
                        obra_id = obra.get("id")
                        erros_consecutivos = obra.get("erros_consecutivos", 0)
                        status_atual = obra.get("status", "ativo")
                        
                        # Verificar se deve ser colocada em quarentena
                        if (erros_consecutivos >= self.QUARANTINE_THRESHOLD and 
                            status_atual != "quarentena"):
                            
                            obras_to_quarantine.append((obra_id, erros_consecutivos))
                            quarantined_obras.append((scan_name, obra_id))
                    
                    # Aplicar quarentena às obras identificadas
                    for obra_id, error_count in obras_to_quarantine:
                        self._set_obra_quarantine_status(scan_name, obra_id, True, error_count)
                        
                        # Log do evento
                        event = QuarantineEvent(
                            obra_id=obra_id,
                            scan_name=scan_name,
                            action="quarantined",
                            error_count=error_count,
                            timestamp=now,
                            reason=f"Quarentena automática: {error_count} erros consecutivos"
                        )
                        self._log_event(event)
                        
                        self.logger.warning(
                            f"🚫 Obra {obra_id} do scan {scan_name} colocada em quarentena "
                            f"({error_count} erros consecutivos)"
                        )
                
                except Exception as e:
                    self.logger.error(f"Erro ao verificar scan {scan_name}: {e}")
                    continue
            
            # Atualizar estatísticas
            self.stats.last_quarantine_check = now
            self.stats.auto_quarantines_today += len(quarantined_obras)
            self._update_stats()
            
            if quarantined_obras:
                self.logger.warning(
                    f"⚠️ {len(quarantined_obras)} obras colocadas em quarentena automática"
                )
            else:
                self.logger.info("✅ Nenhuma obra nova colocada em quarentena")
            
            return quarantined_obras
            
        except Exception as e:
            self.logger.error(f"Erro na verificação de quarentena: {e}")
            return []
    
    def _set_obra_quarantine_status(self, scan_name: str, obra_id: int, 
                                   quarantined: bool, error_count: int = 0) -> bool:
        """
        Define o status de quarentena de uma obra
        
        Args:
            scan_name: Nome do scan
            obra_id: ID da obra
            quarantined: True para quarentena, False para reativar
            error_count: Número de erros (para logging)
            
        Returns:
            True se alteração foi bem-sucedida
        """
        try:
            # Carregar dados do scan
            mapping_data = self.mapping_manager.load_mapping(scan_name)
            if not mapping_data:
                return False
            scan_data = self._mapping_data_to_dict(mapping_data)
            
            # Encontrar a obra
            obra_encontrada = False
            for obra in scan_data.get("obras", []):
                if obra.get("id") == obra_id:
                    old_status = obra.get("status", "ativo")
                    new_status = "quarentena" if quarantined else "ativo"
                    
                    obra["status"] = new_status
                    obra_encontrada = True
                    
                    self.logger.info(
                        f"Status da obra {obra_id} ({scan_name}): {old_status} → {new_status}"
                    )
                    break
            
            if not obra_encontrada:
                self.logger.warning(f"Obra {obra_id} não encontrada em {scan_name}")
                return False
            
            # Salvar alterações
            success = self.mapping_manager.save_scan_data(scan_name, scan_data)
            if success:
                self.logger.info(f"✅ Status de quarentena atualizado: {scan_name}/{obra_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Erro ao alterar status de quarentena: {e}")
            return False
    
    def restore_obra_from_quarantine(self, scan_name: str, obra_id: int, 
                                   user: str = "sistema") -> bool:
        """
        Remove uma obra da quarentena (reativação manual)
        
        Args:
            scan_name: Nome do scan
            obra_id: ID da obra
            user: Usuário que fez a reativação
            
        Returns:
            True se reativação foi bem-sucedida
        """
        try:
            # Verificar se obra está em quarentena
            if not self.is_obra_quarantined(scan_name, obra_id):
                self.logger.warning(f"Obra {obra_id} ({scan_name}) não está em quarentena")
                return False
            
            # Resetar contador de erros
            scan_data = self.mapping_manager.load_scan_data(scan_name)
            if scan_data:
                for obra in scan_data.get("obras", []):
                    if obra.get("id") == obra_id:
                        obra["erros_consecutivos"] = 0
                        break
                
                self.mapping_manager.save_scan_data(scan_name, scan_data)
            
            # Remover da quarentena
            success = self._set_obra_quarantine_status(scan_name, obra_id, False)
            
            if success:
                # Registrar evento
                event = QuarantineEvent(
                    obra_id=obra_id,
                    scan_name=scan_name,
                    action="manual_restore",
                    error_count=0,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    reason="Reativação manual",
                    user=user
                )
                self._log_event(event)
                
                # Atualizar estatísticas
                self.stats.manual_restores_today += 1
                self._update_stats()
                
                self.logger.info(f"✅ Obra {obra_id} ({scan_name}) removida da quarentena por {user}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Erro ao remover obra da quarentena: {e}")
            return False
    
    def is_obra_quarantined(self, scan_name: str, obra_id: int) -> bool:
        """
        Verifica se uma obra está em quarentena
        
        Args:
            scan_name: Nome do scan
            obra_id: ID da obra
            
        Returns:
            True se obra está em quarentena
        """
        try:
            scan_data = self.mapping_manager.load_scan_data(scan_name)
            if not scan_data:
                return False
            
            for obra in scan_data.get("obras", []):
                if obra.get("id") == obra_id:
                    return obra.get("status") == "quarentena"
            
            return False
            
        except Exception as e:
            self.logger.error(f"Erro ao verificar status de quarentena: {e}")
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
                    scan_data = self.mapping_manager.load_scan_data(scan_name)
                    if not scan_data:
                        continue
                    
                    for obra in scan_data.get("obras", []):
                        if obra.get("status") == "quarentena":
                            quarantined_obras.append({
                                "scan_name": scan_name,
                                "obra_id": obra.get("id"),
                                "titulo": obra.get("titulo"),
                                "erros_consecutivos": obra.get("erros_consecutivos", 0),
                                "ultimo_upload": obra.get("ultimo_upload"),
                                "url_relativa": obra.get("url_relativa"),
                                "updated_at": obra.get("updated_at")
                            })
                
                except Exception as e:
                    self.logger.error(f"Erro ao obter obras em quarentena do scan {scan_name}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Erro ao obter obras em quarentena: {e}")
        
        return quarantined_obras
    
    def get_quarantine_history(self, limit: int = 100) -> List[Dict]:
        """
        Obtém histórico de eventos de quarentena
        
        Args:
            limit: Número máximo de eventos a retornar
            
        Returns:
            Lista de eventos ordenados por data (mais recente primeiro)
        """
        try:
            if not self.events_file.exists():
                return []
            
            with open(self.events_file, 'r', encoding='utf-8') as f:
                events = json.load(f)
            
            # Ordenar por timestamp (mais recente primeiro) e limitar
            events = sorted(events, key=lambda x: x['timestamp'], reverse=True)
            return events[:limit]
            
        except Exception as e:
            self.logger.error(f"Erro ao obter histórico de quarentena: {e}")
            return []
    
    def _update_stats(self) -> None:
        """Atualiza estatísticas de quarentena"""
        try:
            # Contar obras em quarentena por scan
            quarantined_obras = self.get_quarantined_obras()
            
            self.stats.total_quarantined = len(quarantined_obras)
            self.stats.quarantined_by_scan = {}
            
            for obra in quarantined_obras:
                scan_name = obra["scan_name"]
                self.stats.quarantined_by_scan[scan_name] = (
                    self.stats.quarantined_by_scan.get(scan_name, 0) + 1
                )
            
            self._save_stats()
            
        except Exception as e:
            self.logger.error(f"Erro ao atualizar estatísticas: {e}")
    
    def get_stats(self) -> QuarantineStats:
        """
        Obtém estatísticas atualizadas de quarentena
        
        Returns:
            Objeto QuarantineStats com estatísticas atuais
        """
        self._update_stats()
        return self.stats
    
    def reset_daily_counters(self) -> None:
        """Reseta contadores diários (deve ser chamado a cada meia-noite)"""
        self.stats.auto_quarantines_today = 0
        self.stats.manual_restores_today = 0
        self._save_stats()
        self.logger.info("🔄 Contadores diários de quarentena resetados")