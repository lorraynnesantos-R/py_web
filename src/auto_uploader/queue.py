"""
Sistema de Fila Unificada - UnifiedQueue
========================================

Sistema dedicado de fila que unifica processos automáticos e manuais com
priorização avançada, estados detalhados e métricas de performance.

Este sistema complementa o AutoUpdateScheduler, fornecendo um gerenciamento
mais granular de jobs com persistência e monitoramento avançado.

Features:
- Priority queue com 3 níveis (URGENT, HIGH, NORMAL)
- Estados detalhados de jobs (PENDING, PROCESSING, COMPLETED, FAILED)
- Persistência entre reinicializações
- Métricas de performance avançadas
- Interface para monitoramento web
- Retry automático com backoff
"""

import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import threading
from queue import PriorityQueue, Empty
from collections import defaultdict, deque

# Configuração de logging
logger = logging.getLogger(__name__)


class QueuePriority(Enum):
    """Níveis de prioridade na fila"""
    URGENT = 1     # Manual imediato (falhas críticas, testes)
    HIGH = 2       # Manual normal (solicitações do usuário)
    NORMAL = 3     # Auto-update (processamento automático)


class JobState(Enum):
    """Estados dos jobs na fila"""
    PENDING = "pending"        # Aguardando processamento
    PROCESSING = "processing"  # Sendo processado atualmente
    COMPLETED = "completed"    # Concluído com sucesso
    FAILED = "failed"         # Falhou (pode ter retries restantes)
    CANCELLED = "cancelled"    # Cancelado pelo usuário
    EXPIRED = "expired"        # Expirou por timeout


