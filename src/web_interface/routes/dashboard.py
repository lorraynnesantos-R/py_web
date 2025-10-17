"""
Blueprint do Dashboard Principal

Rotas para o dashboard principal com visão geral do sistema,
controles de timer e métricas.
"""

from flask import Blueprint, render_template, current_app, jsonify, request
from datetime import datetime, timedelta
import json

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def index():
    """Dashboard principal"""
    try:
        # Estatísticas gerais do mapeamento
        global_stats = current_app.mapping_manager.get_global_stats()
        
        # Estatísticas de quarentena
        quarantine_stats = current_app.quarantine_manager.get_stats()
        
        # Status do scheduler
        scheduler_status = current_app.scheduler.get_status()
        
        # Status da fila
        queue_status = current_app.queue.get_queue_status()
        
        # Obras com muitos erros (alerta) - método simplificado por enquanto
        try:
            high_error_obras = current_app.mapping_manager.get_obras_with_high_errors(min_errors=7)
        except AttributeError:
            high_error_obras = []
        
        # Últimos logs (simplificado por enquanto)
        recent_logs = get_recent_logs(limit=10)
        
        return render_template('dashboard.html',
            global_stats=global_stats,
            quarantine_stats=quarantine_stats,
            scheduler_status=scheduler_status,
            queue_status=queue_status,
            high_error_obras=high_error_obras[:10],
            recent_logs=recent_logs
        )
        
    except Exception as e:
        current_app.logger.error(f"Erro no dashboard: {e}")
        return render_template('errors/500.html', error=str(e)), 500


@dashboard_bp.route('/api/dashboard/stats')
def api_dashboard_stats():
    """API: Estatísticas do dashboard em tempo real"""
    try:
        # Coletar todas as estatísticas
        stats = {
            'global': current_app.mapping_manager.get_global_stats(),
            'quarantine': current_app.quarantine_manager.get_stats().__dict__,
            'scheduler': current_app.scheduler.get_status(),
            'queue': current_app.queue.get_queue_status(),
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro na API de stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dashboard_bp.route('/api/dashboard/timer/control', methods=['POST'])
def api_timer_control():
    """API: Controle do timer (start/pause/stop/reset)"""
    try:
        action = request.json.get('action')
        
        if action == 'start':
            result = current_app.scheduler.start()
        elif action == 'pause':
            result = current_app.scheduler.pause()
        elif action == 'stop':
            result = current_app.scheduler.stop()
        elif action == 'reset':
            result = current_app.scheduler.reset_timer()
        else:
            return jsonify({
                'success': False,
                'error': 'Ação inválida. Use: start, pause, stop, reset'
            }), 400
        
        return jsonify({
            'success': True,
            'action': action,
            'result': result,
            'status': current_app.scheduler.get_status()
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro no controle do timer: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dashboard_bp.route('/api/dashboard/timer/config', methods=['POST'])
def api_timer_config():
    """API: Configuração do intervalo do timer"""
    try:
        interval_minutes = request.json.get('interval', 30)
        
        if not isinstance(interval_minutes, int) or interval_minutes < 1:
            return jsonify({
                'success': False,
                'error': 'Intervalo deve ser um número inteiro maior que 0'
            }), 400
        
        try:
            result = current_app.scheduler.set_interval(interval_minutes)
        except AttributeError:
            # Método ainda não implementado no scheduler real
            result = f"Intervalo configurado para {interval_minutes} minutos (mockado)"
        
        return jsonify({
            'success': True,
            'interval': interval_minutes,
            'result': result,
            'status': current_app.scheduler.get_status()
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro na configuração do timer: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dashboard_bp.route('/api/dashboard/recent-activity')
def api_recent_activity():
    """API: Atividade recente do sistema"""
    try:
        # Últimas execuções do scheduler - usando dados simulados por enquanto
        try:
            recent_executions = []  # Implementar quando o método existir
        except AttributeError:
            recent_executions = []
        
        # Últimos itens da fila - usando dados do status
        try:
            queue_status = current_app.queue.get_queue_status()
            recent_queue_items = []  # Implementar quando o método existir
        except AttributeError:
            recent_queue_items = []
        
        # Últimas quarentenas
        try:
            recent_quarantines = current_app.quarantine_manager.get_quarantine_history(limit=5)
        except AttributeError:
            recent_quarantines = []
        
        return jsonify({
            'success': True,
            'data': {
                'executions': recent_executions,
                'queue_items': recent_queue_items,
                'quarantines': recent_quarantines,
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro na API de atividade recente: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def get_recent_logs(limit=10):
    """
    Obtém logs recentes do sistema
    Por enquanto retorna dados mockados até implementarmos o sistema de logs completo
    """
    try:
        # TODO: Implementar leitura real dos logs quando o sistema estiver completo
        mock_logs = [
            {
                'timestamp': datetime.now() - timedelta(minutes=5),
                'level': 'INFO',
                'message': 'Timer de auto-update iniciado',
                'module': 'scheduler'
            },
            {
                'timestamp': datetime.now() - timedelta(minutes=15),
                'level': 'SUCCESS',
                'message': 'Upload realizado: One Piece Cap. 1098',
                'module': 'uploader'
            },
            {
                'timestamp': datetime.now() - timedelta(minutes=25),
                'level': 'WARNING',
                'message': 'Obra com 8 erros consecutivos: Naruto',
                'module': 'quarantine'
            },
            {
                'timestamp': datetime.now() - timedelta(hours=1),
                'level': 'INFO',
                'message': 'Verificação de updates iniciada',
                'module': 'scheduler'
            },
            {
                'timestamp': datetime.now() - timedelta(hours=2),
                'level': 'ERROR',
                'message': 'Falha na conexão com mangayabu.com',
                'module': 'provider'
            }
        ]
        
        return mock_logs[:limit]
        
    except Exception as e:
        current_app.logger.error(f"Erro ao obter logs recentes: {e}")
        return []