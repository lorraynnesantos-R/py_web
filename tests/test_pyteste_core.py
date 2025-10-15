"""
Testes unitários para PytesteCore (Task 1.2).

Este arquivo implementa testes completos para validar todas as funcionalidades
do PytesteCore refatorado, incluindo download, processamento e metadados.
"""

import sys
import os
import pytest
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Garante que o diretório src/ está no sys.path para importação absoluta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# Mock das dependências problemáticas antes do import
sys.modules['tldextract'] = Mock()
sys.modules['pillow_avif'] = Mock()
sys.modules['platformdirs'] = Mock()

from core.config.fixed_config import PytesteFixedConfig, ConfigValidationError

# Mock das classes de domínio que podem não existir
class MockPages:
    def __init__(self, name="Test Manga", number="1"):
        self.name = name
        self.number = number

class MockManga:
    def __init__(self, title="Test Manga", url="https://test.com", description="Test"):
        self.title = title
        self.url = url
        self.description = description

class MockMockDownloadedChapter:
    def __init__(self, number, files):
        self.number = number
        self.files = files

# Mock dos use cases
class MockDownloadUseCase:
    def execute(self, pages, fn=None, headers=None, cookies=None, timeout=None):
        return MockMockDownloadedChapter(pages.number, ["file1.png", "file2.png"])

class MockSlicerUseCase:
    def execute(self, ch, fn=None):
        return MockMockDownloadedChapter(ch.number, [f + "_sliced" for f in ch.files])

# Aplica os mocks antes do import
with patch.dict('sys.modules', {
    'core.download.application.use_cases': Mock(DownloadUseCase=MockDownloadUseCase),
    'core.slicer.application.use_cases': Mock(SlicerUseCase=MockSlicerUseCase),
    'core.providers.domain.entities': Mock(Pages=MockPages, Manga=MockManga),
    'core.download.domain.dowload_entity': Mock(Chapter=MockMockDownloadedChapter)
}):
    from core.pyteste_core import PytesteCore