@dataclass
class QueueJob:
    """Representa um job na fila unificada"""
    id: str
    obra_id: str
    scan_name: str
    priority: QueuePriority
    state: JobState
    created_at: datetime
    scheduled_for: Optional[datetime] = None  # Para jobs agendados
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300  # 5 minutos
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def __lt__(self, other):
        """Comparação para PriorityQueue (menor valor = maior prioridade)"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        # Se prioridade igual, mais antigo tem prioridade
        return self.created_at < other.created_at


@dataclass
class QueueMetrics:
    """Métricas de performance da fila"""
    total_jobs: int = 0
    pending_jobs: int = 0
    processing_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    cancelled_jobs: int = 0
    expired_jobs: int = 0
    average_processing_time: float = 0.0
    success_rate: float = 0.0
    jobs_per_hour: float = 0.0
    retry_rate: float = 0.0
    priority_distribution: Dict[str, int] = None
    scan_distribution: Dict[str, int] = None
    
    def __post_init__(self):
        if self.priority_distribution is None:
            self.priority_distribution = {}
        if self.scan_distribution is None:
            self.scan_distribution = {}


class UnifiedQueue:
    """
    Sistema de fila unificada para auto-update e manual
    
    Features principais:
    - Priority queue com 3 níveis (URGENT > HIGH > NORMAL)
    - Estados detalhados de jobs
    - Persistência entre reinicializações
    - Métricas de performance
    - Retry automático com backoff
    - Monitoramento em tempo real
    - Interface web para gerenciamento
    """
    
    def __init__(self, data_dir: Path, max_concurrent_jobs: int = 1):
        self.data_dir = Path(data_dir)
        self.max_concurrent_jobs = max_concurrent_jobs
        
        # Filas e controle
        self.job_queue = PriorityQueue()
        self.active_jobs = {}  # job_id -> QueueJob
        self.job_history = {}  # job_id -> QueueJob (últimos 1000)
        self.max_history = 1000
        
        # Métricas e estatísticas
        self.metrics = QueueMetrics()
        self.processing_times = deque(maxlen=100)  # Últimos 100 tempos
        self.hourly_stats = defaultdict(int)  # jobs por hora
        
        # Threading e controle
        self._lock = threading.Lock()
        self._running = False
        self._processor_thread = None
        self._stop_event = threading.Event()
        
        # Arquivos de persistência
        self.queue_file = self.data_dir / "queue_state.json"
        self.metrics_file = self.data_dir / "queue_metrics.json"
        self.history_file = self.data_dir / "queue_history.json"
        
        # Criar diretório se não existir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Carregar estado persistido
        self._load_state()
        
        logger.info("UnifiedQueue inicializada")
    
    def start_processing(self) -> bool:
        """
        Inicia o processamento automático da fila
        
        Returns:
            bool: True se iniciado com sucesso
        """
        try:
            with self._lock:
                if self._running:
                    logger.warning("UnifiedQueue já está processando")
                    return False
                
                self._running = True
                self._stop_event.clear()
                
                self._processor_thread = threading.Thread(
                    target=self._process_loop,
                    daemon=True,
                    name="UnifiedQueueProcessor"
                )
                self._processor_thread.start()
                
                logger.info("UnifiedQueue processamento iniciado")
                return True
                
        except Exception as e:
            logger.error(f"Erro ao iniciar processamento da fila: {e}")
            return False
    
    def stop_processing(self) -> bool:
        """
        Para o processamento automático da fila
        
        Returns:
            bool: True se parado com sucesso
        """
        try:
            with self._lock:
                if not self._running:
                    logger.warning("UnifiedQueue não está processando")
                    return False
                
                self._running = False
                self._stop_event.set()
                
                # Aguardar thread terminar
                if self._processor_thread and self._processor_thread.is_alive():
                    self._processor_thread.join(timeout=5)
                
                logger.info("UnifiedQueue processamento parado")
                self._save_state()
                return True
                
        except Exception as e:
            logger.error(f"Erro ao parar processamento da fila: {e}")
            return False
    
    def add_manual_job(
        self, 
        obra_id: str, 
        scan_name: str, 
        priority: str = 'HIGH',
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Adiciona job manual à fila
        
        Args:
            obra_id: ID da obra
            scan_name: Nome do scan
            priority: Prioridade ('URGENT' ou 'HIGH')
            metadata: Metadados adicionais
            
        Returns:
            str: ID do job criado
        """
        priority_enum = QueuePriority.URGENT if priority == 'URGENT' else QueuePriority.HIGH
        
        job_id = f"manual_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        job = QueueJob(
            id=job_id,
            obra_id=obra_id,
            scan_name=scan_name,
            priority=priority_enum,
            state=JobState.PENDING,
            created_at=datetime.now(),
            metadata=metadata or {}
        )
        
        self.job_queue.put(job)
        self._update_metrics_on_add(job)
        
        logger.info(f"Job manual adicionado: {job_id} (prioridade: {priority})")
        self._save_state()
        
        return job_id
    
    def add_auto_job(
        self, 
        obra_id: str, 
        scan_name: str,
        scheduled_for: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Adiciona job automático à fila
        
        Args:
            obra_id: ID da obra
            scan_name: Nome do scan
            scheduled_for: Quando deve ser processado (None = imediatamente)
            metadata: Metadados adicionais
            
        Returns:
            str: ID do job criado
        """
        job_id = f"auto_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        job = QueueJob(
            id=job_id,
            obra_id=obra_id,
            scan_name=scan_name,
            priority=QueuePriority.NORMAL,
            state=JobState.PENDING,
            created_at=datetime.now(),
            scheduled_for=scheduled_for,
            metadata=metadata or {}
        )
        
        self.job_queue.put(job)
        self._update_metrics_on_add(job)
        
        logger.info(f"Job automático adicionado: {job_id}")
        self._save_state()
        
        return job_id
    
    def get_next_job(self) -> Optional[QueueJob]:
        """
        Obtém próximo job da fila (para processamento externo)
        
        Returns:
            QueueJob ou None se fila vazia
        """
        try:
            job = self.job_queue.get_nowait()
            
            # Verificar se job está agendado para o futuro
            if job.scheduled_for and datetime.now() < job.scheduled_for:
                # Recolocar na fila
                self.job_queue.put(job)
                return None
            
            # Marcar como processando
            job.state = JobState.PROCESSING
            job.started_at = datetime.now()
            
            with self._lock:
                self.active_jobs[job.id] = job
            
            self._update_metrics_on_start(job)
            logger.info(f"Job obtido para processamento: {job.id}")
            
            return job
            
        except Empty:
            return None
    
    def mark_completed(self, job_id: str, result_metadata: Optional[Dict] = None) -> bool:
        """
        Marca job como completado
        
        Args:
            job_id: ID do job
            result_metadata: Metadados do resultado
            
        Returns:
            bool: True se marcado com sucesso
        """
        try:
            with self._lock:
                if job_id not in self.active_jobs:
                    logger.warning(f"Job {job_id} não está ativo")
                    return False
                
                job = self.active_jobs.pop(job_id)
                job.state = JobState.COMPLETED
                job.completed_at = datetime.now()
                
                if result_metadata:
                    job.metadata.update(result_metadata)
                
                # Adicionar ao histórico
                self._add_to_history(job)
                
                # Atualizar métricas
                self._update_metrics_on_complete(job)
                
                logger.info(f"Job completado: {job_id}")
                self._save_state()
                
                return True
                
        except Exception as e:
            logger.error(f"Erro ao marcar job como completado: {e}")
            return False
    
    def mark_failed(self, job_id: str, error_message: str) -> bool:
        """
        Marca job como falhado
        
        Args:
            job_id: ID do job
            error_message: Mensagem de erro
            
        Returns:
            bool: True se marcado com sucesso
        """
        try:
            with self._lock:
                if job_id not in self.active_jobs:
                    logger.warning(f"Job {job_id} não está ativo")
                    return False
                
                job = self.active_jobs.pop(job_id)
                job.error_message = error_message
                
                # Verificar se deve tentar novamente
                if job.retry_count < job.max_retries:
                    job.retry_count += 1
                    job.state = JobState.PENDING
                    job.started_at = None
                    
                    # Reagendar com backoff exponencial
                    delay_seconds = 2 ** job.retry_count * 60  # 2, 4, 8 minutos
                    job.scheduled_for = datetime.now() + timedelta(seconds=delay_seconds)
                    
                    # Recolocar na fila
                    self.job_queue.put(job)
                    
                    logger.info(f"Job {job_id} reagendado (tentativa {job.retry_count}/{job.max_retries})")
                else:
                    # Falhou definitivamente
                    job.state = JobState.FAILED
                    job.completed_at = datetime.now()
                    
                    # Adicionar ao histórico
                    self._add_to_history(job)
                    
                    logger.error(f"Job falhou definitivamente: {job_id} - {error_message}")
                
                # Atualizar métricas
                self._update_metrics_on_fail(job)
                self._save_state()
                
                return True
                
        except Exception as e:
            logger.error(f"Erro ao marcar job como falhado: {e}")
            return False
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancela um job
        
        Args:
            job_id: ID do job a cancelar
            
        Returns:
            bool: True se cancelado com sucesso
        """
        try:
            with self._lock:
                # Verificar se está ativo
                if job_id in self.active_jobs:
                    job = self.active_jobs.pop(job_id)
                    job.state = JobState.CANCELLED
                    job.completed_at = datetime.now()
                    self._add_to_history(job)
                    logger.info(f"Job ativo cancelado: {job_id}")
                    return True
                
                # Procurar na fila
                temp_jobs = []
                found = False
                
                while not self.job_queue.empty():
                    try:
                        job = self.job_queue.get_nowait()
                        if job.id == job_id:
                            job.state = JobState.CANCELLED
                            job.completed_at = datetime.now()
                            self._add_to_history(job)
                            found = True
                            logger.info(f"Job na fila cancelado: {job_id}")
                        else:
                            temp_jobs.append(job)
                    except Empty:
                        break
                
                # Recolocar jobs não cancelados
                for job in temp_jobs:
                    self.job_queue.put(job)
                
                if found:
                    self._update_metrics()
                    self._save_state()
                
                return found
                
        except Exception as e:
            logger.error(f"Erro ao cancelar job: {e}")
            return False
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Retorna status completo da fila
        
        Returns:
            Dict com informações de status
        """
        with self._lock:
            # Contar jobs na fila por estado
            queue_jobs = []
            temp_jobs = []
            
            while not self.job_queue.empty():
                try:
                    job = self.job_queue.get_nowait()
                    queue_jobs.append(job)
                    temp_jobs.append(job)
                except Empty:
                    break
            
            # Recolocar jobs na fila
            for job in temp_jobs:
                self.job_queue.put(job)
            
            # Estatísticas por prioridade
            priority_counts = defaultdict(int)
            for job in queue_jobs:
                priority_counts[job.priority.name] += 1
            
            # Estatísticas por scan
            scan_counts = defaultdict(int)
            for job in queue_jobs:
                scan_counts[job.scan_name] += 1
            
            return {
                "total_queue_size": len(queue_jobs),
                "active_jobs": len(self.active_jobs),
                "priority_counts": dict(priority_counts),
                "scan_counts": dict(scan_counts),
                "metrics": asdict(self.metrics),
                "active_job_details": [asdict(job) for job in self.active_jobs.values()],
                "next_jobs": [asdict(job) for job in queue_jobs[:5]],  # Próximos 5
                "is_processing": self._running
            }
    
    def get_jobs_by_status(self, status: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Obtém jobs por status
        
        Args:
            status: Status dos jobs ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')
            limit: Limite de jobs retornados
            
        Returns:
            Lista de jobs com o status especificado
        """
        jobs = []
        
        try:
            with self._lock:
                if status == 'PENDING':
                    # Para jobs pendentes, retornar lista vazia por enquanto
                    # Evitar manipular a PriorityQueue diretamente
                    jobs = []
                    
                elif status == 'PROCESSING':
                    # Jobs ativos
                    jobs = [asdict(job) for job in list(self.active_jobs.values())[:limit]]
                    
                elif status in ['COMPLETED', 'FAILED']:
                    # Jobs no histórico
                    history_jobs = []
                    for job in self.job_history.values():
                        if hasattr(job, 'status') and hasattr(job.status, 'name') and job.status.name == status:
                            history_jobs.append(job)
                    
                    # Ordenar por timestamp mais recente
                    history_jobs.sort(key=lambda x: x.updated_at if hasattr(x, 'updated_at') else datetime.now(), reverse=True)
                    jobs = [asdict(job) for job in history_jobs[:limit]]
        except Exception as e:
            logger.error(f"Erro ao obter jobs por status {status}: {e}")
            jobs = []
        
        return jobs
    
    def get_recent_completed_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Obtém jobs completados recentemente
        
        Args:
            limit: Limite de jobs retornados
            
        Returns:
            Lista de jobs completados recentemente
        """
        return self.get_jobs_by_status('COMPLETED', limit)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Obtém estatísticas da fila
        
        Returns:
            Dict com estatísticas detalhadas
        """
        try:
            with self._lock:
                # Calcular tempo médio de processamento
                avg_processing_time = 0
                if self.processing_times:
                    avg_processing_time = sum(self.processing_times) / len(self.processing_times)
                
                # Estatísticas de jobs por hora
                current_hour = datetime.now().hour
                jobs_this_hour = self.hourly_stats.get(current_hour, 0)
                
                return {
                    'pending_count': self.job_queue.qsize(),
                    'processing_count': len(self.active_jobs),
                    'completed_count': getattr(self.metrics, 'completed_jobs', 0),
                    'failed_count': getattr(self.metrics, 'failed_jobs', 0),
                    'average_processing_time': avg_processing_time,
                    'jobs_this_hour': jobs_this_hour,
                    'total_jobs_processed': getattr(self.metrics, 'completed_jobs', 0) + getattr(self.metrics, 'failed_jobs', 0),
                    'success_rate': 0 if (getattr(self.metrics, 'completed_jobs', 0) + getattr(self.metrics, 'failed_jobs', 0)) == 0 else (
                        getattr(self.metrics, 'completed_jobs', 0) / 
                        max(1, getattr(self.metrics, 'completed_jobs', 0) + getattr(self.metrics, 'failed_jobs', 0))
                    ) * 100
                }
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {
                'pending_count': 0,
                'processing_count': 0,
                'completed_count': 0,
                'failed_count': 0,
                'average_processing_time': 0,
                'jobs_this_hour': 0,
                'total_jobs_processed': 0,
                'success_rate': 0
            }
    
    def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém detalhes de um job específico
        
        Args:
            job_id: ID do job
            
        Returns:
            Dict com detalhes do job ou None se não encontrado
        """
        # Verificar jobs ativos
        if job_id in self.active_jobs:
            return asdict(self.active_jobs[job_id])
        
        # Verificar histórico
        if job_id in self.job_history:
            return asdict(self.job_history[job_id])
        
        # Procurar na fila
        temp_jobs = []
        found_job = None
        
        while not self.job_queue.empty():
            try:
                job = self.job_queue.get_nowait()
                if job.id == job_id:
                    found_job = job
                temp_jobs.append(job)
            except Empty:
                break
        
        # Recolocar jobs na fila
        for job in temp_jobs:
            self.job_queue.put(job)
        
        return asdict(found_job) if found_job else None
    
    def cleanup_expired_jobs(self) -> int:
        """
        Remove jobs expirados da fila
        
        Returns:
            int: Número de jobs removidos
        """
        current_time = datetime.now()
        expired_count = 0
        temp_jobs = []
        
        while not self.job_queue.empty():
            try:
                job = self.job_queue.get_nowait()
                
                # Verificar se job expirou
                if job.started_at and (current_time - job.started_at).total_seconds() > job.timeout_seconds:
                    job.state = JobState.EXPIRED
                    job.completed_at = current_time
                    self._add_to_history(job)
                    expired_count += 1
                    logger.warning(f"Job expirado removido: {job.id}")
                else:
                    temp_jobs.append(job)
                    
            except Empty:
                break
        
        # Recolocar jobs válidos
        for job in temp_jobs:
            self.job_queue.put(job)
        
        if expired_count > 0:
            self._update_metrics()
            self._save_state()
            logger.info(f"Removidos {expired_count} jobs expirados")
        
        return expired_count
    
    def _process_loop(self):
        """Loop de processamento automático (interno)"""
        logger.info("Iniciando loop de processamento da fila")
        
        while not self._stop_event.is_set():
            try:
                # Limpar jobs expirados periodicamente
                if int(time.time()) % 300 == 0:  # A cada 5 minutos
                    self.cleanup_expired_jobs()
                
                # Verificar se há espaço para novos jobs
                if len(self.active_jobs) >= self.max_concurrent_jobs:
                    time.sleep(1)
                    continue
                
                # Obter próximo job
                job = self.get_next_job()
                if job is None:
                    time.sleep(1)
                    continue
                
                # Simular processamento (em implementação real, seria chamada externa)
                self._simulate_job_processing(job)
                
            except Exception as e:
                logger.error(f"Erro no loop de processamento: {e}")
                time.sleep(5)
        
        logger.info("Loop de processamento da fila finalizado")
    
    def _simulate_job_processing(self, job: QueueJob):
        """
        Simula processamento de job (para desenvolvimento/testes)
        
        Args:
            job: Job a ser processado
        """
        # Simular tempo variável de processamento
        import random
        processing_time = random.randint(3, 10)
        
        logger.info(f"Simulando processamento de {processing_time}s para job {job.id}")
        
        try:
            for i in range(processing_time):
                if self._stop_event.is_set():
                    self.mark_failed(job.id, "Processamento interrompido")
                    return
                time.sleep(1)
            
            # Simular chance de falha (10%)
            if random.random() < 0.1:
                self.mark_failed(job.id, "Erro simulado de processamento")
            else:
                self.mark_completed(job.id, {"simulated": True, "processing_time": processing_time})
            
        except Exception as e:
            self.mark_failed(job.id, f"Erro na simulação: {e}")
    
    def _update_metrics_on_add(self, job: QueueJob):
        """Atualiza métricas quando job é adicionado"""
        self.metrics.total_jobs += 1
        self.metrics.pending_jobs += 1
        self.metrics.priority_distribution[job.priority.name] = \
            self.metrics.priority_distribution.get(job.priority.name, 0) + 1
        self.metrics.scan_distribution[job.scan_name] = \
            self.metrics.scan_distribution.get(job.scan_name, 0) + 1
    
    def _update_metrics_on_start(self, job: QueueJob):
        """Atualiza métricas quando job inicia"""
        self.metrics.pending_jobs -= 1
        self.metrics.processing_jobs += 1
    
    def _update_metrics_on_complete(self, job: QueueJob):
        """Atualiza métricas quando job completa"""
        self.metrics.processing_jobs -= 1
        self.metrics.completed_jobs += 1
        
        # Calcular tempo de processamento
        if job.started_at and job.completed_at:
            processing_time = (job.completed_at - job.started_at).total_seconds()
            self.processing_times.append(processing_time)
            
            # Atualizar média
            if self.processing_times:
                self.metrics.average_processing_time = sum(self.processing_times) / len(self.processing_times)
        
        # Atualizar taxa de sucesso
        total_finished = self.metrics.completed_jobs + self.metrics.failed_jobs
        if total_finished > 0:
            self.metrics.success_rate = self.metrics.completed_jobs / total_finished
        
        # Atualizar jobs por hora
        current_hour = datetime.now().strftime("%Y-%m-%d_%H")
        self.hourly_stats[current_hour] += 1
        
        # Calcular média das últimas 24 horas
        recent_hours = list(self.hourly_stats.keys())[-24:]
        if recent_hours:
            self.metrics.jobs_per_hour = sum(self.hourly_stats[h] for h in recent_hours) / len(recent_hours)
    
    def _update_metrics_on_fail(self, job: QueueJob):
        """Atualiza métricas quando job falha"""
        if job.state == JobState.FAILED:
            self.metrics.processing_jobs -= 1
            self.metrics.failed_jobs += 1
            
            # Atualizar taxa de retry
            total_with_retries = sum(1 for j in self.job_history.values() if j.retry_count > 0)
            if self.metrics.total_jobs > 0:
                self.metrics.retry_rate = total_with_retries / self.metrics.total_jobs
    
    def _update_metrics(self):
        """Atualiza todas as métricas"""
        # Recontagem geral (chamado após operações que podem afetar contadores)
        pass
    
    def _add_to_history(self, job: QueueJob):
        """Adiciona job ao histórico"""
        self.job_history[job.id] = job
        
        # Manter apenas os últimos N jobs
        if len(self.job_history) > self.max_history:
            # Remover jobs mais antigos
            sorted_jobs = sorted(self.job_history.values(), key=lambda j: j.created_at)
            jobs_to_remove = sorted_jobs[:len(self.job_history) - self.max_history]
            
            for job_to_remove in jobs_to_remove:
                del self.job_history[job_to_remove.id]
    
    def _save_state(self):
        """Salva estado atual em arquivos"""
        try:
            # Salvar estado da fila
            queue_jobs = []
            temp_jobs = []
            
            while not self.job_queue.empty():
                try:
                    job = self.job_queue.get_nowait()
                    queue_jobs.append(job)
                    temp_jobs.append(job)
                except Empty:
                    break
            
            # Recolocar jobs na fila
            for job in temp_jobs:
                self.job_queue.put(job)
            
            # Preparar dados para salvamento
            queue_data = {
                "queue_jobs": [asdict(job) for job in queue_jobs],
                "active_jobs": [asdict(job) for job in self.active_jobs.values()],
                "timestamp": datetime.now().isoformat()
            }
            
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump(queue_data, f, indent=2, ensure_ascii=False, default=str)
            
            # Salvar métricas
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(self.metrics), f, indent=2, ensure_ascii=False)
            
            # Salvar histórico (últimos 100 para não ficar muito grande)
            recent_history = dict(list(self.job_history.items())[-100:])
            history_data = {
                "jobs": [asdict(job) for job in recent_history.values()],
                "timestamp": datetime.now().isoformat()
            }
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2, ensure_ascii=False, default=str)
                
        except Exception as e:
            logger.error(f"Erro ao salvar estado da fila: {e}")
    
    def _load_state(self):
        """Carrega estado salvo de arquivos"""
        try:
            # Carregar estado da fila
            if self.queue_file.exists():
                with open(self.queue_file, 'r', encoding='utf-8') as f:
                    queue_data = json.load(f)
                
                # Restaurar jobs da fila
                for job_data in queue_data.get("queue_jobs", []):
                    job = self._dict_to_job(job_data)
                    if job and job.state == JobState.PENDING:
                        self.job_queue.put(job)
                
                # Restaurar jobs ativos (como pendentes, pois processo anterior parou)
                for job_data in queue_data.get("active_jobs", []):
                    job = self._dict_to_job(job_data)
                    if job:
                        job.state = JobState.PENDING
                        job.started_at = None
                        self.job_queue.put(job)
                
                logger.info("Estado da fila carregado")
            
            # Carregar métricas
            if self.metrics_file.exists():
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    metrics_data = json.load(f)
                    # Restaurar métricas básicas (algumas serão recalculadas)
                    self.metrics.total_jobs = metrics_data.get("total_jobs", 0)
                    self.metrics.completed_jobs = metrics_data.get("completed_jobs", 0)
                    self.metrics.failed_jobs = metrics_data.get("failed_jobs", 0)
                
                logger.info("Métricas carregadas")
            
            # Carregar histórico
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                
                for job_data in history_data.get("jobs", []):
                    job = self._dict_to_job(job_data)
                    if job:
                        self.job_history[job.id] = job
                
                logger.info("Histórico da fila carregado")
                
        except Exception as e:
            logger.error(f"Erro ao carregar estado da fila: {e}")
    
    def _dict_to_job(self, job_data: Dict) -> Optional[QueueJob]:
        """
        Converte dict para QueueJob
        
        Args:
            job_data: Dados do job em formato dict
            
        Returns:
            QueueJob ou None se erro
        """
        try:
            # Converter enums
            if isinstance(job_data["priority"], str):
                if job_data["priority"].startswith("QueuePriority."):
                    job_data["priority"] = job_data["priority"].replace("QueuePriority.", "")
                job_data["priority"] = QueuePriority[job_data["priority"]]
            else:
                job_data["priority"] = QueuePriority(job_data["priority"])
            
            if isinstance(job_data["state"], str):
                if job_data["state"].startswith("JobState."):
                    job_data["state"] = job_data["state"].replace("JobState.", "")
                job_data["state"] = JobState[job_data["state"]]
            else:
                job_data["state"] = JobState(job_data["state"])
            
            # Converter datas
            job_data["created_at"] = datetime.fromisoformat(job_data["created_at"])
            
            if job_data.get("scheduled_for"):
                job_data["scheduled_for"] = datetime.fromisoformat(job_data["scheduled_for"])
            
            if job_data.get("started_at"):
                job_data["started_at"] = datetime.fromisoformat(job_data["started_at"])
            
            if job_data.get("completed_at"):
                job_data["completed_at"] = datetime.fromisoformat(job_data["completed_at"])
            
            return QueueJob(**job_data)
            
        except Exception as e:
            logger.error(f"Erro ao converter dict para job: {e}")
            return None


# Instância global para facilitar uso
queue_instance = None


def get_unified_queue(data_dir: Path = None, max_concurrent_jobs: int = 1) -> UnifiedQueue:
    """
    Obtém instância global da fila unificada (singleton)
    
    Args:
        data_dir: Diretório de dados
        max_concurrent_jobs: Número máximo de jobs simultâneos
        
    Returns:
        UnifiedQueue: Instância da fila
    """
    global queue_instance
    
    if queue_instance is None:
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data"
        
        queue_instance = UnifiedQueue(data_dir, max_concurrent_jobs)
    
    return queue_instance


if __name__ == "__main__":
    # Exemplo de uso
    import sys
    from pathlib import Path
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Criar fila
    data_dir = Path(__file__).parent.parent.parent / "data"
    queue = UnifiedQueue(data_dir)
    
    # Adicionar alguns jobs de teste
    manual_id = queue.add_manual_job("obra_manual_1", "mangayabu", "URGENT")
    auto_id1 = queue.add_auto_job("obra_auto_1", "scan1")
    auto_id2 = queue.add_auto_job("obra_auto_2", "scan2")
    
    print("Status inicial:")
    status = queue.get_queue_status()
    print(json.dumps(status, indent=2, default=str))
    
    # Iniciar processamento
    print("\nIniciando processamento...")
    queue.start_processing()
    
    try:
        # Rodar por um tempo
        time.sleep(30)
        
        print("\nStatus após 30s:")
        status = queue.get_queue_status()
        print(json.dumps(status, indent=2, default=str))
        
    except KeyboardInterrupt:
        print("\nParando fila...")
    
    finally:
        queue.stop_processing()
        print("Fila parada.")