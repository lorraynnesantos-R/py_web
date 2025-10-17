"""
Teste da UnifiedQueue
====================

Script de teste para validar o funcionamento do sistema de fila unificada
com priority queue, estados de jobs e métricas de performance.
"""

import sys
import time
import json
import logging
from pathlib import Path

# Adicionar diretório src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from auto_uploader.queue import UnifiedQueue, QueuePriority, JobState


def setup_logging():
    """Configura logging para os testes"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('queue_test.log')
        ]
    )


def test_queue_basic():
    """Teste básico da fila unificada"""
    print("=== Teste Básico da UnifiedQueue ===")
    
    # Criar fila
    data_dir = Path(__file__).parent / "test_data_queue"
    data_dir.mkdir(exist_ok=True)
    
    queue = UnifiedQueue(data_dir, max_concurrent_jobs=2)
    
    try:
        # Testar adição de jobs com diferentes prioridades
        print("\n1. Adicionando jobs com diferentes prioridades...")
        urgent_id = queue.add_manual_job("obra_urgent", "mangayabu", "URGENT")
        manual_id = queue.add_manual_job("obra_manual", "scan1", "HIGH")
        auto_id1 = queue.add_auto_job("obra_auto_1", "scan2")
        auto_id2 = queue.add_auto_job("obra_auto_2", "scan3")
        
        print(f"   - Job URGENT: {urgent_id}")
        print(f"   - Job MANUAL: {manual_id}")
        print(f"   - Job AUTO 1: {auto_id1}")
        print(f"   - Job AUTO 2: {auto_id2}")
        
        # Verificar status inicial
        print("\n2. Status inicial:")
        status = queue.get_queue_status()
        print(f"   - Total na fila: {status['total_queue_size']}")
        print(f"   - Jobs ativos: {status['active_jobs']}")
        print(f"   - Por prioridade: {status['priority_counts']}")
        print(f"   - Por scan: {status['scan_counts']}")
        
        # Testar processamento manual
        print("\n3. Processando jobs manualmente...")
        for i in range(3):
            job = queue.get_next_job()
            if job:
                print(f"   Job obtido: {job.id} (prioridade: {job.priority.name})")
                
                # Simular processamento rápido
                time.sleep(1)
                
                # Marcar como completado
                if i == 2:  # Simular falha no terceiro
                    queue.mark_failed(job.id, "Erro simulado para teste")
                    print(f"   Job falhado: {job.id}")
                else:
                    queue.mark_completed(job.id, {"test_result": "success"})
                    print(f"   Job completado: {job.id}")
            else:
                print("   Nenhum job disponível")
                break
        
        # Status após processamento manual
        print("\n4. Status após processamento manual:")
        status = queue.get_queue_status()
        print(f"   - Total na fila: {status['total_queue_size']}")
        print(f"   - Jobs completados: {status['metrics']['completed_jobs']}")
        print(f"   - Jobs falhados: {status['metrics']['failed_jobs']}")
        print(f"   - Taxa de sucesso: {status['metrics']['success_rate']:.2%}")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Erro durante teste básico: {e}")
        return False
    
    finally:
        queue.stop_processing()


def test_queue_automatic_processing():
    """Teste do processamento automático"""
    print("\n=== Teste de Processamento Automático ===")
    
    data_dir = Path(__file__).parent / "test_data_queue_auto"
    data_dir.mkdir(exist_ok=True)
    
    queue = UnifiedQueue(data_dir, max_concurrent_jobs=1)
    
    try:
        # Adicionar jobs
        print("\n1. Adicionando jobs para processamento automático...")
        queue.add_manual_job("obra_auto_test_1", "teste", "HIGH")
        queue.add_auto_job("obra_auto_test_2", "teste")
        queue.add_auto_job("obra_auto_test_3", "teste")
        
        # Iniciar processamento automático
        print("\n2. Iniciando processamento automático...")
        if queue.start_processing():
            print("   ✓ Processamento iniciado")
        else:
            print("   ✗ Falha ao iniciar processamento")
            return False
        
        # Monitorar por 20 segundos
        print("\n3. Monitorando processamento por 20 segundos...")
        for i in range(20):
            status = queue.get_queue_status()
            active_jobs = status.get('active_job_details', [])
            active_info = f" (processando {active_jobs[0]['id']})" if active_jobs else ""
            
            print(f"   [{i+1:2d}s] Fila: {status['total_queue_size']}, "
                  f"Ativos: {status['active_jobs']}, "
                  f"Completados: {status['metrics']['completed_jobs']}{active_info}")
            
            time.sleep(1)
        
        # Status final
        print("\n4. Status final:")
        status = queue.get_queue_status()
        print(f"   - Fila restante: {status['total_queue_size']}")
        print(f"   - Jobs completados: {status['metrics']['completed_jobs']}")
        print(f"   - Jobs falhados: {status['metrics']['failed_jobs']}")
        print(f"   - Tempo médio: {status['metrics']['average_processing_time']:.1f}s")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Erro durante teste automático: {e}")
        return False
    
    finally:
        queue.stop_processing()


def test_queue_priority_order():
    """Teste da ordem de prioridade"""
    print("\n=== Teste de Ordem de Prioridade ===")
    
    data_dir = Path(__file__).parent / "test_data_queue_priority"
    data_dir.mkdir(exist_ok=True)
    
    queue = UnifiedQueue(data_dir)
    
    try:
        # Adicionar jobs em ordem inversa de prioridade
        print("\n1. Adicionando jobs em ordem inversa...")
        auto_id = queue.add_auto_job("obra_normal", "teste")  # NORMAL (3)
        manual_id = queue.add_manual_job("obra_high", "teste", "HIGH")  # HIGH (2)
        urgent_id = queue.add_manual_job("obra_urgent", "teste", "URGENT")  # URGENT (1)
        
        print(f"   - Adicionado NORMAL: {auto_id}")
        print(f"   - Adicionado HIGH: {manual_id}")
        print(f"   - Adicionado URGENT: {urgent_id}")
        
        # Processar e verificar ordem
        print("\n2. Processando jobs e verificando ordem de prioridade...")
        expected_order = ["URGENT", "HIGH", "NORMAL"]
        actual_order = []
        
        for i in range(3):
            job = queue.get_next_job()
            if job:
                actual_order.append(job.priority.name)
                print(f"   Job {i+1}: {job.id} (prioridade: {job.priority.name})")
                queue.mark_completed(job.id)
            else:
                print(f"   Job {i+1}: Nenhum job disponível")
        
        print(f"\n3. Verificação de ordem:")
        print(f"   - Esperado: {expected_order}")
        print(f"   - Obtido: {actual_order}")
        
        success = actual_order == expected_order
        print(f"   - Ordem correta: {'✓' if success else '✗'}")
        
        return success
        
    except Exception as e:
        print(f"   ✗ Erro durante teste de prioridade: {e}")
        return False


def test_queue_persistence():
    """Teste da persistência de estado"""
    print("\n=== Teste de Persistência ===")
    
    data_dir = Path(__file__).parent / "test_data_queue_persistence"
    data_dir.mkdir(exist_ok=True)
    
    # Primeira fila
    queue1 = UnifiedQueue(data_dir)
    
    try:
        # Adicionar jobs e salvar estado
        print("\n1. Primeira fila - adicionando jobs...")
        queue1.add_manual_job("obra_persist_1", "teste", "HIGH")
        queue1.add_auto_job("obra_persist_2", "teste")
        
        # Simular job completado
        job = queue1.get_next_job()
        if job:
            queue1.mark_completed(job.id, {"persisted": True})
            print(f"   Job completado: {job.id}")
        
        status1 = queue1.get_queue_status()
        print(f"   Estado salvo - Fila: {status1['total_queue_size']}, Completados: {status1['metrics']['completed_jobs']}")
        
        # Segunda fila (deve carregar estado)
        print("\n2. Segunda fila - carregando estado...")
        queue2 = UnifiedQueue(data_dir)
        
        status2 = queue2.get_queue_status()
        print(f"   Estado carregado - Fila: {status2['total_queue_size']}, Completados: {status2['metrics']['completed_jobs']}")
        
        # Verificar se estado foi preservado
        persistence_ok = (
            status2['total_queue_size'] > 0 and 
            status2['metrics']['completed_jobs'] > 0
        )
        
        print(f"   - Persistência: {'✓' if persistence_ok else '✗'}")
        
        return persistence_ok
        
    except Exception as e:
        print(f"   ✗ Erro durante teste de persistência: {e}")
        return False


def test_queue_job_details():
    """Teste de detalhes de jobs"""
    print("\n=== Teste de Detalhes de Jobs ===")
    
    data_dir = Path(__file__).parent / "test_data_queue_details"
    data_dir.mkdir(exist_ok=True)
    
    queue = UnifiedQueue(data_dir)
    
    try:
        # Adicionar job com metadata
        print("\n1. Adicionando job com metadata...")
        metadata = {"source": "test", "priority_reason": "testing"}
        job_id = queue.add_manual_job("obra_details", "teste", "HIGH", metadata)
        
        # Obter detalhes
        print("\n2. Obtendo detalhes do job...")
        details = queue.get_job_details(job_id)
        
        if details:
            print(f"   - ID: {details['id']}")
            print(f"   - Obra: {details['obra_id']}")
            print(f"   - Scan: {details['scan_name']}")
            print(f"   - Prioridade: {details['priority']}")
            print(f"   - Estado: {details['state']}")
            print(f"   - Metadata: {details['metadata']}")
            
            # Verificar se metadata foi preservada
            metadata_ok = details['metadata'] == metadata
            print(f"   - Metadata preservada: {'✓' if metadata_ok else '✗'}")
            
            return metadata_ok
        else:
            print("   ✗ Detalhes não encontrados")
            return False
        
    except Exception as e:
        print(f"   ✗ Erro durante teste de detalhes: {e}")
        return False


if __name__ == "__main__":
    setup_logging()
    
    print("🚀 Iniciando testes da UnifiedQueue")
    print("=" * 50)
    
    # Executar testes
    tests = [
        test_queue_basic,
        test_queue_automatic_processing,
        test_queue_priority_order,
        test_queue_persistence,
        test_queue_job_details
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
        print("🎉 Todos os testes passaram! UnifiedQueue está funcionando corretamente.")
    else:
        print("⚠️  Alguns testes falharam. Verifique os logs para mais detalhes.")
    
    sys.exit(0 if passed_tests == total_tests else 1)