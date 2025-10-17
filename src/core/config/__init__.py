"""
Módulo de configuração do sistema PyWeb.

Este módulo contém todas as classes e utilitários relacionados à configuração
do sistema, incluindo configurações fixas, gerenciamento de configurações e logging.

Implementa as funcionalidades definidas nas Tasks do GITHUB_TASKS_LIST.md:
- Task 1.1: PytesteFixedConfig
- Task 1.2: PytesteCore integração  
- Task 1.3: PytesteConfigManager
- Task 1.4: Sistema de Logging Unificado
"""

from .fixed_config import PytesteFixedConfig, ConfigValidationError
from .config_manager import (
    PytesteConfigManager, 
    ConfigMigrationError, 
    ConfigBackupError
)
from .migration import ConfigMigrator, MigrationResult
from .unified_logger import (
    UnifiedLogger, LogLevel, LogFormat, JsonFormatter,
    LoggerMixin, get_logger, setup_development_logging, setup_production_logging
)

__all__ = [
    'PytesteFixedConfig', 
    'ConfigValidationError',
    'PytesteConfigManager',
    'ConfigMigrationError',
    'ConfigBackupError',
    'ConfigMigrator',
    'MigrationResult',
    'UnifiedLogger',
    'LogLevel',
    'LogFormat', 
    'JsonFormatter',
    'LoggerMixin',
    'get_logger',
    'setup_development_logging',
    'setup_production_logging'
]

__version__ = '1.3.0'
__author__ = 'MediocreToons Auto Uploader v2'