"""
Testes para o Sistema de Health Check

Este módulo contém testes unitários e de integração para verificar
o funcionamento correto do sistema de Health Check.
"""

import sys
import asyncio
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

# Adiciona o diretório src ao sys.path
sys.path.append(str(Path(__file__).parent / "src"))

from auto_uploader.health_checker import APIHealthChecker, HealthCheckResult, HealthStatus, HealthMetrics
from auto_uploader.discord_notifier import DiscordNotifier
from auto_uploader.health_integration import HealthIntegrationManager


class TestHealthChecker(unittest.TestCase):
    """Testes para APIHealthChecker"""
    
    def setUp(self):
        """Configuração antes de cada teste"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.health_checker = APIHealthChecker(data_dir=self.temp_dir)
        self.test_url = "https://api.example.com/health"
    
    def tearDown(self):
        """Limpeza após cada teste"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_health_check_result_creation(self):
        """Testa criação de HealthCheckResult"""
        result = HealthCheckResult(
            url=self.test_url,
            status=HealthStatus.ONLINE,
            response_time_ms=150.0,
            status_code=200
        )
        
        self.assertEqual(result.url, self.test_url)
        self.assertEqual(result.status, HealthStatus.ONLINE)
        self.assertTrue(result.is_healthy)
        self.assertEqual(result.response_time_seconds, 0.15)
    
    def test_health_metrics_update(self):
        """Testa atualização de métricas de saúde"""
        metrics = HealthMetrics()
        
        # Resultado online
        result_online = HealthCheckResult(
            url=self.test_url,
            status=HealthStatus.ONLINE,
            response_time_ms=100.0
        )
        
        metrics.update_from_result(result_online)
        
        self.assertEqual(metrics.total_checks, 1)
        self.assertEqual(metrics.successful_checks, 1)
        self.assertEqual(metrics.failed_checks, 0)
        self.assertEqual(metrics.consecutive_successes, 1)
        self.assertEqual(metrics.consecutive_failures, 0)
        self.assertEqual(metrics.uptime_percentage, 100.0)
        
        # Resultado offline
        result_offline = HealthCheckResult(
            url=self.test_url,
            status=HealthStatus.OFFLINE,
            error_message="Connection timeout"
        )
        
        metrics.update_from_result(result_offline)
        
        self.assertEqual(metrics.total_checks, 2)
        self.assertEqual(metrics.successful_checks, 1)
        self.assertEqual(metrics.failed_checks, 1)
        self.assertEqual(metrics.consecutive_successes, 0)
        self.assertEqual(metrics.consecutive_failures, 1)
        self.assertEqual(metrics.uptime_percentage, 50.0)
        self.assertEqual(metrics.failure_rate, 50.0)
    
    def test_config_management(self):
        """Testa gerenciamento de configurações"""
        # Configuração padrão
        config = self.health_checker.get_config()
        self.assertIn("timeout_seconds", config)
        self.assertEqual(config["timeout_seconds"], 10)
        
        # Atualizar configuração
        new_config = {"timeout_seconds": 15, "max_retries": 5}
        self.health_checker.update_config(new_config)
        
        updated_config = self.health_checker.get_config()
        self.assertEqual(updated_config["timeout_seconds"], 15)
        self.assertEqual(updated_config["max_retries"], 5)
    
    def test_cache_validation(self):
        """Testa validação de cache"""
        # Cache vazio
        self.assertFalse(self.health_checker._is_cache_valid(self.test_url))
        
        # Adicionar resultado ao cache
        result = HealthCheckResult(
            url=self.test_url,
            status=HealthStatus.ONLINE,
            response_time_ms=100.0,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        self.health_checker._last_check_cache[self.test_url] = result
        
        # Cache deve ser válido
        self.assertTrue(self.health_checker._is_cache_valid(self.test_url))
        
        # Resultado antigo no cache
        old_result = HealthCheckResult(
            url=self.test_url,
            status=HealthStatus.ONLINE,
            response_time_ms=100.0,
            timestamp=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        )
        
        self.health_checker._last_check_cache[self.test_url] = old_result
        
        # Cache deve ser inválido
        self.assertFalse(self.health_checker._is_cache_valid(self.test_url))
    
    def test_uptime_summary(self):
        """Testa geração de resumo de uptime"""
        # Adicionar alguns resultados ao histórico
        now = datetime.now(timezone.utc)
        
        # Resultado online
        online_result = HealthCheckResult(
            url=self.test_url,
            status=HealthStatus.ONLINE,
            response_time_ms=100.0,
            timestamp=(now - timedelta(hours=1)).isoformat()
        )
        
        # Resultado offline
        offline_result = HealthCheckResult(
            url=self.test_url,
            status=HealthStatus.OFFLINE,
            error_message="Error",
            timestamp=(now - timedelta(hours=2)).isoformat()
        )
        
        self.health_checker._history = [offline_result, online_result]
        
        summary = self.health_checker.get_uptime_summary(self.test_url, hours=24)
        
        self.assertEqual(summary["url"], self.test_url)
        self.assertEqual(summary["total_checks"], 2)
        self.assertEqual(summary["online_checks"], 1)
        self.assertEqual(summary["uptime_percentage"], 50.0)


class TestHealthCheckerAsync(unittest.IsolatedAsyncioTestCase):
    """Testes assíncronos para APIHealthChecker"""
    
    def setUp(self):
        """Configuração antes de cada teste"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.health_checker = APIHealthChecker(data_dir=self.temp_dir)
        self.test_url = "https://httpbin.org/status/200"
    
    def tearDown(self):
        """Limpeza após cada teste"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('aiohttp.ClientSession.get')
    async def test_successful_health_check(self, mock_get):
        """Testa verificação de saúde bem-sucedida"""
        # Mock da resposta HTTP
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__.return_value = mock_response
        
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            result = await self.health_checker.check_health(self.test_url, use_cache=False)
            
            self.assertEqual(result.url, self.test_url)
            self.assertEqual(result.status, HealthStatus.ONLINE)
            self.assertEqual(result.status_code, 200)
            self.assertIsNotNone(result.response_time_ms)
            self.assertTrue(result.is_healthy)
    
    @patch('aiohttp.ClientSession.get')
    async def test_failed_health_check(self, mock_get):
        """Testa verificação de saúde com falha"""
        # Mock de timeout
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get.side_effect = asyncio.TimeoutError("Timeout")
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            result = await self.health_checker.check_health(self.test_url, use_cache=False)
            
            self.assertEqual(result.url, self.test_url)
            self.assertEqual(result.status, HealthStatus.OFFLINE)
            self.assertIn("Timeout", result.error_message)
            self.assertFalse(result.is_healthy)
    
    async def test_multiple_urls_check(self):
        """Testa verificação de múltiplas URLs"""
        urls = [
            "https://httpbin.org/status/200",
            "https://httpbin.org/status/500", 
            "https://invalid-url-test.example"
        ]
        
        with patch.object(self.health_checker, 'check_health') as mock_check:
            # Mock dos resultados
            mock_results = [
                HealthCheckResult(urls[0], HealthStatus.ONLINE, response_time_ms=100, status_code=200),
                HealthCheckResult(urls[1], HealthStatus.OFFLINE, status_code=500),
                HealthCheckResult(urls[2], HealthStatus.OFFLINE, error_message="Invalid URL")
            ]
            
            mock_check.side_effect = mock_results
            
            results = await self.health_checker.check_multiple_urls(urls)
            
            self.assertEqual(len(results), 3)
            self.assertTrue(results[urls[0]].is_healthy)
            self.assertFalse(results[urls[1]].is_healthy)
            self.assertFalse(results[urls[2]].is_healthy)


class TestDiscordNotifier(unittest.TestCase):
    """Testes para DiscordNotifier"""
    
    def setUp(self):
        """Configuração antes de cada teste"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.notifier = DiscordNotifier(data_dir=self.temp_dir)
        self.test_webhook_url = "https://discord.com/api/webhooks/test/webhook"
    
    def tearDown(self):
        """Limpeza após cada teste"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_webhook_management(self):
        """Testa gerenciamento de webhooks"""
        # Adicionar webhook
        self.notifier.add_webhook(
            "test_webhook",
            self.test_webhook_url,
            "Test Bot"
        )
        
        webhooks = self.notifier.list_webhooks()
        self.assertIn("test_webhook", webhooks)
        self.assertEqual(webhooks["test_webhook"]["username"], "Test Bot")
        
        # Remover webhook
        success = self.notifier.remove_webhook("test_webhook")
        self.assertTrue(success)
        
        webhooks_after = self.notifier.list_webhooks()
        self.assertNotIn("test_webhook", webhooks_after)
    
    def test_embed_creation(self):
        """Testa criação de embeds"""
        result = HealthCheckResult(
            url="https://api.example.com",
            status=HealthStatus.ONLINE,
            response_time_ms=150.0,
            status_code=200
        )
        
        embed = self.notifier._create_health_embed(result, "status_change")
        
        self.assertIn("title", embed)
        self.assertIn("color", embed)
        self.assertIn("fields", embed)
        self.assertEqual(embed["color"], 0x00ff00)  # Verde para online
        
        # Verificar campos do embed
        fields = {field["name"]: field["value"] for field in embed["fields"]}
        self.assertIn("🌐 URL", fields)
        self.assertIn("📊 Status", fields)
        self.assertEqual(fields["🌐 URL"], "https://api.example.com")
    
    def test_color_and_emoji_mapping(self):
        """Testa mapeamento de cores e emojis"""
        # Online
        self.assertEqual(self.notifier._get_color_for_status(HealthStatus.ONLINE), 0x00ff00)
        self.assertEqual(self.notifier._get_emoji_for_status(HealthStatus.ONLINE), "✅")
        
        # Offline
        self.assertEqual(self.notifier._get_color_for_status(HealthStatus.OFFLINE), 0xff0000)
        self.assertEqual(self.notifier._get_emoji_for_status(HealthStatus.OFFLINE), "❌")
        
        # Degraded
        self.assertEqual(self.notifier._get_color_for_status(HealthStatus.DEGRADED), 0xffaa00)
        self.assertEqual(self.notifier._get_emoji_for_status(HealthStatus.DEGRADED), "⚠️")


class TestHealthIntegration(unittest.IsolatedAsyncioTestCase):
    """Testes para HealthIntegrationManager"""
    
    def setUp(self):
        """Configuração antes de cada teste"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.integration = HealthIntegrationManager(data_dir=self.temp_dir)
        self.test_urls = [
            "https://api1.example.com",
            "https://api2.example.com", 
            "https://api3.example.com"
        ]
    
    def tearDown(self):
        """Limpeza após cada teste"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    async def test_check_apis_before_update(self):
        """Testa verificação de APIs antes do auto-update"""
        # Mock dos resultados
        mock_results = {
            self.test_urls[0]: HealthCheckResult(self.test_urls[0], HealthStatus.ONLINE, response_time_ms=100),
            self.test_urls[1]: HealthCheckResult(self.test_urls[1], HealthStatus.ONLINE, response_time_ms=150),
            self.test_urls[2]: HealthCheckResult(self.test_urls[2], HealthStatus.OFFLINE, error_message="Timeout")
        }
        
        with patch.object(self.integration.health_checker, 'check_multiple_urls') as mock_check:
            mock_check.return_value = mock_results
            
            summary = await self.integration.check_apis_before_update(
                self.test_urls, 
                min_healthy_percentage=0.6
            )
            
            self.assertTrue(summary["can_proceed"])  # 2/3 = 66% > 60%
            self.assertEqual(summary["total_apis"], 3)
            self.assertEqual(summary["healthy_apis"], 2)
            self.assertEqual(len(summary["online_apis"]), 2)
            self.assertEqual(len(summary["offline_apis"]), 1)
    
    async def test_provider_health_report(self):
        """Testa geração de relatório de saúde"""
        with patch.object(self.integration.health_checker, 'check_multiple_urls') as mock_check:
            with patch.object(self.integration.health_checker, 'get_metrics') as mock_metrics:
                with patch.object(self.integration.health_checker, 'get_uptime_summary') as mock_uptime:
                    
                    # Mock dos resultados
                    mock_check.return_value = {
                        self.test_urls[0]: HealthCheckResult(self.test_urls[0], HealthStatus.ONLINE, response_time_ms=100)
                    }
                    
                    mock_metrics.return_value = HealthMetrics(
                        total_checks=100,
                        successful_checks=95,
                        uptime_percentage=95.0
                    )
                    
                    mock_uptime.return_value = {
                        "uptime_percentage": 95.0,
                        "total_checks": 24,
                        "online_checks": 23
                    }
                    
                    report = await self.integration.get_provider_health_report([self.test_urls[0]])
                    
                    self.assertIn("summary", report)
                    self.assertIn("providers", report)
                    self.assertEqual(report["summary"]["total_providers"], 1)
                    self.assertIn(self.test_urls[0], report["providers"])
    
    def test_dashboard_data_generation(self):
        """Testa geração de dados para dashboard"""
        # Mock de dados no cache
        self.integration.health_checker._last_check_cache[self.test_urls[0]] = HealthCheckResult(
            self.test_urls[0],
            HealthStatus.ONLINE,
            response_time_ms=120.0
        )
        
        # Mock de métricas
        self.integration.health_checker._metrics[self.test_urls[0]] = HealthMetrics(
            total_checks=50,
            successful_checks=48,
            consecutive_failures=0
        )
        
        with patch.object(self.integration.health_checker, 'get_uptime_summary') as mock_uptime:
            mock_uptime.return_value = {"uptime_percentage": 96.0}
            
            dashboard_data = self.integration.get_health_dashboard_data([self.test_urls[0]])
            
            self.assertIn("providers", dashboard_data)
            self.assertEqual(len(dashboard_data["providers"]), 1)
            
            provider = dashboard_data["providers"][0]
            self.assertEqual(provider["url"], self.test_urls[0])
            self.assertEqual(provider["current_status"], "online")
            self.assertEqual(provider["response_time_ms"], 120.0)


def run_tests():
    """Executa todos os testes"""
    print("🧪 Executando testes do sistema de Health Check...")
    
    # Criar suite de testes
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Adicionar testes
    suite.addTests(loader.loadTestsFromTestCase(TestHealthChecker))
    suite.addTests(loader.loadTestsFromTestCase(TestHealthCheckerAsync))
    suite.addTests(loader.loadTestsFromTestCase(TestDiscordNotifier))
    suite.addTests(loader.loadTestsFromTestCase(TestHealthIntegration))
    
    # Executar testes
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Resumo
    print(f"\n📊 Resumo dos testes:")
    print(f"   • Total: {result.testsRun}")
    print(f"   • Sucesso: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"   • Falhas: {len(result.failures)}")
    print(f"   • Erros: {len(result.errors)}")
    
    if result.failures:
        print(f"\n❌ Falhas:")
        for test, traceback in result.failures:
            print(f"   • {test}: {traceback}")
    
    if result.errors:
        print(f"\n🚨 Erros:")
        for test, traceback in result.errors:
            print(f"   • {test}: {traceback}")
    
    success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun) * 100
    print(f"\n✅ Taxa de sucesso: {success_rate:.1f}%")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)