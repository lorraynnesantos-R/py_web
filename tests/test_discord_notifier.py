"""
Testes para o Sistema de Notificações Discord
===========================================

Testes completos para o DiscordNotifier, incluindo:
- Configuração e inicialização
- Envio de diferentes tipos de notificação
- Rate limiting
- Templates de mensagem
- Fallback para logs
- Integração com sistema de quarentena
"""

import unittest
import asyncio
import time
import json
import threading
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from collections import deque

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from notifications.discord import (
    DiscordNotifier,
    NotificationConfig,
    NotificationType,
    NotificationPriority,
    DiscordMessage,
    get_discord_notifier
)


class TestNotificationConfig(unittest.TestCase):
    """Testes para NotificationConfig"""
    
    def test_default_config(self):
        """Testa configuração padrão"""
        config = NotificationConfig()
        
        self.assertIsNone(config.webhook_url)
        self.assertTrue(config.enabled)
        self.assertEqual(config.rate_limit_seconds, 30)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.timeout_seconds, 10)
        self.assertEqual(config.mention_user_id, "221057164351897610")
        self.assertEqual(config.bot_username, "MediocreToons Bot")
    
    def test_custom_config(self):
        """Testa configuração personalizada"""
        config = NotificationConfig(
            webhook_url="https://discord.com/api/webhooks/test",
            enabled=False,
            rate_limit_seconds=60,
            mention_user_id="123456789"
        )
        
        self.assertEqual(config.webhook_url, "https://discord.com/api/webhooks/test")
        self.assertFalse(config.enabled)
        self.assertEqual(config.rate_limit_seconds, 60)
        self.assertEqual(config.mention_user_id, "123456789")


class TestDiscordMessage(unittest.TestCase):
    """Testes para DiscordMessage"""
    
    def test_message_creation(self):
        """Testa criação de mensagem"""
        message = DiscordMessage(
            content="Teste",
            username="Bot Test"
        )
        
        self.assertEqual(message.content, "Teste")
        self.assertEqual(message.username, "Bot Test")
        self.assertEqual(message.embeds, [])
        self.assertIsNone(message.avatar_url)
    
    def test_message_with_embeds(self):
        """Testa mensagem com embeds"""
        embeds = [{"title": "Teste", "color": 0x44ff44}]
        message = DiscordMessage(
            content="",
            embeds=embeds
        )
        
        self.assertEqual(message.embeds, embeds)


