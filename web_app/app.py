"""
Web App Principal - MediocreToons Auto Uploader v2

Flask app com interface web para gerenciar o sistema de auto-upload,
incluindo quarentena, mapeamentos e monitoramento.
"""

from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from datetime import datetime
import json
from pathlib import Path

# Imports dos módulos do sistema
from ..src.mapping.mapping_manager import MappingManager
from ..src.mapping.quarantine import QuarantineManager
from ..src.core.unified_logger import UnifiedLogger
from ..src.notifications import get_discord_notifier, NotificationConfig


app = Flask(__name__)
app.secret_key = 'mediocre-toons-secret-key-change-in-production'

# Inicialização dos managers
data_dir = Path(__file__).parent.parent / "data"
mapping_manager = MappingManager(data_dir / "mapping")
quarantine_manager = QuarantineManager(mapping_manager, data_dir)
logger = UnifiedLogger().get_logger("webapp")

# Inicializar Discord Notifier
discord_config = NotificationConfig(enabled=True)
discord_notifier = get_discord_notifier(discord_config)


@app.route('/')
def index():
    """Dashboard principal"""
    try:
        # Estatísticas gerais
        global_stats = mapping_manager.get_global_stats()
        quarantine_stats = quarantine_manager.get_stats()
        
        # Obras com muitos erros (alerta)
        high_error_obras = mapping_manager.get_obras_with_high_errors(min_errors=7)
        
        return render_template('dashboard.html',
            global_stats=global_stats,
            quarantine_stats=quarantine_stats,
            high_error_obras=high_error_obras[:10]  # Top 10
        )
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}")
        flash(f"Erro ao carregar dashboard: {e}", "error")
        return render_template('error.html')


@app.route('/obras')
def obras_list():
    """Lista todas as obras"""
    try:
        scan_name = request.args.get('scan', None)
        status_filter = request.args.get('status', 'all')
        
        if scan_name:
            # Obras de um scan específico
            scan_data = mapping_manager.load_scan_data(scan_name)
            if not scan_data:
                flash(f"Scan '{scan_name}' não encontrado", "error")
                return redirect(url_for('obras_list'))
            
            obras = scan_data.get("obras", [])
            scan_info = scan_data.get("scan_info", {})
        else:
            # Todas as obras
            obras = []
            scan_names = mapping_manager.get_scan_names()
            for sname in scan_names:
                sdata = mapping_manager.load_scan_data(sname)
                if sdata:
                    for obra in sdata.get("obras", []):
                        obra["scan_name"] = sname
                        obras.append(obra)
            scan_info = None
        
        # Filtrar por status
        if status_filter != 'all':
            obras = [o for o in obras if o.get("status") == status_filter]
        
        return render_template('obras_list.html',
            obras=obras,
            scan_name=scan_name,
            scan_info=scan_info,
            status_filter=status_filter,
            scans=mapping_manager.get_scan_names()
        )
    except Exception as e:
        logger.error(f"Erro ao listar obras: {e}")
        flash(f"Erro ao carregar obras: {e}", "error")
        return render_template('error.html')


# === ROTAS DE QUARENTENA ===

@app.route('/quarantine')
def quarantine_list():
    """Lista obras em quarentena"""
    try:
        quarantined_obras = quarantine_manager.get_quarantined_obras()
        quarantine_stats = quarantine_manager.get_stats() 
        quarantine_history = quarantine_manager.get_quarantine_history(limit=50)
        
        return render_template('quarantine.html',
            quarantined_obras=quarantined_obras,
            quarantine_stats=quarantine_stats,
            quarantine_history=quarantine_history
        )
    except Exception as e:
        logger.error(f"Erro ao listar quarentena: {e}")
        flash(f"Erro ao carregar quarentena: {e}", "error")
        return render_template('error.html')


@app.route('/quarantine/check', methods=['POST'])
def quarantine_check():
    """Executa verificação manual de quarentena"""
    try:
        quarantined_obras = quarantine_manager.check_and_quarantine_obras()
        
        if quarantined_obras:
            flash(f"✅ {len(quarantined_obras)} obras colocadas em quarentena", "success")
        else:
            flash("ℹ️ Nenhuma obra nova colocada em quarentena", "info")
        
        return redirect(url_for('quarantine_list'))
        
    except Exception as e:
        logger.error(f"Erro na verificação de quarentena: {e}")
        flash(f"Erro na verificação de quarentena: {e}", "error")
        return redirect(url_for('quarantine_list'))


