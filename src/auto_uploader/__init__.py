"""
Auto Uploader Package - Sistema de automação para uploads
========================================================

Este package contém o sistema completo de automação para uploads,
incluindo agendamento, fila unificada, verificação de saúde e notificações.

Módulos:
--------
- scheduler: AutoUpdateScheduler com timer inteligente
- health_checker: Verificação de saúde da API
- scan_update_manager: Gerenciamento de updates por scan
- update_models: Modelos de dados para updates
- discord_notifier: Notificações via Discord
"""

# Importações básicas que sempre existem
from .scheduler import AutoUpdateScheduler, SchedulerConfig, get_scheduler
from .queue import UnifiedQueue, QueueJob, QueuePriority, JobState, get_unified_queue

# Importações condicionais para módulos que podem não existir ainda
try:
    from .health_checker import APIHealthChecker
except ImportError:
    APIHealthChecker = None

try:
    from .scan_update_manager import ScanUpdateManager
except ImportError:
    ScanUpdateManager = None

try:
    from .update_models import (
        UpdateInfo,
        ScanUpdateResult, 
        BatchUpdateResult,
        UpdateMethod,
        UpdateCacheEntry,
        ProviderCapabilities
    )
except ImportError:
    UpdateInfo = None
    ScanUpdateResult = None
    BatchUpdateResult = None
    UpdateMethod = None
    UpdateCacheEntry = None
    ProviderCapabilities = None

# Listar apenas módulos que foram importados com sucesso
__all__ = [
    'AutoUpdateScheduler', 
    'SchedulerConfig', 
    'get_scheduler',
    'UnifiedQueue',
    'QueueJob',
    'QueuePriority', 
    'JobState',
    'get_unified_queue'
]

if APIHealthChecker is not None:
    __all__.append('APIHealthChecker')

if ScanUpdateManager is not None:
    __all__.append('ScanUpdateManager')

if UpdateInfo is not None:
    __all__.extend([
        'UpdateInfo',
        'ScanUpdateResult', 
        'BatchUpdateResult',
        'UpdateMethod',
        'UpdateCacheEntry',
        'ProviderCapabilities'
    ])

__version__ = "2.0.0"
__author__ = "MediocreToons Auto Uploader Team"