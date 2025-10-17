"""
Blueprint de Gerenciamento da Fila

Rotas para monitorar e gerenciar a fila unificada de uploads.
"""

from flask import Blueprint, render_template, current_app, request, jsonify, flash, redirect, url_for
from datetime import datetime
import json

queue_bp = Blueprint('queue', __name__)


@queue_bp.route('/')
def index():
    """Página principal da fila"""
    try:
        # Status geral da fila
        queue_status = current_app.queue.get_queue_status()
        
        # Itens na fila por status
        pending_jobs = current_app.queue.get_jobs_by_status('PENDING')
        processing_jobs = current_app.queue.get_jobs_by_status('PROCESSING')
        completed_jobs = current_app.queue.get_recent_completed_jobs(limit=20)
        failed_jobs = current_app.queue.get_jobs_by_status('FAILED')
        
        # Estatísticas da fila
        queue_stats = current_app.queue.get_statistics()
        
        return render_template('queue/index.html',
            queue_status=queue_status,
            pending_jobs=pending_jobs,
            processing_jobs=processing_jobs,
            completed_jobs=completed_jobs,
            failed_jobs=failed_jobs,
            queue_stats=queue_stats
        )
        
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar fila: {e}")
        flash(f"Erro ao carregar fila: {e}", "error")
        return render_template('errors/500.html'), 500


@queue_bp.route('/job/<job_id>')
def job_detail(job_id):
    """Detalhes de um job específico"""
    try:
        job = current_app.queue.get_job_by_id(job_id)
        if not job:
            flash(f"Job {job_id} não encontrado", "error")
            return redirect(url_for('queue.index'))
        
        # Histórico do job
        job_history = current_app.queue.get_job_history(job_id)
        
        return render_template('queue/job_detail.html',
            job=job,
            job_history=job_history
        )
        
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar job {job_id}: {e}")
        flash(f"Erro ao carregar job: {e}", "error")
        return redirect(url_for('queue.index'))


@queue_bp.route('/add-manual', methods=['POST'])
def add_manual_job():
    """Adicionar job manual à fila"""
    try:
        scan_name = request.form.get('scan_name')
        obra_id = int(request.form.get('obra_id'))
        priority = request.form.get('priority', 'HIGH')
        
        if not scan_name or not obra_id:
            flash("Scan name e Obra ID são obrigatórios", "error")
            return redirect(url_for('queue.index'))
        
        # Verificar se obra existe
        obra = current_app.mapping_manager.get_obra_by_id(scan_name, obra_id)
        if not obra:
            flash(f"Obra {obra_id} não encontrada no scan {scan_name}", "error")
            return redirect(url_for('queue.index'))
        
        # Adicionar à fila
        job_id = current_app.queue.add_manual_job(
            scan_name=scan_name,
            obra_id=obra_id,
            priority=priority
        )
        
        if job_id:
            flash(f"✅ Job manual adicionado à fila: {obra['titulo']}", "success")
            current_app.logger.info(f"Job manual adicionado: {scan_name}/{obra_id}")
        else:
            flash("❌ Erro ao adicionar job à fila", "error")
        
        return redirect(url_for('queue.index'))
        
    except Exception as e:
        current_app.logger.error(f"Erro ao adicionar job manual: {e}")
        flash(f"Erro ao adicionar job: {e}", "error")
        return redirect(url_for('queue.index'))


