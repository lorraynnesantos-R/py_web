"""
Configurações fixas do sistema PytesteCore.

Este módulo contém todas as configurações imutáveis do sistema,
incluindo configurações de imagem, processamento e sistema conforme
especificado na Task 1.1.
"""

import os
from typing import Dict, Any, List
from pathlib import Path


class ConfigValidationError(Exception):
    """Exceção lançada quando a validação de configuração falha."""
    pass


class PytesteFixedConfig:
    """
    Classe responsável por fornecer configurações fixas do sistema PytesteCore.
    
    Esta classe centraliza todas as configurações imutáveis do sistema,
    conforme especificado na Task 1.1 do GITHUB_TASKS_LIST.md.
    
    Configurações incluem:
    - IMG_FORMAT: Formato de imagem padrão
    - SAVE_PATH: Caminho de salvamento dos downloads
    - SLICE_ENABLED: Habilitar fatiamento de imagens
    - SLICE_HEIGHT: Altura máxima para fatiamento
    - AUTOMATIC_WIDTH: Largura automática
    - SLICE_REPLACE_FILES: Substituir arquivos no fatiamento
    - DETECTION_TYPE: Tipo de detecção para processamento
    
    Attributes:
        _fixed_settings (Dict[str, Any]): Dicionário com todas as configurações fixas
    """
    
    def __init__(self):
        """
        Inicializa a classe com configurações fixas pré-definidas.
        
        As configurações são definidas como constantes conforme Task 1.1
        e não podem ser alteradas durante a execução do programa.
        """
        self._fixed_settings = {
            # Configurações principais definidas na Task 1.1
            'IMG_FORMAT': 'png',
            'SAVE_PATH': './downloads/mediocre_uploads/',
            'SLICE_ENABLED': True,
                'SLICE_HEIGHT': 15000,  # Altura máxima para fatiamento
            'AUTOMATIC_WIDTH': True,
            'SLICE_REPLACE_FILES': True,
            'DETECTION_TYPE': 'pixel',
            
            # Configurações complementares do sistema
            'IMG_QUALITY': 95,
            'MAX_CONCURRENT_DOWNLOADS': 5,
            'TEMP_PATH': './temp/',
            'LOG_PATH': './logs/',
            'TIMEOUT': 30,
            'RETRY_ATTEMPTS': 3,
            'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            
            # Configurações do MediocreToons
            'BASE_URL': 'https://mediocreToons.com',
            'API_ENDPOINTS': {
                'login': '/api/auth/login',
                'upload': '/api/manga/upload',
                'chapters': '/api/manga/chapters',
                'status': '/api/status'
            },
            'REQUIRED_HEADERS': {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        }
    
    def get_fixed_settings(self) -> Dict[str, Any]:
        """Retorna todas as configurações fixas do sistema."""
        return self._fixed_settings.copy()

    def get_image_settings(self) -> Dict[str, Any]:
        """Retorna apenas as configurações relacionadas a imagens."""
        return {
            'IMG_FORMAT': self._fixed_settings['IMG_FORMAT'],
            'IMG_QUALITY': self._fixed_settings['IMG_QUALITY'],
            'SLICE_ENABLED': self._fixed_settings['SLICE_ENABLED'],
            'SLICE_HEIGHT': self._fixed_settings['SLICE_HEIGHT'],
            'MAX_CONCURRENT_DOWNLOADS': self._fixed_settings['MAX_CONCURRENT_DOWNLOADS']
        }

    def get_directory_settings(self) -> Dict[str, str]:
        """Retorna apenas as configurações relacionadas a diretórios."""
        return {
            'SAVE_PATH': self._fixed_settings['SAVE_PATH'],
            'TEMP_PATH': self._fixed_settings['TEMP_PATH'],
            'LOG_PATH': self._fixed_settings['LOG_PATH']
        }

    def get_system_settings(self) -> Dict[str, Any]:
        """Retorna apenas as configurações relacionadas ao sistema."""
        return {
            'TIMEOUT': self._fixed_settings['TIMEOUT'],
            'RETRY_ATTEMPTS': self._fixed_settings['RETRY_ATTEMPTS'],
            'USER_AGENT': self._fixed_settings['USER_AGENT']
        }

    def get_mediocre_settings(self) -> Dict[str, Any]:
        """Retorna apenas as configurações relacionadas ao MediocreToons."""
        return {
            'BASE_URL': self._fixed_settings['BASE_URL'],
            'API_ENDPOINTS': self._fixed_settings['API_ENDPOINTS'].copy(),
            'REQUIRED_HEADERS': self._fixed_settings['REQUIRED_HEADERS'].copy()
        }

    def is_valid_configuration(self) -> bool:
        """Verifica se todas as configurações são válidas."""
        try:
            self.validate_paths()
            if self._fixed_settings['IMG_QUALITY'] < 1 or self._fixed_settings['IMG_QUALITY'] > 100:
                return False
            if self._fixed_settings['MAX_CONCURRENT_DOWNLOADS'] < 1:
                return False
            if self._fixed_settings['TIMEOUT'] < 1:
                return False
            if self._fixed_settings['RETRY_ATTEMPTS'] < 0:
                return False
            return True
        except ConfigValidationError:
            return False

    def get_config_summary(self) -> str:
        """Retorna um resumo legível das configurações."""
        summary = []
        summary.append("=== CONFIGURAÇÕES FIXAS PYTESTE ===")
        summary.append(f"Formato de Imagem: {self._fixed_settings['IMG_FORMAT']}")
        summary.append(f"Qualidade: {self._fixed_settings['IMG_QUALITY']}%")
        summary.append(f"Slice Habilitado: {self._fixed_settings['SLICE_ENABLED']}")
        summary.append(f"Downloads Simultâneos: {self._fixed_settings['MAX_CONCURRENT_DOWNLOADS']}")
        summary.append(f"Timeout: {self._fixed_settings['TIMEOUT']}s")
        summary.append(f"Tentativas de Retry: {self._fixed_settings['RETRY_ATTEMPTS']}")
        summary.append(f"Diretório de Downloads: {self._fixed_settings['SAVE_PATH']}")
        summary.append(f"URL Base MediocreToons: {self._fixed_settings['BASE_URL']}")
        summary.append("=====================================")
        return "\n".join(summary)

    def validate_paths(self) -> List[str]:
            """Valida se todos os diretórios necessários existem ou podem ser criados."""
            errors = []
            directory_settings = self.get_directory_settings()
            for setting_name, path in directory_settings.items():
                path_obj = Path(path)
                try:
                    path_obj.mkdir(parents=True, exist_ok=True)
                    if not os.access(path_obj, os.W_OK):
                        errors.append(f"{setting_name}: Diretório '{path}' não é gravável")
                except PermissionError:
                    errors.append(f"{setting_name}: Sem permissão para criar '{path}'")
                except OSError as e:
                    errors.append(f"{setting_name}: Erro ao criar '{path}': {str(e)}")
            if errors:
                raise ConfigValidationError(f"Erros de validação de caminhos: {'; '.join(errors)}")
            return errors
    
    def get_fixed_settings(self) -> Dict[str, Any]:
        """
        Retorna todas as configurações fixas do sistema.
        
        Este método atende ao critério "Método get_fixed_settings() retorna dict
        com todas as configs" da Task 1.1.
        
        Returns:
            Dict[str, Any]: Dicionário contendo todas as configurações fixas
            
        Example:
            >>> config = PytesteFixedConfig()
            >>> settings = config.get_fixed_settings()
            >>> print(settings['IMG_FORMAT'])
            'png'
            >>> print(settings['SLICE_HEIGHT'])
            15000
        """
        return self._fixed_settings.copy()
    
    def apply_to_pyteste_core(self, pyteste_core_instance) -> None:
        """
        Aplica as configurações fixas a uma instância do PytesteCore.
        
        Este método atende ao critério "Método apply_to_pyteste_core() aplica
        configs ao core" da Task 1.1.
        
        Args:
            pyteste_core_instance: Instância do PytesteCore para aplicar configs
            
        Note:
            Este método será implementado completamente quando PytesteCore
            estiver disponível (Task 1.2).
        """
        if hasattr(pyteste_core_instance, 'apply_config'):
            pyteste_core_instance.apply_config(self.get_fixed_settings())
        else:
            # Para compatibilidade, define atributos diretamente
            for key, value in self._fixed_settings.items():
                setattr(pyteste_core_instance, key.lower(), value)
    
    def get_slice_settings(self) -> Dict[str, Any]:
        """
        Retorna apenas as configurações relacionadas ao fatiamento de imagens.
        
        Returns:
            Dict[str, Any]: Configurações de slice (habilitado, altura, etc.)
        """
        return {
            'SLICE_ENABLED': self._fixed_settings['SLICE_ENABLED'],
            'SLICE_HEIGHT': self._fixed_settings['SLICE_HEIGHT'],
            'AUTOMATIC_WIDTH': self._fixed_settings['AUTOMATIC_WIDTH'],
            'SLICE_REPLACE_FILES': self._fixed_settings['SLICE_REPLACE_FILES'],
            'DETECTION_TYPE': self._fixed_settings['DETECTION_TYPE']
        }
    
    def get_image_settings(self) -> Dict[str, Any]:
        """
        Retorna apenas as configurações relacionadas a imagens.
        
        Returns:
            Dict[str, Any]: Configurações de imagem (formato, qualidade, etc.)
        """
        return {
            'IMG_FORMAT': self._fixed_settings['IMG_FORMAT'],
            'IMG_QUALITY': self._fixed_settings['IMG_QUALITY'],
            'MAX_CONCURRENT_DOWNLOADS': self._fixed_settings['MAX_CONCURRENT_DOWNLOADS']
        }
    
    def get_directory_settings(self) -> Dict[str, str]:
        """
        Retorna apenas as configurações relacionadas a diretórios.
        
        Returns:
            Dict[str, str]: Configurações de caminhos (save, temp, log)
        """
        return {
            'SAVE_PATH': self._fixed_settings['SAVE_PATH'],
            'TEMP_PATH': self._fixed_settings['TEMP_PATH'],
            'LOG_PATH': self._fixed_settings['LOG_PATH']
        }
    
    def get_system_settings(self) -> Dict[str, Any]:
        """
        Retorna apenas as configurações relacionadas ao sistema.
        
        Returns:
            Dict[str, Any]: Configurações de sistema (timeout, retry, user-agent)
        """
        return {
            'TIMEOUT': self._fixed_settings['TIMEOUT'],
            'RETRY_ATTEMPTS': self._fixed_settings['RETRY_ATTEMPTS'],
            'USER_AGENT': self._fixed_settings['USER_AGENT']
        }
    
    def get_mediocre_settings(self) -> Dict[str, Any]:
        """
        Retorna apenas as configurações relacionadas ao MediocreToons.
        
        Returns:
            Dict[str, Any]: Configurações da API MediocreToons
        """
        return {
            'BASE_URL': self._fixed_settings['BASE_URL'],
            'API_ENDPOINTS': self._fixed_settings['API_ENDPOINTS'].copy(),
            'REQUIRED_HEADERS': self._fixed_settings['REQUIRED_HEADERS'].copy()
        }
    
    def validate_paths(self) -> List[str]:
        """
        Valida se todos os diretórios necessários existem ou podem ser criados.
        
        Returns:
            List[str]: Lista de mensagens de erro (vazia se tudo estiver OK)
            
        Raises:
            ConfigValidationError: Se não for possível criar diretórios necessários
        """
        errors = []
        directory_settings = self.get_directory_settings()
        
        for setting_name, path in directory_settings.items():
            path_obj = Path(path)
            
            try:
                # Tenta criar o diretório se não existir
                path_obj.mkdir(parents=True, exist_ok=True)
                
                # Verifica se o diretório é gravável
                if not os.access(path_obj, os.W_OK):
                    errors.append(f"{setting_name}: Diretório '{path}' não é gravável")
                    
            except PermissionError:
                errors.append(f"{setting_name}: Sem permissão para criar '{path}'")
            except OSError as e:
                errors.append(f"{setting_name}: Erro ao criar '{path}': {str(e)}")
        
        if errors:
            raise ConfigValidationError(f"Erros de validação de caminhos: {'; '.join(errors)}")
        
        return errors
    
    def is_valid_configuration(self) -> bool:
        """
        Verifica se todas as configurações são válidas.
        
        Returns:
            bool: True se todas as configurações são válidas, False caso contrário
        """
        try:
            self.validate_paths()
            
            # Valida configurações de imagem
            if self._fixed_settings['IMG_QUALITY'] < 1 or self._fixed_settings['IMG_QUALITY'] > 100:
                return False
            
            if self._fixed_settings['MAX_CONCURRENT_DOWNLOADS'] < 1:
                return False
            
            # Valida configurações de slice
            if self._fixed_settings['SLICE_HEIGHT'] < 1000:
                return False
            
            # Valida configurações de sistema
            if self._fixed_settings['TIMEOUT'] < 1:
                return False
            
            if self._fixed_settings['RETRY_ATTEMPTS'] < 0:
                return False
            
            return True
            
        except ConfigValidationError:
            return False
    
    def get_config_summary(self) -> str:
        """
        Retorna um resumo legível das configurações principais.
        
        Returns:
            str: Resumo formatado das configurações principais da Task 1.1
        """
        summary = []
        summary.append("=== CONFIGURAÇÕES FIXAS PYTESTE (Task 1.1) ===")
        summary.append(f"Formato de Imagem: {self._fixed_settings['IMG_FORMAT']}")
        summary.append(f"Diretório de Salvamento: {self._fixed_settings['SAVE_PATH']}")
        summary.append(f"Slice Habilitado: {self._fixed_settings['SLICE_ENABLED']}")
        summary.append(f"Altura do Slice: {self._fixed_settings['SLICE_HEIGHT']}px")
        summary.append(f"Largura Automática: {self._fixed_settings['AUTOMATIC_WIDTH']}")
        summary.append(f"Substituir Arquivos no Slice: {self._fixed_settings['SLICE_REPLACE_FILES']}")
        summary.append(f"Tipo de Detecção: {self._fixed_settings['DETECTION_TYPE']}")
        summary.append("=" * 50)
        
        return "\n".join(summary)
    
    def get_documentation(self) -> str:
        """
        Retorna documentação completa de cada configuração fixa.
        
        Atende ao critério "Documentação completa de cada configuração fixa"
        da Task 1.1.
        
        Returns:
            str: Documentação detalhada de todas as configurações
        """
        docs = []
        docs.append("# 📚 DOCUMENTAÇÃO - CONFIGURAÇÕES FIXAS PYTESTE")
        docs.append("")
        
        # Configurações principais da Task 1.1
        docs.append("## 🎯 Configurações Principais (Task 1.1)")
        docs.append("")
        docs.append("### IMG_FORMAT")
        docs.append("- **Valor**: 'png'")
        docs.append("- **Descrição**: Formato padrão para salvamento de imagens")
        docs.append("- **Justificativa**: PNG oferece qualidade sem perda")
        docs.append("")
        
        docs.append("### SAVE_PATH")
        docs.append("- **Valor**: './downloads/mediocre_uploads/'")
        docs.append("- **Descrição**: Diretório padrão para salvamento dos downloads")
        docs.append("- **Comportamento**: Criado automaticamente se não existir")
        docs.append("")
        
        docs.append("### SLICE_ENABLED")
        docs.append("- **Valor**: True")
        docs.append("- **Descrição**: Habilita fatiamento automático de imagens longas")
        docs.append("- **Impacto**: Melhora compatibilidade com leitores de manga")
        docs.append("")
        
        docs.append("### SLICE_HEIGHT")
        docs.append("- **Valor**: 15000")
        docs.append("- **Descrição**: Altura máxima em pixels antes do fatiamento")
        docs.append("- **Justificativa**: Otimizado para performance e compatibilidade")
        docs.append("")
        
        docs.append("### AUTOMATIC_WIDTH")
        docs.append("- **Valor**: True")
        docs.append("- **Descrição**: Ajusta largura automaticamente ao fatiar")
        docs.append("- **Comportamento**: Mantém proporção original da imagem")
        docs.append("")
        
        docs.append("### SLICE_REPLACE_FILES")
        docs.append("- **Valor**: True")
        docs.append("- **Descrição**: Substitui arquivos originais pelos fatiados")
        docs.append("- **Cuidado**: Remove originais após fatiamento bem-sucedido")
        docs.append("")
        
        docs.append("### DETECTION_TYPE")
        docs.append("- **Valor**: 'pixel'")
        docs.append("- **Descrição**: Método de detecção para processamento")
        docs.append("- **Alternativas**: 'pixel', 'content', 'smart'")
        docs.append("")
        
        return "\n".join(docs)