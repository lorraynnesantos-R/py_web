"""
Blueprint para gerenciamento de mapeamento de obras
Task 4.4: Gerenciamento de Obras - Interface completa para visualizar, editar e gerenciar o mapeamento de obras por scan
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from datetime import datetime, timedelta
import json
import os
import uuid
from typing import Dict, List, Any, Optional

mapping_bp = Blueprint('mapping', __name__)


@mapping_bp.route('/')
def index():
    """Página principal de mapeamento"""
    try:
        # Lista de scans com contadores
        scan_names = current_app.mapping_manager.get_scan_names()
        scans_info = []
        
        for scan_name in scan_names:
            stats = current_app.mapping_manager.get_scan_stats(scan_name)
            scan_data = current_app.mapping_manager.load_scan_data(scan_name)
            
            scans_info.append({
                'name': scan_name,
                'info': scan_data.get('scan_info', {}) if scan_data else {},
                'stats': stats
            })
        
        # Estatísticas globais
        global_stats = current_app.mapping_manager.get_global_stats()
        
        return render_template('mapping/index.html',
            scans=scans_info,
            global_stats=global_stats
        )
        
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar mapeamento: {e}")
        flash(f"Erro ao carregar mapeamento: {e}", "error")
        return render_template('errors/500.html'), 500


@mapping_bp.route('/scan/<scan_name>')
def scan_detail(scan_name):
    """Detalhes de um scan específico"""
    try:
        # Filtros da URL
        status_filter = request.args.get('status', 'all')
        search_term = request.args.get('search', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # Carregar dados do scan
        scan_data = current_app.mapping_manager.load_scan_data(scan_name)
        if not scan_data:
            flash(f"Scan '{scan_name}' não encontrado", "error")
            return redirect(url_for('mapping.index'))
        
        obras = scan_data.get('obras', [])
        scan_info = scan_data.get('scan_info', {})
        
        # Aplicar filtros
        if status_filter != 'all':
            obras = [o for o in obras if o.get('status') == status_filter]
        
        if search_term:
            search_lower = search_term.lower()
            obras = [o for o in obras if search_lower in o.get('titulo', '').lower()]
        
        # Paginação
        total_obras = len(obras)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        obras_page = obras[start_idx:end_idx]
        
        # Estatísticas do scan
        scan_stats = current_app.mapping_manager.get_scan_stats(scan_name)
        
        return render_template('mapping/scan_detail.html',
            scan_name=scan_name,
            scan_info=scan_info,
            obras=obras_page,
            total_obras=total_obras,
            page=page,
            per_page=per_page,
            status_filter=status_filter,
            search_term=search_term,
            scan_stats=scan_stats
        )
        
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar detalhes do scan {scan_name}: {e}")
        flash(f"Erro ao carregar scan: {e}", "error")
        return redirect(url_for('mapping.index'))


@mapping_bp.route('/obra/<scan_name>/<obra_id>')
def obra_detail(scan_name, obra_id):
    """Página de detalhes de uma obra específica"""
    try:
        # Carregar dados da obra
        obra = current_app.mapping_manager.get_obra_by_id(scan_name, obra_id)
        if not obra:
            flash(f"Obra não encontrada", "error")
            return redirect(url_for('mapping.scan_detail', scan_name=scan_name))
            
        # Carregar informações do scan
        scan_data = current_app.mapping_manager.load_scan_data(scan_name)
        scan_info = scan_data.get('scan_info', {}) if scan_data else {}
        
        # Mock do histórico de uploads (TODO: implementar histórico real)
        historico = [
            {
                "data": datetime.now() - timedelta(hours=2),
                "capitulo": f"Cap. {obra.get('total_capitulos', 1)}",
                "status": "sucesso",
                "tempo_processamento": "2m 15s"
            },
            {
                "data": datetime.now() - timedelta(days=1),
                "capitulo": f"Cap. {obra.get('total_capitulos', 1) - 1}",
                "status": "sucesso", 
                "tempo_processamento": "1m 45s"
            }
        ]
        
        return render_template('mapping/obra_detail.html',
                             scan_name=scan_name,
                             scan_info=scan_info,
                             obra=obra,
                             historico=historico,
                             title=f"Obra: {obra.get('titulo', 'N/A')}")
                             
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar obra {obra_id}: {e}")
        flash(f"Erro ao carregar obra: {e}", "error")
        return redirect(url_for('mapping.scan_detail', scan_name=scan_name))


@mapping_bp.route('/obra/<scan_name>/<obra_id>/manual-upload', methods=['POST'])
def manual_upload(scan_name, obra_id):
    """Adicionar obra para upload manual na fila"""
    try:
        # Verificar se obra existe
        obra = current_app.mapping_manager.get_obra_by_id(scan_name, obra_id)
        if not obra:
            flash("Obra não encontrada", "error")
            return redirect(url_for('mapping.scan_detail', scan_name=scan_name))
            
        # Adicionar à fila de upload manual
        if hasattr(current_app, 'queue'):
            job_id = current_app.queue.add_manual_job({
                'scan_name': scan_name,
                'obra_id': obra_id,
                'obra_titulo': obra.get('titulo', 'N/A'),
                'priority': 'HIGH',
                'timestamp': datetime.now().isoformat()
            })
            flash(f"Obra '{obra.get('titulo')}' adicionada à fila de upload manual", "success")
        else:
            flash("Sistema de fila não disponível", "warning")
            
        return redirect(url_for('mapping.obra_detail', scan_name=scan_name, obra_id=obra_id))
        
    except Exception as e:
        current_app.logger.error(f"Erro ao adicionar obra à fila: {e}")
        flash(f"Erro ao adicionar à fila: {e}", "error")
        return redirect(url_for('mapping.obra_detail', scan_name=scan_name, obra_id=obra_id))


@mapping_bp.route('/obra/<scan_name>/<obra_id>/toggle-quarantine', methods=['POST'])
def toggle_quarantine(scan_name, obra_id):
    """Alternar status de quarentena de uma obra"""
    try:
        # Verificar se obra existe
        obra = current_app.mapping_manager.get_obra_by_id(scan_name, obra_id)
        if not obra:
            flash("Obra não encontrada", "error")
            return redirect(url_for('mapping.scan_detail', scan_name=scan_name))
            
        # Alternar status
        current_status = obra.get('status', 'ativo')
        new_status = 'quarentena' if current_status == 'ativo' else 'ativo'
        
        # Atualizar no sistema
        success = current_app.mapping_manager.update_obra_status(scan_name, obra_id, new_status)
        
        if success:
            if new_status == 'quarentena':
                # Resetar contador de erros ao colocar manualmente em quarentena
                current_app.mapping_manager.reset_error_count(scan_name, obra_id)
                flash(f"Obra '{obra.get('titulo')}' colocada em quarentena", "warning")
            else:
                # Resetar contador de erros ao reativar
                current_app.mapping_manager.reset_error_count(scan_name, obra_id)
                flash(f"Obra '{obra.get('titulo')}' reativada da quarentena", "success")
        else:
            flash("Erro ao alterar status da obra", "error")
            
        return redirect(url_for('mapping.obra_detail', scan_name=scan_name, obra_id=obra_id))
        
    except Exception as e:
        current_app.logger.error(f"Erro ao alterar quarentena: {e}")
        flash(f"Erro ao alterar status: {e}", "error")
        return redirect(url_for('mapping.obra_detail', scan_name=scan_name, obra_id=obra_id))


@mapping_bp.route('/obra/<scan_name>/<obra_id>/edit', methods=['GET', 'POST'])
def edit_obra(scan_name, obra_id):
    """Editar informações de uma obra"""
    if request.method == 'GET':
        try:
            # Carregar dados da obra para edição
            obra = current_app.mapping_manager.get_obra_by_id(scan_name, obra_id)
            if not obra:
                flash("Obra não encontrada", "error")
                return redirect(url_for('mapping.scan_detail', scan_name=scan_name))
                
            scan_data = current_app.mapping_manager.load_scan_data(scan_name)
            scan_info = scan_data.get('scan_info', {}) if scan_data else {}
            
            return render_template('mapping/edit_obra.html',
                                 scan_name=scan_name,
                                 scan_info=scan_info,
                                 obra=obra,
                                 title=f"Editar: {obra.get('titulo', 'N/A')}")
                                 
        except Exception as e:
            current_app.logger.error(f"Erro ao carregar obra para edição: {e}")
            flash(f"Erro ao carregar obra: {e}", "error")
            return redirect(url_for('mapping.scan_detail', scan_name=scan_name))
            
    else:  # POST
        try:
            # Obter dados do formulário
            titulo = request.form.get('titulo', '').strip()
            url_relativa = request.form.get('url_relativa', '').strip()
            
            if not titulo or not url_relativa:
                flash("Título e URL são obrigatórios", "error")
                return redirect(url_for('mapping.edit_obra', scan_name=scan_name, obra_id=obra_id))
                
            # Atualizar obra
            success = current_app.mapping_manager.update_obra_info(scan_name, obra_id, {
                'titulo': titulo,
                'url_relativa': url_relativa,
                'updated_at': datetime.now().isoformat()
            })
            
            if success:
                flash("Obra atualizada com sucesso", "success")
                return redirect(url_for('mapping.obra_detail', scan_name=scan_name, obra_id=obra_id))
            else:
                flash("Erro ao atualizar obra", "error")
                return redirect(url_for('mapping.edit_obra', scan_name=scan_name, obra_id=obra_id))
            
        except Exception as e:
            current_app.logger.error(f"Erro ao atualizar obra: {e}")
            flash(f"Erro ao atualizar obra: {e}", "error")
            return redirect(url_for('mapping.edit_obra', scan_name=scan_name, obra_id=obra_id))


@mapping_bp.route('/import-obra', methods=['GET', 'POST'])
def import_obra():
    """Importar nova obra"""
    if request.method == 'GET':
        # Carregar lista de scans disponíveis
        try:
            scan_names = current_app.mapping_manager.get_scan_names()
            scans_info = {}
            
            for scan_name in scan_names:
                scan_data = current_app.mapping_manager.load_scan_data(scan_name)
                if scan_data:
                    scans_info[scan_name] = scan_data.get('scan_info', {})
                    
            return render_template('mapping/import_obra.html',
                                 scans=scans_info,
                                 title="Importar Nova Obra")
        except Exception as e:
            current_app.logger.error(f"Erro ao carregar scans para importação: {e}")
            flash(f"Erro ao carregar scans: {e}", "error")
            return redirect(url_for('mapping.index'))
            
    else:  # POST
        try:
            # Obter dados do formulário
            scan_name = request.form.get('scan_name', '').strip()
            url_obra = request.form.get('url_obra', '').strip()
            titulo = request.form.get('titulo', '').strip()
            
            if not scan_name or not url_obra:
                flash("Scan e URL são obrigatórios", "error")
                return redirect(url_for('mapping.import_obra'))
                
            # Verificar se scan existe
            scan_names = current_app.mapping_manager.get_scan_names()
            if scan_name not in scan_names:
                flash("Scan selecionado não existe", "error")
                return redirect(url_for('mapping.import_obra'))
                
            # Importar obra
            obra_id = current_app.mapping_manager.import_obra(scan_name, {
                'titulo': titulo or 'Título Pendente',
                'url_relativa': url_obra,
                'status': 'ativo',
                'erros_consecutivos': 0,
                'created_at': datetime.now().isoformat(),
                'ultimo_upload': None
            })
            
            if obra_id:
                flash(f"Obra importada com sucesso", "success")
                return redirect(url_for('mapping.obra_detail', scan_name=scan_name, obra_id=obra_id))
            else:
                flash("Erro ao importar obra", "error")
                return redirect(url_for('mapping.import_obra'))
            
        except Exception as e:
            current_app.logger.error(f"Erro ao importar obra: {e}")
            flash(f"Erro ao importar obra: {e}", "error")
            return redirect(url_for('mapping.import_obra'))


# =============================================================================
# API ROUTES
# =============================================================================

@mapping_bp.route('/api/scans')
def api_scans_list():
    """API: Lista todos os scans disponíveis"""
    try:
        scan_names = current_app.mapping_manager.get_scan_names()
        scans_data = {}
        
        for scan_name in scan_names:
            stats = current_app.mapping_manager.get_scan_stats(scan_name)
            scan_data = current_app.mapping_manager.load_scan_data(scan_name)
            scans_data[scan_name] = {
                'info': scan_data.get('scan_info', {}) if scan_data else {},
                'stats': stats
            }
            
        return jsonify({
            "success": True,
            "data": scans_data,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro na API de scans: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


@mapping_bp.route('/api/scan/<scan_name>/obras')
def api_scan_obras(scan_name):
    """API: Lista obras de um scan específico"""
    try:
        # Parâmetros de filtro
        status_filter = request.args.get('status', 'all')  # all, ativo, quarentena
        search_query = request.args.get('search', '').strip()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        scan_data = current_app.mapping_manager.load_scan_data(scan_name)
        if not scan_data:
            return jsonify({
                "success": False,
                "error": f"Scan '{scan_name}' não encontrado"
            }), 404
            
        obras = scan_data.get('obras', [])
            
        # Aplicar filtros
        if status_filter != 'all':
            obras = [o for o in obras if o.get('status') == status_filter]
            
        if search_query:
            obras = [o for o in obras if search_query.lower() in o.get('titulo', '').lower()]
            
        # Paginação
        total = len(obras)
        start = (page - 1) * per_page
        end = start + per_page
        obras_paginated = obras[start:end]
        
        return jsonify({
            "success": True,
            "data": {
                "obras": obras_paginated,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page
                },
                "filters": {
                    "status": status_filter,
                    "search": search_query
                }
            },
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro na API de obras do scan {scan_name}: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500