class TestDiscordNotifier(unittest.TestCase):
    """Testes principais para DiscordNotifier"""
    
    def setUp(self):
        """Setup para cada teste"""
        self.config = NotificationConfig(
            webhook_url="https://discord.com/api/webhooks/test/123",
            enabled=True,
            rate_limit_seconds=1  # Reduzido para testes
        )
        self.notifier = DiscordNotifier(self.config)
    
    def tearDown(self):
        """Cleanup após cada teste"""
        if self.notifier._running:
            self.notifier.stop_sender()
    
    def test_initialization(self):
        """Testa inicialização do notificador"""
        self.assertEqual(self.notifier.config, self.config)
        self.assertEqual(self.notifier.sent_count, 0)
        self.assertEqual(self.notifier.failed_count, 0)
        self.assertEqual(self.notifier.rate_limited_count, 0)
        self.assertFalse(self.notifier._running)
        self.assertIsInstance(self.notifier.templates, dict)
    
    def test_sender_start_stop(self):
        """Testa iniciar e parar sender"""
        # Iniciar
        result = self.notifier.start_sender()
        self.assertTrue(result)
        self.assertTrue(self.notifier._running)
        self.assertIsNotNone(self.notifier._sender_thread)
        
        # Parar
        result = self.notifier.stop_sender()
        self.assertTrue(result)
        self.assertFalse(self.notifier._running)
    
    def test_sender_already_running(self):
        """Testa iniciar sender já rodando"""
        self.notifier.start_sender()
        
        # Tentar iniciar novamente
        result = self.notifier.start_sender()
        self.assertFalse(result)
        
        self.notifier.stop_sender()
    
    def test_should_send_notification_disabled(self):
        """Testa notificação desabilitada"""
        self.config.enabled = False
        
        result = self.notifier._should_send_notification(NotificationType.QUARANTINE_ADD)
        self.assertFalse(result)
    
    def test_should_send_notification_no_webhook(self):
        """Testa sem webhook configurado"""
        self.config.webhook_url = None
        
        result = self.notifier._should_send_notification(NotificationType.QUARANTINE_ADD)
        self.assertFalse(result)
    
    def test_should_send_notification_rate_limit(self):
        """Testa rate limiting"""
        notification_type = NotificationType.QUARANTINE_ADD
        
        # Primeira vez deve permitir
        result = self.notifier._should_send_notification(notification_type)
        self.assertTrue(result)
        
        # Simular envio
        self.notifier.last_notification[notification_type.value] = time.time()
        
        # Segunda vez deve bloquear (rate limit)
        result = self.notifier._should_send_notification(notification_type)
        self.assertFalse(result)
        self.assertEqual(self.notifier.rate_limited_count, 1)
    
    def test_queue_message(self):
        """Testa adicionar mensagem à fila"""
        message = DiscordMessage(content="Teste")
        
        result = self.notifier._queue_message(
            message, 
            NotificationType.QUARANTINE_ADD,
            NotificationPriority.NORMAL
        )
        
        self.assertTrue(result)
        self.assertEqual(len(self.notifier._send_queue), 1)
        self.assertEqual(self.notifier.notification_count[NotificationType.QUARANTINE_ADD.value], 1)
    
    def test_queue_message_priority(self):
        """Testa prioridade na fila"""
        # Adicionar mensagem normal
        normal_msg = DiscordMessage(content="Normal")
        self.notifier._queue_message(
            normal_msg,
            NotificationType.DAILY_SUMMARY,
            NotificationPriority.NORMAL
        )
        
        # Adicionar mensagem crítica (deve ir para frente)
        critical_msg = DiscordMessage(content="Crítico")
        self.notifier._queue_message(
            critical_msg,
            NotificationType.ERROR_CRITICAL,
            NotificationPriority.CRITICAL
        )
        
        # Crítica deve estar na frente
        first_item = self.notifier._send_queue[0]
        self.assertEqual(first_item["priority"], NotificationPriority.CRITICAL)
        self.assertEqual(first_item["message"].content, "Crítico")
    
    def test_notify_quarantine_add(self):
        """Testa notificação de quarentena"""
        with patch.object(self.notifier, '_should_send_notification', return_value=True):
            with patch.object(self.notifier, '_queue_message', return_value=True) as mock_queue:
                
                result = self.notifier.notify_quarantine_add(
                    "One Piece",
                    "mangayabu", 
                    10,
                    "Timeout error"
                )
                
                self.assertTrue(result)
                mock_queue.assert_called_once()
                
                # Verificar argumentos
                args = mock_queue.call_args
                message = args[0][0]
                notification_type = args[0][1]
                priority = args[0][2]
                
                self.assertIsInstance(message, DiscordMessage)
                self.assertEqual(notification_type, NotificationType.QUARANTINE_ADD)
                self.assertEqual(priority, NotificationPriority.CRITICAL)
                
                # Verificar conteúdo da mensagem
                self.assertEqual(len(message.embeds), 1)
                embed = message.embeds[0]
                self.assertIn("Quarentena", embed["title"])
                self.assertEqual(embed["color"], 0xff4444)  # Vermelho
                
                # Verificar mention
                self.assertIn(f"<@{self.config.mention_user_id}>", embed["description"])
    
    def test_notify_quarantine_remove(self):
        """Testa notificação de reativação"""
        with patch.object(self.notifier, '_should_send_notification', return_value=True):
            with patch.object(self.notifier, '_queue_message', return_value=True) as mock_queue:
                
                result = self.notifier.notify_quarantine_remove(
                    "Naruto",
                    "scan1",
                    "Problema resolvido"
                )
                
                self.assertTrue(result)
                mock_queue.assert_called_once()
                
                # Verificar tipo e prioridade
                args = mock_queue.call_args
                notification_type = args[0][1]
                priority = args[0][2]
                
                self.assertEqual(notification_type, NotificationType.QUARANTINE_REMOVE)
                self.assertEqual(priority, NotificationPriority.NORMAL)
                
                # Verificar embed
                message = args[0][0]
                embed = message.embeds[0]
                self.assertIn("Reativada", embed["title"])
                self.assertEqual(embed["color"], 0x44ff44)  # Verde
    
    def test_notify_daily_summary(self):
        """Testa resumo diário"""
        with patch.object(self.notifier, '_should_send_notification', return_value=True):
            with patch.object(self.notifier, '_queue_message', return_value=True) as mock_queue:
                
                result = self.notifier.notify_daily_summary(
                    quarantine_count=5,
                    new_quarantines=2,
                    reactivated_count=1,
                    total_uploads=50,
                    success_rate=0.92
                )
                
                self.assertTrue(result)
                
                # Verificar cor baseada na taxa de sucesso (>90% = verde)
                message = mock_queue.call_args[0][0]
                embed = message.embeds[0]
                self.assertEqual(embed["color"], 0x44ff44)  # Verde
    
    def test_notify_daily_summary_low_success(self):
        """Testa resumo diário com baixa taxa de sucesso"""
        with patch.object(self.notifier, '_should_send_notification', return_value=True):
            with patch.object(self.notifier, '_queue_message', return_value=True) as mock_queue:
                
                result = self.notifier.notify_daily_summary(
                    quarantine_count=10,
                    new_quarantines=5,
                    reactivated_count=0,
                    total_uploads=20,
                    success_rate=0.6  # Baixa taxa
                )
                
                self.assertTrue(result)
                
                # Verificar cor vermelha para baixa performance
                message = mock_queue.call_args[0][0]
                embed = message.embeds[0]
                self.assertEqual(embed["color"], 0xff4444)  # Vermelho
    
    def test_notify_system_error(self):
        """Testa notificação de erro crítico"""
        with patch.object(self.notifier, '_should_send_notification', return_value=True):
            with patch.object(self.notifier, '_queue_message', return_value=True) as mock_queue:
                
                result = self.notifier.notify_system_error(
                    "Database connection failed",
                    "DatabaseManager",
                    {"attempts": 3, "last_error": "Timeout"}
                )
                
                self.assertTrue(result)
                
                # Verificar tipo crítico
                args = mock_queue.call_args
                priority = args[0][2]
                self.assertEqual(priority, NotificationPriority.CRITICAL)
                
                # Verificar mention no embed
                message = args[0][0]
                embed = message.embeds[0]
                self.assertIn(f"<@{self.config.mention_user_id}>", embed["description"])
                self.assertEqual(embed["color"], 0xdd2222)  # Vermelho escuro
    
    def test_notify_system_status(self):
        """Testa notificação de status"""
        with patch.object(self.notifier, '_should_send_notification', return_value=True):
            with patch.object(self.notifier, '_queue_message', return_value=True) as mock_queue:
                
                result = self.notifier.notify_system_status(
                    "online",
                    "2 days 5 hours",
                    active_jobs=3,
                    queue_size=15
                )
                
                self.assertTrue(result)
                
                # Verificar emoji e cor para status online
                message = mock_queue.call_args[0][0]
                embed = message.embeds[0]
                self.assertIn("🟢", embed["title"])
                self.assertEqual(embed["color"], 0x44ff44)  # Verde
    
    def test_send_custom_message(self):
        """Testa mensagem customizada"""
        with patch.object(self.notifier, '_queue_message', return_value=True) as mock_queue:
            
            embeds = [{"title": "Custom", "color": 0x0099ff}]
            result = self.notifier.send_custom_message(
                "Mensagem personalizada",
                embeds,
                NotificationPriority.HIGH
            )
            
            self.assertTrue(result)
            
            # Verificar argumentos
            args = mock_queue.call_args
            message = args[0][0]
            priority = args[0][2]
            
            self.assertEqual(message.content, "Mensagem personalizada")
            self.assertEqual(message.embeds, embeds)
            self.assertEqual(priority, NotificationPriority.HIGH)
    
    @patch('aiohttp.ClientSession')
    async def test_send_message_async_success(self, mock_session):
        """Testa envio assíncrono bem-sucedido"""
        # Mock da resposta HTTP
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        
        mock_session.return_value.__aenter__.return_value.post.return_value = mock_response
        
        message = DiscordMessage(content="Teste")
        result = await self.notifier._send_message_async(message)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["status_code"], 204)
        self.assertIn("response_time", result)
    
    @patch('aiohttp.ClientSession')
    async def test_send_message_async_failure(self, mock_session):
        """Testa envio assíncrono com falha"""
        # Mock da resposta de erro
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text.return_value = "Bad Request"
        mock_response.__aenter__.return_value = mock_response
        
        mock_session.return_value.__aenter__.return_value.post.return_value = mock_response
        
        message = DiscordMessage(content="Teste")
        result = await self.notifier._send_message_async(message)
        
        self.assertFalse(result["success"])
        self.assertEqual(result["status_code"], 400)
        self.assertIn("Bad Request", result["error"])
    
    def test_get_statistics(self):
        """Testa obtenção de estatísticas"""
        # Simular algumas estatísticas
        self.notifier.sent_count = 10
        self.notifier.failed_count = 2
        self.notifier.rate_limited_count = 1
        self.notifier.last_notification["quarantine_add"] = time.time()
        
        stats = self.notifier.get_statistics()
        
        self.assertEqual(stats["sent_count"], 10)
        self.assertEqual(stats["failed_count"], 2)
        self.assertEqual(stats["rate_limited_count"], 1)
        self.assertAlmostEqual(stats["success_rate"], 10/12, places=2)
        self.assertTrue(stats["webhook_configured"])
        self.assertIn("quarantine_add", stats["last_notifications"])
    
    @patch('aiohttp.ClientSession')
    async def test_test_webhook_success(self, mock_session):
        """Testa teste de webhook bem-sucedido"""
        # Mock resposta de sucesso
        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__.return_value = mock_response
        
        mock_session.return_value.__aenter__.return_value.post.return_value = mock_response
        
        result = self.notifier.test_webhook()
        
        self.assertTrue(result["success"])
        self.assertIn("sucesso", result["message"])
    
    def test_test_webhook_no_url(self):
        """Testa teste de webhook sem URL"""
        self.config.webhook_url = None
        
        result = self.notifier.test_webhook()
        
        self.assertFalse(result["success"])
        self.assertIn("não configurada", result["error"])


