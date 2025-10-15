"""
Módulo de configuração do sistema PyWeb.

Este módulo contém todas as classes e utilitários relacionados à configuração
do sistema, incluindo configurações fixas e gerenciamento de configurações.

Implementa as funcionalidades definidas nas Tasks do GITHUB_TASKS_LIST.md:
"""

from .fixed_config import PytesteFixedConfig, ConfigValidationError

__all__ = ['PytesteFixedConfig', 'ConfigValidationError']

__version__ = '1.0.0'
__author__ = 'MediocreToons Auto Uploader v2'