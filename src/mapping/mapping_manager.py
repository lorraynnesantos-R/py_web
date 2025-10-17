"""
Task 2.1: Sistema de Mapeamento Distribuído
Implementa MappingManager para gerenciar arquivos JSON separados por scan/domínio.
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import shutil
from dataclasses import dataclass, asdict
from enum import Enum


class ObraStatus(Enum):
    """Status possíveis para uma obra"""
    ATIVO = "ativo"
    QUARENTENA = "quarentena"
    PAUSADO = "pausado"
    FINALIZADO = "finalizado"


@dataclass
class ScanInfo:
    """Informações básicas de um scan/domínio"""
    name: str
    base_url: str
    last_check: Optional[str] = None
    active: bool = True
    scape_time: int = 30  # Tempo em minutos para esperar antes de postar capítulos
    description: Optional[str] = None


@dataclass
class Capitulo:
    """Informações de um capítulo"""
    numero: Union[str, float]
    data_upload: Optional[str] = None
    status: str = "pendente"  # pendente, baixado, processado, upload_feito


@dataclass
class Obra:
    """Estrutura de uma obra mapeada"""
    id: str
    titulo: str
    url_relativa: str
    status: ObraStatus = ObraStatus.ATIVO
    ultimo_upload: Optional[str] = None
    erros_consecutivos: int = 0
    capitulos: List[Capitulo] = None
    tags: List[str] = None
    autor: Optional[str] = None
    descricao: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def __post_init__(self):
        """Inicialização pós-criação"""
        if self.capitulos is None:
            self.capitulos = []
        if self.tags is None:
            self.tags = []
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = datetime.now(timezone.utc).isoformat()


@dataclass
class MappingData:
    """Estrutura completa de um arquivo de mapeamento"""
    scan_info: ScanInfo
    obras: List[Obra]
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Inicialização pós-criação"""
        if self.metadata is None:
            self.metadata = {
                "version": "2.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "total_obras": len(self.obras)
            }


class MappingError(Exception):
    """Exceção base para erros de mapeamento"""
    pass


class MappingValidationError(MappingError):
    """Erro de validação de schema"""
    pass


class MappingFileError(MappingError):
    """Erro de arquivo de mapeamento"""
    pass