class TestSingletonNotifier(unittest.TestCase):
    """Testa padrão singleton"""
    
    def test_get_discord_notifier_singleton(self):
        """Testa obtenção de instância singleton"""
        # Limpar instância global
        import notifications.discord
        notifications.discord.notifier_instance = None
        
        # Obter primeira instância
        notifier1 = get_discord_notifier()
        
        # Obter segunda instância (deve ser a mesma)
        notifier2 = get_discord_notifier()
        
        self.assertIs(notifier1, notifier2)
        self.assertIsInstance(notifier1, DiscordNotifier)


class TestIntegrationWithQuarantine(unittest.TestCase):
    """Testes de integração com sistema de quarentena"""
    
    def setUp(self):
        """Setup para testes de integração"""
        self.config = NotificationConfig(
            webhook_url="https://discord.com/api/webhooks/test/123",
            enabled=True,
            rate_limit_seconds=0  # Sem rate limit para testes
        )
        self.notifier = DiscordNotifier(self.config)
    
    def test_quarantine_workflow(self):
        """Testa fluxo completo de quarentena"""
        with patch.object(self.notifier, '_queue_message', return_value=True) as mock_queue:
            
            # Simular obra indo para quarentena
            result1 = self.notifier.notify_quarantine_add(
                "Attack on Titan",
                "mangahost",
                10,
                "Connection timeout"
            )
            self.assertTrue(result1)
            
            # Simular obra sendo reativada
            result2 = self.notifier.notify_quarantine_remove(
                "Attack on Titan",
                "mangahost",
                "Site voltou ao ar"
            )
            self.assertTrue(result2)
            
            # Verificar que foram feitas 2 chamadas
            self.assertEqual(mock_queue.call_count, 2)
            
            # Verificar tipos das notificações
            calls = mock_queue.call_args_list
            self.assertEqual(calls[0][0][1], NotificationType.QUARANTINE_ADD)
            self.assertEqual(calls[1][0][1], NotificationType.QUARANTINE_REMOVE)
    
    def test_multiple_quarantines_rate_limit(self):
        """Testa rate limiting com múltiplas quarentenas"""
        # Primeira quarentena - deve passar
        with patch.object(self.notifier, '_should_send_notification', return_value=True):
            result1 = self.notifier.notify_quarantine_add("Obra 1", "scan1", 10)
            self.assertTrue(result1)
        
        # Segunda quarentena imediata - deve ser bloqueada por rate limit
        with patch.object(self.notifier, '_should_send_notification', return_value=False):
            result2 = self.notifier.notify_quarantine_add("Obra 2", "scan1", 10)
            self.assertFalse(result2)


if __name__ == '__main__':
    # Configurar logging para testes
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Executar testes
    unittest.main(verbosity=2)