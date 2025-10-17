"""
AutoUpdateScheduler - Sistema de agendamento inteligente com timer pós-processo
=============================================================================

Sistema de agendamento para auto-update com timer de 30 minutos que inicia
APÓS a conclusão de cada processo, não durante a execução.

Features:
- Timer inteligente pós-processo
- Fila unificada (manual > auto)
- Controles Start/Stop/Pause
- Persistência de estado
- Integração com quarentena
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import threading
from queue import PriorityQueue, Empty

# Configuração de logging
logger = logging.getLogger(__name__)


class SchedulerState(Enum):
    """Estados do agendador"""
    STOPPED = "stopped"
    RUNNING = "running" 
    PAUSED = "paused"
    PROCESSING = "processing"


class JobPriority(Enum):
    """Prioridades dos jobs"""
    HIGH = 1      # Manual
    NORMAL = 2    # Auto


class JobStatus(Enum):
    """Status dos jobs"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SchedulerJob:
    """Representa um job na fila do agendador"""
    id: str
    obra_id: str
    scan_name: str
    priority: JobPriority
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def __lt__(self, other):
        """Comparação para PriorityQueue (menor valor = maior prioridade)"""
        return self.priority.value < other.priority.value


@dataclass 
class SchedulerConfig:
    """Configurações do agendador"""
    timer_interval: int = 30 * 60  # 30 minutos em segundos
    max_retries: int = 3
    retry_delay: int = 5 * 60     # 5 minutos
    enable_quarantine_check: bool = True
    enable_health_check: bool = True
    health_check_timeout: int = 10
    save_state_interval: int = 60  # Salvar estado a cada 60s


