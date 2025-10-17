"""
Task 1.4: Sistema de Logging Unificado
Implementa sistema centralizado de logs com rotação automática e diferentes níveis.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from enum import Enum
import json


class LogLevel(Enum):
    """Níveis de log disponíveis"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(Enum):
    """Formatos de log disponíveis"""
    SIMPLE = "%(levelname)s - %(message)s"
    DETAILED = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    FULL = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s"
    JSON = "json"


class UnifiedLogger:
    """
    Sistema de logging unificado com suporte a:
    - Múltiplos handlers (arquivo, console, rotação)
    - Diferentes formatos (simples, detalhado, JSON)
    - Rotação automática de logs
    - Configuração flexível por módulo
    """
    
    _instances: Dict[str, 'UnifiedLogger'] = {}
    _global_config: Dict[str, Any] = {
        'log_dir': 'logs',
        'max_file_size': 10 * 1024 * 1024,  # 10MB
        'backup_count': 5,
        'console_level': LogLevel.INFO,
        'file_level': LogLevel.DEBUG,
        'format': LogFormat.DETAILED,
        'enable_console': True,
        'enable_file': True,
        'enable_rotation': True
    }
    
    def __init__(self, name: str = "pyteste"):
        """
        Inicializa o logger unificado
        
        Args:
            name: Nome do logger (geralmente nome do módulo)
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Evita handlers duplicados
        if not self.logger.handlers:
            self._setup_handlers()
    
    @classmethod
    def get_logger(cls, name: str = "pyteste") -> 'UnifiedLogger':
        """
        Obtém instância singleton do logger para um nome específico
        
        Args:
            name: Nome do logger
            
        Returns:
            Instância do UnifiedLogger
        """
        if name not in cls._instances:
            cls._instances[name] = cls(name)
        return cls._instances[name]
    
    @classmethod
    def configure_global(cls, **config) -> None:
        """
        Configura parâmetros globais do sistema de logging
        
        Args:
            **config: Configurações globais
        """
        cls._global_config.update(config)
        
        # Reconfigura todas as instâncias existentes
        for instance in cls._instances.values():
            instance._reconfigure()
    
    def _setup_handlers(self) -> None:
        """Configura os handlers do logger"""
        self.logger.handlers.clear()
        
        # Handler para console
        if self._global_config['enable_console']:
            self._add_console_handler()
        
        # Handler para arquivo
        if self._global_config['enable_file']:
            self._add_file_handler()
    
    def _add_console_handler(self) -> None:
        """Adiciona handler para saída no console"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(
            getattr(logging, self._global_config['console_level'].value)
        )
        
        formatter = self._get_formatter()
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(console_handler)
    
    def _add_file_handler(self) -> None:
        """Adiciona handler para arquivo com rotação opcional"""
        log_dir = Path(self._global_config['log_dir'])
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"{self.name}.log"
        
        if self._global_config['enable_rotation']:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=self._global_config['max_file_size'],
                backupCount=self._global_config['backup_count'],
                encoding='utf-8'
            )
        else:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
        
        file_handler.setLevel(
            getattr(logging, self._global_config['file_level'].value)
        )
        
        formatter = self._get_formatter()
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
    
    def _get_formatter(self) -> logging.Formatter:
        """
        Obtém o formatador baseado na configuração
        
        Returns:
            Formatter configurado
        """
        log_format = self._global_config['format']
        
        if log_format == LogFormat.JSON:
            return JsonFormatter()
        else:
            return logging.Formatter(
                log_format.value,
                datefmt='%Y-%m-%d %H:%M:%S'
            )
    
    def _reconfigure(self) -> None:
        """Reconfigura o logger com as novas configurações globais"""
        self._setup_handlers()
    
    # Métodos de logging
    def debug(self, message: str, **kwargs) -> None:
        """Log de debug"""
        self.logger.debug(message, **self._prepare_kwargs(kwargs))
    
    def info(self, message: str, **kwargs) -> None:
        """Log de informação"""
        self.logger.info(message, **self._prepare_kwargs(kwargs))
    
    def warning(self, message: str, **kwargs) -> None:
        """Log de aviso"""
        self.logger.warning(message, **self._prepare_kwargs(kwargs))
    
    def error(self, message: str, **kwargs) -> None:
        """Log de erro"""
        self.logger.error(message, **self._prepare_kwargs(kwargs))
    
    def critical(self, message: str, **kwargs) -> None:
        """Log crítico"""
        self.logger.critical(message, **self._prepare_kwargs(kwargs))
    
    def exception(self, message: str, **kwargs) -> None:
        """Log de exceção com traceback"""
        self.logger.exception(message, **self._prepare_kwargs(kwargs))
    
    def _prepare_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepara kwargs para o logger
        
        Args:
            kwargs: Argumentos adicionais
            
        Returns:
            Kwargs preparados
        """
        # Adiciona informações extras se necessário
        if self._global_config['format'] == LogFormat.JSON:
            return {'extra': kwargs}
        return {}
    
    # Métodos de gerenciamento
    def set_level(self, level: LogLevel) -> None:
        """
        Define o nível de log para esta instância
        
        Args:
            level: Nível de log
        """
        self.logger.setLevel(getattr(logging, level.value))
    
    def add_file_handler(self, filename: str, level: LogLevel = LogLevel.DEBUG) -> None:
        """
        Adiciona handler adicional para arquivo específico
        
        Args:
            filename: Nome do arquivo
            level: Nível de log para este handler
        """
        log_dir = Path(self._global_config['log_dir'])
        log_dir.mkdir(exist_ok=True)
        
        handler = logging.FileHandler(log_dir / filename, encoding='utf-8')
        handler.setLevel(getattr(logging, level.value))
        handler.setFormatter(self._get_formatter())
        
        self.logger.addHandler(handler)
    
    def get_log_files(self) -> List[Path]:
        """
        Obtém lista de arquivos de log existentes
        
        Returns:
            Lista de arquivos de log
        """
        log_dir = Path(self._global_config['log_dir'])
        if not log_dir.exists():
            return []
        
        return list(log_dir.glob(f"{self.name}*.log*"))
    
    def clean_old_logs(self, days: int = 30) -> int:
        """
        Remove logs mais antigos que o número especificado de dias
        
        Args:
            days: Dias para manter os logs
            
        Returns:
            Número de arquivos removidos
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        removed_count = 0
        
        for log_file in self.get_log_files():
            if log_file.stat().st_mtime < cutoff_date.timestamp():
                log_file.unlink()
                removed_count += 1
        
        return removed_count
    
    def get_log_stats(self) -> Dict[str, Any]:
        """
        Obtém estatísticas dos logs
        
        Returns:
            Estatísticas dos logs
        """
        log_files = self.get_log_files()
        total_size = sum(f.stat().st_size for f in log_files if f.exists())
        
        return {
            'total_files': len(log_files),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'oldest_log': min((f.stat().st_mtime for f in log_files), default=None),
            'newest_log': max((f.stat().st_mtime for f in log_files), default=None)
        }