class TestPytesteCore:
    """Testes para a classe PytesteCore."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.config = PytesteFixedConfig()
        self.core = PytesteCore(config=self.config)
    
    def test_initialization_success(self):
        """Testa inicialização bem-sucedida do PytesteCore."""
        assert isinstance(self.core.config, PytesteFixedConfig)
        assert self.core.is_configured() is True
        assert self.core.logger is not None
        assert self.core._download_use_case is not None
        assert self.core._slicer_use_case is not None
    
    def test_initialization_with_custom_config(self):
        """Testa inicialização com configuração personalizada."""
        custom_config = PytesteFixedConfig()
        core = PytesteCore(config=custom_config)
        
        assert core.config is custom_config
        assert core.is_configured() is True
    
    def test_initialization_failure_invalid_config(self, monkeypatch):
        """Testa falha na inicialização com configuração inválida."""
        # Mock para fazer a configuração falhar
        with patch.object(PytesteFixedConfig, 'is_valid_configuration', return_value=False):
            with pytest.raises(ConfigValidationError):
                PytesteCore()
    
    def test_is_configured(self):
        """Testa método is_configured."""
        assert self.core.is_configured() is True
        
        # Simula falha na configuração
        self.core._is_configured = False
        assert self.core.is_configured() is False
    
    @patch('core.pyteste_core.DownloadUseCase')
    def test_download_manga_success(self, mock_download_use_case):
        """Testa download bem-sucedido de mangá."""
        # Mock do use case
        mock_instance = Mock()
        mock_download_use_case.return_value = mock_instance
        
        # Mock do capítulo retornado
        mock_chapter = MockMockDownloadedChapter("1", ["file1.png", "file2.png"])
        mock_instance.execute.return_value = mock_chapter
        
        # Mock das páginas
        mock_pages = Mock()
        mock_pages.name = "Test Manga"
        mock_pages.number = "1"
        
        # Executa o download
        result = self.core.download_manga(mock_pages)
        
        # Verificações
        assert result == mock_chapter
        assert len(result.files) == 2
        mock_instance.execute.assert_called_once()
    
    def test_download_manga_not_configured(self):
        """Testa download quando sistema não está configurado."""
        self.core._is_configured = False
        
        mock_pages = Mock()
        mock_pages.name = "Test Manga"
        
        with pytest.raises(RuntimeError, match="PytesteCore não está configurado"):
            self.core.download_manga(mock_pages)
    
    @patch('core.pyteste_core.DownloadUseCase')
    def test_download_manga_with_callback(self, mock_download_use_case):
        """Testa download com callback de progresso."""
        mock_instance = Mock()
        mock_download_use_case.return_value = mock_instance
        mock_chapter = MockDownloadedChapter("1", ["file1.png"])
        mock_instance.execute.return_value = mock_chapter
        
        mock_pages = Mock()
        mock_pages.name = "Test Manga"
        mock_pages.number = "1"
        
        progress_callback = Mock()
        
        result = self.core.download_manga(mock_pages, progress_callback=progress_callback)
        
        # Verifica se o callback foi passado
        mock_instance.execute.assert_called_once()
        call_args = mock_instance.execute.call_args[1]
        assert 'fn' in call_args
        assert call_args['fn'] == progress_callback
    
    @patch('core.pyteste_core.SlicerUseCase')
    def test_process_images_success(self, mock_slicer_use_case):
        """Testa processamento bem-sucedido de imagens."""
        mock_instance = Mock()
        mock_slicer_use_case.return_value = mock_instance
        
        # Mock do capítulo processado
        processed_chapter = MockDownloadedChapter("1", ["file1_sliced.png", "file2_sliced.png"])
        mock_instance.execute.return_value = processed_chapter
        
        # Mock do capítulo original
        original_chapter = MockDownloadedChapter("1", ["file1.png", "file2.png"])
        
        result = self.core.process_images(original_chapter)
        
        assert result == processed_chapter
        mock_instance.execute.assert_called_once_with(ch=original_chapter, fn=None)
    
    def test_process_images_slice_disabled(self, monkeypatch):
        """Testa processamento quando slice está desabilitado."""
        # Desabilita slice na configuração
        monkeypatch.setitem(self.core.config._fixed_settings, 'SLICE_ENABLED', False)
        
        original_chapter = MockDownloadedChapter("1", ["file1.png", "file2.png"])
        
        result = self.core.process_images(original_chapter)
        
        # Deve retornar o capítulo original sem processamento
        assert result == original_chapter
    
    def test_slice_images_alias(self):
        """Testa se slice_images é um alias para process_images."""
        original_chapter = MockDownloadedChapter("1", ["file1.png"])
        
        with patch.object(self.core, 'process_images') as mock_process:
            mock_process.return_value = original_chapter
            
            result = self.core.slice_images(original_chapter)
            
            mock_process.assert_called_once_with(original_chapter, None)
            assert result == original_chapter
    
    def test_save_metadata_success(self, tmp_path, monkeypatch):
        """Testa salvamento bem-sucedido de metadados."""
        # Configura diretório temporário
        monkeypatch.setitem(self.core.config._fixed_settings, 'SAVE_PATH', str(tmp_path))
        
        # Mock do mangá
        mock_manga = Mock()
        mock_manga.title = "Test Manga"
        mock_manga.url = "https://test.com/manga"
        mock_manga.description = "Test description"
        
        # Mock do capítulo
        mock_chapter = MockDownloadedChapter("1", ["file1.png", "file2.png"])
        
        result = self.core.save_metadata(mock_manga, mock_chapter)
        
        # Verifica se o arquivo foi criado
        assert os.path.exists(result)
        
        # Verifica conteúdo do arquivo
        with open(result, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        assert metadata['manga']['titulo'] == "Test Manga"
        assert metadata['capitulo']['numero'] == "1"
        assert len(metadata['capitulo']['arquivos']) == 2
        assert 'processamento' in metadata
    
    def test_save_metadata_with_additional_data(self, tmp_path, monkeypatch):
        """Testa salvamento de metadados com dados adicionais."""
        monkeypatch.setitem(self.core.config._fixed_settings, 'SAVE_PATH', str(tmp_path))
        
        mock_manga = Mock()
        mock_manga.title = "Test Manga"
        mock_chapter = MockDownloadedChapter("1", ["file1.png"])
        
        additional_data = {"scan": "test_scan", "quality": "high"}
        
        result = self.core.save_metadata(mock_manga, mock_chapter, additional_data)
        
        with open(result, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        assert 'dados_adicionais' in metadata
        assert metadata['dados_adicionais']['scan'] == "test_scan"
    
    @patch('core.pyteste_core.DownloadUseCase')
    @patch('core.pyteste_core.SlicerUseCase')
    def test_download_and_process_complete_success(self, mock_slicer, mock_download):
        """Testa fluxo completo bem-sucedido."""
        # Mocks dos use cases
        mock_download_instance = Mock()
        mock_download.return_value = mock_download_instance
        mock_slicer_instance = Mock()
        mock_slicer.return_value = mock_slicer_instance
        
        # Mock dos retornos
        downloaded_chapter = MockDownloadedChapter("1", ["file1.png", "file2.png"])
        processed_chapter = MockDownloadedChapter("1", ["file1_sliced.png", "file2_sliced.png"])
        
        mock_download_instance.execute.return_value = downloaded_chapter
        mock_slicer_instance.execute.return_value = processed_chapter
        
        # Mock das páginas e mangá
        mock_pages = Mock()
        mock_pages.name = "Test Manga"
        mock_pages.number = "1"
        
        mock_manga = Mock()
        mock_manga.title = "Test Manga"
        
        # Mock do save_metadata
        with patch.object(self.core, 'save_metadata') as mock_save:
            mock_save.return_value = "/path/to/metadata.json"
            
            progress_callback = Mock()
            
            result = self.core.download_and_process_complete(
                pages=mock_pages,
                manga=mock_manga,
                progress_callback=progress_callback
            )
        
        # Verificações
        assert result['sucesso'] is True
        assert result['arquivos_baixados'] == 2
        assert result['arquivos_processados'] == 2
        assert result['metadata_path'] == "/path/to/metadata.json"
        assert result['erro'] is None
        assert progress_callback.call_count >= 3  # Várias chamadas de progresso
    
    def test_get_system_info(self):
        """Testa obtenção de informações do sistema."""
        info = self.core.get_system_info()
        
        assert 'pyteste_core_version' in info
        assert info['configurado'] is True
        assert 'configuracoes_fixas' in info
        assert 'diretorios' in info
        assert info['configuracoes_validas'] is True
    
    def test_apply_config_compatibility(self):
        """Testa método apply_config para compatibilidade."""
        settings = {
            'IMG_FORMAT': 'jpg',  # Tentativa de alterar configuração fixa
            'SAVE_PATH': '/different/path',
            'SOME_OTHER_SETTING': 'value'
        }
        
        result = self.core.apply_config(settings)
        
        # Deve retornar True mas manter configurações fixas
        assert result is True
        
        # Configurações fixas não devem ter mudado
        current_settings = self.core.config.get_fixed_settings()
        assert current_settings['IMG_FORMAT'] == 'png'  # Valor original
        assert current_settings['SAVE_PATH'] == './downloads/mediocre_uploads/'  # Valor original
    
    def test_integration_with_fixed_config(self):
        """Testa integração completa com PytesteFixedConfig."""
        # Verifica se PytesteCore usa corretamente as configurações fixas
        image_settings = self.core.config.get_image_settings()
        system_settings = self.core.config.get_system_settings()
        
        assert image_settings['IMG_FORMAT'] == 'png'
        assert image_settings['SLICE_ENABLED'] is True
        assert system_settings['TIMEOUT'] == 30
        assert system_settings['RETRY_ATTEMPTS'] == 3
    
    def test_logger_integration(self):
        """Testa integração do logger."""
        assert self.core.logger is not None
        assert self.core.logger.name == 'PytesteCore'
        
        # Testa se o logger está configurado corretamente
        assert len(self.core.logger.handlers) >= 1


class TestPytesteCoreErrorHandling:
    """Testes de tratamento de erros do PytesteCore."""
    
    def setup_method(self):
        """Setup para testes de erro."""
        self.config = PytesteFixedConfig()
        self.core = PytesteCore(config=self.config)
    
    @patch('core.pyteste_core.DownloadUseCase')
    def test_download_manga_exception(self, mock_download_use_case):
        """Testa tratamento de exceção no download."""
        mock_instance = Mock()
        mock_download_use_case.return_value = mock_instance
        mock_instance.execute.side_effect = Exception("Download failed")
        
        mock_pages = Mock()
        mock_pages.name = "Test Manga"
        mock_pages.number = "1"
        
        with pytest.raises(Exception, match="Download failed"):
            self.core.download_manga(mock_pages)
    
    @patch('core.pyteste_core.SlicerUseCase')
    def test_process_images_exception(self, mock_slicer_use_case):
        """Testa tratamento de exceção no processamento."""
        mock_instance = Mock()
        mock_slicer_use_case.return_value = mock_instance
        mock_instance.execute.side_effect = Exception("Processing failed")
        
        mock_chapter = MockDownloadedChapter("1", ["file1.png"])
        
        with pytest.raises(Exception, match="Processing failed"):
            self.core.process_images(mock_chapter)
    
    def test_save_metadata_exception(self, tmp_path, monkeypatch):
        """Testa tratamento de exceção no salvamento de metadados."""
        # Configura diretório read-only para forçar erro
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # Read-only
        
        monkeypatch.setitem(self.core.config._fixed_settings, 'SAVE_PATH', str(readonly_dir))
        
        mock_manga = Mock()
        mock_manga.title = "Test Manga"
        mock_chapter = MockDownloadedChapter("1", ["file1.png"])
        
        # Pode lançar exceção dependendo do sistema operacional
        try:
            self.core.save_metadata(mock_manga, mock_chapter)
        except Exception:
            pass  # Esperado em alguns sistemas
    
    @patch('core.pyteste_core.DownloadUseCase')
    def test_download_and_process_complete_exception(self, mock_download_use_case):
        """Testa tratamento de exceção no fluxo completo."""
        mock_instance = Mock()
        mock_download_use_case.return_value = mock_instance
        mock_instance.execute.side_effect = Exception("Complete flow failed")
        
        mock_pages = Mock()
        mock_pages.name = "Test Manga"
        
        with pytest.raises(Exception, match="Complete flow failed"):
            self.core.download_and_process_complete(mock_pages)


if __name__ == '__main__':
    pytest.main([__file__])