class AutoUpdateScheduler:
    """
    Sistema de agendamento inteligente para auto-updates
    
    Features principais:
    - Timer de 30min que inicia APÓS conclusão do processo
    - Fila unificada com prioridade (manual > auto)
    - Controles Start/Stop/Pause
    - Persistência de estado
    - Integração com quarentena
    """
    
    def __init__(self, data_dir: Path, config: Optional[SchedulerConfig] = None):
        self.data_dir = Path(data_dir)
        self.config = config or SchedulerConfig()
        
        # Estado do agendador
        self.state = SchedulerState.STOPPED
        self.timer_remaining = 0
        self.last_process_end = None
        self.current_job = None
        
        # Fila de jobs
        self.job_queue = PriorityQueue()
        self.completed_jobs = []
        self.failed_jobs = []
        
        # Threading
        self._scheduler_thread = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._lock = threading.Lock()
        
        # Arquivos de estado
        self.state_file = self.data_dir / "scheduler_state.json"
        self.queue_file = self.data_dir / "scheduler_queue.json"
        
        # Criar diretório se não existir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Carregar estado persistido
        self._load_state()
        
        logger.info("AutoUpdateScheduler inicializado")
    
    def start(self) -> bool:
        """
        Inicia o agendador
        
        Returns:
            bool: True se iniciado com sucesso
        """
        try:
            with self._lock:
                if self.state in [SchedulerState.RUNNING, SchedulerState.PROCESSING]:
                    logger.warning("Scheduler já está rodando")
                    return False
                
                self.state = SchedulerState.RUNNING
                self._stop_event.clear()
                self._pause_event.clear()
                
                # Iniciar thread do agendador
                self._scheduler_thread = threading.Thread(
                    target=self._scheduler_loop,
                    daemon=True,
                    name="AutoUpdateScheduler"
                )
                self._scheduler_thread.start()
                
                logger.info("AutoUpdateScheduler iniciado")
                self._save_state()
                return True
                
        except Exception as e:
            logger.error(f"Erro ao iniciar scheduler: {e}")
            return False
    
    def stop(self) -> bool:
        """
        Para o agendador
        
        Returns:
            bool: True se parado com sucesso
        """
        try:
            with self._lock:
                if self.state == SchedulerState.STOPPED:
                    logger.warning("Scheduler já está parado")
                    return False
                
                self.state = SchedulerState.STOPPED
                self._stop_event.set()
                self._pause_event.set()  # Liberar pause também
                
                # Aguardar thread terminar
                if self._scheduler_thread and self._scheduler_thread.is_alive():
                    self._scheduler_thread.join(timeout=5)
                
                logger.info("AutoUpdateScheduler parado")
                self._save_state()
                return True
                
        except Exception as e:
            logger.error(f"Erro ao parar scheduler: {e}")
            return False
    
    def pause(self) -> bool:
        """
        Pausa o agendador (timer para, mas não processa novos jobs)
        
        Returns:
            bool: True se pausado com sucesso
        """
        try:
            with self._lock:
                if self.state != SchedulerState.RUNNING:
                    logger.warning("Scheduler não está rodando")
                    return False
                
                self.state = SchedulerState.PAUSED
                self._pause_event.set()
                
                logger.info("AutoUpdateScheduler pausado")
                self._save_state()
                return True
                
        except Exception as e:
            logger.error(f"Erro ao pausar scheduler: {e}")
            return False
    
    def resume(self) -> bool:
        """
        Resume o agendador pausado
        
        Returns:
            bool: True se resumido com sucesso
        """
        try:
            with self._lock:
                if self.state != SchedulerState.PAUSED:
                    logger.warning("Scheduler não está pausado")
                    return False
                
                self.state = SchedulerState.RUNNING
                self._pause_event.clear()
                
                logger.info("AutoUpdateScheduler resumido")
                self._save_state()
                return True
                
        except Exception as e:
            logger.error(f"Erro ao resumir scheduler: {e}")
            return False
    
    def add_manual_job(self, obra_id: str, scan_name: str) -> str:
        """
        Adiciona job manual (alta prioridade)
        
        Args:
            obra_id: ID da obra
            scan_name: Nome do scan
            
        Returns:
            str: ID do job criado
        """
        job_id = f"manual_{int(time.time())}_{obra_id}"
        
        job = SchedulerJob(
            id=job_id,
            obra_id=obra_id,
            scan_name=scan_name,
            priority=JobPriority.HIGH,
            status=JobStatus.PENDING,
            created_at=datetime.now()
        )
        
        self.job_queue.put(job)
        logger.info(f"Job manual adicionado: {job_id}")
        
        self._save_queue()
        return job_id
    
    def add_auto_job(self, obra_id: str, scan_name: str) -> str:
        """
        Adiciona job automático (prioridade normal)
        
        Args:
            obra_id: ID da obra
            scan_name: Nome do scan
            
        Returns:
            str: ID do job criado
        """
        job_id = f"auto_{int(time.time())}_{obra_id}"
        
        job = SchedulerJob(
            id=job_id,
            obra_id=obra_id,
            scan_name=scan_name,
            priority=JobPriority.NORMAL,
            status=JobStatus.PENDING,
            created_at=datetime.now()
        )
        
        self.job_queue.put(job)
        logger.info(f"Job automático adicionado: {job_id}")
        
        self._save_queue()
        return job_id
    
    def get_next_job(self) -> Optional[SchedulerJob]:
        """
        Obtém próximo job da fila (respeitando prioridade)
        
        Returns:
            SchedulerJob ou None se fila vazia
        """
        try:
            return self.job_queue.get_nowait()
        except Empty:
            return None
    
    def mark_job_completed(self, job: SchedulerJob) -> None:
        """
        Marca job como completado
        
        Args:
            job: Job a ser marcado como completado
        """
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now()
        self.completed_jobs.append(job)
        
        # Atualizar timestamp de fim do processo
        self.last_process_end = datetime.now()
        
        logger.info(f"Job completado: {job.id}")
        self._save_state()
    
    def mark_job_failed(self, job: SchedulerJob, error_message: str) -> None:
        """
        Marca job como falhado
        
        Args:
            job: Job que falhou
            error_message: Mensagem de erro
        """
        job.status = JobStatus.FAILED
        job.error_message = error_message
        job.completed_at = datetime.now()
        
        # Verificar se deve tentar novamente
        if job.retry_count < job.max_retries:
            job.retry_count += 1
            job.status = JobStatus.PENDING
            
            # Re-adicionar à fila com delay
            logger.info(f"Reagendando job {job.id} (tentativa {job.retry_count}/{job.max_retries})")
            
            # TODO: Implementar delay antes de re-adicionar
            self.job_queue.put(job)
        else:
            self.failed_jobs.append(job)
            logger.error(f"Job falhou definitivamente: {job.id} - {error_message}")
        
        self._save_state()
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retorna status completo do agendador
        
        Returns:
            Dict com informações de status
        """
        with self._lock:
            queue_size = self.job_queue.qsize()
            
            return {
                "state": self.state.value,
                "timer_remaining": self.timer_remaining,
                "last_process_end": self.last_process_end.isoformat() if self.last_process_end else None,
                "current_job": asdict(self.current_job) if self.current_job else None,
                "queue_size": queue_size,
                "completed_jobs_count": len(self.completed_jobs),
                "failed_jobs_count": len(self.failed_jobs),
                "next_execution": self._calculate_next_execution(),
                "config": asdict(self.config)
            }
    
    def _scheduler_loop(self) -> None:
        """Loop principal do agendador (executado em thread separada)"""
        logger.info("Iniciando loop do scheduler")
        
        while not self._stop_event.is_set():
            try:
                # Verificar se está pausado
                if self.state == SchedulerState.PAUSED:
                    self._pause_event.wait(timeout=1)
                    continue
                
                # Processar próximo job se disponível
                if self._should_process_job():
                    job = self.get_next_job()
                    if job:
                        self._process_job(job)
                
                # Atualizar timer
                self._update_timer()
                
                # Salvar estado periodicamente
                if int(time.time()) % self.config.save_state_interval == 0:
                    self._save_state()
                
                # Sleep pequeno para não sobrecarregar CPU
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Erro no loop do scheduler: {e}")
                time.sleep(5)  # Sleep maior em caso de erro
        
        logger.info("Loop do scheduler finalizado")
    
    def _should_process_job(self) -> bool:
        """
        Verifica se deve processar próximo job
        
        Returns:
            bool: True se deve processar
        """
        # Não processar se já está processando
        if self.state == SchedulerState.PROCESSING:
            return False
        
        # Sempre processar jobs manuais (alta prioridade)
        if not self.job_queue.empty():
            # Peek no próximo job sem removê-lo
            temp_queue = []
            next_job = None
            
            try:
                while not self.job_queue.empty():
                    job = self.job_queue.get_nowait()
                    if next_job is None:
                        next_job = job
                    temp_queue.append(job)
                
                # Recolocar jobs na fila
                for job in temp_queue:
                    self.job_queue.put(job)
                
                # Se é job manual, processar imediatamente
                if next_job and next_job.priority == JobPriority.HIGH:
                    return True
                
            except Empty:
                pass
        
        # Para jobs automáticos, verificar timer
        return self._is_timer_expired()
    
    def _is_timer_expired(self) -> bool:
        """
        Verifica se o timer expirou
        
        Returns:
            bool: True se timer expirou
        """
        if self.last_process_end is None:
            return True  # Primeira execução
        
        elapsed = datetime.now() - self.last_process_end
        return elapsed.total_seconds() >= self.config.timer_interval
    
    def _update_timer(self) -> None:
        """Atualiza o timer restante"""
        if self.last_process_end is None:
            self.timer_remaining = 0
            return
        
        elapsed = datetime.now() - self.last_process_end
        remaining = self.config.timer_interval - elapsed.total_seconds()
        self.timer_remaining = max(0, int(remaining))
    
    def _calculate_next_execution(self) -> Optional[str]:
        """
        Calcula próxima execução baseada no timer
        
        Returns:
            ISO timestamp da próxima execução ou None
        """
        if self.last_process_end is None:
            return None
        
        next_exec = self.last_process_end + timedelta(seconds=self.config.timer_interval)
        return next_exec.isoformat()
    
    def _process_job(self, job: SchedulerJob) -> None:
        """
        Processa um job
        
        Args:
            job: Job a ser processado
        """
        try:
            with self._lock:
                self.state = SchedulerState.PROCESSING
                self.current_job = job
                job.status = JobStatus.PROCESSING
                job.started_at = datetime.now()
            
            logger.info(f"Processando job: {job.id}")
            
            # TODO: Integrar com sistema de download/upload
            # Por enquanto, simular processamento
            self._simulate_processing(job)
            
            # Marcar como completado
            self.mark_job_completed(job)
            
        except Exception as e:
            logger.error(f"Erro ao processar job {job.id}: {e}")
            self.mark_job_failed(job, str(e))
        
        finally:
            with self._lock:
                self.state = SchedulerState.RUNNING
                self.current_job = None
    
    def _simulate_processing(self, job: SchedulerJob) -> None:
        """
        Simula processamento de job (para testes)
        
        Args:
            job: Job sendo processado
        """
        # Simular tempo de processamento variável
        import random
        processing_time = random.randint(5, 15)
        
        logger.info(f"Simulando processamento de {processing_time}s para job {job.id}")
        
        for i in range(processing_time):
            if self._stop_event.is_set():
                raise Exception("Processamento interrompido por stop")
            time.sleep(1)
        
        logger.info(f"Processamento simulado concluído para job {job.id}")
    
    def _save_state(self) -> None:
        """Salva estado atual em arquivo"""
        try:
            state_data = {
                "state": self.state.value,
                "timer_remaining": self.timer_remaining,
                "last_process_end": self.last_process_end.isoformat() if self.last_process_end else None,
                "current_job": asdict(self.current_job) if self.current_job else None,
                "completed_jobs": [asdict(job) for job in self.completed_jobs[-50:]],  # Manter últimos 50
                "failed_jobs": [asdict(job) for job in self.failed_jobs[-50:]],
                "config": asdict(self.config)
            }
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False, default=self._json_serializer)
                
        except Exception as e:
            logger.error(f"Erro ao salvar estado: {e}")
    
    def _save_queue(self) -> None:
        """Salva fila atual em arquivo"""
        try:
            # Extrair jobs da fila para salvar
            temp_jobs = []
            while not self.job_queue.empty():
                try:
                    job = self.job_queue.get_nowait()
                    temp_jobs.append(job)
                except Empty:
                    break
            
            # Salvar em arquivo
            queue_data = {
                "jobs": [asdict(job) for job in temp_jobs]
            }
            
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump(queue_data, f, indent=2, ensure_ascii=False, default=self._json_serializer)
            
            # Recolocar jobs na fila
            for job in temp_jobs:
                self.job_queue.put(job)
                
        except Exception as e:
            logger.error(f"Erro ao salvar fila: {e}")
    
    def _load_state(self) -> None:
        """Carrega estado salvo de arquivo"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                
                # Restaurar estado básico
                self.timer_remaining = state_data.get("timer_remaining", 0)
                
                if state_data.get("last_process_end"):
                    self.last_process_end = datetime.fromisoformat(state_data["last_process_end"])
                
                # Restaurar jobs completados/falhados
                for job_data in state_data.get("completed_jobs", []):
                    job = self._dict_to_job(job_data)
                    if job:
                        self.completed_jobs.append(job)
                
                for job_data in state_data.get("failed_jobs", []):
                    job = self._dict_to_job(job_data)
                    if job:
                        self.failed_jobs.append(job)
                
                logger.info("Estado carregado do arquivo")
            
            # Carregar fila
            if self.queue_file.exists():
                with open(self.queue_file, 'r', encoding='utf-8') as f:
                    queue_data = json.load(f)
                
                for job_data in queue_data.get("jobs", []):
                    job = self._dict_to_job(job_data)
                    if job and job.status == JobStatus.PENDING:
                        self.job_queue.put(job)
                
                logger.info("Fila carregada do arquivo")
                
        except Exception as e:
            logger.error(f"Erro ao carregar estado: {e}")
    
    def _dict_to_job(self, job_data: Dict) -> Optional[SchedulerJob]:
        """
        Converte dict para SchedulerJob
        
        Args:
            job_data: Dados do job em formato dict
            
        Returns:
            SchedulerJob ou None se erro
        """
        try:
            # Converter enums (tratar tanto string quanto valor do enum)
            priority_value = job_data["priority"]
            if isinstance(priority_value, str):
                # Se é string, tentar converter pelo nome do enum
                if priority_value in ["JobPriority.HIGH", "HIGH"]:
                    job_data["priority"] = JobPriority.HIGH
                elif priority_value in ["JobPriority.NORMAL", "NORMAL"]:  
                    job_data["priority"] = JobPriority.NORMAL
                else:
                    job_data["priority"] = JobPriority(int(priority_value))
            else:
                job_data["priority"] = JobPriority(priority_value)
            
            status_value = job_data["status"]
            if isinstance(status_value, str):
                # Se é string, tentar converter pelo nome do enum
                if status_value.startswith("JobStatus."):
                    status_value = status_value.replace("JobStatus.", "")
                job_data["status"] = JobStatus(status_value)
            else:
                job_data["status"] = JobStatus(status_value)
            
            # Converter datas
            job_data["created_at"] = datetime.fromisoformat(job_data["created_at"])
            
            if job_data.get("started_at"):
                job_data["started_at"] = datetime.fromisoformat(job_data["started_at"])
            
            if job_data.get("completed_at"):
                job_data["completed_at"] = datetime.fromisoformat(job_data["completed_at"])
            
            return SchedulerJob(**job_data)
            
        except Exception as e:
            logger.error(f"Erro ao converter dict para job: {e}")
            return None
    
    def _json_serializer(self, obj):
        """
        Serializer customizado para JSON
        
        Args:
            obj: Objeto a ser serializado
            
        Returns:
            Versão serializável do objeto
        """
        if isinstance(obj, (SchedulerState, JobPriority, JobStatus)):
            return obj.value
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return str(obj)


