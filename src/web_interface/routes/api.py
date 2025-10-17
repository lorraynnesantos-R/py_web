"""
Blueprint da API

Endpoints da API REST para integração externa e AJAX.
"""

from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import json

api_bp = Blueprint('api', __name__)


# === ENDPOINTS DE SISTEMA ===

@api_bp.route('/health')
def health_check():
    """Health check da aplicação"""
    try:
        # Verificar componentes principais
        components_status = {
            'mapping_manager': check_component_health('mapping_manager'),
            'quarantine_manager': check_component_health('quarantine_manager'),
            'scheduler': check_component_health('scheduler'),
            'queue': check_component_health('queue'),
            'discord_notifier': check_component_health('discord_notifier')
        }
        
        # Status geral
        all_healthy = all(components_status.values())
        
        response_data = {
            'status': 'healthy' if all_healthy else 'degraded',
            'timestamp': datetime.now().isoformat(),
            'version': '2.0.0',
            'components': components_status
        }
        
        status_code = 200 if all_healthy else 503
        return jsonify(response_data), status_code
        
    except Exception as e:
        current_app.logger.error(f"Erro no health check: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 500


@api_bp.route('/version')
def version_info():
    """Informações de versão"""
    return jsonify({
        'app_name': 'MediocreToons Auto Uploader',
        'version': '2.0.0',
        'build_date': '2024-10-16',
        'python_version': '3.12+',
        'framework': 'Flask',
        'environment': current_app.config.get('ENV', 'development')
    })


@api_bp.route('/stats/global')
def global_stats():
    """Estatísticas globais do sistema"""
    try:
        stats = {
            'mapping': current_app.mapping_manager.get_global_stats(),
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
        current_app.logger.error(f"Erro ao obter estatísticas globais: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === ENDPOINTS DE MAPEAMENTO ===

@api_bp.route('/mapping/scans')
def api_mapping_scans():
    """Lista de scans disponíveis"""
    try:
        scan_names = current_app.mapping_manager.get_scan_names()
        scans_data = []
        
        for scan_name in scan_names:
            stats = current_app.mapping_manager.get_scan_stats(scan_name)
            scans_data.append({
                'name': scan_name,
                'stats': stats
            })
        
        return jsonify({
            'success': True,
            'data': scans_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/mapping/scan/<scan_name>/obras')
def api_mapping_scan_obras(scan_name):
    """Obras de um scan específico"""
    try:
        scan_data = current_app.mapping_manager.load_scan_data(scan_name)
        if not scan_data:
            return jsonify({
                'success': False,
                'error': f"Scan '{scan_name}' não encontrado"
            }), 404
        
        # Filtros opcionais
        status_filter = request.args.get('status')
        limit = request.args.get('limit', type=int)
        
        obras = scan_data.get('obras', [])
        
        if status_filter:
            obras = [o for o in obras if o.get('status') == status_filter]
        
        if limit and limit > 0:
            obras = obras[:limit]
        
        return jsonify({
            'success': True,
            'data': {
                'scan_name': scan_name,
                'scan_info': scan_data.get('scan_info', {}),
                'obras_count': len(obras),
                'obras': obras
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/mapping/obra/<scan_name>/<int:obra_id>')
def api_mapping_obra_detail(scan_name, obra_id):
    """Detalhes de uma obra específica"""
    try:
        obra = current_app.mapping_manager.get_obra_by_id(scan_name, obra_id)
        if not obra:
            return jsonify({
                'success': False,
                'error': f"Obra {obra_id} não encontrada no scan {scan_name}"
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'scan_name': scan_name,
                'obra': obra
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === ENDPOINTS DE QUARENTENA ===

@api_bp.route('/quarantine/list')
def api_quarantine_list():
    """Lista de obras em quarentena"""
    try:
        quarantined_obras = current_app.quarantine_manager.get_quarantined_obras()
        return jsonify({
            'success': True,
            'data': quarantined_obras
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/quarantine/stats')
def api_quarantine_stats():
    """Estatísticas de quarentena"""
    try:
        stats = current_app.quarantine_manager.get_stats()
        return jsonify({
            'success': True,
            'data': stats.__dict__
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/quarantine/check', methods=['POST'])
def api_quarantine_check():
    """Executar verificação de quarentena"""
    try:
        quarantined_obras = current_app.quarantine_manager.check_and_quarantine_obras()
        
        return jsonify({
            'success': True,
            'data': {
                'quarantined_count': len(quarantined_obras),
                'quarantined_obras': quarantined_obras
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro na verificação de quarentena via API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === ENDPOINTS DE SCHEDULER ===

@api_bp.route('/scheduler/status')
def api_scheduler_status():
    """Status do scheduler"""
    try:
        status = current_app.scheduler.get_status()
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/scheduler/control', methods=['POST'])
def api_scheduler_control():
    """Controle do scheduler (start/pause/stop/reset)"""
    try:
        data = request.get_json()
        action = data.get('action')
        
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
        current_app.logger.error(f"Erro no controle do scheduler via API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === ENDPOINTS DE FILA ===

@api_bp.route('/queue/status')
def api_queue_status():
    """Status da fila"""
    try:
        status = current_app.queue.get_queue_status()
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/queue/jobs')
def api_queue_jobs():
    """Lista de jobs na fila"""
    try:
        status_filter = request.args.get('status', 'all')
        limit = int(request.args.get('limit', 50))
        
        if status_filter == 'all':
            jobs = current_app.queue.get_all_jobs(limit=limit)
        else:
            jobs = current_app.queue.get_jobs_by_status(status_filter, limit=limit)
        
        return jsonify({
            'success': True,
            'data': {
                'jobs': jobs,
                'status_filter': status_filter,
                'total': len(jobs)
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/queue/add-manual', methods=['POST'])
def api_queue_add_manual():
    """Adicionar job manual à fila"""
    try:
        data = request.get_json()
        scan_name = data.get('scan_name')
        obra_id = data.get('obra_id')
        priority = data.get('priority', 'HIGH')
        
        if not scan_name or not obra_id:
            return jsonify({
                'success': False,
                'error': 'scan_name e obra_id são obrigatórios'
            }), 400
        
        # Verificar se obra existe
        obra = current_app.mapping_manager.get_obra_by_id(scan_name, obra_id)
        if not obra:
            return jsonify({
                'success': False,
                'error': f"Obra {obra_id} não encontrada no scan {scan_name}"
            }), 404
        
        # Adicionar à fila
        job_id = current_app.queue.add_manual_job(
            scan_name=scan_name,
            obra_id=obra_id,
            priority=priority
        )
        
        if job_id:
            current_app.logger.info(f"Job manual adicionado via API: {scan_name}/{obra_id}")
            return jsonify({
                'success': True,
                'message': f"Job manual adicionado: {obra['titulo']}",
                'job_id': job_id
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Erro ao adicionar job à fila'
            }), 500
        
    except Exception as e:
        current_app.logger.error(f"Erro ao adicionar job manual via API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === ENDPOINTS DE DISCORD ===

@api_bp.route('/discord/stats')
def api_discord_stats():
    """Estatísticas do Discord Notifier"""
    try:
        stats = current_app.discord_notifier.get_statistics()
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/discord/test-webhook', methods=['POST'])
def api_discord_test_webhook():
    """Testar webhook do Discord"""
    try:
        result = current_app.discord_notifier.test_webhook()
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Erro ao testar webhook via API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/discord/send-test', methods=['POST'])
def api_discord_send_test():
    """Enviar mensagem de teste via Discord"""
    try:
        result = current_app.discord_notifier.notify_quarantine_add(
            "Obra de Teste - API",
            "teste-scan",
            10,
            "Teste enviado via API"
        )
        
        if result:
            return jsonify({
                'success': True,
                'message': 'Mensagem de teste enviada com sucesso!'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Falha ao enviar mensagem de teste'
            })
    except Exception as e:
        current_app.logger.error(f"Erro ao enviar teste Discord via API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === FUNÇÕES AUXILIARES ===

def check_component_health(component_name):
    """Verificar saúde de um componente"""
    try:
        component = getattr(current_app, component_name, None)
        if component is None:
            return False
        
        # Verificações específicas por componente
        if component_name == 'mapping_manager':
            # Tentar carregar lista de scans
            scan_names = component.get_scan_names()
            return isinstance(scan_names, list)
        
        elif component_name == 'quarantine_manager':
            # Tentar obter estatísticas
            stats = component.get_stats()
            return stats is not None
        
        elif component_name == 'scheduler':
            # Tentar obter status
            status = component.get_status()
            return isinstance(status, dict)
        
        elif component_name == 'queue':
            # Tentar obter status da fila
            status = component.get_queue_status()
            return isinstance(status, dict)
        
        elif component_name == 'discord_notifier':
            # Verificar se está configurado
            return hasattr(component, 'get_statistics')
        
        return True
        
    except Exception as e:
        current_app.logger.error(f"Erro ao verificar saúde do componente {component_name}: {e}")
        return False


# === ERROR HANDLERS ESPECÍFICOS DA API ===

@api_bp.errorhandler(404)
def api_not_found(error):
    """Endpoint da API não encontrado"""
    return jsonify({
        'success': False,
        'error': 'Endpoint não encontrado',
        'status_code': 404
    }), 404


@api_bp.errorhandler(405)
def api_method_not_allowed(error):
    """Método não permitido"""
    return jsonify({
        'success': False,
        'error': 'Método não permitido',
        'status_code': 405
    }), 405


@api_bp.errorhandler(400)
def api_bad_request(error):
    """Requisição inválida"""
    return jsonify({
        'success': False,
        'error': 'Requisição inválida',
        'status_code': 400
    }), 400


@api_bp.errorhandler(500)
def api_internal_error(error):
    """Erro interno da API"""
    return jsonify({
        'success': False,
        'error': 'Erro interno do servidor',
        'status_code': 500
    }), 500