class JsonFormatter(logging.Formatter):
    """Formatador JSON para logs estruturados"""
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Formata o log como JSON
        
        Args:
            record: Record do log
            
        Returns:
            Log formatado como JSON
        """
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Adiciona informações extras se disponíveis
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
        
        # Adiciona traceback se for uma exceção
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class LoggerMixin:
    """
    Mixin para adicionar capacidades de logging a qualquer classe
    """
    
    @property
    def logger(self) -> UnifiedLogger:
        """Obtém o logger para esta classe"""
        if not hasattr(self, '_logger'):
            self._logger = UnifiedLogger.get_logger(self.__class__.__name__)
        return self._logger


# Função de conveniência para obter logger global
def get_logger(name: str = "pyteste") -> UnifiedLogger:
    """
    Função de conveniência para obter um logger
    
    Args:
        name: Nome do logger
        
    Returns:
        Instância do UnifiedLogger
    """
    return UnifiedLogger.get_logger(name)


# Configuração padrão para desenvolvimento
def setup_development_logging():
    """Configura logging para ambiente de desenvolvimento"""
    UnifiedLogger.configure_global(
        console_level=LogLevel.DEBUG,
        file_level=LogLevel.DEBUG,
        format=LogFormat.DETAILED,
        enable_console=True,
        enable_file=True,
        enable_rotation=True
    )


# Configuração padrão para produção
def setup_production_logging():
    """Configura logging para ambiente de produção"""
    UnifiedLogger.configure_global(
        console_level=LogLevel.WARNING,
        file_level=LogLevel.INFO,
        format=LogFormat.JSON,
        enable_console=False,
        enable_file=True,
        enable_rotation=True,
        max_file_size=50 * 1024 * 1024,  # 50MB
        backup_count=10
    )