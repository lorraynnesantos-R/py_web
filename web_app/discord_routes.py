"""
Interface Web para Testes do Sistema Discord
===========================================

Interface web para testar notificações Discord e configurar o sistema.
Permite enviar mensagens de teste, visualizar estatísticas e configurar webhooks.
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
import json
import logging
from datetime import datetime
import os

from ..notifications import get_discord_notifier, NotificationConfig, NotificationPriority

# Configurar logging
logger = logging.getLogger(__name__)

# Blueprint para rotas do Discord
discord_bp = Blueprint('discord', __name__, url_prefix='/discord')


@discord_bp.route('/')
def index():
    """Página principal de testes do Discord"""
    try:
        notifier = get_discord_notifier()
        stats = notifier.get_statistics()
        
        return render_template('discord/index.html', 
                             stats=stats,
                             title="Discord Notifier - Testes")
    
    except Exception as e:
        logger.error(f"Erro ao carregar página Discord: {e}")
        flash(f"Erro ao carregar: {e}", "error")
        return redirect(url_for('main.index'))


@discord_bp.route('/test-webhook', methods=['POST'])
def test_webhook():
    """Testa o webhook do Discord"""
    try:
        notifier = get_discord_notifier()
        result = notifier.test_webhook()
        
        if result["success"]:
            flash("✅ Webhook testado com sucesso!", "success")
        else:
            flash(f"❌ Falha no teste: {result['error']}", "error")
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Erro ao testar webhook: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@discord_bp.route('/send-test-message', methods=['POST'])
def send_test_message():
    """Envia mensagem de teste personalizada"""
    try:
        data = request.get_json()
        
        message_type = data.get('type', 'custom')
        content = data.get('content', '')
        priority = data.get('priority', 'normal')
        
        notifier = get_discord_notifier()
        
        # Converter prioridade
        priority_map = {
            'low': NotificationPriority.LOW,
            'normal': NotificationPriority.NORMAL,
            'high': NotificationPriority.HIGH,
            'critical': NotificationPriority.CRITICAL
        }
        
        notification_priority = priority_map.get(priority, NotificationPriority.NORMAL)
        
        # Enviar mensagem baseada no tipo
        if message_type == 'quarantine_add':
            result = notifier.notify_quarantine_add(
                data.get('obra', 'Obra de Teste'),
                data.get('scan', 'scan_teste'), 
                int(data.get('errors', 10)),
                data.get('error_message', 'Erro de teste')
            )
        
        elif message_type == 'quarantine_remove':
            result = notifier.notify_quarantine_remove(
                data.get('obra', 'Obra de Teste'),
                data.get('scan', 'scan_teste'),
                data.get('reason', 'Teste de reativação')
            )
        
        elif message_type == 'daily_summary':
            result = notifier.notify_daily_summary(
                int(data.get('quarantine_count', 5)),
                int(data.get('new_quarantines', 2)),
                int(data.get('reactivated', 1)),
                int(data.get('total_uploads', 50)),
                float(data.get('success_rate', 0.85))
            )
        
        elif message_type == 'system_error':
            result = notifier.notify_system_error(
                data.get('error_message', 'Erro de teste'),
                data.get('component', 'TestComponent'),
                data.get('details', {})
            )
        
        elif message_type == 'system_status':
            result = notifier.notify_system_status(
                data.get('status', 'online'),
                data.get('uptime', '1 day 2 hours'),
                int(data.get('active_jobs', 3)),
                int(data.get('queue_size', 10))
            )
        
        else:  # custom
            embeds = []
            if data.get('embed_title'):
                embeds.append({
                    "title": data.get('embed_title'),
                    "description": data.get('embed_description', ''),
                    "color": int(data.get('embed_color', '0x0099ff'), 16),
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            result = notifier.send_custom_message(
                content,
                embeds,
                notification_priority
            )
        
        if result:
            return jsonify({
                "success": True,
                "message": "Mensagem enviada com sucesso!"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Falha ao enviar mensagem"
            })
    
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem de teste: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@discord_bp.route('/statistics')
def get_statistics():
    """Retorna estatísticas do notificador"""
    try:
        notifier = get_discord_notifier()
        stats = notifier.get_statistics()
        
        return jsonify({
            "success": True,
            "statistics": stats
        })
    
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@discord_bp.route('/configure', methods=['GET', 'POST'])
def configure():
    """Configura o sistema Discord"""
    if request.method == 'POST':
        try:
            data = request.get_json()
            
            # Atualizar configurações
            notifier = get_discord_notifier()
            
            if 'webhook_url' in data:
                notifier.config.webhook_url = data['webhook_url']
            
            if 'enabled' in data:
                notifier.config.enabled = bool(data['enabled'])
            
            if 'rate_limit_seconds' in data:
                notifier.config.rate_limit_seconds = int(data['rate_limit_seconds'])
            
            if 'mention_user_id' in data:
                notifier.config.mention_user_id = data['mention_user_id']
            
            if 'bot_username' in data:
                notifier.config.bot_username = data['bot_username']
            
            # Reiniciar sender se necessário
            if notifier._running:
                notifier.stop_sender()
                notifier.start_sender()
            
            flash("✅ Configurações atualizadas!", "success")
            
            return jsonify({
                "success": True,
                "message": "Configurações salvas com sucesso!"
            })
        
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    else:
        # GET - mostrar página de configuração
        try:
            notifier = get_discord_notifier()
            config = {
                "webhook_url": notifier.config.webhook_url or "",
                "enabled": notifier.config.enabled,
                "rate_limit_seconds": notifier.config.rate_limit_seconds,
                "mention_user_id": notifier.config.mention_user_id,
                "bot_username": notifier.config.bot_username,
                "bot_avatar_url": notifier.config.bot_avatar_url
            }
            
            return render_template('discord/configure.html',
                                 config=config,
                                 title="Configurar Discord")
        
        except Exception as e:
            logger.error(f"Erro ao carregar configurações: {e}")
            flash(f"Erro ao carregar: {e}", "error")
            return redirect(url_for('discord.index'))


@discord_bp.route('/start-sender', methods=['POST'])
def start_sender():
    """Inicia o sender de notificações"""
    try:
        notifier = get_discord_notifier()
        result = notifier.start_sender()
        
        if result:
            flash("✅ Sender iniciado com sucesso!", "success")
            return jsonify({
                "success": True,
                "message": "Sender iniciado!"
            })
        else:
            flash("⚠️ Sender já estava rodando", "warning")
            return jsonify({
                "success": False,
                "error": "Sender já estava rodando"
            })
    
    except Exception as e:
        logger.error(f"Erro ao iniciar sender: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@discord_bp.route('/stop-sender', methods=['POST'])
def stop_sender():
    """Para o sender de notificações"""
    try:
        notifier = get_discord_notifier()
        result = notifier.stop_sender()
        
        if result:
            flash("✅ Sender parado com sucesso!", "success")
            return jsonify({
                "success": True,
                "message": "Sender parado!"
            })
        else:
            flash("⚠️ Sender não estava rodando", "warning")
            return jsonify({
                "success": False,
                "error": "Sender não estava rodando"
            })
    
    except Exception as e:
        logger.error(f"Erro ao parar sender: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@discord_bp.route('/clear-queue', methods=['POST'])
def clear_queue():
    """Limpa a fila de notificações"""
    try:
        notifier = get_discord_notifier()
        queue_size = len(notifier._send_queue)
        notifier._send_queue.clear()
        
        flash(f"��� Fila limpa! {queue_size} mensagens removidas.", "success")
        
        return jsonify({
            "success": True,
            "message": f"Fila limpa! {queue_size} mensagens removidas."
        })
    
    except Exception as e:
        logger.error(f"Erro ao limpar fila: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@discord_bp.route('/reset-statistics', methods=['POST'])
def reset_statistics():
    """Reseta estatísticas do notificador"""
    try:
        notifier = get_discord_notifier()
        
        notifier.sent_count = 0
        notifier.failed_count = 0
        notifier.rate_limited_count = 0
        notifier.last_notification.clear()
        notifier.notification_count.clear()
        
        flash("✅ Estatísticas resetadas!", "success")
        
        return jsonify({
            "success": True,
            "message": "Estatísticas resetadas!"
        })
    
    except Exception as e:
        logger.error(f"Erro ao resetar estatísticas: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# Template filters para o Discord
@discord_bp.app_template_filter('discord_status')
def discord_status_filter(enabled, webhook_configured, sender_running):
    """Retorna status colorido do Discord"""
    if not enabled:
        return '<span class="badge bg-secondary">Desabilitado</span>'
    elif not webhook_configured:
        return '<span class="badge bg-warning">Webhook não configurado</span>'
    elif not sender_running:
        return '<span class="badge bg-danger">Sender parado</span>'
    else:
        return '<span class="badge bg-success">Ativo</span>'


@discord_bp.app_template_filter('notification_type_icon')
def notification_type_icon(notification_type):
    """Retorna ícone para tipo de notificação"""
    icons = {
        'quarantine_add': '🚨',
        'quarantine_remove': '✅',
        'daily_summary': '📊',
        'error_critical': '🔥',
        'system_status': '🟢'
    }
    return icons.get(notification_type, '📨')


@discord_bp.app_template_filter('priority_badge')
def priority_badge(priority):
    """Retorna badge colorido para prioridade"""
    badges = {
        'LOW': '<span class="badge bg-info">Baixa</span>',
        'NORMAL': '<span class="badge bg-primary">Normal</span>',
        'HIGH': '<span class="badge bg-warning">Alta</span>',
        'CRITICAL': '<span class="badge bg-danger">Crítica</span>'
    }
    return badges.get(str(priority), '<span class="badge bg-secondary">Desconhecida</span>')


if __name__ == '__main__':
    # Para testes diretos
    from flask import Flask
    
    app = Flask(__name__)
    app.secret_key = 'discord_test_key'
    app.register_blueprint(discord_bp)
    
    app.run(debug=True, port=5001)