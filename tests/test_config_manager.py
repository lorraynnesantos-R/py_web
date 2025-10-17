"""
Testes unitários para PytesteConfigManager (Task 1.3).

Este arquivo implementa testes completos para validar todas as funcionalidades
do PytesteConfigManager, incluindo configurações flexíveis, backup e migração.
"""

import sys
import os
import pytest
import tempfile
import json
import sqlite3
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Garante que o diretório src/ está no sys.path para importação absoluta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from core.config.fixed_config import PytesteFixedConfig
from core.config.config_manager import (
    PytesteConfigManager, 
    ConfigMigrationError, 
    ConfigBackupError
)
from core.config.migration import ConfigMigrator, MigrationResult


class TestPytesteConfigManager:
    """Testes para a classe PytesteConfigManager."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_db_path = os.path.join(self.temp_dir, 'test_config.db')
        self.backup_dir = os.path.join(self.temp_dir, 'backups')
        
        self.fixed_config = PytesteFixedConfig()
        self.config_manager = PytesteConfigManager(
            config_db_path=self.config_db_path,
            backup_dir=self.backup_dir,
            fixed_config=self.fixed_config
        )
    
    def teardown_method(self):
        """Cleanup após cada teste."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_initialization_success(self):
        """Testa inicialização bem-sucedida do PytesteConfigManager."""
        assert isinstance(self.config_manager.fixed_config, PytesteFixedConfig)
        assert os.path.exists(self.config_db_path)
        assert os.path.exists(self.backup_dir)
        assert self.config_manager.logger is not None
    
    def test_database_initialization(self):
        """Testa se o banco de dados foi inicializado corretamente."""
        with self.config_manager._get_connection() as conn:
            cursor = conn.cursor()
            
            # Verifica se tabelas existem
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            assert 'configurations' in tables
            assert 'config_history' in tables
            assert 'config_backups' in tables
    
    def test_get_set_config_basic(self):
        """Testa operações básicas de get/set de configuração."""
        # Define uma configuração
        result = self.config_manager.set_config('test_key', 'test_value')
        assert result is True
        
        # Obtém a configuração
        value = self.config_manager.get_config('test_key')
        assert value == 'test_value'
    
    def test_get_config_with_default(self):
        """Testa get_config com valor padrão."""
        # Configuração inexistente com padrão
        value = self.config_manager.get_config('nonexistent_key', 'default_value')
        assert value == 'default_value'
        
        # Configuração inexistente sem padrão (deve usar configurações padrão)
        value = self.config_manager.get_config('proxy_enabled')
        assert value is False  # Valor padrão das configurações flexíveis
    
    def test_set_config_validation(self):
        """Testa validação de configurações."""
        # Configuração válida
        assert self.config_manager.set_config('proxy_port', 8080) is True
        
        # Configuração inválida (porta fora do range)
        assert self.config_manager.set_config('proxy_port', 70000) is False
        
        # Configuração boolean válida
        assert self.config_manager.set_config('cache_enabled', True) is True
        
        # Configuração boolean inválida
        assert self.config_manager.set_config('cache_enabled', 'invalid') is False
    
    def test_get_all_configs(self):
        """Testa obtenção de todas as configurações."""
        # Define algumas configurações
        self.config_manager.set_config('test1', 'value1', category='test')
        self.config_manager.set_config('test2', 'value2', category='test')
        self.config_manager.set_config('other', 'value3', category='other')
        
        # Obtém todas as configurações
        all_configs = self.config_manager.get_all_configs()
        assert isinstance(all_configs, dict)
        assert len(all_configs) > 0
        
        # Obtém configurações por categoria
        test_configs = self.config_manager.get_all_configs(category='test')
        assert 'test1' in test_configs
        assert 'test2' in test_configs
        assert 'other' not in test_configs
    
    def test_get_config_categories(self):
        """Testa obtenção de categorias de configuração."""
        # Define configurações em diferentes categorias
        self.config_manager.set_config('net1', 'value', category='network')
        self.config_manager.set_config('cache1', 'value', category='cache')
        
        categories = self.config_manager.get_config_categories()
        assert 'network' in categories
        assert 'cache' in categories
    
    def test_create_backup(self):
        """Testa criação de backup."""
        # Define algumas configurações
        self.config_manager.set_config('backup_test', 'test_value')
        
        # Cria backup
        backup_path = self.config_manager.create_backup(
            'test_backup', 
            'Backup de teste'
        )
        
        assert os.path.exists(backup_path)
        
        # Verifica conteúdo do backup
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        assert 'metadata' in backup_data
        assert 'configurations' in backup_data
        assert backup_data['metadata']['backup_name'] == 'test_backup'
        assert 'backup_test' in backup_data['configurations']
    
    def test_restore_backup(self):
        """Testa restauração de backup."""
        # Cria configuração inicial
        self.config_manager.set_config('restore_test', 'original_value')
        
        # Cria backup
        backup_path = self.config_manager.create_backup('restore_test_backup')
        
        # Altera configuração
        self.config_manager.set_config('restore_test', 'changed_value')
        assert self.config_manager.get_config('restore_test') == 'changed_value'
        
        # Restaura backup
        result = self.config_manager.restore_backup(backup_path)
        assert result is True
        
        # Verifica se foi restaurado
        assert self.config_manager.get_config('restore_test') == 'original_value'
    
    def test_get_effective_config(self):
        """Testa obtenção de configuração efetiva com override."""
        # Testa timeout customizado
        self.config_manager.set_config('custom_timeout', 60)
        effective_timeout = self.config_manager.get_effective_config('custom_timeout')
        assert effective_timeout == 60
        
        # Testa timeout padrão (0 = usa configuração fixa)
        self.config_manager.set_config('custom_timeout', 0)
        effective_timeout = self.config_manager.get_effective_config('custom_timeout')
        assert effective_timeout == 30  # Valor das configurações fixas
        
        # Testa configuração normal (não-override)
        self.config_manager.set_config('cache_enabled', True)
        cache_enabled = self.config_manager.get_effective_config('cache_enabled')
        assert cache_enabled is True
    
    def test_reset_to_defaults(self):
        """Testa reset para valores padrão."""
        # Altera algumas configurações
        self.config_manager.set_config('proxy_enabled', True)
        self.config_manager.set_config('cache_enabled', False)
        
        # Verifica alterações
        assert self.config_manager.get_config('proxy_enabled') is True
        assert self.config_manager.get_config('cache_enabled') is False
        
        # Reseta para padrões
        result = self.config_manager.reset_to_defaults()
        assert result is True
        
        # Verifica se foram resetadas
        assert self.config_manager.get_config('proxy_enabled') is False
        assert self.config_manager.get_config('cache_enabled') is True
    
    def test_reset_by_category(self):
        """Testa reset por categoria específica."""
        # Altera configurações de diferentes categorias
        self.config_manager.set_config('proxy_enabled', True, category='network')
        self.config_manager.set_config('cache_enabled', False, category='cache')
        
        # Reseta apenas categoria network
        result = self.config_manager.reset_to_defaults(category='network')
        assert result is True
        
        # Verifica se apenas network foi resetada
        assert self.config_manager.get_config('proxy_enabled') is False  # Resetado
        assert self.config_manager.get_config('cache_enabled') is False  # Mantido
    
    def test_config_info(self):
        """Testa obtenção de informações do sistema."""
        info = self.config_manager.get_config_info()
        
        assert 'config_manager_version' in info
        assert 'database_path' in info
        assert 'total_configurations' in info
        assert 'configurations_by_category' in info
        assert info['fixed_config_integration'] is True


