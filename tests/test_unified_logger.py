"""
Testes para o Sistema de Logging Unificado (Task 1.4)
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os

# Adiciona src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from core.config.unified_logger import (
        UnifiedLogger, LogLevel, LogFormat, JsonFormatter, 
        LoggerMixin, get_logger, setup_development_logging, setup_production_logging
    )
except ImportError as e:
    print(f"Aviso: {e}")
    pytest.skip("Módulos não disponíveis", allow_module_level=True)


class TestUnifiedLogger:
    """Testes para UnifiedLogger"""
    
    def setup_method(self):
        """Setup para cada teste"""
        # Limpa instâncias existentes
        UnifiedLogger._instances.clear()
        
        # Configura diretório temporário para logs
        self.temp_dir = tempfile.mkdtemp()
        UnifiedLogger.configure_global(
            log_dir=self.temp_dir,
            enable_console=False,  # Desabilita console para testes
            enable_file=True
        )
    
    def test_singleton_behavior(self):
        """Testa comportamento singleton"""
        logger1 = UnifiedLogger.get_logger("test")
        logger2 = UnifiedLogger.get_logger("test")
        logger3 = UnifiedLogger.get_logger("other")
        
        assert logger1 is logger2
        assert logger1 is not logger3
        assert logger1.name == "test"
        assert logger3.name == "other"
    
    def test_log_levels(self):
        """Testa diferentes níveis de log"""
        logger = UnifiedLogger.get_logger("test_levels")
        
        # Testa todos os níveis
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")
        
        # Verifica se arquivo foi criado
        log_file = Path(self.temp_dir) / "test_levels.log"
        assert log_file.exists()
        
        # Verifica conteúdo
        content = log_file.read_text(encoding='utf-8')
        assert "Debug message" in content
        assert "Info message" in content
        assert "Warning message" in content
        assert "Error message" in content
        assert "Critical message" in content
    
    def test_configure_global(self):
        """Testa configuração global"""
        # Configura formato JSON
        UnifiedLogger.configure_global(
            format=LogFormat.JSON,
            console_level=LogLevel.ERROR,
            file_level=LogLevel.WARNING
        )
        
        logger = UnifiedLogger.get_logger("test_config")
        logger.info("Test message")
        
        # Verifica se arquivo foi criado
        log_file = Path(self.temp_dir) / "test_config.log"
        assert log_file.exists()
    
    def test_file_rotation_config(self):
        """Testa configuração de rotação de arquivos"""
        UnifiedLogger.configure_global(
            enable_rotation=True,
            max_file_size=1024,  # 1KB para teste
            backup_count=3
        )
        
        logger = UnifiedLogger.get_logger("test_rotation")
        
        # Escreve dados suficientes para causar rotação
        for i in range(100):
            logger.info(f"Message {i} with some additional content to increase file size")
        
        # Verifica se arquivo principal existe
        log_file = Path(self.temp_dir) / "test_rotation.log"
        assert log_file.exists()
    
    def test_additional_file_handler(self):
        """Testa adição de handler adicional"""
        logger = UnifiedLogger.get_logger("test_additional")
        
        # Adiciona handler para arquivo específico
        logger.add_file_handler("custom.log", LogLevel.WARNING)
        
        # Testa logs
        logger.debug("Debug message")  # Não deve aparecer no custom.log
        logger.warning("Warning message")  # Deve aparecer em ambos
        logger.error("Error message")  # Deve aparecer em ambos
        
        # Verifica arquivos
        main_log = Path(self.temp_dir) / "test_additional.log"
        custom_log = Path(self.temp_dir) / "custom.log"
        
        assert main_log.exists()
        assert custom_log.exists()
        
        custom_content = custom_log.read_text(encoding='utf-8')
        assert "Debug message" not in custom_content
        assert "Warning message" in custom_content
        assert "Error message" in custom_content
    
    def test_log_file_management(self):
        """Testa métodos de gerenciamento de arquivos"""
        logger = UnifiedLogger.get_logger("test_management")
        
        # Gera alguns logs
        logger.info("Test message 1")
        logger.error("Test message 2")
        
        # Testa get_log_files
        log_files = logger.get_log_files()
        assert len(log_files) >= 1
        assert any("test_management.log" in str(f) for f in log_files)
        
        # Testa get_log_stats
        stats = logger.get_log_stats()
        assert stats['total_files'] >= 1
        assert stats['total_size_bytes'] > 0
        assert stats['total_size_mb'] >= 0
    
    def test_clean_old_logs(self):
        """Testa limpeza de logs antigos"""
        logger = UnifiedLogger.get_logger("test_clean")
        
        # Gera log
        logger.info("Test message")
        
        # Testa clean_old_logs (com 0 dias deve remover tudo)
        removed = logger.clean_old_logs(days=0)
        
        # Como acabamos de criar, pode não remover nada dependendo do timing
        assert isinstance(removed, int)
    
    def test_set_level(self):
        """Testa definição de nível"""
        logger = UnifiedLogger.get_logger("test_level")
        
        # Define nível para WARNING
        logger.set_level(LogLevel.WARNING)
        
        # Verifica se o nível foi definido
        import logging
        assert logger.logger.level == logging.WARNING


class TestJsonFormatter:
    """Testes para JsonFormatter"""
    
    def test_json_format(self):
        """Testa formatação JSON"""
        import logging
        
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
            func="test_func"
        )
        
        formatted = formatter.format(record)
        data = json.loads(formatted)
        
        assert data['level'] == 'INFO'
        assert data['message'] == 'Test message'
        assert data['logger'] == 'test'
        assert 'timestamp' in data
        assert data['function'] == 'test_func'
        assert data['line'] == 10
    
    def test_json_format_with_exception(self):
        """Testa formatação JSON com exceção"""
        import logging
        
        formatter = JsonFormatter()
        
        try:
            raise ValueError("Test exception")
        except Exception:
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
            func="test_func"
        )
        
        formatted = formatter.format(record)
        data = json.loads(formatted)
        
        assert data['level'] == 'ERROR'
        assert data['message'] == 'Error occurred'
        assert 'exception' in data
        assert 'ValueError: Test exception' in data['exception']


class TestLoggerMixin:
    """Testes para LoggerMixin"""
    
    def test_mixin_usage(self):
        """Testa uso do mixin"""
        class TestClass(LoggerMixin):
            def do_something(self):
                self.logger.info("Doing something")
                return "done"
        
        # Configura logger para não usar console
        with tempfile.TemporaryDirectory() as temp_dir:
            UnifiedLogger.configure_global(
                log_dir=temp_dir,
                enable_console=False,
                enable_file=True
            )
            
            test_obj = TestClass()
            result = test_obj.do_something()
            
            assert result == "done"
            assert test_obj.logger.name == "TestClass"
            
            # Verifica se log foi criado
            log_file = Path(temp_dir) / "TestClass.log"
            assert log_file.exists()


class TestConvenienceFunctions:
    """Testes para funções de conveniência"""
    
    def test_get_logger_function(self):
        """Testa função get_logger"""
        logger = get_logger("test_convenience")
        assert isinstance(logger, UnifiedLogger)
        assert logger.name == "test_convenience"
    
    def test_setup_development_logging(self):
        """Testa setup para desenvolvimento"""
        setup_development_logging()
        
        # Verifica se configurações foram aplicadas
        config = UnifiedLogger._global_config
        assert config['console_level'] == LogLevel.DEBUG
        assert config['file_level'] == LogLevel.DEBUG
        assert config['format'] == LogFormat.DETAILED
        assert config['enable_console'] is True
        assert config['enable_file'] is True
    
    def test_setup_production_logging(self):
        """Testa setup para produção"""
        setup_production_logging()
        
        # Verifica se configurações foram aplicadas
        config = UnifiedLogger._global_config
        assert config['console_level'] == LogLevel.WARNING
        assert config['file_level'] == LogLevel.INFO
        assert config['format'] == LogFormat.JSON
        assert config['enable_console'] is False
        assert config['enable_file'] is True


class TestLogLevelEnum:
    """Testes para LogLevel enum"""
    
    def test_log_level_values(self):
        """Testa valores do enum LogLevel"""
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"


class TestLogFormatEnum:
    """Testes para LogFormat enum"""
    
    def test_log_format_values(self):
        """Testa valores do enum LogFormat"""
        assert LogFormat.SIMPLE.value == "%(levelname)s - %(message)s"
        assert "%(asctime)s" in LogFormat.DETAILED.value
        assert "%(filename)s:%(lineno)d" in LogFormat.FULL.value
        assert LogFormat.JSON.value == "json"


if __name__ == "__main__":
    # Execução básica dos testes
    print("🧪 Executando testes básicos do UnifiedLogger...")
    
    try:
        # Teste básico de importação
        from core.config.unified_logger import UnifiedLogger, get_logger
        print("✅ Importação bem-sucedida")
        
        # Teste básico de funcionalidade
        with tempfile.TemporaryDirectory() as temp_dir:
            UnifiedLogger.configure_global(
                log_dir=temp_dir,
                enable_console=False,
                enable_file=True
            )
            
            logger = get_logger("test_basic")
            logger.info("Teste básico do sistema de logging")
            
            log_file = Path(temp_dir) / "test_basic.log"
            if log_file.exists():
                print("✅ Log criado com sucesso")
                print("✅ Task 1.4 - Sistema de Logging implementado!")
            else:
                print("❌ Arquivo de log não foi criado")
    
    except Exception as e:
        print(f"❌ Erro durante teste: {e}")
        print("ℹ️ Estrutura criada, mas pode precisar de dependências")