@queue_bp.route('/job/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    """Cancelar job pendente"""
    try:
        result = current_app.queue.cancel_job(job_id)
        
        if result:
            flash(f"✅ Job {job_id} cancelado com sucesso", "success")
            current_app.logger.info(f"Job cancelado: {job_id}")
        else:
            flash(f"❌ Erro ao cancelar job {job_id}", "error")
        
        return redirect(url_for('queue.index'))
        
    except Exception as e:
        current_app.logger.error(f"Erro ao cancelar job {job_id}: {e}")
        flash(f"Erro ao cancelar job: {e}", "error")
        return redirect(url_for('queue.index'))


@queue_bp.route('/job/<job_id>/retry', methods=['POST'])
def retry_job(job_id):
    """Tentar novamente job falhado"""
    try:
        result = current_app.queue.retry_job(job_id)
        
        if result:
            flash(f"✅ Job {job_id} recolocado na fila", "success")
            current_app.logger.info(f"Job recolocado na fila: {job_id}")
        else:
            flash(f"❌ Erro ao tentar novamente job {job_id}", "error")
        
        return redirect(url_for('queue.index'))
        
    except Exception as e:
        current_app.logger.error(f"Erro ao tentar novamente job {job_id}: {e}")
        flash(f"Erro ao tentar novamente job: {e}", "error")
        return redirect(url_for('queue.index'))


@queue_bp.route('/clear-completed', methods=['POST'])
def clear_completed():
    """Limpar jobs completados"""
    try:
        count = current_app.queue.clear_completed_jobs()
        
        if count > 0:
            flash(f"✅ {count} jobs completados removidos", "success")
            current_app.logger.info(f"{count} jobs completados removidos")
        else:
            flash("ℹ️ Nenhum job completado para remover", "info")
        
        return redirect(url_for('queue.index'))
        
    except Exception as e:
        current_app.logger.error(f"Erro ao limpar jobs completados: {e}")
        flash(f"Erro ao limpar jobs: {e}", "error")
        return redirect(url_for('queue.index'))


@queue_bp.route('/clear-failed', methods=['POST'])
def clear_failed():
    """Limpar jobs falhados"""
    try:
        count = current_app.queue.clear_failed_jobs()
        
        if count > 0:
            flash(f"✅ {count} jobs falhados removidos", "success")
            current_app.logger.info(f"{count} jobs falhados removidos")
        else:
            flash("ℹ️ Nenhum job falhado para remover", "info")
        
        return redirect(url_for('queue.index'))
        
    except Exception as e:
        current_app.logger.error(f"Erro ao limpar jobs falhados: {e}")
        flash(f"Erro ao limpar jobs: {e}", "error")
        return redirect(url_for('queue.index'))


# === API ENDPOINTS ===

@queue_bp.route('/api/status')
def api_queue_status():
    """API: Status da fila"""
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


@queue_bp.route('/api/stats')
def api_queue_stats():
    """API: Estatísticas da fila"""
    try:
        stats = current_app.queue.get_statistics()
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@queue_bp.route('/api/jobs')
def api_jobs_list():
    """API: Lista de jobs"""
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


@queue_bp.route('/api/job/<job_id>')
def api_job_detail(job_id):
    """API: Detalhes de um job"""
    try:
        job = current_app.queue.get_job_by_id(job_id)
        if not job:
            return jsonify({
                'success': False,
                'error': f"Job {job_id} não encontrado"
            }), 404
        
        job_history = current_app.queue.get_job_history(job_id)
        
        return jsonify({
            'success': True,
            'data': {
                'job': job,
                'history': job_history
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@queue_bp.route('/api/job/<job_id>/cancel', methods=['POST'])
def api_cancel_job(job_id):
    """API: Cancelar job"""
    try:
        result = current_app.queue.cancel_job(job_id)
        
        if result:
            current_app.logger.info(f"Job cancelado via API: {job_id}")
            return jsonify({
                'success': True,
                'message': f"Job {job_id} cancelado com sucesso"
            })
        else:
            return jsonify({
                'success': False,
                'error': f"Erro ao cancelar job {job_id}"
            }), 500
        
    except Exception as e:
        current_app.logger.error(f"Erro ao cancelar job via API {job_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@queue_bp.route('/api/job/<job_id>/retry', methods=['POST'])
def api_retry_job(job_id):
    """API: Tentar novamente job"""
    try:
        result = current_app.queue.retry_job(job_id)
        
        if result:
            current_app.logger.info(f"Job recolocado na fila via API: {job_id}")
            return jsonify({
                'success': True,
                'message': f"Job {job_id} recolocado na fila"
            })
        else:
            return jsonify({
                'success': False,
                'error': f"Erro ao tentar novamente job {job_id}"
            }), 500
        
    except Exception as e:
        current_app.logger.error(f"Erro ao tentar novamente job via API {job_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@queue_bp.route('/api/add-manual', methods=['POST'])
def api_add_manual_job():
    """API: Adicionar job manual"""
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