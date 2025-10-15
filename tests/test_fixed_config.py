# Teste unitário para PytesteFixedConfig

import sys
import os
import pytest

# Garante que o diretório src/ está no sys.path para importação absoluta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from core.config.fixed_config import PytesteFixedConfig, ConfigValidationError

def test_pyteste_fixed_config():
    config = PytesteFixedConfig()
    settings = config.get_fixed_settings()
    assert settings['IMG_FORMAT'] == 'png'
    assert settings['SAVE_PATH'] == './downloads/mediocre_uploads/'
    assert settings['SLICE_ENABLED'] is True
    assert settings['IMG_QUALITY'] == 95
    assert settings['MAX_CONCURRENT_DOWNLOADS'] == 5
    assert settings['TIMEOUT'] == 30
    assert settings['RETRY_ATTEMPTS'] == 3
    assert 'Mozilla' in settings['USER_AGENT']
    assert settings['BASE_URL'] == 'https://mediocreToons.com'
    assert 'login' in settings['API_ENDPOINTS']
    assert 'Content-Type' in settings['REQUIRED_HEADERS']

def test_validate_paths_ok(tmp_path, monkeypatch):
    config = PytesteFixedConfig()
    # Redefine os diretórios para pastas temporárias
    monkeypatch.setitem(config._fixed_settings, 'SAVE_PATH', str(tmp_path / 'downloads'))
    monkeypatch.setitem(config._fixed_settings, 'TEMP_PATH', str(tmp_path / 'temp'))
    monkeypatch.setitem(config._fixed_settings, 'LOG_PATH', str(tmp_path / 'logs'))
    # Não deve lançar exceção
    assert config.validate_paths() == []

def test_validate_paths_permission_error(monkeypatch):
    import platform
    config = PytesteFixedConfig()
    
    # Usa caminhos inválidos específicos para cada OS
    if platform.system() == 'Windows':
        # No Windows, usa uma unidade inexistente
        forbidden_path = 'Z:\\forbidden_dir'
    else:
        # No Linux/Unix, usa diretório sem permissão
        forbidden_path = '/root/forbidden_dir'
    
    monkeypatch.setitem(config._fixed_settings, 'SAVE_PATH', forbidden_path)
    
    # Verifica se lança ConfigValidationError ou retorna False para is_valid_configuration
    try:
        config.validate_paths()
        # Se não lançou exceção, pelo menos is_valid_configuration deve retornar False
        assert not config.is_valid_configuration()
    except ConfigValidationError:
        # Se lançou exceção, está correto
        pass
"""
Testes para a classe PytesteFixedConfig (Task 1.1).

Este arquivo implementa testes unitários completos conforme critério
"Testes unitários para todas as configurações" da Task 1.1.
"""

import pytest
import os
import tempfile
from pathlib import Path
import sys

# Adiciona o caminho do src ao Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.config.fixed_config import PytesteFixedConfig, ConfigValidationError


