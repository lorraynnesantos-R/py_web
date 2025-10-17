"""
Testes de integração seguros que funcioram mesmo com componentes limitados.
"""
import sys
import os
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Adicionar src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.mediocre_auto_uploader import MediocreAutoUploader, MediocreConfig
    print("✅ Import da classe MediocreAutoUploader bem-sucedido")
except Exception as e:
    print(f"❌ Erro ao importar MediocreAutoUploader: {e}")
    sys.exit(1)


class MockPytesteCore:
    """Mock básico do PytesteCore para testes"""
    def __init__(self, config=None):
        self.config = config or {}
        self.is_initialized = True
        
    def get_all_works(self):
        """Retorna lista mockada de obras"""
        return [
            {"id": "1", "title": "Obra Test 1", "type": "Novel", "status": "ongoing"},
            {"id": "2", "title": "Obra Test 2", "type": "Manhwa", "status": "completed"}
        ]
    
    def get_work_details(self, work_id):
        """Retorna detalhes mockados de uma obra"""
        return {
            "id": work_id,
            "title": f"Obra {work_id}",
            "chapters": [{"id": f"ch{i}", "title": f"Chapter {i}"} for i in range(1, 6)]
        }


class MockScheduler:
    """Mock básico do AutoUpdateScheduler"""
    def __init__(self, config=None):
        self.config = config or {}
        self.is_running = False
        self.jobs = []
        
    def start(self):
        self.is_running = True
        print("📅 Mock Scheduler iniciado")
        
    def stop(self):
        self.is_running = False
        print("📅 Mock Scheduler parado")
        
    def add_job(self, job_id, func, interval=3600):
        self.jobs.append({"id": job_id, "func": func, "interval": interval})
        print(f"📅 Job {job_id} adicionado ao scheduler")


class MockUnifiedQueue:
    """Mock básico da UnifiedQueue"""
    def __init__(self, config=None):
        self.config = config or {}
        self.queue = []
        self.processing = []
        self.completed = []
        
    def add_job(self, job_data):
        self.queue.append(job_data)
        print(f"📋 Job adicionado à fila: {job_data.get('id', 'unknown')}")
        
    def get_next_job(self):
        if self.queue:
            job = self.queue.pop(0)
            self.processing.append(job)
            return job
        return None
        
    def complete_job(self, job_id):
        self.processing = [j for j in self.processing if j.get('id') != job_id]
        self.completed.append({"id": job_id, "completed_at": time.time()})
        print(f"📋 Job {job_id} marcado como completo")
        
    def get_queue_status(self):
        return {
            "queue_size": len(self.queue),
            "processing": len(self.processing),
            "completed": len(self.completed)
        }


class MockMappingManager:
    """Mock básico do MappingManager"""
    def __init__(self, config=None):
        self.config = config or {}
        self.mappings = {}
        
    def get_mapping(self, source_id):
        return self.mappings.get(source_id, {"status": "not_mapped"})
        
    def update_mapping(self, source_id, data):
        self.mappings[source_id] = data
        print(f"🗺️ Mapping atualizado para {source_id}")


class MockDiscordNotifier:
    """Mock básico do DiscordNotifier"""
    def __init__(self, config=None):
        self.config = config or {}
        self.sent_notifications = []
        
    async def send_notification(self, message, channel=None):
        self.sent_notifications.append({"message": message, "channel": channel})
        print(f"🔔 Notificação enviada: {message[:50]}...")


