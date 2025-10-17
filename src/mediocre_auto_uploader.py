"""
MediocreAutoUploader Principal - Classe Central de Integração
============================================================

Esta é a classe principal que integra todos os componentes do sistema
MediocreToons Auto Uploader v2, orquestrando o fluxo completo de:

Timer -> Busca obras -> Fila -> Processo -> Atualiza status -> Notifica -> Reinicia

Componentes Integrados:
- PytesteCore: Download e processamento de obras
- AutoUpdateScheduler: Timer inteligente de 30 minutos
- UnifiedQueue: Fila unificada auto/manual
- MappingManager: Gerenciamento distribuído de obras
- QuarantineManager: Sistema de quarentena automática
- DiscordNotifier: Notificações via webhook

Arquitetura:
    MediocreAutoUploader (Central)
    ├── PytesteCore (Downloads)
    ├── AutoUpdateScheduler (Timer)
    ├── UnifiedQueue (Fila)
    ├── MappingManager (Dados)
    ├── QuarantineManager (Quarentena)
    └── DiscordNotifier (Alertas)

Autor: GitHub Copilot
Data: 16 de outubro de 2025
"""

import asyncio
import logging
import threading
import time
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
import json

# Logging setup
logger = logging.getLogger(__name__)

# Core components
try:
    from src.core.pyteste_core import PytesteCore
    from src.core.config.fixed_config import PytesteFixedConfig
    from src.core.config.config_manager import PytesteConfigManager
    PYTESTE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"PytesteCore não disponível: {e}")
    PYTESTE_AVAILABLE = False

# Auto-uploader components
try:
    from src.auto_uploader.scheduler import AutoUpdateScheduler, SchedulerConfig
    from src.auto_uploader.queue import UnifiedQueue, QueueJob, QueuePriority
    from src.auto_uploader.discord_notifier import DiscordNotifier
    SCHEDULER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Componentes de auto-uploader não disponíveis: {e}")
    SCHEDULER_AVAILABLE = False

# Mapping and quarantine
try:
    from src.mapping.mapping_manager import MappingManager
    from src.mapping.quarantine import QuarantineManager
    MAPPING_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Componentes de mapeamento não disponíveis: {e}")
    MAPPING_AVAILABLE = False


@dataclass
class MediocreConfig:
    """Configuração principal do MediocreAutoUploader"""
    
    # Diretórios
    data_dir: Path = Path("./data")
    downloads_dir: Path = Path("./downloads/mediocre_uploads")
    logs_dir: Path = Path("./logs")
    
    # Timer settings
    auto_update_interval_minutes: int = 30
    retry_failed_after_minutes: int = 60
    
    # Queue settings
    max_concurrent_jobs: int = 1
    max_retry_attempts: int = 3
    
    # Quarentena
    quarantine_error_threshold: int = 10
    quarantine_cooldown_hours: int = 24
    
    # Discord
    discord_webhook_url: Optional[str] = None
    discord_notifications_enabled: bool = True
    
    # Processing
    enable_auto_update: bool = True
    enable_manual_queue: bool = True
    graceful_shutdown: bool = True
    
    def __post_init__(self):
        """Garantir que diretórios existam"""
        for directory in [self.data_dir, self.downloads_dir, self.logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)


class MediocreAutoUploaderError(Exception):
    """Exceção base para erros do MediocreAutoUploader"""
    pass