class TestPytesteFixedConfig:
    """Testes completos para PytesteFixedConfig conforme Task 1.1."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.config = PytesteFixedConfig()
    
    def test_get_fixed_settings_all_required_configs(self):
        """
        Testa se get_fixed_settings() retorna TODAS as configurações 
        especificadas na Task 1.1.
        """
        settings = self.config.get_fixed_settings()
        
        # Verifica configurações obrigatórias da Task 1.1
        assert settings['IMG_FORMAT'] == 'png'
        assert settings['SAVE_PATH'] == './downloads/mediocre_uploads/'
        assert settings['SLICE_ENABLED'] == True
        assert settings['SLICE_HEIGHT'] == 15000
        assert settings['AUTOMATIC_WIDTH'] == True
        assert settings['SLICE_REPLACE_FILES'] == True
        assert settings['DETECTION_TYPE'] == 'pixel'
        
        # Verifica que é um dict completo
        assert isinstance(settings, dict)
        assert len(settings) > 7  # Deve ter pelo menos as 7 configs da Task 1.1
    
    def test_get_fixed_settings_returns_copy(self):
        """Testa se get_fixed_settings() retorna uma cópia (não referência)."""
        settings1 = self.config.get_fixed_settings()
        settings2 = self.config.get_fixed_settings()
        
        # Modifica uma cópia
        settings1['IMG_FORMAT'] = 'jpg'
        
        # Verifica que a outra não foi afetada
        assert settings2['IMG_FORMAT'] == 'png'
        
        # Verifica que o original não foi afetado
        assert self.config.get_fixed_settings()['IMG_FORMAT'] == 'png'
    
    def test_apply_to_pyteste_core_with_apply_config_method(self):
        """
        Testa apply_to_pyteste_core() quando a instância tem método apply_config.
        """
        class MockPytesteCore:
            def __init__(self):
                self.applied_config = None
            
            def apply_config(self, config):
                self.applied_config = config
        
        mock_core = MockPytesteCore()
        self.config.apply_to_pyteste_core(mock_core)
        
        # Verifica se o config foi aplicado
        assert mock_core.applied_config is not None
        assert mock_core.applied_config['IMG_FORMAT'] == 'png'
        assert mock_core.applied_config['SLICE_HEIGHT'] == 15000
    
    def test_apply_to_pyteste_core_without_apply_config_method(self):
        """
        Testa apply_to_pyteste_core() quando a instância não tem método apply_config.
        """
        class MockPytesteCoreOld:
            pass
        
        mock_core = MockPytesteCoreOld()
        self.config.apply_to_pyteste_core(mock_core)
        
        # Verifica se os atributos foram definidos diretamente
        assert hasattr(mock_core, 'img_format')
        assert mock_core.img_format == 'png'
        assert hasattr(mock_core, 'slice_height')
        assert mock_core.slice_height == 15000
    
    def test_get_slice_settings(self):
        """Testa se get_slice_settings() retorna apenas configurações de slice."""
        slice_settings = self.config.get_slice_settings()
        
        expected_keys = {
            'SLICE_ENABLED', 'SLICE_HEIGHT', 'AUTOMATIC_WIDTH',
            'SLICE_REPLACE_FILES', 'DETECTION_TYPE'
        }
        assert set(slice_settings.keys()) == expected_keys
        
        # Verifica valores específicos da Task 1.1
        assert slice_settings['SLICE_ENABLED'] == True
        assert slice_settings['SLICE_HEIGHT'] == 15000
        assert slice_settings['AUTOMATIC_WIDTH'] == True
        assert slice_settings['SLICE_REPLACE_FILES'] == True
        assert slice_settings['DETECTION_TYPE'] == 'pixel'
    
    def test_get_image_settings(self):
        """Testa se get_image_settings() retorna configurações de imagem."""
        image_settings = self.config.get_image_settings()
        
        assert 'IMG_FORMAT' in image_settings
        assert image_settings['IMG_FORMAT'] == 'png'
        assert 'IMG_QUALITY' in image_settings
    
    def test_get_directory_settings(self):
        """Testa se get_directory_settings() retorna configurações de diretório."""
        dir_settings = self.config.get_directory_settings()
        
        assert 'SAVE_PATH' in dir_settings
        assert dir_settings['SAVE_PATH'] == './downloads/mediocre_uploads/'
        assert 'TEMP_PATH' in dir_settings
        assert 'LOG_PATH' in dir_settings
    
    def test_validate_paths_success(self):
        """Testa validate_paths() com diretórios válidos."""
        # Usa diretório temporário para teste seguro
        with tempfile.TemporaryDirectory() as temp_dir:
            # Cria config temporária com paths válidos
            temp_config = PytesteFixedConfig()
            temp_config._fixed_settings['SAVE_PATH'] = os.path.join(temp_dir, 'save')
            temp_config._fixed_settings['TEMP_PATH'] = os.path.join(temp_dir, 'temp')
            temp_config._fixed_settings['LOG_PATH'] = os.path.join(temp_dir, 'log')
            
            # Não deve levantar exceção
            errors = temp_config.validate_paths()
            assert errors == []
    
    def test_is_valid_configuration_true(self):
        """Testa is_valid_configuration() com configuração válida."""
        # Para teste isolado, usa diretório temporário
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_config = PytesteFixedConfig()
            temp_config._fixed_settings['SAVE_PATH'] = os.path.join(temp_dir, 'save')
            temp_config._fixed_settings['TEMP_PATH'] = os.path.join(temp_dir, 'temp')
            temp_config._fixed_settings['LOG_PATH'] = os.path.join(temp_dir, 'log')
            
            assert temp_config.is_valid_configuration() == True
    
    def test_is_valid_configuration_false_invalid_quality(self):
        """Testa is_valid_configuration() com qualidade inválida."""
        self.config._fixed_settings['IMG_QUALITY'] = 0  # Inválido
        assert self.config.is_valid_configuration() == False
        
        self.config._fixed_settings['IMG_QUALITY'] = 101  # Inválido
        assert self.config.is_valid_configuration() == False
    
    def test_is_valid_configuration_false_invalid_slice_height(self):
        """Testa is_valid_configuration() com altura de slice inválida."""
        self.config._fixed_settings['SLICE_HEIGHT'] = 500  # Muito baixo
        assert self.config.is_valid_configuration() == False
    
    def test_get_config_summary_contains_task_1_1_configs(self):
        """Testa se get_config_summary() inclui todas as configs da Task 1.1."""
        summary = self.config.get_config_summary()
        
        # Verifica se contém as configurações principais da Task 1.1
        assert 'png' in summary  # IMG_FORMAT
        assert './downloads/mediocre_uploads/' in summary  # SAVE_PATH
        assert 'True' in summary  # SLICE_ENABLED
        assert '15000' in summary  # SLICE_HEIGHT
        assert 'pixel' in summary  # DETECTION_TYPE
        assert 'Task 1.1' in summary  # Referência à task
    
    def test_get_documentation_comprehensive(self):
        """
        Testa se get_documentation() fornece documentação completa
        conforme critério da Task 1.1.
        """
        docs = self.config.get_documentation()
        
        # Verifica se documenta todas as configurações principais
        config_names = ['IMG_FORMAT', 'SAVE_PATH', 'SLICE_ENABLED', 
                       'SLICE_HEIGHT', 'AUTOMATIC_WIDTH', 'SLICE_REPLACE_FILES', 
                       'DETECTION_TYPE']
        
        for config_name in config_names:
            assert config_name in docs
        
        # Verifica estrutura da documentação
        assert 'DOCUMENTAÇÃO' in docs
        assert 'Task 1.1' in docs
        assert 'Descrição' in docs
        assert 'Valor' in docs
    
    def test_all_task_1_1_requirements_met(self):
        """
        Teste meta que verifica se TODOS os critérios da Task 1.1 foram atendidos.
        """
        settings = self.config.get_fixed_settings()
        
        # ✅ Classe PytesteFixedConfig criada com configurações hardcoded
        assert isinstance(self.config, PytesteFixedConfig)
        
        # ✅ Todas as configurações específicas da Task 1.1
        task_1_1_configs = {
            'IMG_FORMAT': 'png',
            'SAVE_PATH': './downloads/mediocre_uploads/',
            'SLICE_ENABLED': True,
            'SLICE_HEIGHT': 15000,
            'AUTOMATIC_WIDTH': True,
            'SLICE_REPLACE_FILES': True,
            'DETECTION_TYPE': 'pixel'
        }
        
        for key, expected_value in task_1_1_configs.items():
            assert settings[key] == expected_value, f"Config {key} não confere: esperado {expected_value}, obtido {settings[key]}"
        
        # ✅ Método get_fixed_settings() retorna dict com todas as configs
        assert isinstance(settings, dict)
        assert len(settings) >= 7
        
        # ✅ Método apply_to_pyteste_core() existe
        assert hasattr(self.config, 'apply_to_pyteste_core')
        assert callable(self.config.apply_to_pyteste_core)
        
        # ✅ Documentação completa existe
        docs = self.config.get_documentation()
        assert len(docs) > 100  # Documentação substancial
        
        print("✅ TODOS os critérios da Task 1.1 foram atendidos!")


if __name__ == '__main__':
    # Execução rápida dos testes
    test_instance = TestPytesteFixedConfig()
    test_instance.setup_method()
    
    try:
        test_instance.test_all_task_1_1_requirements_met()
        print("🎉 Task 1.1 - PytesteFixedConfig implementada com sucesso!")
    except AssertionError as e:
        print(f"❌ Erro na implementação: {e}")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")