"""
Módulo de Mapeamento Distribuído do PyWeb

Este módulo implementa o sistema de mapeamento distribuído que substitui
o arquivo único obras_mapeadas.json por arquivos separados por scan/domínio.

Implementa a Task 2.1 do GITHUB_TASKS_LIST.md:
- MappingManager para arquivos JSON por scan
- Schema padronizado com validação
- Sistema de backup automático
- Cache inteligente para performance
- Migração de dados antigos
"""

from .mapping_manager import (
    MappingManager,
    MappingData,
    Obra,
    Capitulo,
    ScanInfo,
    ObraStatus,
    MappingError,
    MappingValidationError,
    MappingFileError
)

__all__ = [
    'MappingManager',
    'MappingData',
    'Obra',
    'Capitulo', 
    'ScanInfo',
    'ObraStatus',
    'MappingError',
    'MappingValidationError',
    'MappingFileError'
]