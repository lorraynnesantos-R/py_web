"""
PytesteConfigManager - Gerenciador de configurações flexíveis do sistema PyWeb.

Este módulo implementa o sistema centralizado para gerenciar configurações
flexíveis (não-fixas) do pyteste, com suporte a SQLite e migração automática.

Task 1.3: Implementar PytesteConfigManager
"""

import os
import json
import sqlite3
import logging
import shutil
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

from .fixed_config import PytesteFixedConfig, ConfigValidationError


class ConfigMigrationError(Exception):
    """Exceção lançada quando ocorre erro na migração de configurações."""
    pass


class ConfigBackupError(Exception):
    """Exceção lançada quando ocorre erro no backup de configurações."""
    pass


class PytesteConfigManager:
    """
    Gerenciador centralizado de configurações flexíveis do sistema PytesteCore.
    
    Responsável por gerenciar configurações que podem ser alteradas pelo usuário,
    mantendo compatibilidade com SQLite existente e fornecendo migração automática.
    
    Attributes:
        config_db_path (Path): Caminho para o banco SQLite de configurações
        backup_dir (Path): Diretório para backups de configuração
        fixed_config (PytesteFixedConfig): Referência para configurações fixas
        logger (logging.Logger): Logger para operações
    """
    
    def __init__(
        self, 
        config_db_path: Optional[str] = None,
        backup_dir: Optional[str] = None,
        fixed_config: Optional[PytesteFixedConfig] = None
    ):
        """
        Inicializa o gerenciador de configurações.
        
        Args:
            config_db_path (Optional[str]): Caminho personalizado para o banco SQLite
            backup_dir (Optional[str]): Diretório personalizado para backups
            fixed_config (Optional[PytesteFixedConfig]): Configurações fixas
        """
        self.fixed_config = fixed_config or PytesteFixedConfig()
        
        # Configura caminhos
        base_dir = Path(self.fixed_config.get_directory_settings()['SAVE_PATH']).parent
        self.config_db_path = Path(config_db_path) if config_db_path else base_dir / 'config' / 'pyteste_config.db'
        self.backup_dir = Path(backup_dir) if backup_dir else base_dir / 'config' / 'backups'
        
        # Cria diretórios necessários
        self.config_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Configura logger
        self.logger = self._setup_logger()
        
        # Inicializa banco de dados
        self._initialize_database()
        
        # Configurações padrão flexíveis
        self._default_flexible_configs = {
            # Configurações de Proxy/VPN
            'proxy_enabled': False,
            'proxy_host': '',
            'proxy_port': 8080,
            'proxy_username': '',
            'proxy_password': '',
            'vpn_enabled': False,
            'vpn_profile': '',
            
            # Headers HTTP customizáveis
            'custom_headers': {},
            'user_agent_override': '',
            'referer_policy': 'default',
            'accept_language': 'pt-BR,pt;q=0.9,en;q=0.8',
            
            # Timeout e Retry customizáveis
            'custom_timeout': 0,  # 0 = usa padrão das configurações fixas
            'custom_retry_attempts': 0,  # 0 = usa padrão das configurações fixas
            'retry_delay': 1.0,
            'exponential_backoff': True,
            
            # Cache settings
            'cache_enabled': True,
            'cache_duration_hours': 24,
            'cache_max_size_mb': 500,
            'auto_cleanup_cache': True,
            'cache_compression': True,
            
            # Configurações de download avançadas
            'concurrent_downloads_override': 0,  # 0 = usa padrão das configurações fixas
            'chunk_size_kb': 8192,
            'verify_ssl': True,
            'follow_redirects': True,
            'max_redirects': 10,
            
            # Configurações de processamento
            'auto_convert_format': False,
            'target_format': 'png',
            'quality_override': 0,  # 0 = usa padrão das configurações fixas
            'resize_enabled': False,
            'max_width': 0,
            'max_height': 0,
            
            # Configurações de notificação
            'discord_webhook_enabled': False,
            'discord_webhook_url': '',
            'email_notifications': False,
            'email_smtp_server': '',
            'email_username': '',
            'email_password': '',
            
            # Configurações de interface
            'theme': 'default',
            'language': 'pt-BR',
            'auto_start_downloads': False,
            'show_progress_details': True,
            'minimize_to_tray': False
        }
    
    def _setup_logger(self) -> logging.Logger:
        """
        Configura o logger para o PytesteConfigManager.
        
        Returns:
            logging.Logger: Logger configurado
        """
        logger = logging.getLogger('PytesteConfigManager')
        logger.setLevel(logging.INFO)
        
        # Remove handlers existentes para evitar duplicação
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Handler para arquivo
        log_path = Path(self.fixed_config.get_directory_settings()['LOG_PATH'])
        log_path.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(
            log_path / 'config_manager.log',
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        
        # Formatação
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        return logger
    
    def _initialize_database(self) -> None:
        """
        Inicializa o banco de dados SQLite para configurações.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Tabela principal de configurações
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS configurations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key TEXT UNIQUE NOT NULL,
                        value TEXT NOT NULL,
                        type TEXT NOT NULL,
                        category TEXT DEFAULT 'general',
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Tabela de histórico de alterações
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS config_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_key TEXT NOT NULL,
                        old_value TEXT,
                        new_value TEXT NOT NULL,
                        changed_by TEXT DEFAULT 'system',
                        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Tabela de backups
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS config_backups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        backup_name TEXT UNIQUE NOT NULL,
                        backup_path TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        description TEXT
                    )
                ''')
                
                conn.commit()
                
            # Inicializa configurações padrão se necessário
            self._initialize_default_configs()
            
            self.logger.info("Banco de dados de configurações inicializado com sucesso")
            
        except Exception as e:
            self.logger.error(f"Erro ao inicializar banco de dados: {str(e)}")
            raise ConfigValidationError(f"Falha na inicialização do banco: {str(e)}")
    
    @contextmanager
    def _get_connection(self):
        """
        Context manager para conexões SQLite.
        
        Yields:
            sqlite3.Connection: Conexão com o banco
        """
        conn = None
        try:
            conn = sqlite3.connect(str(self.config_db_path))
            conn.row_factory = sqlite3.Row
            yield conn
        finally:
            if conn:
                conn.close()
    
    def _initialize_default_configs(self) -> None:
        """
        Inicializa configurações padrão no banco de dados.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                for key, default_value in self._default_flexible_configs.items():
                    # Verifica se a configuração já existe
                    cursor.execute('SELECT id FROM configurations WHERE key = ?', (key,))
                    
                    if not cursor.fetchone():
                        # Determina tipo e categoria
                        value_type = type(default_value).__name__
                        category = self._get_config_category(key)
                        description = self._get_config_description(key)
                        
                        # Serializa valor para JSON
                        serialized_value = json.dumps(default_value)
                        
                        cursor.execute('''
                            INSERT INTO configurations 
                            (key, value, type, category, description)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (key, serialized_value, value_type, category, description))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Erro ao inicializar configurações padrão: {str(e)}")
            raise
    
    def _get_config_category(self, key: str) -> str:
        """
        Determina a categoria de uma configuração baseada na chave.
        
        Args:
            key (str): Chave da configuração
            
        Returns:
            str: Categoria da configuração
        """
        if 'proxy' in key or 'vpn' in key:
            return 'network'
        elif 'header' in key or 'user_agent' in key or 'referer' in key:
            return 'http'
        elif 'timeout' in key or 'retry' in key:
            return 'performance'
        elif 'cache' in key:
            return 'cache'
        elif 'download' in key or 'concurrent' in key:
            return 'download'
        elif 'format' in key or 'quality' in key or 'resize' in key:
            return 'processing'
        elif 'discord' in key or 'email' in key or 'notification' in key:
            return 'notifications'
        elif 'theme' in key or 'language' in key or 'interface' in key:
            return 'interface'
        else:
            return 'general'
    
    def _get_config_description(self, key: str) -> str:
        """
        Retorna descrição para uma configuração baseada na chave.
        
        Args:
            key (str): Chave da configuração
            
        Returns:
            str: Descrição da configuração
        """
        descriptions = {
            'proxy_enabled': 'Habilita uso de proxy para downloads',
            'proxy_host': 'Endereço do servidor proxy',
            'proxy_port': 'Porta do servidor proxy',
            'vpn_enabled': 'Habilita uso de VPN',
            'cache_enabled': 'Habilita sistema de cache',
            'cache_duration_hours': 'Duração do cache em horas',
            'custom_timeout': 'Timeout personalizado (0 = padrão)',
            'discord_webhook_enabled': 'Habilita notificações Discord',
            'theme': 'Tema da interface do usuário',
            'language': 'Idioma da interface',
        }
        
        return descriptions.get(key, f'Configuração {key}')
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Obtém valor de uma configuração.
        
        Args:
            key (str): Chave da configuração
            default (Any): Valor padrão se não encontrado
            
        Returns:
            Any: Valor da configuração
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value, type FROM configurations WHERE key = ?', (key,))
                result = cursor.fetchone()
                
                if result:
                    # Desserializa valor do JSON
                    return json.loads(result['value'])
                else:
                    # Retorna padrão se não encontrado
                    if default is not None:
                        return default
                    else:
                        return self._default_flexible_configs.get(key, None)
                
        except Exception as e:
            self.logger.error(f"Erro ao obter configuração '{key}': {str(e)}")
            return default
    
    def set_config(
        self, 
        key: str, 
        value: Any, 
        category: str = 'general',
        description: str = None,
        create_backup: bool = True
    ) -> bool:
        """
        Define valor de uma configuração.
        
        Args:
            key (str): Chave da configuração
            value (Any): Valor da configuração
            category (str): Categoria da configuração
            description (str): Descrição da configuração
            create_backup (bool): Se deve criar backup antes da alteração
            
        Returns:
            bool: True se alteração foi bem-sucedida
        """
        try:
            # Validação da configuração
            if not self._validate_config(key, value):
                return False
            
            # Cria backup se solicitado
            if create_backup:
                self.create_backup(f'before_set_{key}_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Obtém valor atual para histórico
                cursor.execute('SELECT value FROM configurations WHERE key = ?', (key,))
                current_result = cursor.fetchone()
                old_value = json.loads(current_result['value']) if current_result else None
                
                # Serializa novo valor
                serialized_value = json.dumps(value)
                value_type = type(value).__name__
                
                # Atualiza ou insere configuração
                cursor.execute('''
                    INSERT OR REPLACE INTO configurations 
                    (key, value, type, category, description, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    key, 
                    serialized_value, 
                    value_type,
                    category or self._get_config_category(key),
                    description or self._get_config_description(key)
                ))
                
                # Registra no histórico
                cursor.execute('''
                    INSERT INTO config_history 
                    (config_key, old_value, new_value, changed_by)
                    VALUES (?, ?, ?, ?)
                ''', (key, json.dumps(old_value), serialized_value, 'user'))
                
                conn.commit()
                
            self.logger.info(f"Configuração '{key}' alterada para: {value}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao definir configuração '{key}': {str(e)}")
            return False
    
    def _validate_config(self, key: str, value: Any) -> bool:
        """
        Valida uma configuração antes de salvá-la.
        
        Args:
            key (str): Chave da configuração
            value (Any): Valor a validar
            
        Returns:
            bool: True se válido
        """
        try:
            # Validações específicas por tipo de configuração
            if key.endswith('_port') and isinstance(value, int):
                return 1 <= value <= 65535
                
            elif key.endswith('_enabled') and not isinstance(value, bool):
                return False
                
            elif key in ['cache_duration_hours', 'cache_max_size_mb'] and isinstance(value, int):
                return value >= 0
                
            elif key in ['custom_timeout', 'custom_retry_attempts'] and isinstance(value, int):
                return value >= 0
                
            elif key == 'retry_delay' and isinstance(value, (int, float)):
                return value >= 0.1
                
            elif key == 'max_redirects' and isinstance(value, int):
                return 0 <= value <= 50
                
            elif key in ['max_width', 'max_height'] and isinstance(value, int):
                return value >= 0
                
            elif key == 'quality_override' and isinstance(value, int):
                return 0 <= value <= 100
                
            elif key == 'chunk_size_kb' and isinstance(value, int):
                return value >= 1024  # Mínimo 1MB
                
            # Validação geral - deve ser serializável em JSON
            json.dumps(value)
            return True
            
        except Exception as e:
            self.logger.error(f"Erro na validação de '{key}': {str(e)}")
            return False
    
    def get_all_configs(self, category: str = None) -> Dict[str, Any]:
        """
        Obtém todas as configurações ou de uma categoria específica.
        
        Args:
            category (str): Categoria específica (opcional)
            
        Returns:
            Dict[str, Any]: Dicionário com todas as configurações
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                if category:
                    cursor.execute(
                        'SELECT key, value FROM configurations WHERE category = ?',
                        (category,)
                    )
                else:
                    cursor.execute('SELECT key, value FROM configurations')
                
                configs = {}
                for row in cursor.fetchall():
                    configs[row['key']] = json.loads(row['value'])
                
                return configs
                
        except Exception as e:
            self.logger.error(f"Erro ao obter configurações: {str(e)}")
            return {}
    
    def get_config_categories(self) -> List[str]:
        """
        Obtém lista de todas as categorias de configuração.
        
        Returns:
            List[str]: Lista de categorias
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT category FROM configurations ORDER BY category')
                return [row['category'] for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"Erro ao obter categorias: {str(e)}")
            return []
    
    def create_backup(self, backup_name: str = None, description: str = None) -> str:
        """
        Cria backup das configurações atuais.
        
        Args:
            backup_name (str): Nome personalizado do backup
            description (str): Descrição do backup
            
        Returns:
            str: Caminho do arquivo de backup criado
        """
        try:
            # Gera nome do backup se não fornecido
            if not backup_name:
                backup_name = f'config_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            
            backup_file = self.backup_dir / f'{backup_name}.json'
            
            # Obtém todas as configurações
            all_configs = self.get_all_configs()
            
            # Adiciona metadados do backup
            backup_data = {
                'metadata': {
                    'backup_name': backup_name,
                    'created_at': datetime.now().isoformat(),
                    'description': description or 'Backup automático',
                    'total_configs': len(all_configs),
                    'pyteste_version': '2.0.0'
                },
                'configurations': all_configs
            }
            
            # Salva backup
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            # Registra backup no banco
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO config_backups 
                    (backup_name, backup_path, description)
                    VALUES (?, ?, ?)
                ''', (backup_name, str(backup_file), description))
                conn.commit()
            
            self.logger.info(f"Backup criado: {backup_file}")
            return str(backup_file)
            
        except Exception as e:
            self.logger.error(f"Erro ao criar backup: {str(e)}")
            raise ConfigBackupError(f"Falha ao criar backup: {str(e)}")
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        Restaura configurações de um backup.
        
        Args:
            backup_path (str): Caminho para o arquivo de backup
            
        Returns:
            bool: True se restauração foi bem-sucedida
        """
        try:
            # Cria backup atual antes de restaurar
            self.create_backup('before_restore_' + datetime.now().strftime("%Y%m%d_%H%M%S"))
            
            # Carrega dados do backup
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            configurations = backup_data.get('configurations', {})
            
            # Restaura cada configuração
            restored_count = 0
            for key, value in configurations.items():
                if self.set_config(key, value, create_backup=False):
                    restored_count += 1
            
            self.logger.info(f"Backup restaurado: {restored_count} configurações")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao restaurar backup: {str(e)}")
            return False
    
    def migrate_from_old_config(self, old_config_path: str) -> bool:
        """
        Migra configurações do sistema antigo.
        
        Args:
            old_config_path (str): Caminho para configurações antigas
            
        Returns:
            bool: True se migração foi bem-sucedida
        """
        try:
            # Cria backup antes da migração
            self.create_backup('before_migration_' + datetime.now().strftime("%Y%m%d_%H%M%S"))
            
            migrated_count = 0
            
            # Tenta diferentes formatos de configuração antiga
            if os.path.exists(old_config_path):
                if old_config_path.endswith('.json'):
                    migrated_count = self._migrate_from_json(old_config_path)
                elif old_config_path.endswith('.db') or 'sqlite' in old_config_path:
                    migrated_count = self._migrate_from_sqlite(old_config_path)
            
            self.logger.info(f"Migração concluída: {migrated_count} configurações migradas")
            return migrated_count > 0
            
        except Exception as e:
            self.logger.error(f"Erro na migração: {str(e)}")
            raise ConfigMigrationError(f"Falha na migração: {str(e)}")
    
    def _migrate_from_json(self, json_path: str) -> int:
        """Migra configurações de arquivo JSON."""
        with open(json_path, 'r', encoding='utf-8') as f:
            old_configs = json.load(f)
        
        migrated_count = 0
        for key, value in old_configs.items():
            if self.set_config(key, value, create_backup=False):
                migrated_count += 1
        
        return migrated_count
    
    def _migrate_from_sqlite(self, sqlite_path: str) -> int:
        """Migra configurações de banco SQLite antigo."""
        migrated_count = 0
        
        try:
            conn = sqlite3.connect(sqlite_path)
            cursor = conn.cursor()
            
            # Tenta diferentes esquemas de tabela que podem existir
            tables = ['config', 'configurations', 'settings']
            
            for table in tables:
                try:
                    cursor.execute(f'SELECT * FROM {table}')
                    rows = cursor.fetchall()
                    
                    for row in rows:
                        # Adapta baseado na estrutura encontrada
                        if len(row) >= 2:
                            key, value = row[0], row[1]
                            if self.set_config(str(key), value, create_backup=False):
                                migrated_count += 1
                    
                except sqlite3.OperationalError:
                    continue  # Tabela não existe
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Erro ao migrar SQLite: {str(e)}")
        
        return migrated_count
    
    def get_effective_config(self, key: str) -> Any:
        """
        Obtém configuração efetiva, considerando override de configurações fixas.
        
        Para configurações que podem fazer override das fixas (como timeout),
        retorna o valor personalizado se definido, senão o valor das configurações fixas.
        
        Args:
            key (str): Chave da configuração
            
        Returns:
            Any: Valor efetivo da configuração
        """
        # Mapeamento entre configurações flexíveis e fixas
        override_mapping = {
            'custom_timeout': 'TIMEOUT',
            'custom_retry_attempts': 'RETRY_ATTEMPTS',
            'concurrent_downloads_override': 'MAX_CONCURRENT_DOWNLOADS',
            'quality_override': 'IMG_QUALITY'
        }
        
        if key in override_mapping:
            custom_value = self.get_config(key, 0)
            
            if custom_value > 0:  # 0 significa "usar padrão"
                return custom_value
            else:
                # Retorna valor das configurações fixas
                fixed_settings = self.fixed_config.get_fixed_settings()
                return fixed_settings.get(override_mapping[key])
        
        # Para outras configurações, retorna valor normal
        return self.get_config(key)
    
    def reset_to_defaults(self, category: str = None) -> bool:
        """
        Reseta configurações para valores padrão.
        
        Args:
            category (str): Categoria específica para resetar (opcional)
            
        Returns:
            bool: True se reset foi bem-sucedido
        """
        try:
            # Cria backup antes do reset
            backup_name = f'before_reset_{category or "all"}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            self.create_backup(backup_name)
            
            reset_count = 0
            
            for key, default_value in self._default_flexible_configs.items():
                config_category = self._get_config_category(key)
                
                if category is None or config_category == category:
                    if self.set_config(key, default_value, create_backup=False):
                        reset_count += 1
            
            self.logger.info(f"Reset concluído: {reset_count} configurações resetadas")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro no reset: {str(e)}")
            return False
    
    def get_config_info(self) -> Dict[str, Any]:
        """
        Retorna informações sobre o sistema de configurações.
        
        Returns:
            Dict[str, Any]: Informações do sistema
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Conta configurações por categoria
                cursor.execute('''
                    SELECT category, COUNT(*) as count 
                    FROM configurations 
                    GROUP BY category
                ''')
                categories = {row['category']: row['count'] for row in cursor.fetchall()}
                
                # Conta total
                cursor.execute('SELECT COUNT(*) as total FROM configurations')
                total_configs = cursor.fetchone()['total']
                
                # Conta backups
                cursor.execute('SELECT COUNT(*) as total FROM config_backups')
                total_backups = cursor.fetchone()['total']
            
            return {
                'config_manager_version': '1.0.0',
                'database_path': str(self.config_db_path),
                'backup_directory': str(self.backup_dir),
                'total_configurations': total_configs,
                'configurations_by_category': categories,
                'total_backups': total_backups,
                'default_configs_available': len(self._default_flexible_configs),
                'fixed_config_integration': True
            }
            
        except Exception as e:
            self.logger.error(f"Erro ao obter informações: {str(e)}")
            return {'error': str(e)}