# Instância global para facilitar uso
scheduler_instance = None


def get_scheduler(data_dir: Path = None, config: SchedulerConfig = None) -> AutoUpdateScheduler:
    """
    Obtém instância global do scheduler (singleton)
    
    Args:
        data_dir: Diretório de dados
        config: Configuração personalizada
        
    Returns:
        AutoUpdateScheduler: Instância do scheduler
    """
    global scheduler_instance
    
    if scheduler_instance is None:
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data"
        
        scheduler_instance = AutoUpdateScheduler(data_dir, config)
    
    return scheduler_instance


if __name__ == "__main__":
    # Exemplo de uso
    import sys
    from pathlib import Path
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Criar scheduler
    data_dir = Path(__file__).parent.parent.parent / "data"
    scheduler = AutoUpdateScheduler(data_dir)
    
    # Adicionar alguns jobs de teste
    scheduler.add_manual_job("obra_1", "mangayabu")
    scheduler.add_auto_job("obra_2", "scan1")
    scheduler.add_auto_job("obra_3", "scan2")
    
    print("Status inicial:")
    print(json.dumps(scheduler.get_status(), indent=2, default=str))
    
    # Iniciar scheduler
    print("\nIniciando scheduler...")
    scheduler.start()
    
    try:
        # Rodar por um tempo
        time.sleep(30)
        
        print("\nStatus após 30s:")
        print(json.dumps(scheduler.get_status(), indent=2, default=str))
        
    except KeyboardInterrupt:
        print("\nParando scheduler...")
    
    finally:
        scheduler.stop()
        print("Scheduler parado.")