class MediocreAutoUploader:
    """
    Classe principal do MediocreToons Auto Uploader v2
    
    Responsável por orquestrar todo o sistema de auto-update,
    integrando todos os componentes e gerenciando o fluxo completo.
    """
    
    def __init__(self, config: Optional[MediocreConfig] = None):
        """
        Inicializa o MediocreAutoUploader
        
        Args:
            config: Configuração personalizada (opcional)
        """
        self.config = config or MediocreConfig()
        self._running = False
        self._shutdown_event = threading.Event()
        self._main_thread: Optional[threading.Thread] = None
        
        # Status tracking
        self._last_auto_update: Optional[datetime] = None
        self._total_processed = 0
        self._total_errors = 0
        self._startup_time: Optional[datetime] = None
        
        # Initialize components
        self._init_logging()
        self._init_components()
        self._setup_signal_handlers()
        
        logger.info("🚀 MediocreAutoUploader inicializado")
    
    def _init_logging(self):
        """Configurar sistema de logging"""
        log_file = self.config.logs_dir / "mediocre_auto_uploader.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Ajustar níveis para componentes específicos
        logging.getLogger('src.auto_uploader').setLevel(logging.DEBUG)
        logging.getLogger('src.mapping').setLevel(logging.INFO)
        logging.getLogger('src.core').setLevel(logging.INFO)
    
    def _init_components(self):
        """Inicializar todos os componentes"""
        try:
            logger.info("Inicializando componentes...")
            
            # 1. Configurações
            self.fixed_config = PytesteFixedConfig()
            self.config_manager = PytesteConfigManager()
            
            # 2. Core PytesteCore
            self.pyteste_core = PytesteCore(
                fixed_config=self.fixed_config,
                config_manager=self.config_manager
            )
            
            # 3. Mapping e Quarentena
            self.mapping_manager = MappingManager(self.config.data_dir / "mapping")
            self.quarantine_manager = QuarantineManager(
                mapping_manager=self.mapping_manager,
                error_threshold=self.config.quarantine_error_threshold,
                cooldown_hours=self.config.quarantine_cooldown_hours
            )
            
            # 4. Fila Unificada
            self.queue = UnifiedQueue(
                data_dir=self.config.data_dir,
                max_concurrent_jobs=self.config.max_concurrent_jobs
            )
            
            # 5. Discord Notifier
            if self.config.discord_webhook_url:
                self.discord_notifier = DiscordNotifier(
                    webhook_url=self.config.discord_webhook_url,
                    enabled=self.config.discord_notifications_enabled
                )
            else:
                self.discord_notifier = None
                logger.warning("Discord webhook não configurado - notificações desabilitadas")
            
            # 6. Scheduler (último, pois depende dos outros)
            scheduler_config = SchedulerConfig(
                interval_minutes=self.config.auto_update_interval_minutes,
                enabled=self.config.enable_auto_update
            )
            
            self.scheduler = AutoUpdateScheduler(
                config=scheduler_config,
                data_dir=self.config.data_dir
            )
            
            # Conectar callback do scheduler
            self.scheduler.set_update_callback(self._execute_auto_update_cycle)
            
            logger.info("✅ Todos os componentes inicializados com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar componentes: {e}")
            raise MediocreAutoUploaderError(f"Falha na inicialização: {e}")
    
    def _setup_signal_handlers(self):
        """Configurar handlers para graceful shutdown"""
        if self.config.graceful_shutdown:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handler para sinais de shutdown"""
        logger.info(f"🛑 Sinal {signum} recebido, iniciando shutdown graceful...")
        self.stop()
    
    def start(self) -> bool:
        """
        Iniciar o sistema completo
        
        Returns:
            bool: True se iniciado com sucesso
        """
        if self._running:
            logger.warning("Sistema já está rodando")
            return False
        
        try:
            logger.info("🚀 Iniciando MediocreAutoUploader...")
            self._running = True
            self._startup_time = datetime.now()
            self._shutdown_event.clear()
            
            # Iniciar componentes
            self.queue.start()
            
            if self.config.enable_auto_update:
                self.scheduler.start()
                logger.info("⏰ Auto-update scheduler iniciado")
            
            # Thread principal do sistema
            self._main_thread = threading.Thread(
                target=self._main_loop,
                name="MediocreAutoUploader-Main"
            )
            self._main_thread.start()
            
            # Notificar Discord sobre startup
            if self.discord_notifier:
                asyncio.run(self.discord_notifier.notify_system_startup())
            
            logger.info("✅ MediocreAutoUploader iniciado com sucesso!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar sistema: {e}")
            self._running = False
            return False
    
    def stop(self) -> bool:
        """
        Parar o sistema gracefully
        
        Returns:
            bool: True se parado com sucesso
        """
        if not self._running:
            logger.warning("Sistema já está parado")
            return False
        
        try:
            logger.info("🛑 Parando MediocreAutoUploader...")
            
            # Sinalizar shutdown
            self._running = False
            self._shutdown_event.set()
            
            # Parar scheduler
            if hasattr(self, 'scheduler'):
                self.scheduler.stop()
                logger.info("⏰ Scheduler parado")
            
            # Parar fila
            if hasattr(self, 'queue'):
                self.queue.stop()
                logger.info("📦 Fila parada")
            
            # Aguardar thread principal
            if self._main_thread and self._main_thread.is_alive():
                self._main_thread.join(timeout=30)
                if self._main_thread.is_alive():
                    logger.warning("Thread principal não finalizou no tempo esperado")
            
            # Notificar Discord sobre shutdown
            if self.discord_notifier:
                uptime = datetime.now() - self._startup_time if self._startup_time else timedelta(0)
                asyncio.run(self.discord_notifier.notify_system_shutdown(
                    uptime_seconds=int(uptime.total_seconds()),
                    jobs_processed=self._total_processed
                ))
            
            logger.info("✅ MediocreAutoUploader parado com sucesso!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao parar sistema: {e}")
            return False
    
    def _main_loop(self):
        """Loop principal do sistema"""
        logger.info("🔄 Iniciando loop principal")
        
        while self._running and not self._shutdown_event.is_set():
            try:
                # Processar fila manual/urgente
                self._process_manual_queue()
                
                # Verificar quarentena (a cada 5 minutos)
                if self._should_check_quarantine():
                    self._process_quarantine_check()
                
                # Aguardar próximo ciclo (1 segundo)
                self._shutdown_event.wait(1.0)
                
            except Exception as e:
                logger.error(f"❌ Erro no loop principal: {e}")
                self._total_errors += 1
                time.sleep(5)  # Evitar loop de erro
        
        logger.info("🔄 Loop principal finalizado")
    
    def _execute_auto_update_cycle(self):
        """
        Executar ciclo completo de auto-update
        
        Este é o método callback chamado pelo scheduler
        quando o timer de 30 minutos expira.
        """
        logger.info("🔄 Iniciando ciclo de auto-update")
        start_time = datetime.now()
        
        try:
            # 1. Buscar obras ativas para update
            active_obras = self._get_obras_for_auto_update()
            
            if not active_obras:
                logger.info("📭 Nenhuma obra ativa encontrada para auto-update")
                return
            
            logger.info(f"📚 Encontradas {len(active_obras)} obras para auto-update")
            
            # 2. Adicionar à fila com prioridade NORMAL (auto-update)
            for obra in active_obras:
                job = QueueJob(
                    obra_id=obra['id'],
                    obra_name=obra['titulo'],
                    obra_url=obra['url_completa'],
                    scan_name=obra['scan'],
                    job_type='AUTO',
                    priority=QueuePriority.NORMAL
                )
                
                self.queue.add_auto_job(
                    obra_id=obra['id'],
                    obra_name=obra['titulo'],
                    obra_url=obra['url_completa'],
                    scan_name=obra['scan']
                )
            
            # 3. Processar fila
            processed_count = self._process_auto_update_queue()
            
            # 4. Atualizar estatísticas
            self._last_auto_update = datetime.now()
            self._total_processed += processed_count
            
            duration = datetime.now() - start_time
            logger.info(f"✅ Ciclo de auto-update concluído em {duration.total_seconds():.1f}s")
            logger.info(f"📊 Processadas {processed_count} obras")
            
        except Exception as e:
            logger.error(f"❌ Erro no ciclo de auto-update: {e}")
            self._total_errors += 1
            
            # Notificar Discord sobre erro crítico
            if self.discord_notifier:
                asyncio.run(self.discord_notifier.notify_critical_error(
                    error_message=str(e),
                    context="Auto-update cycle"
                ))
    
    def _get_obras_for_auto_update(self) -> List[Dict[str, Any]]:
        """
        Buscar obras ativas elegíveis para auto-update
        
        Returns:
            Lista de obras para processar
        """
        try:
            all_obras = []
            
            # Iterar por todos os scans
            for scan_name in self.mapping_manager.get_available_scans():
                try:
                    mapping = self.mapping_manager.load_mapping(scan_name)
                    
                    for obra in mapping.obras:
                        # Verificar se obra está ativa (não em quarentena)
                        if not self.quarantine_manager.is_quarantined(scan_name, obra.id):
                            obra_dict = {
                                'id': obra.id,
                                'titulo': obra.titulo,
                                'url_relativa': obra.url_relativa,
                                'url_completa': f"{mapping.scan_info.base_url}{obra.url_relativa}",
                                'scan': scan_name,
                                'ultimo_upload': obra.ultimo_upload,
                                'erros_consecutivos': obra.erros_consecutivos
                            }
                            all_obras.append(obra_dict)
                
                except Exception as e:
                    logger.error(f"Erro ao processar scan {scan_name}: {e}")
                    continue
            
            return all_obras
            
        except Exception as e:
            logger.error(f"Erro ao buscar obras para auto-update: {e}")
            return []
    
    def _process_auto_update_queue(self) -> int:
        """
        Processar fila de auto-update
        
        Returns:
            Número de obras processadas
        """
        processed = 0
        
        while True:
            # Buscar próximo job da fila
            job = self.queue.get_next_job()
            if not job:
                break
            
            try:
                # Processar obra com PytesteCore
                success = self._process_single_obra(job)
                
                if success:
                    self.queue.mark_completed(job.job_id)
                    processed += 1
                else:
                    self.queue.mark_failed(job.job_id, "Falha no processamento")
                
            except Exception as e:
                logger.error(f"Erro ao processar job {job.job_id}: {e}")
                self.queue.mark_failed(job.job_id, str(e))
        
        return processed
    
    def _process_manual_queue(self):
        """Processar jobs manuais de alta prioridade"""
        # Verificar se há jobs manuais (URGENT/HIGH priority)
        manual_jobs = self.queue.get_jobs_by_status('PENDING', limit=10)
        
        for job_data in manual_jobs:
            if job_data.get('priority') in ['URGENT', 'HIGH']:
                try:
                    # Processar imediatamente
                    job = self.queue.get_next_job()
                    if job:
                        success = self._process_single_obra(job)
                        
                        if success:
                            self.queue.mark_completed(job.job_id)
                            logger.info(f"✅ Job manual {job.job_id} processado com sucesso")
                        else:
                            self.queue.mark_failed(job.job_id, "Falha no processamento manual")
                            logger.error(f"❌ Falha no job manual {job.job_id}")
                
                except Exception as e:
                    logger.error(f"Erro ao processar job manual: {e}")
    
    def _process_single_obra(self, job: QueueJob) -> bool:
        """
        Processar uma única obra
        
        Args:
            job: Job a ser processado
            
        Returns:
            bool: True se processado com sucesso
        """
        try:
            logger.info(f"📥 Processando obra: {job.obra_name} ({job.scan_name})")
            
            # Usar interface simplificada para processamento
            result = self._download_obra_with_pyteste(job)
            
            if result.get('success', False):
                # Atualizar mapping com sucesso
                self._update_obra_success(job)
                logger.info(f"✅ Obra processada com sucesso: {job.obra_name}")
                return True
            else:
                # Atualizar mapping com erro
                self._update_obra_error(job, result.get('error', 'Erro desconhecido'))
                logger.error(f"❌ Falha ao processar obra: {job.obra_name}")
                return False
        
        except Exception as e:
            self._update_obra_error(job, str(e))
            logger.error(f"❌ Exceção ao processar obra {job.obra_name}: {e}")
            return False
    
    def _download_obra_with_pyteste(self, job: QueueJob) -> Dict[str, Any]:
        """
        Interface simplificada para download usando PytesteCore
        
        Args:
            job: Job a ser processado
            
        Returns:
            Dict com resultado do processamento
        """
        try:
            # Por enquanto, simular o processamento
            # Futuramente será integrado com PytesteCore real
            
            # Simular diferentes cenários baseados no nome da obra
            if "test_fail" in job.obra_name.lower():
                return {
                    'success': False,
                    'error': 'Simulação de falha para teste'
                }
            elif "test_error" in job.obra_name.lower():
                raise Exception("Simulação de exceção para teste")
            else:
                # Simular sucesso
                import time
                time.sleep(2)  # Simular tempo de processamento
                
                return {
                    'success': True,
                    'capitulos_processados': 1,
                    'paginas_baixadas': 15,
                    'tempo_processamento': 2.0
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _update_obra_success(self, job: QueueJob):
        """Atualizar obra após sucesso"""
        try:
            # Resetar contador de erros
            self.mapping_manager.update_obra_error_count(
                scan_name=job.scan_name,
                obra_id=job.obra_id,
                error_count=0
            )
            
            # Atualizar timestamp
            self.mapping_manager.update_obra_timestamp(
                scan_name=job.scan_name,
                obra_id=job.obra_id,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Erro ao atualizar obra após sucesso: {e}")
    
    def _update_obra_error(self, job: QueueJob, error_message: str):
        """Atualizar obra após erro"""
        try:
            # Incrementar contador de erros
            current_errors = self.mapping_manager.get_obra_error_count(
                scan_name=job.scan_name,
                obra_id=job.obra_id
            )
            
            new_error_count = current_errors + 1
            
            self.mapping_manager.update_obra_error_count(
                scan_name=job.scan_name,
                obra_id=job.obra_id,
                error_count=new_error_count
            )
            
            # Verificar se deve ir para quarentena
            if new_error_count >= self.config.quarantine_error_threshold:
                self.quarantine_manager.quarantine_obra(
                    scan_name=job.scan_name,
                    obra_id=job.obra_id,
                    reason=f"Atingiu {new_error_count} erros consecutivos"
                )
                
                logger.warning(f"🔒 Obra {job.obra_name} colocada em quarentena")
                
                # Notificar Discord
                if self.discord_notifier:
                    asyncio.run(self.discord_notifier.notify_quarantine_added(
                        obra_name=job.obra_name,
                        scan_name=job.scan_name,
                        error_count=new_error_count,
                        last_error=error_message
                    ))
        
        except Exception as e:
            logger.error(f"Erro ao atualizar obra após erro: {e}")
    
    def _should_check_quarantine(self) -> bool:
        """Verificar se deve executar check de quarentena"""
        # A cada 5 minutos
        return int(time.time()) % 300 == 0
    
    def _process_quarantine_check(self):
        """Verificar se obras podem sair da quarentena"""
        try:
            recovered = self.quarantine_manager.check_recovery_candidates()
            
            if recovered:
                logger.info(f"🔓 {len(recovered)} obras recuperadas da quarentena")
                
                # Notificar Discord
                if self.discord_notifier:
                    for obra in recovered:
                        asyncio.run(self.discord_notifier.notify_quarantine_removed(
                            obra_name=obra['obra_name'],
                            scan_name=obra['scan_name'],
                            quarantine_duration=obra['quarantine_duration']
                        ))
        
        except Exception as e:
            logger.error(f"Erro no check de quarentena: {e}")
    
    # API Methods for Web Interface
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Obter status completo do sistema
        
        Returns:
            Dict com informações de status
        """
        uptime = datetime.now() - self._startup_time if self._startup_time else timedelta(0)
        
        return {
            'running': self._running,
            'uptime_seconds': int(uptime.total_seconds()),
            'startup_time': self._startup_time.isoformat() if self._startup_time else None,
            'last_auto_update': self._last_auto_update.isoformat() if self._last_auto_update else None,
            'total_processed': self._total_processed,
            'total_errors': self._total_errors,
            'scheduler_status': self.scheduler.get_status() if hasattr(self, 'scheduler') else None,
            'queue_status': self.queue.get_queue_status() if hasattr(self, 'queue') else None,
            'quarantine_stats': self.quarantine_manager.get_stats() if hasattr(self, 'quarantine_manager') else None
        }
    
    def add_manual_job(self, obra_id: str, obra_name: str, obra_url: str, 
                      scan_name: str, priority: str = 'HIGH') -> bool:
        """
        Adicionar job manual à fila
        
        Args:
            obra_id: ID da obra
            obra_name: Nome da obra
            obra_url: URL da obra
            scan_name: Nome do scan
            priority: Prioridade (URGENT/HIGH)
            
        Returns:
            bool: True se adicionado com sucesso
        """
        try:
            priority_enum = QueuePriority.URGENT if priority == 'URGENT' else QueuePriority.HIGH
            
            self.queue.add_manual_job(
                obra_id=obra_id,
                obra_name=obra_name,
                obra_url=obra_url,
                scan_name=scan_name,
                priority=priority_enum
            )
            
            logger.info(f"📌 Job manual adicionado: {obra_name} ({priority})")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao adicionar job manual: {e}")
            return False
    
    def pause_auto_update(self) -> bool:
        """Pausar auto-update temporariamente"""
        try:
            if hasattr(self, 'scheduler'):
                self.scheduler.pause()
                logger.info("⏸️ Auto-update pausado")
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao pausar auto-update: {e}")
            return False
    
    def resume_auto_update(self) -> bool:
        """Retomar auto-update"""
        try:
            if hasattr(self, 'scheduler'):
                self.scheduler.resume()
                logger.info("▶️ Auto-update retomado")
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao retomar auto-update: {e}")
            return False
    
    def reset_timer(self) -> bool:
        """Resetar timer do auto-update"""
        try:
            if hasattr(self, 'scheduler'):
                self.scheduler.reset_timer()
                logger.info("🔄 Timer resetado")
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao resetar timer: {e}")
            return False