class MappingManager:
    """
    Gerenciador de mapeamento distribuído para obras por scan/domínio.
    
    Funcionalidades:
    - Arquivos JSON separados por scan
    - Schema padronizado e validado
    - Sistema de backup automático
    - Migração de dados antigos
    - Cache inteligente para performance
    """
    
    def __init__(self, data_dir: Union[str, Path] = "data/mapping"):
        """
        Inicializa o MappingManager
        
        Args:
            data_dir: Diretório para arquivos de mapeamento
        """
        self.data_dir = Path(data_dir)
        self.backup_dir = self.data_dir / "backups"
        self._cache: Dict[str, MappingData] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self.cache_timeout = 300  # 5 minutos
        self.logger = logging.getLogger(__name__)
        
        # Cria diretórios se não existirem
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_mapping_file(self, scan_name: str) -> Path:
        """
        Obtém o caminho do arquivo de mapeamento para um scan
        
        Args:
            scan_name: Nome do scan
            
        Returns:
            Path para o arquivo de mapeamento
        """
        # Sanitiza o nome do arquivo
        safe_name = "".join(c for c in scan_name if c.isalnum() or c in "._-").lower()
        return self.data_dir / f"{safe_name}.json"
    
    def _validate_mapping_data(self, data: Dict[str, Any]) -> None:
        """
        Valida estrutura do arquivo de mapeamento
        
        Args:
            data: Dados para validar
            
        Raises:
            MappingValidationError: Se os dados são inválidos
        """
        required_fields = ["scan_info", "obras", "metadata"]
        
        for field in required_fields:
            if field not in data:
                raise MappingValidationError(f"Campo obrigatório '{field}' não encontrado")
        
        # Valida scan_info
        scan_info = data["scan_info"]
        if not isinstance(scan_info, dict):
            raise MappingValidationError("scan_info deve ser um objeto")
        
        if "name" not in scan_info or "base_url" not in scan_info:
            raise MappingValidationError("scan_info deve conter 'name' e 'base_url'")
        
        # Valida obras
        obras = data["obras"]
        if not isinstance(obras, list):
            raise MappingValidationError("obras deve ser uma lista")
        
        for i, obra in enumerate(obras):
            if not isinstance(obra, dict):
                raise MappingValidationError(f"Obra {i} deve ser um objeto")
            
            required_obra_fields = ["id", "titulo", "url_relativa"]
            for field in required_obra_fields:
                if field not in obra:
                    raise MappingValidationError(f"Obra {i} deve conter '{field}'")
    
    def _clean_obra_data(self, obra_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove campos incompatíveis dos dados de uma obra
        
        Args:
            obra_data: Dados da obra para limpar
            
        Returns:
            Dados limpos compatíveis com a classe Obra
        """
        # Campos válidos para a classe Obra
        valid_fields = {
            'id', 'titulo', 'url_relativa', 'status', 'ultimo_upload', 
            'erros_consecutivos', 'capitulos', 'tags', 'autor', 'descricao',
            'created_at', 'updated_at'
        }
        
        # Remove campos inválidos
        cleaned_data = {k: v for k, v in obra_data.items() if k in valid_fields}
        
        # Garantir valores padrão para campos obrigatórios
        if 'erros_consecutivos' not in cleaned_data:
            cleaned_data['erros_consecutivos'] = 0
        if 'tags' not in cleaned_data:
            cleaned_data['tags'] = []
        if 'capitulos' not in cleaned_data:
            cleaned_data['capitulos'] = []
            
        return cleaned_data
    
    def _clean_capitulo_data(self, cap_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove campos incompatíveis dos dados de um capítulo
        
        Args:
            cap_data: Dados do capítulo para limpar
            
        Returns:
            Dados limpos compatíveis com a classe Capitulo
        """
        # Campos válidos para a classe Capitulo
        valid_fields = {'numero', 'data_upload', 'status'}
        
        # Remove campos inválidos
        cleaned_data = {k: v for k, v in cap_data.items() if k in valid_fields}
        
        # Garantir valores padrão para campos obrigatórios
        if 'numero' not in cleaned_data:
            cleaned_data['numero'] = "0"
        if 'status' not in cleaned_data:
            cleaned_data['status'] = "pendente"
            
        return cleaned_data
    
    def _is_cache_valid(self, scan_name: str) -> bool:
        """
        Verifica se o cache é válido para um scan
        
        Args:
            scan_name: Nome do scan
            
        Returns:
            True se o cache é válido
        """
        if scan_name not in self._cache:
            return False
        
        if scan_name not in self._cache_timestamps:
            return False
        
        age = datetime.now().timestamp() - self._cache_timestamps[scan_name]
        return age < self.cache_timeout
    
    def _update_cache(self, scan_name: str, mapping_data: MappingData) -> None:
        """
        Atualiza o cache para um scan
        
        Args:
            scan_name: Nome do scan
            mapping_data: Dados de mapeamento
        """
        self._cache[scan_name] = mapping_data
        self._cache_timestamps[scan_name] = datetime.now().timestamp()
    
    def _clear_cache(self, scan_name: Optional[str] = None) -> None:
        """
        Limpa o cache
        
        Args:
            scan_name: Nome específico do scan ou None para limpar tudo
        """
        if scan_name:
            self._cache.pop(scan_name, None)
            self._cache_timestamps.pop(scan_name, None)
        else:
            self._cache.clear()
            self._cache_timestamps.clear()
    
    def create_backup(self, scan_name: str) -> Path:
        """
        Cria backup de um arquivo de mapeamento
        
        Args:
            scan_name: Nome do scan
            
        Returns:
            Caminho do arquivo de backup criado
            
        Raises:
            MappingFileError: Se não conseguir criar o backup
        """
        mapping_file = self._get_mapping_file(scan_name)
        
        if not mapping_file.exists():
            raise MappingFileError(f"Arquivo de mapeamento não encontrado: {mapping_file}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"{scan_name}_{timestamp}.json"
        
        try:
            shutil.copy2(mapping_file, backup_file)
            return backup_file
        except Exception as e:
            raise MappingFileError(f"Erro ao criar backup: {e}")
    
    def load_mapping(self, scan_name: str, use_cache: bool = True) -> MappingData:
        """
        Carrega mapeamento de um scan
        
        Args:
            scan_name: Nome do scan
            use_cache: Se deve usar cache
            
        Returns:
            Dados de mapeamento
            
        Raises:
            MappingFileError: Se não conseguir carregar o arquivo
            MappingValidationError: Se os dados são inválidos
        """
        # Verifica cache primeiro
        if use_cache and self._is_cache_valid(scan_name):
            return self._cache[scan_name]
        
        mapping_file = self._get_mapping_file(scan_name)
        
        if not mapping_file.exists():
            # Cria arquivo vazio se não existir
            scan_info = ScanInfo(name=scan_name, base_url="")
            mapping_data = MappingData(scan_info=scan_info, obras=[])
            self.save_mapping(scan_name, mapping_data)
            return mapping_data
        
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Valida estrutura
            self._validate_mapping_data(data)
            
            # Converte para objetos dataclass
            scan_info = ScanInfo(**data["scan_info"])
            
            obras = []
            for obra_data in data["obras"]:
                # Limpar campos incompatíveis da obra
                obra_data = self._clean_obra_data(obra_data.copy())
                
                # Converte capítulos se existirem
                capitulos = []
                if "capitulos" in obra_data and obra_data["capitulos"]:
                    for cap_data in obra_data["capitulos"]:
                        if isinstance(cap_data, dict):
                            # Limpar campos incompatíveis do capítulo
                            cap_data = self._clean_capitulo_data(cap_data.copy())
                            capitulos.append(Capitulo(**cap_data))
                        else:
                            # Compatibilidade com formato antigo
                            capitulos.append(Capitulo(numero=cap_data))
                
                obra_data["capitulos"] = capitulos
                
                # Converte status se for string
                if "status" in obra_data and isinstance(obra_data["status"], str):
                    try:
                        obra_data["status"] = ObraStatus(obra_data["status"])
                    except ValueError:
                        obra_data["status"] = ObraStatus.ATIVO
                
                obras.append(Obra(**obra_data))
            
            mapping_data = MappingData(
                scan_info=scan_info,
                obras=obras,
                metadata=data.get("metadata", {})
            )
            
            # Atualiza cache
            if use_cache:
                self._update_cache(scan_name, mapping_data)
            
            return mapping_data
            
        except json.JSONDecodeError as e:
            raise MappingFileError(f"Erro ao decodificar JSON: {e}")
        except Exception as e:
            raise MappingFileError(f"Erro ao carregar mapeamento: {e}")
    
    def save_mapping(self, scan_name: str, mapping_data: MappingData, create_backup: bool = True) -> None:
        """
        Salva mapeamento de um scan
        
        Args:
            scan_name: Nome do scan
            mapping_data: Dados para salvar
            create_backup: Se deve criar backup antes de salvar
            
        Raises:
            MappingFileError: Se não conseguir salvar o arquivo
        """
        mapping_file = self._get_mapping_file(scan_name)
        
        # Cria backup se arquivo existe
        if create_backup and mapping_file.exists():
            try:
                self.create_backup(scan_name)
            except Exception:
                pass  # Não falha se backup falhar
        
        # Atualiza metadata
        mapping_data.metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        mapping_data.metadata["total_obras"] = len(mapping_data.obras)
        
        # Converte para dict
        data = {
            "scan_info": asdict(mapping_data.scan_info),
            "obras": [asdict(obra) for obra in mapping_data.obras],
            "metadata": mapping_data.metadata
        }
        
        # Converte enums para strings
        for obra in data["obras"]:
            if isinstance(obra.get("status"), ObraStatus):
                obra["status"] = obra["status"].value
        
        try:
            # Salva temporariamente primeiro
            temp_file = mapping_file.with_suffix('.tmp')
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            # Move arquivo temporário para final
            temp_file.replace(mapping_file)
            
            # Atualiza cache
            self._update_cache(scan_name, mapping_data)
            
        except Exception as e:
            # Remove arquivo temporário se existir
            if temp_file.exists():
                temp_file.unlink()
            raise MappingFileError(f"Erro ao salvar mapeamento: {e}")
    
    def get_obra_by_id(self, scan_name: str, obra_id: str) -> Optional[Obra]:
        """
        Obtém obra por ID
        
        Args:
            scan_name: Nome do scan
            obra_id: ID da obra
            
        Returns:
            Obra encontrada ou None
        """
        try:
            mapping_data = self.load_mapping(scan_name)
            
            for obra in mapping_data.obras:
                if obra.id == obra_id:
                    return obra
            
            return None
            
        except Exception:
            return None
    
    def get_obra_by_title(self, scan_name: str, titulo: str) -> Optional[Obra]:
        """
        Obtém obra por título
        
        Args:
            scan_name: Nome do scan
            titulo: Título da obra
            
        Returns:
            Obra encontrada ou None
        """
        try:
            mapping_data = self.load_mapping(scan_name)
            
            for obra in mapping_data.obras:
                if obra.titulo.lower() == titulo.lower():
                    return obra
            
            return None
            
        except Exception:
            return None
    
    def add_obra(self, scan_name: str, obra: Obra) -> bool:
        """
        Adiciona nova obra
        
        Args:
            scan_name: Nome do scan
            obra: Obra para adicionar
            
        Returns:
            True se adicionada com sucesso
        """
        try:
            mapping_data = self.load_mapping(scan_name)
            
            # Verifica se já existe
            for existing_obra in mapping_data.obras:
                if existing_obra.id == obra.id or existing_obra.titulo == obra.titulo:
                    return False
            
            # Adiciona obra
            mapping_data.obras.append(obra)
            self.save_mapping(scan_name, mapping_data)
            
            return True
            
        except Exception:
            return False
    
    def update_obra_status(self, scan_name: str, obra_id: str, status: ObraStatus) -> bool:
        """
        Atualiza status de uma obra
        
        Args:
            scan_name: Nome do scan
            obra_id: ID da obra
            status: Novo status
            
        Returns:
            True se atualizada com sucesso
        """
        try:
            mapping_data = self.load_mapping(scan_name)
            
            for obra in mapping_data.obras:
                if obra.id == obra_id:
                    obra.status = status
                    obra.updated_at = datetime.now(timezone.utc).isoformat()
                    self.save_mapping(scan_name, mapping_data)
                    return True
            
            return False
            
        except Exception:
            return False
    
    def increment_error_count(self, scan_name: str, obra_id: str) -> int:
        """
        Incrementa contador de erros de uma obra
        
        Args:
            scan_name: Nome do scan
            obra_id: ID da obra
            
        Returns:
            Novo contador de erros ou -1 se falhou
        """
        try:
            mapping_data = self.load_mapping(scan_name)
            
            for obra in mapping_data.obras:
                if obra.id == obra_id:
                    obra.erros_consecutivos += 1
                    obra.updated_at = datetime.now(timezone.utc).isoformat()
                    
                    # Auto-quarentena após 5 erros
                    if obra.erros_consecutivos >= 5:
                        obra.status = ObraStatus.QUARENTENA
                    
                    self.save_mapping(scan_name, mapping_data)
                    return obra.erros_consecutivos
            
            return -1
            
        except Exception:
            return -1
    
    def reset_error_count(self, scan_name: str, obra_id: str) -> bool:
        """
        Reseta contador de erros de uma obra
        
        Args:
            scan_name: Nome do scan
            obra_id: ID da obra
            
        Returns:
            True se resetado com sucesso
        """
        try:
            mapping_data = self.load_mapping(scan_name)
            
            for obra in mapping_data.obras:
                if obra.id == obra_id:
                    obra.erros_consecutivos = 0
                    obra.updated_at = datetime.now(timezone.utc).isoformat()
                    self.save_mapping(scan_name, mapping_data)
                    return True
            
            return False
            
        except Exception:
            return False
    
    def list_scans(self) -> List[str]:
        """
        Lista todos os scans disponíveis
        
        Returns:
            Lista de nomes de scans
        """
        scan_files = self.data_dir.glob("*.json")
        return [f.stem for f in scan_files if f.is_file()]
    
    def get_scan_stats(self, scan_name: str) -> Dict[str, Any]:
        """
        Obtém estatísticas de um scan
        
        Args:
            scan_name: Nome do scan
            
        Returns:
            Estatísticas do scan
        """
        try:
            mapping_data = self.load_mapping(scan_name)
            
            total_obras = len(mapping_data.obras)
            ativas = sum(1 for obra in mapping_data.obras if obra.status == ObraStatus.ATIVO)
            quarentena = sum(1 for obra in mapping_data.obras if obra.status == ObraStatus.QUARENTENA)
            pausadas = sum(1 for obra in mapping_data.obras if obra.status == ObraStatus.PAUSADO)
            finalizadas = sum(1 for obra in mapping_data.obras if obra.status == ObraStatus.FINALIZADO)
            
            total_capitulos = sum(len(obra.capitulos) for obra in mapping_data.obras)
            obras_com_erros = sum(1 for obra in mapping_data.obras if obra.erros_consecutivos > 0)
            
            return {
                "scan_name": scan_name,
                "total_obras": total_obras,
                "total": total_obras,  # Alias compatível com template
                "ativas": ativas,  # Alias compatível com template  
                "quarentena": quarentena,  # Alias compatível com template
                "status_count": {
                    "ativas": ativas,
                    "quarentena": quarentena,
                    "pausadas": pausadas,
                    "finalizadas": finalizadas
                },
                "total_capitulos": total_capitulos,
                "obras_com_erros": obras_com_erros,
                "last_updated": mapping_data.metadata.get("updated_at")
            }
            
        except Exception:
            return {"scan_name": scan_name, "error": "Não foi possível carregar estatísticas"}
    
    def migrate_from_old_format(self, old_file: Union[str, Path], scan_mappings: Dict[str, str]) -> Dict[str, int]:
        """
        Migra dados do formato antigo obras_mapeadas.json
        
        Args:
            old_file: Caminho do arquivo antigo
            scan_mappings: Mapeamento de URL para nome do scan
            
        Returns:
            Estatísticas da migração por scan
        """
        old_file = Path(old_file)
        
        if not old_file.exists():
            raise MappingFileError(f"Arquivo antigo não encontrado: {old_file}")
        
        try:
            with open(old_file, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
        except Exception as e:
            raise MappingFileError(f"Erro ao ler arquivo antigo: {e}")
        
        migration_stats = {}
        
        # Agrupa obras por scan baseado na URL
        scan_obras = {}
        
        for obra_data in old_data:
            # Determina o scan baseado na URL
            url = obra_data.get("url", "")
            scan_name = "unknown"
            
            for url_pattern, name in scan_mappings.items():
                if url_pattern in url:
                    scan_name = name
                    break
            
            if scan_name not in scan_obras:
                scan_obras[scan_name] = []
            
            # Converte para novo formato
            obra = Obra(
                id=str(uuid.uuid4()),
                titulo=obra_data.get("titulo", ""),
                url_relativa=obra_data.get("url", ""),
                status=ObraStatus.ATIVO,
                ultimo_upload=obra_data.get("ultimo_upload"),
                erros_consecutivos=obra_data.get("erros_consecutivos", 0),
                capitulos=[],
                tags=obra_data.get("tags", []),
                autor=obra_data.get("autor"),
                descricao=obra_data.get("descricao")
            )
            
            # Converte capítulos se existirem
            if "capitulos" in obra_data:
                for cap in obra_data["capitulos"]:
                    if isinstance(cap, dict):
                        capitulo = Capitulo(
                            numero=cap.get("numero", ""),
                            url_relativa=cap.get("url", ""),
                            data_upload=cap.get("data_upload"),
                            status=cap.get("status", "pendente")
                        )
                    else:
                        capitulo = Capitulo(numero=cap, url_relativa="")
                    
                    obra.capitulos.append(capitulo)
            
            scan_obras[scan_name].append(obra)
        
        # Salva cada scan
        for scan_name, obras in scan_obras.items():
            try:
                # Carrega ou cria mapping
                try:
                    mapping_data = self.load_mapping(scan_name)
                except:
                    base_url = ""
                    for url_pattern, name in scan_mappings.items():
                        if name == scan_name:
                            base_url = url_pattern
                            break
                    
                    scan_info = ScanInfo(name=scan_name, base_url=base_url)
                    mapping_data = MappingData(scan_info=scan_info, obras=[])
                
                # Adiciona obras (evita duplicatas)
                added_count = 0
                for obra in obras:
                    # Verifica se já existe
                    exists = any(
                        existing.titulo == obra.titulo or existing.url_relativa == obra.url_relativa
                        for existing in mapping_data.obras
                    )
                    
                    if not exists:
                        mapping_data.obras.append(obra)
                        added_count += 1
                
                # Salva
                self.save_mapping(scan_name, mapping_data)
                migration_stats[scan_name] = added_count
                
            except Exception as e:
                migration_stats[scan_name] = f"Erro: {e}"
        
        return migration_stats
    
    def cleanup_old_backups(self, days_to_keep: int = 30) -> int:
        """
        Remove backups antigos
        
        Args:
            days_to_keep: Dias para manter backups
            
        Returns:
            Número de backups removidos
        """
        if not self.backup_dir.exists():
            return 0
        
        cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 3600)
        removed_count = 0
        
        for backup_file in self.backup_dir.glob("*.json"):
            if backup_file.stat().st_mtime < cutoff_date:
                try:
                    backup_file.unlink()
                    removed_count += 1
                except Exception:
                    pass
        
        return removed_count
    
    def get_global_stats(self) -> Dict[str, Any]:
        """
        Obtém estatísticas globais de todos os scans
        
        Returns:
            Estatísticas globais
        """
        scans = self.list_scans()
        
        total_obras = 0
        total_capitulos = 0
        total_ativas = 0
        total_quarentena = 0
        
        scan_stats = []
        
        for scan in scans:
            stats = self.get_scan_stats(scan)
            if "error" not in stats:
                total_obras += stats["total_obras"]
                total_capitulos += stats["total_capitulos"]
                total_ativas += stats["status_count"]["ativas"]
                total_quarentena += stats["status_count"]["quarentena"]
                scan_stats.append(stats)
        
        return {
            "total_scans": len(scans),
            "total_obras": total_obras,
            "obras_ativas": total_ativas,  # Nome compatível com template
            "obras_quarentena": total_quarentena,  # Nome compatível com template
            "total_capitulos": total_capitulos,
            "cache_size": len(self._cache),
            "scans": scan_stats
        }
    
    # Métodos relacionados ao Sistema de Quarentena
    
    def increment_obra_errors(self, scan_name: str, obra_id: Union[str, int]) -> bool:
        """
        Incrementa contador de erros consecutivos de uma obra
        
        Args:
            scan_name: Nome do scan
            obra_id: ID da obra
            
        Returns:
            True se incremento foi bem-sucedido
        """
        try:
            scan_data = self.load_scan_data(scan_name)
            if not scan_data:
                return False
            
            # Encontrar a obra
            for obra in scan_data.get("obras", []):
                if str(obra.get("id")) == str(obra_id):
                    obra["erros_consecutivos"] = obra.get("erros_consecutivos", 0) + 1
                    obra["updated_at"] = datetime.now(timezone.utc).isoformat()
                    
                    # Salvar alterações
                    return self.save_scan_data(scan_name, scan_data)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Erro ao incrementar erros da obra {obra_id}: {e}")
            return False
    
    def reset_obra_errors(self, scan_name: str, obra_id: Union[str, int]) -> bool:
        """
        Zera contador de erros consecutivos de uma obra
        
        Args:
            scan_name: Nome do scan
            obra_id: ID da obra
            
        Returns:
            True se reset foi bem-sucedido
        """
        try:
            scan_data = self.load_scan_data(scan_name)
            if not scan_data:
                return False
            
            # Encontrar a obra
            for obra in scan_data.get("obras", []):
                if str(obra.get("id")) == str(obra_id):
                    obra["erros_consecutivos"] = 0
                    obra["updated_at"] = datetime.now(timezone.utc).isoformat()
                    
                    # Salvar alterações
                    return self.save_scan_data(scan_name, scan_data)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Erro ao resetar erros da obra {obra_id}: {e}")
            return False
    
    def get_obras_with_high_errors(self, min_errors: int = 5) -> List[Dict[str, Any]]:
        """
        Obtém obras com alta quantidade de erros consecutivos
        
        Args:
            min_errors: Número mínimo de erros para incluir na lista
            
        Returns:
            Lista de obras com muitos erros
        """
        obras_com_erros = []
        
        try:
            scan_names = self.get_scan_names()
            
            for scan_name in scan_names:
                try:
                    scan_data = self.load_scan_data(scan_name)
                    if not scan_data:
                        continue
                    
                    for obra in scan_data.get("obras", []):
                        erros = obra.get("erros_consecutivos", 0)
                        if erros >= min_errors:
                            obras_com_erros.append({
                                "scan_name": scan_name,
                                "obra_id": obra.get("id"),
                                "titulo": obra.get("titulo"),
                                "erros_consecutivos": erros,
                                "status": obra.get("status"),
                                "ultimo_upload": obra.get("ultimo_upload"),
                                "updated_at": obra.get("updated_at")
                            })
                
                except Exception as e:
                    self.logger.error(f"Erro ao verificar scan {scan_name}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Erro ao obter obras com muitos erros: {e}")
        
        return sorted(obras_com_erros, key=lambda x: x["erros_consecutivos"], reverse=True)
    
    def get_active_obras_for_auto_update(self) -> List[Dict[str, Any]]:
        """
        Obtém lista de obras ativas para auto-update (exclui quarentena)
        
        Returns:
            Lista de obras ativas para processamento automático
        """
        obras_ativas = []
        
        try:
            scan_names = self.get_scan_names()
            
            for scan_name in scan_names:
                try:
                    scan_data = self.load_scan_data(scan_name)
                    if not scan_data:
                        continue
                    
                    # Verificar se scan está ativo
                    scan_info = scan_data.get("scan_info", {})
                    if not scan_info.get("active", True):
                        continue
                    
                    for obra in scan_data.get("obras", []):
                        status = obra.get("status", "ativo")
                        
                        # Incluir apenas obras ativas (excluir quarentena, pausado, etc.)
                        if status == "ativo":
                            obras_ativas.append({
                                "scan_name": scan_name,
                                "obra_id": obra.get("id"),
                                "titulo": obra.get("titulo"),
                                "url_relativa": obra.get("url_relativa"),
                                "ultimo_upload": obra.get("ultimo_upload"),
                                "erros_consecutivos": obra.get("erros_consecutivos", 0),
                                "capitulos": obra.get("capitulos", [])
                            })
                
                except Exception as e:
                    self.logger.error(f"Erro ao obter obras ativas do scan {scan_name}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Erro ao obter obras ativas: {e}")
        
        return obras_ativas
    
    # Métodos de compatibilidade para as rotas web
    def get_scan_names(self) -> List[str]:
        """Alias para list_scans() - compatibilidade com rotas web"""
        return self.list_scans()
    
    def load_scan_data(self, scan_name: str) -> Dict[str, Any]:
        """Carrega dados de um scan em formato compatível com as rotas web"""
        try:
            mapping_data = self.load_mapping(scan_name)
            
            # Converter MappingData para dict compatível com JSON
            return {
                "scan_info": self._dataclass_to_dict(mapping_data.scan_info),
                "obras": [self._dataclass_to_dict(obra) for obra in mapping_data.obras],
                "metadata": mapping_data.metadata
            }
        except Exception as e:
            self.logger.error(f"Erro ao carregar dados do scan {scan_name}: {e}")
            return {}
    
    def _dataclass_to_dict(self, obj) -> Dict[str, Any]:
        """Converte dataclass para dict, tratando enums e outros tipos especiais"""
        if hasattr(obj, '__dataclass_fields__'):
            result = {}
            for field_name, field_value in asdict(obj).items():
                if isinstance(field_value, list):
                    result[field_name] = [self._dataclass_to_dict(item) if hasattr(item, '__dataclass_fields__') else self._serialize_value(item) for item in field_value]
                else:
                    result[field_name] = self._serialize_value(field_value)
            return result
        else:
            return self._serialize_value(obj)
    
    def _serialize_value(self, value):
        """Serializa valores especiais (enums, etc) para JSON"""
        if isinstance(value, ObraStatus):
            return value.value
        elif hasattr(value, '__dict__'):
            return self._dataclass_to_dict(value)
        else:
            return value
    
    def update_obra_info(self, scan_name: str, obra_id: str, updates: Dict[str, Any]) -> bool:
        """Atualiza informações de uma obra"""
        try:
            mapping_data = self.load_mapping(scan_name)
            
            for obra in mapping_data.obras:
                if obra.id == obra_id:
                    # Atualizar campos permitidos
                    if 'titulo' in updates:
                        obra.titulo = updates['titulo']
                    if 'url_relativa' in updates:
                        obra.url_relativa = updates['url_relativa']
                    if 'status' in updates:
                        # Converter string para enum se necessário
                        if isinstance(updates['status'], str):
                            obra.status = ObraStatus(updates['status'])
                        else:
                            obra.status = updates['status']
                    
                    obra.updated_at = datetime.now(timezone.utc).isoformat()
                    self.save_mapping(scan_name, mapping_data)
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Erro ao atualizar obra {obra_id} do scan {scan_name}: {e}")
            return False
    
    def import_obra(self, scan_name: str, obra_data: Dict[str, Any]) -> Optional[str]:
        """Importa uma nova obra para um scan"""
        try:
            # Criar nova obra com ID único
            obra_id = str(uuid.uuid4())
            
            nova_obra = Obra(
                id=obra_id,
                titulo=obra_data.get('titulo', ''),
                url_relativa=obra_data.get('url_relativa', ''),
                status=ObraStatus.ATIVO,
                capitulos=[]
            )
            
            if self.add_obra(scan_name, nova_obra):
                return obra_id
            return None
            
        except Exception as e:
            self.logger.error(f"Erro ao importar obra para scan {scan_name}: {e}")
            return None