class TestConfigMigrator:
    """Testes para a classe ConfigMigrator."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_db_path = os.path.join(self.temp_dir, 'test_config.db')
        self.backup_dir = os.path.join(self.temp_dir, 'backups')
        
        self.config_manager = PytesteConfigManager(
            config_db_path=self.config_db_path,
            backup_dir=self.backup_dir
        )
        self.migrator = ConfigMigrator(
            config_manager=self.config_manager
        )
    
    def teardown_method(self):
        """Cleanup após cada teste."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_migration_result_initialization(self):
        """Testa inicialização de MigrationResult."""
        result = MigrationResult()
        
        assert result.success is False
        assert result.migrated_count == 0
        assert result.errors == []
        assert result.warnings == []
        assert result.backup_path is None
    
    def test_migrate_json_config(self):
        """Testa migração de arquivo JSON."""
        # Cria arquivo JSON de teste
        json_config = {
            'timeout': 60,
            'retry_attempts': 5,
            'proxy_enabled': True,
            'unknown_config': 'value'
        }
        
        json_file = os.path.join(self.temp_dir, 'test_config.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_config, f)
        
        # Executa migração
        result = MigrationResult()
        migrated_count = self.migrator._migrate_json_file(Path(json_file), result)
        
        assert migrated_count > 0
        
        # Verifica se configurações foram migradas
        assert self.config_manager.get_config('custom_timeout') == 60
        assert self.config_manager.get_config('custom_retry_attempts') == 5
        assert self.config_manager.get_config('proxy_enabled') is True
    
    def test_migrate_sqlite_config(self):
        """Testa migração de banco SQLite."""
        # Cria banco SQLite de teste
        sqlite_file = os.path.join(self.temp_dir, 'old_config.db')
        conn = sqlite3.connect(sqlite_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE config (key TEXT, value TEXT)
        ''')
        cursor.execute("INSERT INTO config VALUES ('timeout', '45')")
        cursor.execute("INSERT INTO config VALUES ('cache_enabled', 'True')")
        
        conn.commit()
        conn.close()
        
        # Executa migração
        result = MigrationResult()
        migrated_count = self.migrator._migrate_sqlite_file(Path(sqlite_file), result)
        
        assert migrated_count > 0
        
        # Verifica se configurações foram migradas
        assert self.config_manager.get_config('custom_timeout') == '45'
        assert self.config_manager.get_config('cache_enabled') == 'True'
    
    def test_generate_migration_report(self):
        """Testa geração de relatório de migração."""
        result = MigrationResult()
        result.success = True
        result.migrated_count = 5
        result.errors = ['Erro de teste']
        result.warnings = ['Aviso de teste']
        result.backup_path = '/path/to/backup.json'
        
        report = self.migrator.generate_migration_report(result)
        
        assert '# 📋 Relatório de Migração - Task 1.3' in report
        assert '✅ Status Geral' in report
        assert 'Configurações Migradas:** 5' in report
        assert '❌ Erros Encontrados' in report
        assert '⚠️ Avisos' in report
        assert 'Mapeamento de Configurações' in report
    
    def test_validate_migration(self):
        """Testa validação de migração."""
        # Configura resultado de migração válido
        result = MigrationResult()
        result.success = True
        result.migrated_count = 3
        result.backup_path = self.config_manager.create_backup('test_validation')
        
        # Define configurações essenciais
        self.config_manager.set_config('custom_timeout', 30)
        self.config_manager.set_config('proxy_enabled', False)
        self.config_manager.set_config('cache_enabled', True)
        
        validation = self.migrator.validate_migration(result)
        
        assert validation['valid'] is True
        assert len(validation['issues']) == 0
    
    def test_validate_migration_with_issues(self):
        """Testa validação de migração com problemas."""
        result = MigrationResult()
        result.success = False
        result.migrated_count = 0
        result.backup_path = None
        
        validation = self.migrator.validate_migration(result)
        
        assert validation['valid'] is False
        assert len(validation['issues']) > 0


class TestConfigManagerIntegration:
    """Testes de integração entre componentes."""
    
    def setup_method(self):
        """Setup para testes de integração."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_db_path = os.path.join(self.temp_dir, 'integration_config.db')
        self.backup_dir = os.path.join(self.temp_dir, 'backups')
        
        self.fixed_config = PytesteFixedConfig()
        self.config_manager = PytesteConfigManager(
            config_db_path=self.config_db_path,
            backup_dir=self.backup_dir,
            fixed_config=self.fixed_config
        )
    
    def teardown_method(self):
        """Cleanup após testes de integração."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_integration_with_fixed_config(self):
        """Testa integração completa com PytesteFixedConfig."""
        # Testa override de configuração fixa
        fixed_timeout = self.fixed_config.get_system_settings()['TIMEOUT']
        assert fixed_timeout == 30
        
        # Define timeout customizado
        self.config_manager.set_config('custom_timeout', 60)
        
        # Verifica configuração efetiva
        effective_timeout = self.config_manager.get_effective_config('custom_timeout')
        assert effective_timeout == 60
        
        # Reseta para usar configuração fixa
        self.config_manager.set_config('custom_timeout', 0)
        effective_timeout = self.config_manager.get_effective_config('custom_timeout')
        assert effective_timeout == 30  # Volta para configuração fixa
    
    def test_default_configs_initialization(self):
        """Testa se configurações padrão foram inicializadas."""
        default_configs = [
            'proxy_enabled',
            'cache_enabled',
            'discord_webhook_enabled',
            'theme',
            'language',
            'verify_ssl',
            'auto_start_downloads'
        ]
        
        for config_key in default_configs:
            value = self.config_manager.get_config(config_key)
            assert value is not None
    
    def test_backup_and_restore_cycle(self):
        """Testa ciclo completo de backup e restauração."""
        # Configurações iniciais
        initial_configs = {
            'proxy_enabled': True,
            'cache_duration_hours': 48,
            'custom_timeout': 90,
            'theme': 'dark'
        }
        
        for key, value in initial_configs.items():
            self.config_manager.set_config(key, value)
        
        # Cria backup
        backup_path = self.config_manager.create_backup('integration_test')
        
        # Altera configurações
        self.config_manager.set_config('proxy_enabled', False)
        self.config_manager.set_config('cache_duration_hours', 12)
        self.config_manager.set_config('theme', 'light')
        
        # Verifica alterações
        assert self.config_manager.get_config('proxy_enabled') is False
        assert self.config_manager.get_config('cache_duration_hours') == 12
        assert self.config_manager.get_config('theme') == 'light'
        
        # Restaura backup
        restore_success = self.config_manager.restore_backup(backup_path)
        assert restore_success is True
        
        # Verifica se foi restaurado
        assert self.config_manager.get_config('proxy_enabled') is True
        assert self.config_manager.get_config('cache_duration_hours') == 48
        assert self.config_manager.get_config('custom_timeout') == 90
        assert self.config_manager.get_config('theme') == 'dark'
    
    def test_config_history_tracking(self):
        """Testa se histórico de alterações está sendo registrado."""
        # Altera uma configuração
        self.config_manager.set_config('test_history', 'initial_value')
        self.config_manager.set_config('test_history', 'changed_value')
        
        # Verifica se histórico foi registrado no banco
        with self.config_manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) FROM config_history WHERE config_key = ?',
                ('test_history',)
            )
            history_count = cursor.fetchone()[0]
        
        assert history_count >= 1  # Pelo menos uma entrada de histórico


if __name__ == '__main__':
    pytest.main([__file__])