@app.route('/quarantine/restore/<scan_name>/<int:obra_id>', methods=['POST'])
def quarantine_restore(scan_name, obra_id):
    """Remove obra da quarentena"""
    try:
        user = request.form.get('user', 'web-interface')
        
        success = quarantine_manager.restore_obra_from_quarantine(
            scan_name, obra_id, user
        )
        
        if success:
            flash(f"✅ Obra {obra_id} removida da quarentena", "success")
        else:
            flash(f"❌ Erro ao remover obra {obra_id} da quarentena", "error")
        
        return redirect(url_for('quarantine_list'))
        
    except Exception as e:
        logger.error(f"Erro ao restaurar obra: {e}")
        flash(f"Erro ao restaurar obra: {e}", "error")
        return redirect(url_for('quarantine_list'))


@app.route('/api/quarantine/stats')
def api_quarantine_stats():
    """API: Estatísticas de quarentena"""
    try:
        stats = quarantine_manager.get_stats()
        return jsonify({
            "success": True,
            "data": {
                "total_quarantined": stats.total_quarantined,
                "quarantined_by_scan": stats.quarantined_by_scan,
                "last_check": stats.last_quarantine_check,
                "auto_quarantines_today": stats.auto_quarantines_today,
                "manual_restores_today": stats.manual_restores_today
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/quarantine/list')
def api_quarantine_list():
    """API: Lista de obras em quarentena"""
    try:
        quarantined_obras = quarantine_manager.get_quarantined_obras()
        return jsonify({
            "success": True,
            "data": quarantined_obras
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/obras/high-errors')
def api_high_error_obras():
    """API: Obras com muitos erros"""
    try:
        min_errors = request.args.get('min_errors', 5, type=int)
        obras = mapping_manager.get_obras_with_high_errors(min_errors)
        return jsonify({
            "success": True,
            "data": obras
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# === ROTAS GERAIS ===

@app.route('/scans')
def scans_list():
    """Lista todos os scans"""
    try:
        scan_names = mapping_manager.get_scan_names()
        scans_info = []
        
        for scan_name in scan_names:
            scan_data = mapping_manager.load_scan_data(scan_name)
            if scan_data:
                stats = mapping_manager.get_scan_stats(scan_name)
                scans_info.append({
                    "name": scan_name,
                    "info": scan_data.get("scan_info", {}),
                    "stats": stats
                })
        
        return render_template('scans_list.html', scans=scans_info)
    except Exception as e:
        logger.error(f"Erro ao listar scans: {e}")
        flash(f"Erro ao carregar scans: {e}", "error")
        return render_template('error.html')


@app.route('/logs')
def logs():
    """Visualizar logs do sistema"""
    try:
        # Implementar visualização de logs
        return render_template('logs.html')
    except Exception as e:
        logger.error(f"Erro ao carregar logs: {e}")
        flash(f"Erro ao carregar logs: {e}", "error")
        return render_template('error.html')


@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error="Página não encontrada"), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error="Erro interno do servidor"), 500


# Rotas do Discord Notifier
@app.route('/discord')
def discord_dashboard():
    """Dashboard do Discord Notifier"""
    try:
        stats = discord_notifier.get_statistics()
        return render_template('discord/index.html', stats=stats)
    except Exception as e:
        logger.error(f"Erro no Discord dashboard: {e}")
        flash(f"Erro ao carregar Discord: {e}", "error")
        return redirect(url_for('index'))


@app.route('/discord/test-webhook', methods=['POST'])
def test_discord_webhook():
    """Testa o webhook do Discord"""
    try:
        result = discord_notifier.test_webhook()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Erro ao testar webhook: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/discord/send-test', methods=['POST'])
def send_discord_test():
    """Envia mensagem de teste"""
    try:
        # Exemplo de notificação de quarentena
        result = discord_notifier.notify_quarantine_add(
            "One Piece - Teste",
            "mangayabu",
            10,
            "Teste do sistema Discord"
        )
        
        if result:
            return jsonify({"success": True, "message": "Mensagem de teste enviada!"})
        else:
            return jsonify({"success": False, "error": "Falha ao enviar mensagem"})
    except Exception as e:
        logger.error(f"Erro ao enviar teste Discord: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    # Configuração para desenvolvimento
    app.run(debug=True, host='0.0.0.0', port=5000)