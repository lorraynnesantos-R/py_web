"""
Módulo core do sistema PyWeb.

Este módulo contém os componentes centrais do sistema, incluindo
o núcleo refatorado PytesteCore e sistema de configurações.

Tasks implementadas:
- Task 1.1: PytesteFixedConfig - Configurações fixas
- Task 1.2: PytesteCore - Núcleo refatorado do sistema
"""

from .pyteste_core import PytesteCore
from .config import PytesteFixedConfig, ConfigValidationError

__all__ = [
    'PytesteCore',
    'PytesteFixedConfig', 
    'ConfigValidationError'
]

__version__ = '2.0.0'
__author__ = 'MediocreToons Auto Uploader v2'