"""
Rotas Flask para dashboard de Health Check

Este módulo implementa as rotas da web app para visualização
e gerenciamento do sistema de Health Check.
"""

from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
import asyncio
import logging
from datetime import datetime, timezone
import json
from pathlib import Path

from auto_uploader.health_integration import HealthIntegrationManager

# Blueprint para rotas de health check
health_bp = Blueprint('health', __name__, url_prefix='/health')

# Logger
logger = logging.getLogger("health_routes")

# Instância global do health manager
health_manager = None

def init_health_manager(data_dir: Path = None):
    """Inicializa o health manager"""
    global health_manager
    if health_manager is None:
        health_manager = HealthIntegrationManager(data_dir)

def run_async(coro):
    """Executa corrotina em um loop de eventos"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

@health_bp.route('/dashboard')
def dashboard():
    """Página principal do dashboard de saúde"""
    return render_template('health_dashboard.html')

@health_bp.route('/api/status')
def api_status():
    """API endpoint para status atual das APIs"""
    if not health_manager:
        return jsonify({"error": "Health manager não inicializado"}), 500
    
    try:
        # Lista de URLs exemplo - em produção, isso deveria vir da configuração
        provider_urls = [
            "https://api.example1.com/health",
            "https://api.example2.com/health", 
            "https://api.example3.com/health"
        ]
        
        dashboard_data = health_manager.get_health_dashboard_data(provider_urls)
        return jsonify(dashboard_data)
        
    except Exception as e:
        logger.error(f"Erro ao obter status das APIs: {e}")
        return jsonify({"error": str(e)}), 500

@health_bp.route('/api/check', methods=['POST'])
def check_apis():
    """Força verificação das APIs"""
    if not health_manager:
        return jsonify({"error": "Health manager não inicializado"}), 500
    
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        
        if not urls:
            return jsonify({"error": "URLs são obrigatórias"}), 400
        
        # Executar verificação assíncrona
        results = run_async(health_manager.health_checker.check_multiple_urls(urls, use_cache=False))
        
        # Converter resultados para formato JSON serializável
        json_results = {}
        for url, result in results.items():
            json_results[url] = {
                "url": result.url,
                "status": result.status.value,
                "response_time_ms": result.response_time_ms,
                "status_code": result.status_code,
                "error_message": result.error_message,
                "timestamp": result.timestamp,
                "is_healthy": result.is_healthy
            }
        
        return jsonify({
            "success": True,
            "results": json_results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erro ao verificar APIs: {e}")
        return jsonify({"error": str(e)}), 500

@health_bp.route('/api/metrics/<path:url>')
def api_metrics(url):
    """Obtém métricas detalhadas para uma URL"""
    if not health_manager:
        return jsonify({"error": "Health manager não inicializado"}), 500
    
    try:
        # Decodificar URL
        import urllib.parse
        decoded_url = urllib.parse.unquote(url)
        
        # Obter métricas
        metrics = health_manager.health_checker.get_metrics(decoded_url)
        
        if not metrics:
            return jsonify({"error": "Métricas não encontradas para esta URL"}), 404
        
        # Obter resumos de uptime
        uptime_24h = health_manager.health_checker.get_uptime_summary(decoded_url, hours=24)
        uptime_7d = health_manager.health_checker.get_uptime_summary(decoded_url, hours=168)
        
        # Obter histórico recente
        recent_history = health_manager.health_checker.get_recent_history(decoded_url, limit=50)
        
        return jsonify({
            "url": decoded_url,
            "metrics": {
                "total_checks": metrics.total_checks,
                "successful_checks": metrics.successful_checks,
                "failed_checks": metrics.failed_checks,
                "failure_rate": metrics.failure_rate,
                "avg_response_time_ms": metrics.avg_response_time_ms,
                "uptime_percentage": metrics.uptime_percentage,
                "consecutive_failures": metrics.consecutive_failures,
                "consecutive_successes": metrics.consecutive_successes,
                "last_online": metrics.last_online,
                "last_offline": metrics.last_offline
            },
            "uptime_24h": uptime_24h,
            "uptime_7d": uptime_7d,
            "recent_history": [
                {
                    "timestamp": h.timestamp,
                    "status": h.status.value,
                    "response_time_ms": h.response_time_ms,
                    "error_message": h.error_message,
                    "is_healthy": h.is_healthy
                }
                for h in recent_history
            ]
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter métricas para {url}: {e}")
        return jsonify({"error": str(e)}), 500

@health_bp.route('/api/report')
def health_report():
    """Gera relatório completo de saúde"""
    if not health_manager:
        return jsonify({"error": "Health manager não inicializado"}), 500
    
    try:
        # Lista de URLs exemplo
        provider_urls = [
            "https://api.example1.com/health",
            "https://api.example2.com/health",
            "https://api.example3.com/health"
        ]
        
        # Gerar relatório assíncrono
        report = run_async(health_manager.get_provider_health_report(provider_urls))
        
        return jsonify(report)
        
    except Exception as e:
        logger.error(f"Erro ao gerar relatório: {e}")
        return jsonify({"error": str(e)}), 500

@health_bp.route('/config')
def config_page():
    """Página de configuração do health checker"""
    if not health_manager:
        flash("Health manager não inicializado", "error")
        return redirect(url_for('health.dashboard'))
    
    # Obter configurações atuais
    config = health_manager.health_checker.get_config()
    webhooks = health_manager.discord_notifier.list_webhooks()
    
    return render_template('health_config.html', config=config, webhooks=webhooks)

@health_bp.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """API para configuração do health checker"""
    if not health_manager:
        return jsonify({"error": "Health manager não inicializado"}), 500
    
    if request.method == 'GET':
        config = health_manager.health_checker.get_config()
        webhooks = health_manager.discord_notifier.list_webhooks()
        
        return jsonify({
            "config": config,
            "webhooks": webhooks
        })
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            # Atualizar configuração do health checker
            if 'config' in data:
                health_manager.health_checker.update_config(data['config'])
            
            # Atualizar webhooks
            if 'webhooks' in data:
                for webhook_name, webhook_data in data['webhooks'].items():
                    if webhook_data.get('action') == 'add':
                        health_manager.discord_notifier.add_webhook(
                            webhook_name,
                            webhook_data['url'],
                            webhook_data.get('username', 'Health Monitor'),
                            webhook_data.get('avatar_url'),
                            webhook_data.get('enabled', True)
                        )
                    elif webhook_data.get('action') == 'remove':
                        health_manager.discord_notifier.remove_webhook(webhook_name)
            
            return jsonify({"success": True, "message": "Configuração atualizada"})
            
        except Exception as e:
            logger.error(f"Erro ao atualizar configuração: {e}")
            return jsonify({"error": str(e)}), 500

@health_bp.route('/api/webhook/test/<name>', methods=['POST'])
def test_webhook(name):
    """Testa um webhook específico"""
    if not health_manager:
        return jsonify({"error": "Health manager não inicializado"}), 500
    
    try:
        result = run_async(health_manager.discord_notifier.test_webhook(name))
        
        if result:
            return jsonify({"success": True, "message": f"Webhook '{name}' testado com sucesso"})
        else:
            return jsonify({"success": False, "message": f"Falha ao testar webhook '{name}'"})
            
    except Exception as e:
        logger.error(f"Erro ao testar webhook {name}: {e}")
        return jsonify({"error": str(e)}), 500

@health_bp.route('/api/notifications')
def notification_history():
    """Obtém histórico de notificações"""
    if not health_manager:
        return jsonify({"error": "Health manager não inicializado"}), 500
    
    try:
        limit = request.args.get('limit', 50, type=int)
        history = health_manager.discord_notifier.get_notification_history(limit)
        
        return jsonify({
            "notifications": history,
            "total": len(history)
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter histórico de notificações: {e}")
        return jsonify({"error": str(e)}), 500

@health_bp.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """Limpa cache de health checks"""
    if not health_manager:
        return jsonify({"error": "Health manager não inicializado"}), 500
    
    try:
        health_manager.health_checker.clear_cache()
        return jsonify({"success": True, "message": "Cache limpo com sucesso"})
        
    except Exception as e:
        logger.error(f"Erro ao limpar cache: {e}")
        return jsonify({"error": str(e)}), 500

@health_bp.route('/monitoring')
def monitoring_page():
    """Página de monitoramento em tempo real"""
    return render_template('health_monitoring.html')

@health_bp.route('/api/monitoring/start', methods=['POST'])
def start_monitoring():
    """Inicia monitoramento contínuo"""
    if not health_manager:
        return jsonify({"error": "Health manager não inicializado"}), 500
    
    try:
        data = request.get_json()
        provider_urls = data.get('urls', [])
        check_interval = data.get('check_interval_minutes', 15)
        summary_interval = data.get('summary_interval_hours', 6)
        
        if not provider_urls:
            return jsonify({"error": "URLs são obrigatórias"}), 400
        
        # Em um ambiente de produção, isso deveria ser executado em um processo separado
        # ou usando um task queue como Celery
        
        return jsonify({
            "success": True, 
            "message": "Monitoramento configurado",
            "note": "Implementar execução em background"
        })
        
    except Exception as e:
        logger.error(f"Erro ao iniciar monitoramento: {e}")
        return jsonify({"error": str(e)}), 500

# Filtros Jinja2 personalizados para os templates
@health_bp.app_template_filter('format_timestamp')
def format_timestamp(timestamp_str):
    """Formata timestamp para exibição"""
    try:
        if timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%d/%m/%Y %H:%M:%S')
        return '-'
    except Exception:
        return timestamp_str

@health_bp.app_template_filter('status_badge')
def status_badge(status):
    """Retorna classe CSS para badge de status"""
    status_classes = {
        'online': 'badge-success',
        'degraded': 'badge-warning', 
        'offline': 'badge-danger',
        'unknown': 'badge-secondary'
    }
    return status_classes.get(status, 'badge-secondary')

@health_bp.app_template_filter('format_duration')
def format_duration(minutes):
    """Formata duração em minutos para exibição amigável"""
    if not minutes or minutes == 0:
        return '0 min'
    
    if minutes < 60:
        return f"{int(minutes)} min"
    elif minutes < 1440:  # 24 horas
        hours = int(minutes / 60)
        remaining_minutes = int(minutes % 60)
        if remaining_minutes == 0:
            return f"{hours}h"
        else:
            return f"{hours}h {remaining_minutes}min"
    else:
        days = int(minutes / 1440)
        remaining_hours = int((minutes % 1440) / 60)
        if remaining_hours == 0:
            return f"{days}d"
        else:
            return f"{days}d {remaining_hours}h"