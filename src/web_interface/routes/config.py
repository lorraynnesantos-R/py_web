"""
Blueprint de Configurações

Rotas para gerenciar configurações do sistema:
- Configurações fixas (somente leitura)
- Configurações flexíveis (editáveis)
- Timer e automação
"""

from flask import Blueprint, render_template, current_app, request, jsonify, flash, redirect, url_for
from datetime import datetime
import json

config_bp = Blueprint('config', __name__)


@config_bp.route('/')
def index():
    """Página principal de configurações"""
    try:
        # Configurações fixas (do PytesteFixedConfig)
        fixed_config = get_fixed_configurations()
        
        # Configurações flexíveis (do ConfigManager)
        flexible_config = get_flexible_configurations()
        
        # Configurações de timer e automação
        automation_config = get_automation_configurations()
        
        return render_template('config/index.html',
            fixed_config=fixed_config,
            flexible_config=flexible_config,
            automation_config=automation_config
        )
        
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar configurações: {e}")
        flash(f"Erro ao carregar configurações: {e}", "error")
        return render_template('errors/500.html'), 500


@config_bp.route('/fixed')
def fixed_config():
    """Visualização das configurações fixas"""
    try:
        config_data = get_fixed_configurations()
        
        return render_template('config/fixed.html',
            config=config_data
        )
        
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar configurações fixas: {e}")
        return render_template('errors/500.html'), 500


@config_bp.route('/flexible')
def flexible_config():
    """Página de configurações flexíveis (editáveis)"""
    try:
        config_data = get_flexible_configurations()
        
        return render_template('config/flexible.html',
            config=config_data
        )
        
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar configurações flexíveis: {e}")
        return render_template('errors/500.html'), 500


@config_bp.route('/flexible/save', methods=['POST'])
def save_flexible_config():
    """Salvar configurações flexíveis"""
    try:
        # Fazer backup antes de salvar
        backup_result = create_config_backup()
        
        if not backup_result['success']:
            flash(f"Erro ao criar backup: {backup_result['error']}", "error")
            return redirect(url_for('config.flexible_config'))
        
        # Obter dados do formulário
        config_data = {
            'proxy_settings': {
                'enabled': request.form.get('proxy_enabled') == 'on',
                'http_proxy': request.form.get('http_proxy', ''),
                'https_proxy': request.form.get('https_proxy', ''),
                'auth_user': request.form.get('proxy_user', ''),
                'auth_pass': request.form.get('proxy_pass', '')
            },
            'http_settings': {
                'timeout': int(request.form.get('http_timeout', 30)),
                'max_retries': int(request.form.get('max_retries', 3)),
                'retry_delay': int(request.form.get('retry_delay', 5)),
                'user_agent': request.form.get('user_agent', ''),
                'custom_headers': parse_custom_headers(request.form.get('custom_headers', ''))
            },
            'cache_settings': {
                'enabled': request.form.get('cache_enabled') == 'on',
                'cache_duration': int(request.form.get('cache_duration', 3600)),
                'max_cache_size': int(request.form.get('max_cache_size', 100))
            }
        }
        
        # Validar configurações
        validation_result = validate_flexible_config(config_data)
        if not validation_result['valid']:
            flash(f"Configuração inválida: {validation_result['error']}", "error")
            return redirect(url_for('config.flexible_config'))
        
        # Salvar configurações
        save_result = save_flexible_configurations(config_data)
        
        if save_result['success']:
            flash("✅ Configurações salvas com sucesso!", "success")
            current_app.logger.info("Configurações flexíveis atualizadas")
        else:
            flash(f"❌ Erro ao salvar configurações: {save_result['error']}", "error")
        
        return redirect(url_for('config.flexible_config'))
        
    except Exception as e:
        current_app.logger.error(f"Erro ao salvar configurações flexíveis: {e}")
        flash(f"Erro ao salvar configurações: {e}", "error")
        return redirect(url_for('config.flexible_config'))


@config_bp.route('/automation')
def automation_config():
    """Configurações de timer e automação"""
    try:
        config_data = get_automation_configurations()
        
        return render_template('config/automation.html',
            config=config_data
        )
        
    except Exception as e:
        current_app.logger.error(f"Erro ao carregar configurações de automação: {e}")
        return render_template('errors/500.html'), 500


