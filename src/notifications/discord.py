"""
Sistema de Notificações Discord - DiscordNotifier
================================================

Sistema de notificações via Discord webhook para avisar sobre obras 
colocadas em quarentena e outros eventos importantes do sistema.

Features:
- Webhook configurável via environment variable
- Templates de mensagens personalizáveis
- Rate limiting para evitar spam
- Fallback para logs caso webhook falhe
- Interface web para testar notificações
- Configuração on/off para notificações
- Mention específico para alertas críticos
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import threading
from collections import defaultdict, deque
from pathlib import Path

# Configuração de logging
logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Tipos de notificação"""
    QUARANTINE_ADD = "quarantine_add"        # Obra colocada em quarentena
    QUARANTINE_REMOVE = "quarantine_remove"  # Obra reativada
    DAILY_SUMMARY = "daily_summary"          # Resumo diário
    ERROR_CRITICAL = "error_critical"        # Erro crítico do sistema
    SYSTEM_STATUS = "system_status"          # Status do sistema


class NotificationPriority(Enum):
    """Prioridades de notificação"""
    LOW = 1      # Informativo
    NORMAL = 2   # Normal
    HIGH = 3     # Importante
    CRITICAL = 4 # Crítico (com mention)


@dataclass
class DiscordMessage:
    """Representa uma mensagem do Discord"""
    content: str
    embeds: List[Dict[str, Any]] = None
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    
    def __post_init__(self):
        if self.embeds is None:
            self.embeds = []


@dataclass
class NotificationConfig:
    """Configurações do sistema de notificações"""
    webhook_url: Optional[str] = None
    enabled: bool = True
    rate_limit_seconds: int = 30  # Mínimo entre notificações do mesmo tipo
    max_retries: int = 3
    timeout_seconds: int = 10
    mention_user_id: str = "221057164351897610"  # ID do usuário para mention
    bot_username: str = "MediocreToons Bot"
    bot_avatar_url: str = "https://cdn.discordapp.com/embed/avatars/0.png"


