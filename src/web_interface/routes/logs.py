"""
Blueprint de Visualização de Logs

Rotas para visualizar logs do sistema com filtros e busca.
"""

from flask import Blueprint, render_template, current_app, request, jsonify
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

logs_bp = Blueprint('logs', __name__)


@logs_bp.route('/')
def index():
    """Página principal de logs"""
    try:
        # Parâmetros de filtro
        level_filter = request.args.get('level', 'all')
        module_filter = request.args.get('module', 'all')
        date_filter = request.args.get('date', 'today')
        search_term = request.args.get('search', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        # Obter logs filtrados
        logs_data = get_filtered_logs(
            level_filter, module_filter, date_filter, search_term, page, per_page
        )
        
        # Obter estatísticas de logs
        log_stats = get_log_statistics()
        
        # Obter módulos disponíveis
        available_modules = get_available_log_modules()
        
        return render_template('logs/index.html',
            logs=logs_data['logs'],
            total_logs=logs_data['total'],
            page=page,
            per_page=per_page,
            level_filter=level_filter,
            module_filter=module_filter,
            date_filter=date_filter,
            search_term=search_term,
            log_stats=log_stats,
            available_modules=available_modules
        )
        
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar logs: {e}")
        return render_template('errors/500.html', error=str(e)), 500


@logs_bp.route('/realtime')
def realtime():
    """Página de logs em tempo real"""
    try:
        return render_template('logs/realtime.html')
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar logs em tempo real: {e}")
        return render_template('errors/500.html', error=str(e)), 500


@logs_bp.route('/download')
def download_logs():
    """Download de logs como arquivo"""
    try:
        log_type = request.args.get('type', 'all')
        date_range = request.args.get('range', 'today')
        
        # TODO: Implementar download real de logs
        current_app.logger.info(f"Download de logs solicitado: {log_type}, {date_range}")
        
        return jsonify({
            'success': True,
            'message': 'Download iniciado',
            'download_url': '/api/logs/export'
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro no download de logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === API ENDPOINTS ===

@logs_bp.route('/api/logs')
def api_logs():
    """API: Obter logs com filtros"""
    try:
        level_filter = request.args.get('level', 'all')
        module_filter = request.args.get('module', 'all')
        date_filter = request.args.get('date', 'today')
        search_term = request.args.get('search', '')
        limit = int(request.args.get('limit', 100))
        
        logs_data = get_filtered_logs(
            level_filter, module_filter, date_filter, search_term, 1, limit
        )
        
        return jsonify({
            'success': True,
            'data': {
                'logs': logs_data['logs'],
                'total': logs_data['total'],
                'filters_applied': {
                    'level': level_filter,
                    'module': module_filter,
                    'date': date_filter,
                    'search': search_term
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/api/logs/realtime')
def api_logs_realtime():
    """API: Logs em tempo real (últimos)"""
    try:
        since = request.args.get('since')  # timestamp
        limit = int(request.args.get('limit', 20))
        
        # Obter logs mais recentes
        recent_logs = get_recent_logs(since, limit)
        
        return jsonify({
            'success': True,
            'data': {
                'logs': recent_logs,
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/api/logs/stats')
def api_log_stats():
    """API: Estatísticas de logs"""
    try:
        stats = get_log_statistics()
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/api/logs/export')
def api_export_logs():
    """API: Exportar logs como arquivo"""
    try:
        # TODO: Implementar exportação real
        return jsonify({
            'success': True,
            'message': 'Exportação não implementada ainda'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === FUNÇÕES AUXILIARES ===

def get_filtered_logs(level_filter, module_filter, date_filter, search_term, page, per_page):
    """Obter logs filtrados"""
    try:
        # TODO: Implementar leitura real dos arquivos de log
        # Por enquanto, retorna dados mockados
        
        mock_logs = generate_mock_logs(100)
        
        # Aplicar filtros
        filtered_logs = mock_logs
        
        if level_filter != 'all':
            filtered_logs = [log for log in filtered_logs if log['level'] == level_filter.upper()]
        
        if module_filter != 'all':
            filtered_logs = [log for log in filtered_logs if log['module'] == module_filter]
        
        if search_term:
            search_lower = search_term.lower()
            filtered_logs = [
                log for log in filtered_logs 
                if search_lower in log['message'].lower()
            ]
        
        # Filtro de data
        if date_filter == 'today':
            today = datetime.now().date()
            filtered_logs = [
                log for log in filtered_logs 
                if datetime.fromisoformat(log['timestamp']).date() == today
            ]
        elif date_filter == 'yesterday':
            yesterday = (datetime.now() - timedelta(days=1)).date()
            filtered_logs = [
                log for log in filtered_logs 
                if datetime.fromisoformat(log['timestamp']).date() == yesterday
            ]
        elif date_filter == 'week':
            week_ago = datetime.now() - timedelta(days=7)
            filtered_logs = [
                log for log in filtered_logs 
                if datetime.fromisoformat(log['timestamp']) >= week_ago
            ]
        
        # Ordenar por timestamp (mais recente primeiro)
        filtered_logs.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Paginação
        total = len(filtered_logs)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_logs = filtered_logs[start_idx:end_idx]
        
        return {
            'logs': page_logs,
            'total': total
        }
        
    except Exception as e:
        current_app.logger.error(f"Erro ao filtrar logs: {e}")
        return {'logs': [], 'total': 0}


def get_recent_logs(since_timestamp=None, limit=20):
    """Obter logs mais recentes"""
    try:
        # TODO: Implementar leitura real dos logs mais recentes
        mock_logs = generate_mock_logs(limit)
        
        if since_timestamp:
            since_dt = datetime.fromisoformat(since_timestamp)
            mock_logs = [
                log for log in mock_logs 
                if datetime.fromisoformat(log['timestamp']) > since_dt
            ]
        
        return mock_logs
        
    except Exception as e:
        current_app.logger.error(f"Erro ao obter logs recentes: {e}")
        return []


def get_log_statistics():
    """Obter estatísticas de logs"""
    try:
        # TODO: Calcular estatísticas reais dos logs
        return {
            'total_logs_today': 1234,
            'error_count_today': 5,
            'warning_count_today': 23,
            'info_count_today': 1206,
            'logs_by_module': {
                'webapp': 450,
                'scheduler': 234,
                'uploader': 123,
                'quarantine': 89,
                'discord': 67
            },
            'logs_by_hour': [
                {'hour': '00:00', 'count': 12},
                {'hour': '01:00', 'count': 8},
                {'hour': '02:00', 'count': 5},
                # ... mais dados por hora
            ]
        }
        
    except Exception as e:
        current_app.logger.error(f"Erro ao obter estatísticas de logs: {e}")
        return {}


def get_available_log_modules():
    """Obter módulos disponíveis nos logs"""
    return ['webapp', 'scheduler', 'uploader', 'quarantine', 'discord', 'mapping']


def generate_mock_logs(count=50):
    """Gerar logs mockados para teste"""
    import random
    
    levels = ['INFO', 'WARNING', 'ERROR', 'DEBUG']
    modules = ['webapp', 'scheduler', 'uploader', 'quarantine', 'discord']
    messages = [
        'Timer de auto-update iniciado',
        'Upload realizado com sucesso: One Piece Cap. 1098',
        'Obra colocada em quarentena: Naruto',
        'Falha na conexão com mangayabu.com',
        'Verificação de updates concluída',
        'Discord webhook enviado com sucesso',
        'Erro ao processar capítulo',
        'Sistema iniciado com sucesso',
        'Configurações carregadas',
        'Backup criado automaticamente'
    ]
    
    mock_logs = []
    base_time = datetime.now()
    
    for i in range(count):
        timestamp = base_time - timedelta(minutes=random.randint(0, 1440))  # Últimas 24h
        
        mock_logs.append({
            'timestamp': timestamp.isoformat(),
            'level': random.choice(levels),
            'module': random.choice(modules),
            'message': random.choice(messages),
            'line_number': random.randint(1, 500),
            'function': f'function_{random.randint(1, 10)}'
        })
    
    return mock_logs