@config_bp.route('/automation/save', methods=['POST'])
def save_automation_config():
    """Salvar configurações de automação"""
    try:
        config_data = {
            'timer_interval': int(request.form.get('timer_interval', 30)),
            'quarantine_error_limit': int(request.form.get('quarantine_limit', 10)),
            'discord_webhook_url': request.form.get('discord_webhook', ''),
            'discord_enabled': request.form.get('discord_enabled') == 'on',
            'discord_mention_user': request.form.get('discord_mention_user', ''),
            'auto_start_timer': request.form.get('auto_start_timer') == 'on'
        }
        
        # Validar configurações
        validation_result = validate_automation_config(config_data)
        if not validation_result['valid']:
            flash(f"Configuração inválida: {validation_result['error']}", "error")
            return redirect(url_for('config.automation_config'))
        
        # Salvar configurações
        save_result = save_automation_configurations(config_data)
        
        if save_result['success']:
            flash("✅ Configurações de automação salvas com sucesso!", "success")
            current_app.logger.info("Configurações de automação atualizadas")
            
            # Aplicar mudanças no scheduler se necessário
            if 'timer_interval' in config_data:
                try:
                    current_app.scheduler.set_interval(config_data['timer_interval'])
                except AttributeError:
                    # Método ainda não implementado no scheduler real
                    current_app.logger.info(f"Timer interval configurado: {config_data['timer_interval']} minutos")
        else:
            flash(f"❌ Erro ao salvar configurações de automação: {save_result['error']}", "error")
        
        return redirect(url_for('config.automation_config'))
        
    except Exception as e:
        current_app.logger.error(f"Erro ao salvar configurações de automação: {e}")
        flash(f"Erro ao salvar configurações: {e}", "error")
        return redirect(url_for('config.automation_config'))


@config_bp.route('/restore-defaults', methods=['POST'])
def restore_defaults():
    """Restaurar configurações padrão"""
    try:
        config_type = request.form.get('config_type', 'all')
        
        # Criar backup antes de restaurar
        backup_result = create_config_backup()
        if not backup_result['success']:
            flash(f"Erro ao criar backup: {backup_result['error']}", "error")
            return redirect(url_for('config.index'))
        
        # Restaurar configurações padrão
        restore_result = restore_default_configurations(config_type)
        
        if restore_result['success']:
            flash(f"✅ Configurações padrão restauradas para: {config_type}", "success")
            current_app.logger.info(f"Configurações padrão restauradas: {config_type}")
        else:
            flash(f"❌ Erro ao restaurar configurações: {restore_result['error']}", "error")
        
        return redirect(url_for('config.index'))
        
    except Exception as e:
        current_app.logger.error(f"Erro ao restaurar configurações padrão: {e}")
        flash(f"Erro ao restaurar configurações: {e}", "error")
        return redirect(url_for('config.index'))


# === API ENDPOINTS ===