class DiscordNotifier:
    """
    Sistema de notificações Discord via webhook
    
    Features principais:
    - Notificações automáticas para eventos do sistema
    - Templates personalizáveis de mensagens
    - Rate limiting inteligente
    - Fallback para logs
    - Interface web para testes
    - Mention específico para alertas críticos
    """
    
    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or NotificationConfig()
        
        # Rate limiting por tipo de notificação
        self.last_notification = defaultdict(float)
        self.notification_count = defaultdict(int)
        
        # Templates de mensagens
        self.templates = self._load_message_templates()
        
        # Estatísticas
        self.sent_count = 0
        self.failed_count = 0
        self.rate_limited_count = 0
        
        # Threading para envios assíncronos
        self._send_queue = deque()
        self._sender_thread = None
        self._running = False
        self._stop_event = threading.Event()
        
        logger.info("DiscordNotifier inicializado")
    
    def start_sender(self) -> bool:
        """
        Inicia thread de envio assíncrono
        
        Returns:
            bool: True se iniciado com sucesso
        """
        try:
            if self._running:
                logger.warning("Sender já está rodando")
                return False
            
            self._running = True
            self._stop_event.clear()
            
            self._sender_thread = threading.Thread(
                target=self._sender_loop,
                daemon=True,
                name="DiscordNotifierSender"
            )
            self._sender_thread.start()
            
            logger.info("Discord sender iniciado")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao iniciar sender: {e}")
            return False
    
    def stop_sender(self) -> bool:
        """
        Para thread de envio assíncrono
        
        Returns:
            bool: True se parado com sucesso
        """
        try:
            if not self._running:
                logger.warning("Sender não está rodando")
                return False
            
            self._running = False
            self._stop_event.set()
            
            # Aguardar thread terminar
            if self._sender_thread and self._sender_thread.is_alive():
                self._sender_thread.join(timeout=5)
            
            logger.info("Discord sender parado")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao parar sender: {e}")
            return False
    
    def notify_quarantine_add(
        self, 
        obra_titulo: str, 
        scan_name: str, 
        error_count: int,
        last_error: str = None
    ) -> bool:
        """
        Notifica sobre obra colocada em quarentena
        
        Args:
            obra_titulo: Título da obra
            scan_name: Nome do scan
            error_count: Número de erros
            last_error: Último erro registrado
            
        Returns:
            bool: True se notificação foi agendada
        """
        if not self._should_send_notification(NotificationType.QUARANTINE_ADD):
            return False
        
        # Criar mensagem com mention para alertas críticos
        mention = f"<@{self.config.mention_user_id}>"
        
        embed = {
            "title": "🚨 Obra em Quarentena",
            "description": f"{mention} Uma obra foi colocada em quarentena após {error_count} erros consecutivos.",
            "color": 0xff4444,  # Vermelho
            "fields": [
                {
                    "name": "📚 Obra",
                    "value": obra_titulo,
                    "inline": True
                },
                {
                    "name": "🌐 Scan",
                    "value": scan_name,
                    "inline": True
                },
                {
                    "name": "❌ Erros",
                    "value": str(error_count),
                    "inline": True
                }
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "Sistema de Auto-Upload MediocreToons",
                "icon_url": self.config.bot_avatar_url
            }
        }
        
        if last_error:
            embed["fields"].append({
                "name": "🔍 Último Erro",
                "value": last_error[:1000],  # Limitar tamanho
                "inline": False
            })
        
        message = DiscordMessage(
            content="",
            embeds=[embed],
            username=self.config.bot_username,
            avatar_url=self.config.bot_avatar_url
        )
        
        return self._queue_message(message, NotificationType.QUARANTINE_ADD, NotificationPriority.CRITICAL)
    
    def notify_quarantine_remove(
        self, 
        obra_titulo: str, 
        scan_name: str,
        reason: str = "Reativação manual"
    ) -> bool:
        """
        Notifica sobre obra reativada da quarentena
        
        Args:
            obra_titulo: Título da obra
            scan_name: Nome do scan  
            reason: Motivo da reativação
            
        Returns:
            bool: True se notificação foi agendada
        """
        if not self._should_send_notification(NotificationType.QUARANTINE_REMOVE):
            return False
        
        embed = {
            "title": "✅ Obra Reativada",
            "description": "Uma obra foi reativada e removida da quarentena.",
            "color": 0x44ff44,  # Verde
            "fields": [
                {
                    "name": "📚 Obra",
                    "value": obra_titulo,
                    "inline": True
                },
                {
                    "name": "🌐 Scan", 
                    "value": scan_name,
                    "inline": True
                },
                {
                    "name": "🔄 Motivo",
                    "value": reason,
                    "inline": False
                }
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "Sistema de Auto-Upload MediocreToons",
                "icon_url": self.config.bot_avatar_url
            }
        }
        
        message = DiscordMessage(
            content="",
            embeds=[embed],
            username=self.config.bot_username,
            avatar_url=self.config.bot_avatar_url
        )
        
        return self._queue_message(message, NotificationType.QUARANTINE_REMOVE, NotificationPriority.NORMAL)
    
    def notify_daily_summary(
        self, 
        quarantine_count: int,
        new_quarantines: int,
        reactivated_count: int,
        total_uploads: int,
        success_rate: float
    ) -> bool:
        """
        Envia resumo diário das atividades
        
        Args:
            quarantine_count: Total de obras em quarentena
            new_quarantines: Novas quarentenas hoje
            reactivated_count: Obras reativadas hoje
            total_uploads: Total de uploads hoje
            success_rate: Taxa de sucesso hoje
            
        Returns:
            bool: True se notificação foi agendada
        """
        if not self._should_send_notification(NotificationType.DAILY_SUMMARY):
            return False
        
        # Escolher cor baseada na performance
        if success_rate >= 0.9:
            color = 0x44ff44  # Verde (boa)
        elif success_rate >= 0.7:
            color = 0xffaa44  # Amarelo (ok)
        else:
            color = 0xff4444  # Vermelho (ruim)
        
        embed = {
            "title": "📊 Resumo Diário - MediocreToons",
            "description": f"Relatório das atividades de {datetime.now().strftime('%d/%m/%Y')}",
            "color": color,
            "fields": [
                {
                    "name": "📈 Uploads Hoje",
                    "value": str(total_uploads),
                    "inline": True
                },
                {
                    "name": "✅ Taxa de Sucesso",
                    "value": f"{success_rate:.1%}",
                    "inline": True
                },
                {
                    "name": "🚨 Em Quarentena",
                    "value": str(quarantine_count),
                    "inline": True
                },
                {
                    "name": "⚠️ Novas Quarentenas",
                    "value": str(new_quarantines),
                    "inline": True
                },
                {
                    "name": "🔄 Reativadas",
                    "value": str(reactivated_count),
                    "inline": True
                },
                {
                    "name": "⏱️ Próximo Resumo",
                    "value": "Amanhã às 20:00",
                    "inline": True
                }
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "Sistema de Auto-Upload MediocreToons",
                "icon_url": self.config.bot_avatar_url
            }
        }
        
        message = DiscordMessage(
            content="",
            embeds=[embed],
            username=self.config.bot_username,
            avatar_url=self.config.bot_avatar_url
        )
        
        return self._queue_message(message, NotificationType.DAILY_SUMMARY, NotificationPriority.LOW)
    
    def notify_system_error(
        self, 
        error_message: str,
        component: str = "Sistema",
        details: Dict[str, Any] = None
    ) -> bool:
        """
        Notifica sobre erro crítico do sistema
        
        Args:
            error_message: Mensagem de erro
            component: Componente que gerou o erro
            details: Detalhes adicionais
            
        Returns:
            bool: True se notificação foi agendada
        """
        if not self._should_send_notification(NotificationType.ERROR_CRITICAL):
            return False
        
        mention = f"<@{self.config.mention_user_id}>"
        
        embed = {
            "title": "🔥 Erro Crítico do Sistema",
            "description": f"{mention} Um erro crítico foi detectado no sistema.",
            "color": 0xdd2222,  # Vermelho escuro
            "fields": [
                {
                    "name": "🔧 Componente",
                    "value": component,
                    "inline": True
                },
                {
                    "name": "⚡ Erro",
                    "value": error_message[:1000],
                    "inline": False
                }
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "Sistema de Auto-Upload MediocreToons",
                "icon_url": self.config.bot_avatar_url
            }
        }
        
        if details:
            details_str = "\n".join([f"**{k}**: {v}" for k, v in details.items()])
            embed["fields"].append({
                "name": "📋 Detalhes",
                "value": details_str[:1000],
                "inline": False
            })
        
        message = DiscordMessage(
            content="",
            embeds=[embed],
            username=self.config.bot_username,
            avatar_url=self.config.bot_avatar_url
        )
        
        return self._queue_message(message, NotificationType.ERROR_CRITICAL, NotificationPriority.CRITICAL)
    
    def notify_system_status(
        self, 
        status: str,
        uptime: str = None,
        active_jobs: int = 0,
        queue_size: int = 0
    ) -> bool:
        """
        Notifica sobre status do sistema
        
        Args:
            status: Status atual (online/offline/maintenance)
            uptime: Tempo de atividade
            active_jobs: Jobs ativos
            queue_size: Tamanho da fila
            
        Returns:
            bool: True se notificação foi agendada
        """
        if not self._should_send_notification(NotificationType.SYSTEM_STATUS):
            return False
        
        # Escolher emoji e cor baseado no status
        if status.lower() == "online":
            emoji = "🟢"
            color = 0x44ff44
        elif status.lower() == "offline":
            emoji = "🔴"
            color = 0xff4444
        else:
            emoji = "🟡"
            color = 0xffaa44
        
        embed = {
            "title": f"{emoji} Status do Sistema",
            "description": f"Sistema está **{status.upper()}**",
            "color": color,
            "fields": [
                {
                    "name": "⚡ Jobs Ativos",
                    "value": str(active_jobs),
                    "inline": True
                },
                {
                    "name": "📋 Fila",
                    "value": str(queue_size),
                    "inline": True
                }
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "Sistema de Auto-Upload MediocreToons",
                "icon_url": self.config.bot_avatar_url
            }
        }
        
        if uptime:
            embed["fields"].append({
                "name": "⏱️ Uptime",
                "value": uptime,
                "inline": True
            })
        
        message = DiscordMessage(
            content="",
            embeds=[embed],
            username=self.config.bot_username,
            avatar_url=self.config.bot_avatar_url
        )
        
        return self._queue_message(message, NotificationType.SYSTEM_STATUS, NotificationPriority.NORMAL)
    
    def send_custom_message(
        self, 
        content: str, 
        embeds: List[Dict] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> bool:
        """
        Envia mensagem customizada
        
        Args:
            content: Conteúdo da mensagem
            embeds: Embeds opcionais
            priority: Prioridade da mensagem
            
        Returns:
            bool: True se mensagem foi agendada
        """
        message = DiscordMessage(
            content=content,
            embeds=embeds or [],
            username=self.config.bot_username,
            avatar_url=self.config.bot_avatar_url
        )
        
        return self._queue_message(message, NotificationType.SYSTEM_STATUS, priority)
    
    def test_webhook(self) -> Dict[str, Any]:
        """
        Testa o webhook do Discord
        
        Returns:
            Dict com resultado do teste
        """
        if not self.config.webhook_url:
            return {
                "success": False,
                "error": "Webhook URL não configurada",
                "details": "Configure DISCORD_WEBHOOK_URL no .env"
            }
        
        test_message = DiscordMessage(
            content="🧪 **Teste de Webhook**\n\nEste é um teste do sistema de notificações Discord.",
            embeds=[{
                "title": "✅ Teste Bem-sucedido",
                "description": "O webhook está funcionando corretamente!",
                "color": 0x44ff44,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "Sistema de Auto-Upload MediocreToons - Teste",
                    "icon_url": self.config.bot_avatar_url
                }
            }],
            username=self.config.bot_username,
            avatar_url=self.config.bot_avatar_url
        )
        
        try:
            # Enviar diretamente (síncrono para teste)
            result = asyncio.run(self._send_message_async(test_message))
            
            if result["success"]:
                return {
                    "success": True,
                    "message": "Webhook testado com sucesso!",
                    "details": f"Mensagem enviada em {result.get('response_time', 0):.2f}s"
                }
            else:
                return {
                    "success": False,
                    "error": "Falha no envio",
                    "details": result.get("error", "Erro desconhecido")
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": "Erro na execução do teste",
                "details": str(e)
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do sistema de notificações
        
        Returns:
            Dict com estatísticas
        """
        return {
            "enabled": self.config.enabled,
            "webhook_configured": bool(self.config.webhook_url),
            "sent_count": self.sent_count,
            "failed_count": self.failed_count,
            "rate_limited_count": self.rate_limited_count,
            "success_rate": self.sent_count / max(1, self.sent_count + self.failed_count),
            "queue_size": len(self._send_queue),
            "last_notifications": dict(self.last_notification),
            "notification_counts": dict(self.notification_count),
            "sender_running": self._running
        }
    
    def _should_send_notification(self, notification_type: NotificationType) -> bool:
        """
        Verifica se deve enviar notificação (rate limiting)
        
        Args:
            notification_type: Tipo da notificação
            
        Returns:
            bool: True se pode enviar
        """
        if not self.config.enabled:
            logger.debug("Notificações desabilitadas")
            return False
        
        if not self.config.webhook_url:
            logger.debug("Webhook URL não configurada")
            return False
        
        # Verificar rate limiting
        current_time = time.time()
        last_sent = self.last_notification.get(notification_type.value, 0)
        
        if current_time - last_sent < self.config.rate_limit_seconds:
            self.rate_limited_count += 1
            logger.debug(f"Rate limit ativo para {notification_type.value}")
            return False
        
        return True
    
    def _queue_message(
        self, 
        message: DiscordMessage, 
        notification_type: NotificationType,
        priority: NotificationPriority
    ) -> bool:
        """
        Adiciona mensagem à fila de envio
        
        Args:
            message: Mensagem a enviar
            notification_type: Tipo da notificação
            priority: Prioridade
            
        Returns:
            bool: True se adicionado à fila
        """
        try:
            # Atualizar timestamp de última notificação
            self.last_notification[notification_type.value] = time.time()
            self.notification_count[notification_type.value] += 1
            
            # Adicionar à fila (com prioridade)
            queue_item = {
                "message": message,
                "type": notification_type,
                "priority": priority,
                "timestamp": time.time()
            }
            
            # Inserir por prioridade (crítico primeiro)
            if priority == NotificationPriority.CRITICAL:
                self._send_queue.appendleft(queue_item)
            else:
                self._send_queue.append(queue_item)
            
            logger.info(f"Mensagem {notification_type.value} adicionada à fila")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao adicionar mensagem à fila: {e}")
            return False
    
    def _sender_loop(self):
        """Loop da thread de envio assíncrono"""
        logger.info("Iniciando loop de envio Discord")
        
        while not self._stop_event.is_set():
            try:
                if not self._send_queue:
                    time.sleep(1)
                    continue
                
                # Obter próxima mensagem
                queue_item = self._send_queue.popleft()
                
                # Enviar mensagem
                result = asyncio.run(self._send_message_async(queue_item["message"]))
                
                if result["success"]:
                    self.sent_count += 1
                    logger.info(f"Mensagem {queue_item['type'].value} enviada com sucesso")
                else:
                    self.failed_count += 1
                    logger.error(f"Falha ao enviar {queue_item['type'].value}: {result.get('error')}")
                
                # Pequeno delay entre envios
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Erro no loop de envio: {e}")
                time.sleep(5)
        
        logger.info("Loop de envio Discord finalizado")
    
    async def _send_message_async(self, message: DiscordMessage) -> Dict[str, Any]:
        """
        Envia mensagem via webhook (assíncrono)
        
        Args:
            message: Mensagem a enviar
            
        Returns:
            Dict com resultado
        """
        start_time = time.time()
        
        try:
            # Preparar payload
            payload = {
                "content": message.content,
                "embeds": message.embeds,
                "username": message.username,
                "avatar_url": message.avatar_url
            }
            
            # Remover campos vazios
            payload = {k: v for k, v in payload.items() if v}
            
            # Enviar via webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                ) as response:
                    
                    response_time = time.time() - start_time
                    
                    if response.status == 204:  # Discord webhook success
                        return {
                            "success": True,
                            "status_code": response.status,
                            "response_time": response_time
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "status_code": response.status,
                            "error": f"HTTP {response.status}: {error_text}",
                            "response_time": response_time
                        }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Timeout na requisição",
                "response_time": time.time() - start_time
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response_time": time.time() - start_time
            }
    
    def _load_message_templates(self) -> Dict[str, str]:
        """
        Carrega templates de mensagens personalizáveis
        
        Returns:
            Dict com templates
        """
        return {
            "quarantine_add": "🚨 **{titulo}** foi colocada em quarentena após {erros} erros no scan **{scan}**.",
            "quarantine_remove": "✅ **{titulo}** foi reativada da quarentena no scan **{scan}**.",
            "daily_summary": "📊 Resumo diário: {uploads} uploads, {taxa_sucesso} de sucesso, {quarentenas} em quarentena.",
            "system_error": "🔥 Erro crítico no componente **{componente}**: {erro}",
            "system_status": "🟢 Sistema **{status}** - {jobs} jobs ativos, {fila} na fila"
        }


# Instância global para facilitar uso
notifier_instance = None


def get_discord_notifier(config: NotificationConfig = None) -> DiscordNotifier:
    """
    Obtém instância global do notificador (singleton)
    
    Args:
        config: Configuração personalizada
        
    Returns:
        DiscordNotifier: Instância do notificador
    """
    global notifier_instance
    
    if notifier_instance is None:
        notifier_instance = DiscordNotifier(config)
    
    return notifier_instance


if __name__ == "__main__":
    # Exemplo de uso
    import os
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configurar notificador (webhook seria do .env)
    config = NotificationConfig(
        webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
        enabled=True
    )
    
    notifier = DiscordNotifier(config)
    notifier.start_sender()
    
    try:
        # Testar notificações
        print("Testando notificações...")
        
        # Teste de quarentena
        notifier.notify_quarantine_add(
            "One Piece", 
            "mangayabu", 
            10, 
            "Timeout na conexão"
        )
        
        # Teste de reativação
        notifier.notify_quarantine_remove(
            "Naruto", 
            "scan1", 
            "Problema resolvido"
        )
        
        # Teste de resumo diário
        notifier.notify_daily_summary(5, 2, 1, 50, 0.92)
        
        # Teste de erro crítico
        notifier.notify_system_error(
            "Falha na conexão com a API",
            "AutoUpdateScheduler",
            {"tentativas": 3, "último_erro": "Connection timeout"}
        )
        
        print("Notificações enviadas! Aguardando processamento...")
        time.sleep(10)
        
        # Estatísticas
        stats = notifier.get_statistics()
        print(f"Estatísticas: {json.dumps(stats, indent=2)}")
        
    except KeyboardInterrupt:
        print("\nParando notificador...")
    
    finally:
        notifier.stop_sender()
        print("Notificador parado.")