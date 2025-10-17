"""
MediocreToons Auto Uploader v2 - Sistema Principal
==================================================

Sistema completo de auto-upload para MediocreToons com arquitetura
refatorada, timer inteligente, fila unificada e sistema de quarentena.

Componentes Principais:
- MediocreAutoUploader: Classe central de integração
- PytesteCore: Motor de download e processamento
- AutoUpdateScheduler: Timer inteligente de 30 minutos
- UnifiedQueue: Fila unificada auto/manual
- MappingManager: Gerenciamento distribuído de obras
- QuarantineManager: Sistema de quarentena automática
- DiscordNotifier: Notificações via webhook

Uso:
    from src.mediocre_auto_uploader import MediocreAutoUploader, MediocreConfig
    
    config = MediocreConfig(
        auto_update_interval_minutes=30,
        quarantine_error_threshold=10
    )
    
    uploader = MediocreAutoUploader(config)
    uploader.start()

Autor: GitHub Copilot
Data: 16 de outubro de 2025
Versão: 2.0.0
"""

from .mediocre_auto_uploader import (
    MediocreAutoUploader,
    MediocreConfig,
    MediocreAutoUploaderError,
    get_mediocre_auto_uploader,
    cleanup_mediocre_auto_uploader
)

__version__ = "2.0.0"
__author__ = "GitHub Copilot"
__email__ = "mediocretoons@example.com"

__all__ = [
    "MediocreAutoUploader",
    "MediocreConfig", 
    "MediocreAutoUploaderError",
    "get_mediocre_auto_uploader",
    "cleanup_mediocre_auto_uploader"
]