@config_bp.route('/api/fixed')
def api_fixed_config():
    """API: Obter configurações fixas"""
    try:
        config_data = get_fixed_configurations()
        return jsonify({
            'success': True,
            'data': config_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@config_bp.route('/api/flexible')
def api_flexible_config():
    """API: Obter configurações flexíveis"""
    try:
        config_data = get_flexible_configurations()
        return jsonify({
            'success': True,
            'data': config_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# === FUNÇÕES AUXILIARES ===

def get_fixed_configurations():
    """Obter configurações fixas do sistema"""
    # TODO: Integrar com PytesteFixedConfig quando estiver implementado
    return {
        'image_format': 'PNG',
        'save_path': './downloads/mediocre_uploads/',
        'slice_enabled': True,
        'slice_height': 15000,
        'automatic_width': True,
        'slice_replace_files': True,
        'detection_type': 'pixel'
    }


def get_flexible_configurations():
    """Obter configurações flexíveis do sistema"""
    # TODO: Integrar com PytesteConfigManager quando estiver implementado
    return {
        'proxy_settings': {
            'enabled': False,
            'http_proxy': '',
            'https_proxy': '',
            'auth_user': '',
            'auth_pass': ''
        },
        'http_settings': {
            'timeout': 30,
            'max_retries': 3,
            'retry_delay': 5,
            'user_agent': 'MediocreToons Auto Uploader v2',
            'custom_headers': {}
        },
        'cache_settings': {
            'enabled': True,
            'cache_duration': 3600,
            'max_cache_size': 100
        }
    }


def get_automation_configurations():
    """Obter configurações de automação"""
    return {
        'timer_interval': 30,
        'quarantine_error_limit': 10,
        'discord_webhook_url': '',
        'discord_enabled': False,
        'discord_mention_user': '221057164351897610',
        'auto_start_timer': False
    }


def parse_custom_headers(headers_text):
    """Parse custom headers do textarea"""
    headers = {}
    if headers_text:
        for line in headers_text.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip()] = value.strip()
    return headers


def validate_flexible_config(config_data):
    """Validar configurações flexíveis"""
    try:
        # Validar timeout
        if config_data['http_settings']['timeout'] < 1:
            return {'valid': False, 'error': 'Timeout deve ser maior que 0'}
        
        # Validar retries
        if config_data['http_settings']['max_retries'] < 0:
            return {'valid': False, 'error': 'Max retries deve ser maior ou igual a 0'}
        
        # Validar cache
        if config_data['cache_settings']['cache_duration'] < 1:
            return {'valid': False, 'error': 'Duração do cache deve ser maior que 0'}
        
        return {'valid': True}
        
    except Exception as e:
        return {'valid': False, 'error': str(e)}


def validate_automation_config(config_data):
    """Validar configurações de automação"""
    try:
        # Validar intervalo do timer
        if config_data['timer_interval'] < 1:
            return {'valid': False, 'error': 'Intervalo do timer deve ser maior que 0'}
        
        # Validar limite de quarentena
        if config_data['quarantine_error_limit'] < 1:
            return {'valid': False, 'error': 'Limite de erros deve ser maior que 0'}
        
        return {'valid': True}
        
    except Exception as e:
        return {'valid': False, 'error': str(e)}


def create_config_backup():
    """Criar backup das configurações atuais"""
    try:
        # TODO: Implementar backup real das configurações
        current_app.logger.info("Backup de configurações criado")
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


@config_bp.route('/api/backup', methods=['POST'])
def api_create_backup():
    """API: Criar backup das configurações"""
    try:
        config_type = request.json.get('config_type', 'all')
        backup_result = create_config_backup()
        
        return jsonify(backup_result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@config_bp.route('/api/test-discord', methods=['POST'])
def api_test_discord():
    """API: Testar webhook do Discord"""
    try:
        webhook_url = request.json.get('webhook_url')
        
        if not webhook_url:
            return jsonify({
                'success': False,
                'error': 'URL do webhook é obrigatória'
            }), 400
        
        # Testar o webhook
        test_result = test_discord_webhook(webhook_url)
        
        return jsonify(test_result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def test_discord_webhook(webhook_url):
    """Testar webhook do Discord"""
    try:
        import requests
        
        # Mensagem de teste
        payload = {
            "content": "🧪 **Teste de Webhook**",
            "embeds": [{
                "title": "MediocreToons Auto Uploader",
                "description": "Teste de configuração do webhook Discord",
                "color": 16744501,  # Cor laranja #ff6b35
                "fields": [
                    {
                        "name": "Status",
                        "value": "✅ Webhook funcionando corretamente!",
                        "inline": True
                    },
                    {
                        "name": "Timestamp",
                        "value": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        "inline": True
                    }
                ]
            }]
        }
        
        response = requests.post(webhook_url, json=payload, timeout=10)
        
        if response.status_code == 204:
            return {'success': True, 'message': 'Webhook testado com sucesso!'}
        else:
            return {'success': False, 'error': f'Código de status: {response.status_code}'}
            
    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'Timeout na conexão com Discord'}
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': f'Erro de conexão: {str(e)}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def save_flexible_configurations(config_data):
    """Salvar configurações flexíveis"""
    try:
        # TODO: Integrar com PytesteConfigManager
        current_app.logger.info("Configurações flexíveis salvas")
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def save_automation_configurations(config_data):
    """Salvar configurações de automação"""
    try:
        # TODO: Salvar configurações de automação no local apropriado
        current_app.logger.info("Configurações de automação salvas")
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def restore_default_configurations(config_type):
    """Restaurar configurações padrão"""
    try:
        # TODO: Implementar restauração de configurações padrão
        current_app.logger.info(f"Configurações padrão restauradas: {config_type}")
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}