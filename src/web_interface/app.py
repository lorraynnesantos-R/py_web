"""
App Flask Principal - MediocreToons Auto Uploader v2

Aplicação Flask base com estrutura modularizada, rotas organizadas
e configuração para desenvolvimento e produção.

Task 4.1: Estrutura Base Flask
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, session, g
from werkzeug.middleware.proxy_fix import ProxyFix

# Configurar path para imports
import sys
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Imports dos módulos do sistema (com fallback para desenvolvimento)
try:
    from core.unified_logger import UnifiedLogger
except ImportError:
    # Mock para desenvolvimento
    class UnifiedLogger:
        def get_logger(self, name):
            import logging
            return logging.getLogger(name)

try:
    from mapping.mapping_manager import MappingManager
except ImportError:
    # Mock para desenvolvimento
    class MappingManager:
        def __init__(self, data_dir):
            self.data_dir = data_dir
        def get_scan_names(self): return []
        def get_global_stats(self): return {'total_obras': 0, 'obras_ativas': 0}
        def load_scan_data(self, scan): return None
        def get_obra_by_id(self, scan, id): return None

try:
    from mapping.quarantine import QuarantineManager
except ImportError:
    # Mock para desenvolvimento
    class QuarantineManager:
        def __init__(self, mapping_manager, data_dir):
            pass
        def get_stats(self): 
            class Stats:
                def __init__(self):
                    self.total_quarantined = 0
                    self.auto_quarantines_today = 0
            return Stats()

try:
    from notifications import get_discord_notifier, NotificationConfig
except ImportError:
    # Mock para desenvolvimento
    class NotificationConfig:
        def __init__(self, enabled=True):
            self.enabled = enabled
    
    def get_discord_notifier(config):
        class MockDiscordNotifier:
            def get_statistics(self): return {}
            def test_webhook(self): return {'success': True}
        return MockDiscordNotifier()

try:
    from auto_uploader.scheduler import AutoUpdateScheduler
except ImportError:
    # Mock para desenvolvimento
    class AutoUpdateScheduler:
        def __init__(self, **kwargs):
            pass
        def get_status(self): return {'is_running': False, 'time_remaining': None}
        def start(self): return True
        def pause(self): return True
        def stop(self): return True
        def reset_timer(self): return True
        def set_interval(self, minutes): return True

try:
    from auto_uploader.queue import UnifiedQueue
except ImportError:
    # Mock para desenvolvimento
    class UnifiedQueue:
        def __init__(self, data_dir):
            pass
        def get_status(self): return {'pending_count': 0, 'processing_count': 0}
        def add_manual_job(self, **kwargs): return 'mock-job-id'
        def get_jobs_by_status(self, status, limit=50): return []


def create_app(config_name='development'):
    """
    Factory function para criar a aplicação Flask.
    
    Args:
        config_name: 'development', 'production', 'testing'
    
    Returns:
        Flask app configurada
    """
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')
    
    # Configuração baseada no ambiente
    configure_app(app, config_name)
    
    # Middleware de logging personalizado
    setup_logging_middleware(app)
    
    # Configuração de sessões
    setup_sessions(app)
    
    # Inicialização dos componentes do sistema
    init_system_components(app)
    
    # Registro dos blueprints (rotas modulares)
    register_blueprints(app)
    
    # Error handlers customizados
    register_error_handlers(app)
    
    # Template filters e context processors
    register_template_filters(app)
    
    # Proxy fix para produção
    if config_name == 'production':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    return app


def configure_app(app, config_name):
    """Configuração da aplicação baseada no ambiente"""
    
    # Configurações base
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'mediocre-toons-dev-key-change-in-production')
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600
    
    # Configurações específicas por ambiente
    if config_name == 'development':
        app.config['DEBUG'] = True
        app.config['TESTING'] = False
        app.config['LOG_LEVEL'] = logging.DEBUG
        app.config['SESSION_COOKIE_SECURE'] = False
        
    elif config_name == 'production':
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
        app.config['LOG_LEVEL'] = logging.INFO
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hora
        
    elif config_name == 'testing':
        app.config['DEBUG'] = False
        app.config['TESTING'] = True
        app.config['LOG_LEVEL'] = logging.WARNING
        app.config['WTF_CSRF_ENABLED'] = False
    
    # Configurações de arquivos upload (futuro)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
    
    # Configuração de paths
    base_path = Path(__file__).parent.parent.parent
    app.config['BASE_PATH'] = base_path
    app.config['DATA_PATH'] = base_path / 'data'
    app.config['LOGS_PATH'] = base_path / 'logs'


def setup_logging_middleware(app):
    """Configura middleware de logging personalizado"""
    
    logger = UnifiedLogger().get_logger('webapp')
    app.logger.handlers = logger.handlers
    app.logger.setLevel(app.config.get('LOG_LEVEL', logging.INFO))
    
    @app.before_request
    def log_request_info():
        """Log informações da requisição"""
        if not request.endpoint or request.endpoint == 'static':
            return
            
        app.logger.info(f"Request: {request.method} {request.url} - IP: {request.remote_addr}")
        g.start_time = datetime.now()
    
    @app.after_request
    def log_response_info(response):
        """Log informações da resposta"""
        if not request.endpoint or request.endpoint == 'static':
            return response
            
        if hasattr(g, 'start_time'):
            duration = (datetime.now() - g.start_time).total_seconds()
            app.logger.info(f"Response: {response.status_code} - Duration: {duration:.3f}s")
        
        return response


def setup_sessions(app):
    """Configuração do sistema de sessões"""
    
    @app.before_request
    def before_request():
        """Preparação antes de cada requisição"""
        session.permanent = True
        
        # Inicializar dados da sessão se necessário
        if 'user_preferences' not in session:
            session['user_preferences'] = {
                'theme': 'light',
                'items_per_page': 20,
                'auto_refresh': True
            }


def init_system_components(app):
    """Inicialização dos componentes do sistema"""
    
    try:
        # Paths base
        data_dir = app.config['DATA_PATH']
        
        # Inicializar componentes
        app.mapping_manager = MappingManager(data_dir / "mapping")
        app.quarantine_manager = QuarantineManager(app.mapping_manager, data_dir)
        
        # Discord Notifier
        discord_config = NotificationConfig(enabled=True)
        app.discord_notifier = get_discord_notifier(discord_config)
        
        # Auto Update Scheduler
        try:
            app.scheduler = AutoUpdateScheduler(data_dir)
        except Exception as e:
            app.logger.warning(f"Usando mock do AutoUpdateScheduler: {e}")
            # Fallback para mock
            class MockScheduler:
                def get_status(self): return {'is_running': False, 'time_remaining': None}
                def start(self): return True
                def pause(self): return True
                def stop(self): return True
                def reset_timer(self): return True
                def set_interval(self, minutes): return True
            app.scheduler = MockScheduler()
        
        # Unified Queue
        app.queue = UnifiedQueue(data_dir)
        
        app.logger.info("✅ Componentes do sistema inicializados com sucesso")
        
    except Exception as e:
        app.logger.error(f"❌ Erro ao inicializar componentes do sistema: {e}")
        raise


def register_blueprints(app):
    """Registro dos blueprints (rotas modulares)"""
    
    # Import dos blueprints
    from .routes.dashboard import dashboard_bp
    from .routes.config import config_bp
    from .routes.mapping import mapping_bp
    from .routes.logs import logs_bp
    from .routes.queue import queue_bp
    from .routes.api import api_bp
    
    # Registrar blueprints
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(config_bp, url_prefix='/config')
    app.register_blueprint(mapping_bp, url_prefix='/mapping')
    app.register_blueprint(logs_bp, url_prefix='/logs')
    app.register_blueprint(queue_bp, url_prefix='/queue')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    app.logger.info("✅ Blueprints registrados com sucesso")


def register_error_handlers(app):
    """Registro dos error handlers customizados"""
    
    @app.errorhandler(404)
    def page_not_found(error):
        """Página não encontrada"""
        app.logger.warning(f"404 - Página não encontrada: {request.url}")
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """Erro interno do servidor"""
        app.logger.error(f"500 - Erro interno: {error}")
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden(error):
        """Acesso negado"""
        app.logger.warning(f"403 - Acesso negado: {request.url}")
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(400)
    def bad_request(error):
        """Requisição inválida"""
        app.logger.warning(f"400 - Requisição inválida: {error}")
        return render_template('errors/400.html'), 400


def register_template_filters(app):
    """Registro dos filtros de template customizados"""
    
    @app.context_processor
    def inject_global_vars():
        """Injetar variáveis globais nos templates"""
        return {
            'app_name': 'MediocreToons Auto Uploader v2',
            'app_version': '2.0.0',
            'current_time': datetime.now(),
            'debug_mode': app.config.get('DEBUG', False)
        }

    @app.template_filter('datetime_format')
    def datetime_format(value, format='%d/%m/%Y %H:%M'):
        """Filtro customizado para formatação de data/hora"""
        if value is None:
            return ''
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except:
                return value
        return value.strftime(format)

    @app.template_filter('file_size')
    def file_size_format(value):
        """Filtro para formatação de tamanho de arquivo"""
        if value is None:
            return '0 B'
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if value < 1024.0:
                return f"{value:.1f} {unit}"
            value /= 1024.0
        return f"{value:.1f} TB"


if __name__ == '__main__':
    # Execução direta para desenvolvimento
    from flask import current_app
    
    app = create_app('development')
    
    with app.app_context():
        app.logger.info("🚀 Iniciando MediocreToons Auto Uploader v2 - Interface Web")
        app.logger.info(f"📁 Base Path: {current_app.config['BASE_PATH']}")
        app.logger.info(f"🗂️ Data Path: {current_app.config['DATA_PATH']}")
        app.logger.info(f"📝 Logs Path: {current_app.config['LOGS_PATH']}")
    
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=True,
        use_reloader=True
    )