# Singleton instance
_mediocre_instance: Optional[MediocreAutoUploader] = None


def get_mediocre_auto_uploader(config: Optional[MediocreConfig] = None) -> MediocreAutoUploader:
    """
    Obter instância singleton do MediocreAutoUploader
    
    Args:
        config: Configuração personalizada (apenas na primeira chamada)
        
    Returns:
        Instância do MediocreAutoUploader
    """
    global _mediocre_instance
    
    if _mediocre_instance is None:
        _mediocre_instance = MediocreAutoUploader(config)
    
    return _mediocre_instance


def cleanup_mediocre_auto_uploader():
    """Limpar instância singleton"""
    global _mediocre_instance
    
    if _mediocre_instance:
        _mediocre_instance.stop()
        _mediocre_instance = None


if __name__ == "__main__":
    """Executar standalone para testes"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Configuração de teste
    config = MediocreConfig(
        discord_webhook_url=os.getenv('DISCORD_WEBHOOK_URL'),
        auto_update_interval_minutes=1,  # 1 minuto para testes
        enable_auto_update=True
    )
    
    # Inicializar sistema
    uploader = MediocreAutoUploader(config)
    
    try:
        print("🚀 Iniciando MediocreAutoUploader em modo de teste...")
        uploader.start()
        
        # Manter rodando
        while uploader._running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Shutdown solicitado pelo usuário")
    finally:
        uploader.stop()
        print("✅ Sistema finalizado")