class TestMediocreAutoUploaderIntegration(unittest.TestCase):
    """Testes de integração com mocks seguros"""
    
    def setUp(self):
        """Configuração inicial para cada teste"""
        self.test_config = MediocreConfig(
            base_dir=Path("test_data"),
            work_interval=60,  # 1 minuto para testes rápidos
            enable_notifications=True,
            discord_webhook_url="https://test.webhook.url",
            max_queue_size=10,
            max_concurrent_jobs=2
        )
        
        # Patches para usar mocks
        self.patches = []
        self.start_patches()
        
    def start_patches(self):
        """Inicia todos os patches necessários"""
        # Patch do PytesteCore
        patch_pyteste = patch('src.core.PytesteCore', MockPytesteCore)
        self.patches.append(patch_pyteste)
        patch_pyteste.start()
        
        # Patch do Scheduler
        patch_scheduler = patch('src.core.AutoUpdateScheduler', MockScheduler)
        self.patches.append(patch_scheduler)
        patch_scheduler.start()
        
        # Patch da Queue
        patch_queue = patch('src.core.UnifiedQueue', MockUnifiedQueue)
        self.patches.append(patch_queue)
        patch_queue.start()
        
        # Patch do MappingManager
        patch_mapping = patch('src.mapping.MappingManager', MockMappingManager)
        self.patches.append(patch_mapping)
        patch_mapping.start()
        
        # Patch do DiscordNotifier
        patch_discord = patch('src.notifications.DiscordNotifier', MockDiscordNotifier)
        self.patches.append(patch_discord)
        patch_discord.start()
        
    def tearDown(self):
        """Limpeza após cada teste"""
        # Para todos os patches
        for p in self.patches:
            p.stop()
            
    def test_safe_initialization(self):
        """Testa inicialização com mocks seguros"""
        print("\n🧪 Testando inicialização segura...")
        
        uploader = MediocreAutoUploader(self.test_config)
        
        # Verifica se foi inicializado
        self.assertIsNotNone(uploader)
        self.assertEqual(uploader.config, self.test_config)
        
        # Verifica componentes mockados
        self.assertIsNotNone(uploader.pyteste_core)
        self.assertIsNotNone(uploader.scheduler)
        self.assertIsNotNone(uploader.queue)
        
        print("✅ Inicialização segura bem-sucedida")
        
    def test_safe_start_stop_cycle(self):
        """Testa ciclo de start/stop com mocks"""
        print("\n🧪 Testando ciclo start/stop seguro...")
        
        uploader = MediocreAutoUploader(self.test_config)
        
        # Testa start
        uploader.start()
        self.assertTrue(uploader.is_running)
        
        # Aguarda um momento
        time.sleep(0.1)
        
        # Testa stop
        uploader.stop()
        self.assertFalse(uploader.is_running)
        
        print("✅ Ciclo start/stop seguro bem-sucedido")
        
    def test_manual_job_processing(self):
        """Testa processamento manual de jobs"""
        print("\n🧪 Testando processamento manual de jobs...")
        
        uploader = MediocreAutoUploader(self.test_config)
        
        # Adiciona job manual
        result = uploader.add_manual_job("test_work_1", "update")
        self.assertTrue(result)
        
        # Verifica se foi adicionado à fila
        queue_status = uploader.get_queue_status()
        self.assertGreater(queue_status["queue_size"], 0)
        
        print("✅ Processamento manual de jobs bem-sucedido")
        
    def test_system_status_reporting(self):
        """Testa relatório de status do sistema"""
        print("\n🧪 Testando relatório de status...")
        
        uploader = MediocreAutoUploader(self.test_config)
        uploader.start()
        
        # Obtém status
        status = uploader.get_system_status()
        
        # Verifica campos obrigatórios
        required_fields = ["is_running", "queue_status", "component_status", "uptime"]
        for field in required_fields:
            self.assertIn(field, status)
            
        uploader.stop()
        
        print("✅ Relatório de status bem-sucedido")


def run_safe_integration_tests():
    """Executa os testes de integração seguros"""
    print("🚀 Iniciando testes de integração seguros...")
    print("=" * 60)
    
    # Cria suite de testes
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMediocreAutoUploaderIntegration)
    
    # Executa testes
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("🎉 Todos os testes de integração passaram!")
        return True
    else:
        print(f"❌ {len(result.failures)} teste(s) falharam")
        print(f"❌ {len(result.errors)} erro(s) encontrado(s)")
        return False


if __name__ == "__main__":
    success = run_safe_integration_tests()
    sys.exit(0 if success else 1)