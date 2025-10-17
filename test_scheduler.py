"""
Teste do AutoUpdateScheduler
===========================

Script de teste para validar o funcionamento do sistema de agendamento
inteligente com timer pós-processo.
"""

import sys
import time
import json
import logging
from pathlib import Path

# Adicionar diretório src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from auto_uploader.scheduler import AutoUpdateScheduler, SchedulerConfig


def setup_logging():
    """Configura logging para os testes"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('scheduler_test.log')
        ]
    )


def test_scheduler_basic():
    """Teste básico do scheduler"""
    print("=== Teste Básico do AutoUpdateScheduler ===")
    
    # Criar configuração de teste (timer mais curto)
    config = SchedulerConfig(
        timer_interval=10,  # 10 segundos para teste
        max_retries=2,
        save_state_interval=5
    )
    
    # Criar scheduler
    data_dir = Path(__file__).parent / "test_data"
    data_dir.mkdir(exist_ok=True)
    
    scheduler = AutoUpdateScheduler(data_dir, config)
    
    try:
        # Testar adição de jobs
        print("\n1. Adicionando jobs de teste...")
        manual_id = scheduler.add_manual_job("obra_manual_1", "mangayabu")
        auto_id1 = scheduler.add_auto_job("obra_auto_1", "scan1")
        auto_id2 = scheduler.add_auto_job("obra_auto_2", "scan2")
        
        print(f"   - Job manual: {manual_id}")
        print(f"   - Job auto 1: {auto_id1}")
        print(f"   - Job auto 2: {auto_id2}")
        
        # Verificar status inicial
        print("\n2. Status inicial:")
        status = scheduler.get_status()
        print(f"   - Estado: {status['state']}")
        print(f"   - Fila: {status['queue_size']} jobs")
        print(f"   - Timer: {status['timer_remaining']}s")
        
        # Iniciar scheduler
        print("\n3. Iniciando scheduler...")
        if scheduler.start():
            print("   ✓ Scheduler iniciado com sucesso")
        else:
            print("   ✗ Falha ao iniciar scheduler")
            return False
        
        # Monitorar por 30 segundos
        print("\n4. Monitorando execução por 30 segundos...")
        for i in range(30):
            status = scheduler.get_status()
            current_job = status.get('current_job')
            job_info = f" (processando {current_job['id']})" if current_job else ""
            
            print(f"   [{i+1:2d}s] Estado: {status['state']}, "
                  f"Fila: {status['queue_size']}, "
                  f"Timer: {status['timer_remaining']}s{job_info}")
            
            time.sleep(1)
        
        # Status final
        print("\n5. Status final:")
        status = scheduler.get_status()
        print(f"   - Estado: {status['state']}")
        print(f"   - Fila restante: {status['queue_size']} jobs")
        print(f"   - Jobs completados: {status['completed_jobs_count']}")
        print(f"   - Jobs falhados: {status['failed_jobs_count']}")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Erro durante teste: {e}")
        return False
    
    finally:
        print("\n6. Parando scheduler...")
        if scheduler.stop():
            print("   ✓ Scheduler parado com sucesso")
        else:
            print("   ✗ Falha ao parar scheduler")


def test_scheduler_controls():
    """Teste dos controles do scheduler (pause/resume)"""
    print("\n=== Teste dos Controles do Scheduler ===")
    
    config = SchedulerConfig(timer_interval=5)
    data_dir = Path(__file__).parent / "test_data_controls"
    data_dir.mkdir(exist_ok=True)
    
    scheduler = AutoUpdateScheduler(data_dir, config)
    
    try:
        # Adicionar jobs
        scheduler.add_auto_job("obra_controle_1", "teste")
        scheduler.add_auto_job("obra_controle_2", "teste")
        
        # Iniciar
        print("\n1. Iniciando scheduler...")
        scheduler.start()
        
        # Rodar por 5 segundos
        print("\n2. Executando por 5 segundos...")
        time.sleep(5)
        
        # Pausar
        print("\n3. Pausando scheduler...")
        if scheduler.pause():
            print("   ✓ Pausado com sucesso")
        
        status = scheduler.get_status()
        print(f"   Estado: {status['state']}")
        
        # Aguardar 3 segundos pausado
        print("\n4. Aguardando 3 segundos pausado...")
        time.sleep(3)
        
        # Resumir
        print("\n5. Resumindo scheduler...")
        if scheduler.resume():
            print("   ✓ Resumido com sucesso")
        
        # Rodar mais 5 segundos
        print("\n6. Executando por mais 5 segundos...")
        time.sleep(5)
        
        # Status final
        status = scheduler.get_status()
        print(f"\n7. Status final: {status['state']}")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Erro durante teste de controles: {e}")
        return False
    
    finally:
        scheduler.stop()


def test_scheduler_persistence():
    """Teste da persistência de estado"""
    print("\n=== Teste de Persistência ===")
    
    data_dir = Path(__file__).parent / "test_data_persistence"
    data_dir.mkdir(exist_ok=True)
    
    # Primeiro scheduler
    config = SchedulerConfig(timer_interval=60)
    scheduler1 = AutoUpdateScheduler(data_dir, config)
    
    try:
        # Adicionar jobs e marcar alguns como completados
        scheduler1.add_manual_job("obra_persist_1", "teste")
        scheduler1.add_auto_job("obra_persist_2", "teste")
        
        # Simular job completado manualmente
        from auto_uploader.scheduler import SchedulerJob, JobPriority, JobStatus
        from datetime import datetime
        
        completed_job = SchedulerJob(
            id="completed_test",
            obra_id="obra_completed",
            scan_name="teste",
            priority=JobPriority.NORMAL,
            status=JobStatus.COMPLETED,
            created_at=datetime.now(),
            completed_at=datetime.now()
        )
        
        scheduler1.completed_jobs.append(completed_job)
        scheduler1._save_state()
        
        print("1. Estado salvo pelo primeiro scheduler")
        
        # Criar segundo scheduler (deve carregar estado)
        scheduler2 = AutoUpdateScheduler(data_dir, config)
        
        status = scheduler2.get_status()
        print(f"2. Estado carregado pelo segundo scheduler:")
        print(f"   - Fila: {status['queue_size']} jobs")
        print(f"   - Completados: {status['completed_jobs_count']}")
        
        return status['queue_size'] > 0 and status['completed_jobs_count'] > 0
        
    except Exception as e:
        print(f"   ✗ Erro durante teste de persistência: {e}")
        return False


if __name__ == "__main__":
    setup_logging()
    
    print("🚀 Iniciando testes do AutoUpdateScheduler")
    print("=" * 50)
    
    # Executar testes
    tests = [
        test_scheduler_basic,
        test_scheduler_controls,
        test_scheduler_persistence
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
            print(f"✓ {test_func.__name__}: {'SUCESSO' if result else 'FALHA'}")
        except Exception as e:
            results.append(False)
            print(f"✗ {test_func.__name__}: ERRO - {e}")
        
        print("-" * 50)
    
    # Resultado final
    total_tests = len(tests)
    passed_tests = sum(results)
    
    print(f"\n📊 RESULTADO FINAL: {passed_tests}/{total_tests} testes passaram")
    
    if passed_tests == total_tests:
        print("🎉 Todos os testes passaram! AutoUpdateScheduler está funcionando corretamente.")
    else:
        print("⚠️  Alguns testes falharam. Verifique os logs para mais detalhes.")
    
    sys.exit(0 if passed_tests == total_tests else 1)