"""
Pacote de rotas da interface web

Contém todos os blueprints organizados por funcionalidade.
"""

from .dashboard import dashboard_bp
from .config import config_bp
from .mapping import mapping_bp
from .logs import logs_bp
from .queue import queue_bp
from .api import api_bp

__all__ = [
    'dashboard_bp',
    'config_bp', 
    'mapping_bp',
    'logs_bp',
    'queue_bp',
    'api_bp'
]