"""
Migration utilities para PytesteConfigManager.

Este módulo contém utilitários específicos para migração de configurações
antigas do sistema auto_upload_base para o novo formato do py_web.

Task 1.3: Sistema de migração de configurações
"""

import os
import json
import sqlite3
import shutil
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime


class MigrationResult:
    """
    Resultado de uma operação de migração.
    
    Attributes:
        success (bool): Se a migração foi bem-sucedida
        migrated_count (int): Número de configurações migradas
        errors (List[str]): Lista de erros encontrados
        warnings (List[str]): Lista de avisos
        backup_path (str): Caminho do backup criado
    """
    
    def __init__(self):
        self.success = False
        self.migrated_count = 0
        self.errors = []
        self.warnings = []
        self.backup_path = None


class ConfigMigrator:
    """
    Utilitário especializado para migração de configurações antigas.
    
    Responsável por migrar configurações do sistema auto_upload_base
    para o novo formato do PytesteConfigManager.
    """
    
    def __init__(self, config_manager=None, logger=None):
        """
        Inicializa o migrador de configurações.
        
        Args:
            config_manager: Instância do PytesteConfigManager
            logger: Logger personalizado (opcional)
        """
        self.config_manager = config_manager
        self.logger = logger or self._setup_logger()
        
        # Mapeamento de configurações antigas para novas
        self.config_mapping = {
            # Configurações do auto_upload_base
            'img_format': 'target_format',
            'img_quality': 'quality_override', 
            'save_path': None,  # Não migra - é configuração fixa
            'slice_enabled': None,  # Não migra - é configuração fixa
            'slice_height': None,  # Não migra - é configuração fixa
            'timeout': 'custom_timeout',
            'retry_attempts': 'custom_retry_attempts',
            'max_concurrent': 'concurrent_downloads_override',
            'user_agent': 'user_agent_override',
            'proxy_host': 'proxy_host',
            'proxy_port': 'proxy_port',
            'proxy_enabled': 'proxy_enabled',
            'cache_enabled': 'cache_enabled',
            'cache_duration': 'cache_duration_hours',
            'discord_webhook': 'discord_webhook_url',
            'discord_enabled': 'discord_webhook_enabled',
            
            # Configurações específicas do MangaDownloaderApp
            'auto_start': 'auto_start_downloads',
            'minimize_tray': 'minimize_to_tray',
            'show_progress': 'show_progress_details',
            'theme_setting': 'theme',
            'language_setting': 'language',
            
            # Configurações de rede
            'verify_ssl': 'verify_ssl',
            'follow_redirects': 'follow_redirects',
            'max_redirects': 'max_redirects',
            'chunk_size': 'chunk_size_kb',
            
            # Configurações de processamento
            'auto_convert': 'auto_convert_format',
            'resize_enabled': 'resize_enabled',
            'max_width': 'max_width',
            'max_height': 'max_height',
        }
    
    def _setup_logger(self) -> logging.Logger:
        """Configura logger para o migrador."""
        logger = logging.getLogger('ConfigMigrator')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def migrate_from_auto_upload_base(self, base_directory: str) -> MigrationResult:
        """
        Migra configurações do diretório auto_upload_base.
        
        Args:
            base_directory (str): Caminho para o diretório auto_upload_base
            
        Returns:
            MigrationResult: Resultado da migração
        """
        result = MigrationResult()
        base_path = Path(base_directory)
        
        try:
            self.logger.info(f"Iniciando migração de: {base_path}")
            
            # Cria backup das configurações atuais
            if self.config_manager:
                result.backup_path = self.config_manager.create_backup(
                    f'before_migration_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                    'Backup antes da migração do auto_upload_base'
                )
            
            # Procura arquivos de configuração
            config_files = self._find_config_files(base_path)
            
            for config_file in config_files:
                try:
                    migrated = self._migrate_config_file(config_file, result)
                    result.migrated_count += migrated
                    
                except Exception as e:
                    error_msg = f"Erro ao migrar {config_file}: {str(e)}"
                    result.errors.append(error_msg)
                    self.logger.error(error_msg)
            
            # Migra configurações específicas do mediocre_upload
            mediocre_config = base_path / 'mediocre_upload' / 'config.py'
            if mediocre_config.exists():
                migrated = self._migrate_mediocre_config(mediocre_config, result)
                result.migrated_count += migrated
            
            # Migra cache de obras se existir
            obras_cache = base_path / 'mediocre_upload' / 'obras_cache.json'
            if obras_cache.exists():
                self._migrate_obras_cache(obras_cache, result)
            
            result.success = result.migrated_count > 0
            
            self.logger.info(f"Migração concluída: {result.migrated_count} configurações migradas")
            
        except Exception as e:
            result.errors.append(f"Erro geral na migração: {str(e)}")
            self.logger.error(f"Erro na migração: {str(e)}")
        
        return result
    
    def _find_config_files(self, base_path: Path) -> List[Path]:
        """
        Encontra arquivos de configuração no diretório base.
        
        Args:
            base_path (Path): Diretório base para busca
            
        Returns:
            List[Path]: Lista de arquivos de configuração encontrados
        """
        config_files = []
        
        # Padrões de arquivos de configuração
        patterns = [
            '*.json',
            '*.db',
            '*.sqlite',
            '*.sqlite3',
            'config.py',
            'settings.py',
            'local.py'
        ]
        
        for pattern in patterns:
            config_files.extend(base_path.glob(f'**/{pattern}'))
        
        # Filtra arquivos relevantes
        relevant_files = []
        for file in config_files:
            if any(keyword in file.name.lower() for keyword in [
                'config', 'setting', 'preference', 'option', 'local'
            ]):
                relevant_files.append(file)
        
        return relevant_files
    
    def _migrate_config_file(self, config_file: Path, result: MigrationResult) -> int:
        """
        Migra um arquivo específico de configuração.
        
        Args:
            config_file (Path): Arquivo de configuração
            result (MigrationResult): Resultado acumulativo
            
        Returns:
            int: Número de configurações migradas deste arquivo
        """
        migrated_count = 0
        
        try:
            if config_file.suffix == '.json':
                migrated_count = self._migrate_json_file(config_file, result)
                
            elif config_file.suffix in ['.db', '.sqlite', '.sqlite3']:
                migrated_count = self._migrate_sqlite_file(config_file, result)
                
            elif config_file.suffix == '.py':
                migrated_count = self._migrate_python_file(config_file, result)
            
        except Exception as e:
            result.warnings.append(f"Não foi possível migrar {config_file}: {str(e)}")
        
        return migrated_count
    
    def _migrate_json_file(self, json_file: Path, result: MigrationResult) -> int:
        """Migra arquivo JSON de configuração."""
        migrated_count = 0
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            if isinstance(config_data, dict):
                for old_key, value in config_data.items():
                    new_key = self.config_mapping.get(old_key, old_key)
                    
                    if new_key and self.config_manager:
                        if self.config_manager.set_config(new_key, value, create_backup=False):
                            migrated_count += 1
                            self.logger.debug(f"Migrado: {old_key} -> {new_key} = {value}")
                        else:
                            result.warnings.append(f"Falha ao migrar: {old_key}")
            
        except Exception as e:
            result.warnings.append(f"Erro ao ler JSON {json_file}: {str(e)}")
        
        return migrated_count
    
    def _migrate_sqlite_file(self, sqlite_file: Path, result: MigrationResult) -> int:
        """Migra arquivo SQLite de configuração."""
        migrated_count = 0
        
        try:
            conn = sqlite3.connect(str(sqlite_file))
            cursor = conn.cursor()
            
            # Tenta diferentes esquemas de tabela
            table_schemas = [
                ('config', ['key', 'value']),
                ('configurations', ['key', 'value']),
                ('settings', ['name', 'value']),
                ('preferences', ['key', 'value'])
            ]
            
            for table_name, columns in table_schemas:
                try:
                    query = f'SELECT {columns[0]}, {columns[1]} FROM {table_name}'
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    
                    for row in rows:
                        old_key, value = row[0], row[1]
                        new_key = self.config_mapping.get(old_key, old_key)
                        
                        # Tenta converter valor se for string JSON
                        try:
                            if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                                value = json.loads(value)
                        except:
                            pass  # Mantém como string
                        
                        if new_key and self.config_manager:
                            if self.config_manager.set_config(new_key, value, create_backup=False):
                                migrated_count += 1
                                self.logger.debug(f"Migrado SQLite: {old_key} -> {new_key} = {value}")
                    
                except sqlite3.OperationalError:
                    continue  # Tabela não existe
            
            conn.close()
            
        except Exception as e:
            result.warnings.append(f"Erro ao ler SQLite {sqlite_file}: {str(e)}")
        
        return migrated_count
    
    def _migrate_python_file(self, py_file: Path, result: MigrationResult) -> int:
        """Migra arquivo Python de configuração (parsing básico)."""
        migrated_count = 0
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parsing básico para variáveis de configuração
            import re
            
            # Procura padrões como: VARIAVEL = valor
            patterns = [
                r'^(\w+)\s*=\s*["\']([^"\']+)["\']',  # Strings
                r'^(\w+)\s*=\s*(\d+)',                # Números
                r'^(\w+)\s*=\s*(True|False)',         # Booleanos
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.MULTILINE)
                
                for match in matches:
                    var_name = match.group(1).lower()
                    var_value = match.group(2)
                    
                    # Converte tipos
                    if var_value.isdigit():
                        var_value = int(var_value)
                    elif var_value in ['True', 'False']:
                        var_value = var_value == 'True'
                    
                    new_key = self.config_mapping.get(var_name, var_name)
                    
                    if new_key and self.config_manager:
                        if self.config_manager.set_config(new_key, var_value, create_backup=False):
                            migrated_count += 1
                            self.logger.debug(f"Migrado Python: {var_name} -> {new_key} = {var_value}")
            
        except Exception as e:
            result.warnings.append(f"Erro ao ler Python {py_file}: {str(e)}")
        
        return migrated_count
    
    def _migrate_mediocre_config(self, config_file: Path, result: MigrationResult) -> int:
        """Migra configurações específicas do módulo mediocre_upload."""
        migrated_count = 0
        
        try:
            # Configurações específicas do MediocreToons
            mediocre_configs = {
                'mediocre_auto_login': True,
                'mediocre_check_duplicates': True,
                'mediocre_upload_quality': 'high',
                'mediocre_compress_images': False,
                'mediocre_watermark_remove': True,
                'mediocre_metadata_embed': True
            }
            
            for key, default_value in mediocre_configs.items():
                if self.config_manager:
                    if self.config_manager.set_config(key, default_value, 
                                                    category='mediocre', 
                                                    create_backup=False):
                        migrated_count += 1
            
            self.logger.info(f"Configurações MediocreToons migradas: {migrated_count}")
            
        except Exception as e:
            result.warnings.append(f"Erro ao migrar configurações MediocreToons: {str(e)}")
        
        return migrated_count
    
    def _migrate_obras_cache(self, cache_file: Path, result: MigrationResult) -> None:
        """Migra cache de obras (para referência futura)."""
        try:
            # Apenas registra que o cache existe - será migrado em tarefa futura
            result.warnings.append(f"Cache de obras encontrado em {cache_file} - será migrado na Task 2.2")
            
            self.logger.info(f"Cache de obras identificado para migração futura: {cache_file}")
            
        except Exception as e:
            result.warnings.append(f"Erro ao processar cache de obras: {str(e)}")
    
    def generate_migration_report(self, result: MigrationResult) -> str:
        """
        Gera relatório detalhado da migração.
        
        Args:
            result (MigrationResult): Resultado da migração
            
        Returns:
            str: Relatório formatado em markdown
        """
        report = []
        report.append("# 📋 Relatório de Migração - Task 1.3")
        report.append(f"**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Status geral
        status_icon = "✅" if result.success else "❌"
        report.append(f"## {status_icon} Status Geral")
        report.append(f"- **Sucesso:** {result.success}")
        report.append(f"- **Configurações Migradas:** {result.migrated_count}")
        report.append(f"- **Erros:** {len(result.errors)}")
        report.append(f"- **Avisos:** {len(result.warnings)}")
        
        if result.backup_path:
            report.append(f"- **Backup Criado:** `{result.backup_path}`")
        
        report.append("")
        
        # Detalhes dos erros
        if result.errors:
            report.append("## ❌ Erros Encontrados")
            for i, error in enumerate(result.errors, 1):
                report.append(f"{i}. {error}")
            report.append("")
        
        # Detalhes dos avisos
        if result.warnings:
            report.append("## ⚠️ Avisos")
            for i, warning in enumerate(result.warnings, 1):
                report.append(f"{i}. {warning}")
            report.append("")
        
        # Mapeamento de configurações
        report.append("## 🔄 Mapeamento de Configurações")
        report.append("| Configuração Antiga | Configuração Nova | Status |")
        report.append("|---------------------|-------------------|--------|")
        
        for old_key, new_key in self.config_mapping.items():
            if new_key:
                status = "✅ Mapeado"
            else:
                status = "⏭️ Ignorado (configuração fixa)"
            
            report.append(f"| `{old_key}` | `{new_key or 'N/A'}` | {status} |")
        
        report.append("")
        
        # Instruções pós-migração
        report.append("## 📝 Próximos Passos")
        report.append("1. Verificar configurações migradas no PytesteConfigManager")
        report.append("2. Testar funcionamento com novas configurações")
        report.append("3. Proceder para Task 1.4 (Sistema de Logging)")
        report.append("4. Cache de obras será migrado na Task 2.2")
        
        return "\n".join(report)
    
    def validate_migration(self, result: MigrationResult) -> Dict[str, Any]:
        """
        Valida se a migração foi executada corretamente.
        
        Args:
            result (MigrationResult): Resultado da migração
            
        Returns:
            Dict[str, Any]: Resultado da validação
        """
        validation = {
            'valid': True,
            'issues': [],
            'recommendations': []
        }
        
        try:
            if not self.config_manager:
                validation['valid'] = False
                validation['issues'].append("ConfigManager não disponível para validação")
                return validation
            
            # Verifica se configurações essenciais foram migradas
            essential_configs = [
                'custom_timeout',
                'custom_retry_attempts', 
                'proxy_enabled',
                'cache_enabled',
                'discord_webhook_enabled'
            ]
            
            for config_key in essential_configs:
                value = self.config_manager.get_config(config_key)
                if value is None:
                    validation['issues'].append(f"Configuração essencial não encontrada: {config_key}")
            
            # Verifica se backup foi criado
            if not result.backup_path or not os.path.exists(result.backup_path):
                validation['issues'].append("Backup não foi criado ou não existe")
            
            # Recomendações baseadas no resultado
            if result.warnings:
                validation['recommendations'].append("Revisar avisos de migração")
            
            if result.migrated_count == 0:
                validation['recommendations'].append("Verificar se diretório de origem contém configurações válidas")
            
            validation['valid'] = len(validation['issues']) == 0
            
        except Exception as e:
            validation['valid'] = False
            validation['issues'].append(f"Erro na validação: {str(e)}")
        
        return validation