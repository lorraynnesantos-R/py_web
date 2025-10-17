#!/usr/bin/env python3
"""
Script de Teste - MediocreAutoUploader Integration Test
======================================================

Script para testar a integração da classe principal MediocreAutoUploader
com componentes mockados para validar o fluxo completo.

Uso:
    python test_integration.py

Autor: GitHub Copilot
Data: 16 de outubro de 2025
"""

import sys
import os
import time
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from src.mediocre_auto_uploader import MediocreAutoUploader, MediocreConfig
    print("✅ Import da classe principal bem-sucedido")
except ImportError as e:
    print(f"❌ Erro ao importar MediocreAutoUploader: {e}")
    sys.exit(1)


def test_basic_initialization():
    """Testar inicialização básica"""
    print("\n🧪 Teste 1: Inicialização Básica")
    
    try:
        config = MediocreConfig(
            auto_update_interval_minutes=1,  # 1 minuto para teste
            enable_auto_update=False,  # Desabilitar para teste inicial
            discord_webhook_url=None
        )
        
        uploader = MediocreAutoUploader(config)
        print("✅ MediocreAutoUploader criado com sucesso")
        
        # Verificar status inicial
        status = uploader.get_system_status()
        print(f"📊 Status inicial: running={status['running']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na inicialização: {e}")
        return False


def test_start_stop_cycle():
    """Testar ciclo de start/stop"""
    print("\n🧪 Teste 2: Ciclo Start/Stop")
    
    try:
        config = MediocreConfig(
            auto_update_interval_minutes=1,
            enable_auto_update=False,  # Desabilitar auto-update
            enable_manual_queue=True
        )
        
        uploader = MediocreAutoUploader(config)
        
        # Iniciar sistema
        print("🚀 Iniciando sistema...")
        started = uploader.start()
        
        if not started:
            print("❌ Falha ao iniciar sistema")
            return False
        
        print("✅ Sistema iniciado com sucesso")
        
        # Aguardar um pouco
        time.sleep(3)
        
        # Verificar status
        status = uploader.get_system_status()
        print(f"📊 Status durante execução: running={status['running']}")
        
        # Parar sistema
        print("🛑 Parando sistema...")
        stopped = uploader.stop()
        
        if not stopped:
            print("❌ Falha ao parar sistema")
            return False
        
        print("✅ Sistema parado com sucesso")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no ciclo start/stop: {e}")
        return False


def test_manual_job_addition():
    """Testar adição de job manual"""
    print("\n🧪 Teste 3: Adição de Job Manual")
    
    try:
        config = MediocreConfig(
            enable_auto_update=False,
            enable_manual_queue=True
        )
        
        uploader = MediocreAutoUploader(config)
        uploader.start()
        
        # Adicionar job manual
        print("📌 Adicionando job manual...")
        job_added = uploader.add_manual_job(
            obra_id="test_001",
            obra_name="Teste de Obra",
            obra_url="https://example.com/teste",
            scan_name="test_scan",
            priority="HIGH"
        )
        
        if not job_added:
            print("❌ Falha ao adicionar job manual")
            uploader.stop()
            return False
        
        print("✅ Job manual adicionado com sucesso")
        
        # Aguardar processamento
        time.sleep(5)
        
        # Verificar status da fila
        if hasattr(uploader, 'queue'):
            queue_status = uploader.queue.get_queue_status()
            print(f"📊 Status da fila: {queue_status}")
        
        uploader.stop()
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de job manual: {e}")
        return False


def test_configuration_scenarios():
    """Testar diferentes cenários de configuração"""
    print("\n🧪 Teste 4: Cenários de Configuração")
    
    scenarios = [
        {
            "name": "Configuração Mínima",
            "config": MediocreConfig(enable_auto_update=False)
        },
        {
            "name": "Com Discord",
            "config": MediocreConfig(
                discord_webhook_url="https://discord.com/api/webhooks/test",
                enable_auto_update=False
            )
        },
        {
            "name": "Auto-update Habilitado",
            "config": MediocreConfig(
                auto_update_interval_minutes=1,
                enable_auto_update=True
            )
        }
    ]
    
    for scenario in scenarios:
        try:
            print(f"  🔧 Testando: {scenario['name']}")
            uploader = MediocreAutoUploader(scenario['config'])
            
            # Tentar iniciar e parar rapidamente
            if uploader.start():
                time.sleep(1)
                uploader.stop()
                print(f"  ✅ {scenario['name']}: OK")
            else:
                print(f"  ❌ {scenario['name']}: Falha ao iniciar")
                return False
                
        except Exception as e:
            print(f"  ❌ {scenario['name']}: Erro - {e}")
            return False
    
    print("✅ Todos os cenários de configuração passaram")
    return True


def main():
    """Função principal de teste"""
    print("🎯 MediocreAutoUploader - Teste de Integração")
    print("=" * 50)
    
    tests = [
        test_basic_initialization,
        test_start_stop_cycle, 
        test_manual_job_addition,
        test_configuration_scenarios
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print("❌ Teste falhou")
        except Exception as e:
            print(f"❌ Exceção no teste: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Resultado Final: {passed}/{total} testes passaram")
    
    if passed == total:
        print("🎉 Todos os testes passaram! Integração básica funcionando.")
        return 0
    else:
        print("⚠️ Alguns testes falharam. Verifique os componentes.")
        return 1


if __name__ == "__main__":
    sys.exit(main())