"""
PytesteCore - Núcleo refatorado do sistema PyWeb.

Este módulo implementa a lógica principal de download e processamento
de mangás, extraída e refatorada da MangaDownloaderApp original.
Responsável por orquestrar todo o processo sem depender da interface Qt.

Task 1.2: Refatorar PytesteCore
"""

import os
import json
import logging
import traceback
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from datetime import datetime

from core.config.fixed_config import PytesteFixedConfig, ConfigValidationError
from core.download.application.use_cases import DownloadUseCase
from core.slicer.application.use_cases import SlicerUseCase
from core.providers.domain.entities import Chapter, Pages, Manga
from core.download.domain.dowload_entity import Chapter as DownloadedChapter


class PytesteCore:
    """
    Classe principal do sistema PytesteCore refatorado.
    
    Responsável por orquestrar todo o processo de download e processamento
    de mangás, mantendo separação completa da interface Qt.
    
    Attributes:
        config (PytesteFixedConfig): Configurações fixas do sistema
        logger (logging.Logger): Logger para operações
        _is_configured (bool): Status de configuração do sistema
    """
    
    def __init__(self, config: Optional[PytesteFixedConfig] = None):
        """
        Inicializa o núcleo PytesteCore.
        
        Args:
            config (Optional[PytesteFixedConfig]): Configurações fixas personalizadas
        """
        self.config = config or PytesteFixedConfig()
        self.logger = self._setup_logger()
        self._is_configured = False
        self._download_use_case = DownloadUseCase()
        self._slicer_use_case = SlicerUseCase()
        
        # Inicializa o sistema
        self._initialize_system()
    
    def _setup_logger(self) -> logging.Logger:
        """
        Configura o logger para o PytesteCore.
        
        Returns:
            logging.Logger: Logger configurado
        """
        logger = logging.getLogger('PytesteCore')
        logger.setLevel(logging.INFO)
        
        # Remove handlers existentes para evitar duplicação
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Handler para arquivo
        log_path = Path(self.config.get_directory_settings()['LOG_PATH'])
        log_path.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(
            log_path / 'pyteste_core.log',
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        
        # Handler para console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatação
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _initialize_system(self) -> None:
        """
        Inicializa o sistema PytesteCore.
        
        Realiza validações necessárias e configura componentes.
        """
        try:
            # Valida configurações
            if not self.config.is_valid_configuration():
                raise ConfigValidationError("Configurações inválidas")
            
            # Valida caminhos
            self.config.validate_paths()
            
            self._is_configured = True
            self.logger.info("PytesteCore inicializado com sucesso")
            
        except Exception as e:
            self.logger.error(f"Erro na inicialização do PytesteCore: {str(e)}")
            self._is_configured = False
            raise
    
    def is_configured(self) -> bool:
        """
        Verifica se o sistema está configurado e pronto para uso.
        
        Returns:
            bool: True se configurado, False caso contrário
        """
        return self._is_configured
    
    def download_manga(
        self,
        pages: Pages,
        progress_callback: Optional[Callable[[float], None]] = None,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None
    ) -> DownloadedChapter:
        """
        Executa o download de um capítulo de mangá.
        
        Args:
            pages (Pages): Dados das páginas para download
            progress_callback (Optional[Callable]): Callback para progresso
            headers (Optional[Dict]): Headers HTTP personalizados
            cookies (Optional[Dict]): Cookies personalizados
            
        Returns:
            DownloadedChapter: Capítulo baixado com lista de arquivos
            
        Raises:
            Exception: Em caso de erro no download
        """
        if not self._is_configured:
            raise RuntimeError("PytesteCore não está configurado")
        
        try:
            self.logger.info(f"Iniciando download: {pages.name} - Capítulo {pages.number}")
            
            # Usa configurações fixas para timeout
            system_settings = self.config.get_system_settings()
            timeout = system_settings['TIMEOUT']
            
            # Executa o download usando o use case existente
            chapter = self._download_use_case.execute(
                pages=pages,
                fn=progress_callback,
                headers=headers,
                cookies=cookies,
                timeout=timeout
            )
            
            self.logger.info(f"Download concluído: {len(chapter.files)} arquivos baixados")
            return chapter
            
        except Exception as e:
            self.logger.error(f"Erro no download: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise
    
    def process_images(
        self,
        chapter: DownloadedChapter,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> DownloadedChapter:
        """
        Processa as imagens de um capítulo (slice/manipulação).
        
        Args:
            chapter (DownloadedChapter): Capítulo com imagens para processar
            progress_callback (Optional[Callable]): Callback para progresso
            
        Returns:
            DownloadedChapter: Capítulo com imagens processadas
            
        Raises:
            Exception: Em caso de erro no processamento
        """
        if not self._is_configured:
            raise RuntimeError("PytesteCore não está configurado")
        
        try:
            # Verifica se o slice está habilitado nas configurações fixas
            image_settings = self.config.get_image_settings()
            
            if not image_settings['SLICE_ENABLED']:
                self.logger.info("Slice desabilitado - retornando capítulo sem processamento")
                return chapter
            
            self.logger.info(f"Iniciando processamento de imagens: Capítulo {chapter.number}")
            
            # Executa o slice usando o use case existente
            processed_chapter = self._slicer_use_case.execute(
                ch=chapter,
                fn=progress_callback
            )
            
            self.logger.info(f"Processamento concluído: {len(processed_chapter.files)} arquivos processados")
            return processed_chapter
            
        except Exception as e:
            self.logger.error(f"Erro no processamento de imagens: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise
    
    def slice_images(
        self,
        chapter: DownloadedChapter,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> DownloadedChapter:
        """
        Executa o slice das imagens de um capítulo.
        
        Método alias para process_images, mantido para compatibilidade.
        
        Args:
            chapter (DownloadedChapter): Capítulo para slice
            progress_callback (Optional[Callable]): Callback para progresso
            
        Returns:
            DownloadedChapter: Capítulo com imagens fatiadas
        """
        return self.process_images(chapter, progress_callback)
    
    def save_metadata(
        self,
        manga: Manga,
        chapter: DownloadedChapter,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Salva metadados de um mangá/capítulo processado.
        
        Args:
            manga (Manga): Dados do mangá
            chapter (DownloadedChapter): Capítulo processado
            additional_data (Optional[Dict]): Dados adicionais
            
        Returns:
            str: Caminho do arquivo de metadados salvo
            
        Raises:
            Exception: Em caso de erro ao salvar metadados
        """
        if not self._is_configured:
            raise RuntimeError("PytesteCore não está configurado")
        
        try:
            # Prepara diretório de metadados
            save_path = Path(self.config.get_directory_settings()['SAVE_PATH'])
            metadata_dir = save_path / 'metadata'
            metadata_dir.mkdir(parents=True, exist_ok=True)
            
            # Prepara dados dos metadados
            metadata = {
                'manga': {
                    'titulo': getattr(manga, 'title', 'N/A'),
                    'url': getattr(manga, 'url', 'N/A'),
                    'descricao': getattr(manga, 'description', 'N/A')
                },
                'capitulo': {
                    'numero': chapter.number,
                    'arquivos': chapter.files,
                    'total_arquivos': len(chapter.files)
                },
                'processamento': {
                    'data_download': datetime.now().isoformat(),
                    'configuracoes_usadas': self.config.get_fixed_settings(),
                    'slice_aplicado': self.config.get_image_settings()['SLICE_ENABLED']
                }
            }
            
            # Adiciona dados extras se fornecidos
            if additional_data:
                metadata['dados_adicionais'] = additional_data
            
            # Salva arquivo de metadados
            metadata_file = metadata_dir / f"metadata_{manga.title}_{chapter.number}.json"
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Metadados salvos: {metadata_file}")
            return str(metadata_file)
            
        except Exception as e:
            self.logger.error(f"Erro ao salvar metadados: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise
    
    def download_and_process_complete(
        self,
        pages: Pages,
        manga: Optional[Manga] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Executa o fluxo completo: download + processamento + metadados.
        
        Args:
            pages (Pages): Páginas para download
            manga (Optional[Manga]): Dados do mangá
            progress_callback (Optional[Callable]): Callback para progresso
            headers (Optional[Dict]): Headers HTTP
            cookies (Optional[Dict]): Cookies
            
        Returns:
            Dict[str, Any]: Resultado completo do processamento
        """
        if not self._is_configured:
            raise RuntimeError("PytesteCore não está configurado")
        
        results = {
            'sucesso': False,
            'capitulo': None,
            'arquivos_baixados': 0,
            'arquivos_processados': 0,
            'metadata_path': None,
            'erro': None
        }
        
        try:
            # Fase 1: Download
            if progress_callback:
                progress_callback("Baixando imagens...", 0.0)
            
            def download_progress(progress: float):
                if progress_callback:
                    progress_callback("Baixando imagens...", progress * 0.4)
            
            chapter = self.download_manga(
                pages=pages,
                progress_callback=download_progress,
                headers=headers,
                cookies=cookies
            )
            
            results['arquivos_baixados'] = len(chapter.files)
            
            # Fase 2: Processamento
            if progress_callback:
                progress_callback("Processando imagens...", 40.0)
            
            def process_progress(progress: float):
                if progress_callback:
                    progress_callback("Processando imagens...", 40.0 + (progress * 0.4))
            
            processed_chapter = self.process_images(
                chapter=chapter,
                progress_callback=process_progress
            )
            
            results['arquivos_processados'] = len(processed_chapter.files)
            results['capitulo'] = processed_chapter
            
            # Fase 3: Metadados
            if progress_callback:
                progress_callback("Salvando metadados...", 80.0)
            
            if manga:
                metadata_path = self.save_metadata(
                    manga=manga,
                    chapter=processed_chapter
                )
                results['metadata_path'] = metadata_path
            
            # Conclusão
            if progress_callback:
                progress_callback("Concluído!", 100.0)
            
            results['sucesso'] = True
            self.logger.info(f"Fluxo completo concluído com sucesso: {pages.name}")
            
            return results
            
        except Exception as e:
            error_msg = f"Erro no fluxo completo: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            
            results['erro'] = error_msg
            
            if progress_callback:
                progress_callback(f"Erro: {error_msg}", 0.0)
            
            raise
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        Retorna informações do sistema PytesteCore.
        
        Returns:
            Dict[str, Any]: Informações do sistema
        """
        return {
            'pyteste_core_version': '2.0.0',
            'configurado': self._is_configured,
            'configuracoes_fixas': self.config.get_fixed_settings(),
            'configuracoes_validas': self.config.is_valid_configuration(),
            'diretorios': self.config.get_directory_settings(),
            'resumo_config': self.config.get_config_summary()
        }
    
    def apply_config(self, settings: Dict[str, Any]) -> bool:
        """
        Aplica configurações ao PytesteCore.
        
        Método para compatibilidade com sistema existente.
        
        Args:
            settings (Dict[str, Any]): Configurações para aplicar
            
        Returns:
            bool: True se aplicado com sucesso
        """
        try:
            self.logger.info("Aplicando configurações ao PytesteCore")
            
            # As configurações fixas não podem ser alteradas
            # Este método existe apenas para compatibilidade
            current_settings = self.config.get_fixed_settings()
            
            compatible_keys = [
                'IMG_FORMAT', 'SAVE_PATH', 'SLICE_ENABLED', 
                'TIMEOUT', 'RETRY_ATTEMPTS'
            ]
            
            for key in compatible_keys:
                if key in settings:
                    if settings[key] != current_settings[key]:
                        self.logger.warning(
                            f"Tentativa de alterar configuração fixa '{key}' ignorada"
                        )
            
            self.logger.info("Configurações processadas (configurações fixas mantidas)")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao aplicar configurações: {str(e)}")
            return False