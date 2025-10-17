"""
Task 2.2: Script de Migração de Dados Antigos
Converte obras_mapeadas.json do formato antigo (auto_upload_base) para o novo formato distribuído (py_web).
"""

import json
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from urllib.parse import urlparse
import uuid
import argparse


class MigrationError(Exception):
    """Erro durante migração"""
    pass


class MigrationReporter:
    """Relatório detalhado da migração"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.total_obras = 0
        self.migrated_obras = 0
        self.skipped_obras = 0
        self.errors = []
        self.warnings = []
        self.scan_stats = {}
        self.backup_files = []
    
    def add_error(self, message: str, obra_data: Dict[str, Any] = None):
        """Adiciona erro ao relatório"""
        error_info = {
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "obra": obra_data.get("nome_mediocre") if obra_data else None
        }
        self.errors.append(error_info)
    
    def add_warning(self, message: str, obra_data: Dict[str, Any] = None):
        """Adiciona aviso ao relatório"""
        warning_info = {
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "obra": obra_data.get("nome_mediocre") if obra_data else None
        }
        self.warnings.append(warning_info)
    
    def update_scan_stats(self, scan_name: str, count: int):
        """Atualiza estatísticas por scan"""
        self.scan_stats[scan_name] = self.scan_stats.get(scan_name, 0) + count
    
    def generate_report(self) -> Dict[str, Any]:
        """Gera relatório final"""
        end_time = datetime.now()
        duration = end_time - self.start_time
        
        return {
            "migration_summary": {
                "start_time": self.start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration.total_seconds(),
                "total_obras": self.total_obras,
                "migrated_obras": self.migrated_obras,
                "skipped_obras": self.skipped_obras,
                "success_rate": (self.migrated_obras / self.total_obras * 100) if self.total_obras > 0 else 0
            },
            "scan_distribution": self.scan_stats,
            "backup_files": self.backup_files,
            "errors": self.errors,
            "warnings": self.warnings,
            "status": "SUCCESS" if len(self.errors) == 0 else "PARTIAL" if self.migrated_obras > 0 else "FAILED"
        }


class OldFormatMigrator:
    """
    Migrador do formato antigo obras_mapeadas.json para novo formato distribuído
    """
    
    def __init__(self, py_web_root: Path):
        """
        Inicializa o migrador
        
        Args:
            py_web_root: Diretório raiz do py_web
        """
        self.py_web_root = Path(py_web_root)
        self.data_dir = self.py_web_root / "data" / "mapping"
        self.backup_dir = self.data_dir / "backups"
        self.reporter = MigrationReporter()
        
        # Mapeamento de domínios para nomes de scan
        self.domain_mappings = {
            "astratoons.com": "astratoons",
            "mangayabu.top": "mangayabu", 
            "mangayabu.com": "mangayabu",
            "lermanga.org": "lermanga",
            "tsundokutraducoes.com.br": "tsundoku",
            "slimeread.com": "slimeread",
            "goldenmangas.top": "goldenmangas",
            "neoxscan.com": "neoxscan",
            "readergen.com": "readergen",
            "mangaschan.net": "mangaschan"
        }
        
        # Garantir que diretórios existem
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def detect_scan_from_url(self, url: str) -> str:
        """
        Detecta o scan baseado na URL
        
        Args:
            url: URL da obra
            
        Returns:
            Nome do scan detectado ou 'unknown'
        """
        try:
            if not url:
                return "unknown"
            
            parsed = urlparse(url.lower())
            domain = parsed.netloc.replace("www.", "")
            
            # Busca mapeamento exato
            for mapped_domain, scan_name in self.domain_mappings.items():
                if domain == mapped_domain or mapped_domain in domain:
                    return scan_name
            
            # Se não encontrou, usa o domínio como nome do scan
            if domain:
                # Remove caracteres especiais
                clean_name = "".join(c for c in domain if c.isalnum() or c in "._-")
                return clean_name.replace(".", "_")
            
            return "unknown"
            
        except Exception:
            return "unknown"
    
    def convert_obra_to_new_format(self, old_obra: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converte obra do formato antigo para novo
        
        Args:
            old_obra: Dados da obra no formato antigo
            
        Returns:
            Obra no novo formato
        """
        # Mapeia campos básicos - mantém o ID original da obra
        obra_id = old_obra.get("id_obra")
        if not obra_id:
            # Se não tiver ID, gera um UUID como fallback
            obra_id = str(uuid.uuid4())
        
        new_obra = {
            "id": obra_id,
            "titulo": old_obra.get("nome_mediocre", ""),
            "url_relativa": old_obra.get("link_download", ""),
            "status": "ativo" if old_obra.get("auto_update", False) else "pausado",
            "ultimo_upload": old_obra.get("data_ultima_atualizacao"),
            "erros_consecutivos": max(0, old_obra.get("contador_pulos_atual", 0)),
            "capitulos": [],
            "tags": [],
            "autor": None,
            "descricao": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "id_obra_original": obra_id  # Mantém referência ao ID original
        }
        
        # Converte capítulos - pega apenas os 2 últimos (com maior número)
        old_capitulos = old_obra.get("capitulos", [])
        if old_capitulos:
            try:
                # Converte para números e ordena
                capitulos_numericos = []
                for cap_num in old_capitulos:
                    try:
                        if isinstance(cap_num, str):
                            try:
                                numero = float(cap_num)
                            except ValueError:
                                # Se não conseguir converter, usa string como está
                                numero = cap_num
                        else:
                            numero = cap_num
                        capitulos_numericos.append(numero)
                    except Exception:
                        continue
                
                # Ordena e pega os 2 últimos
                if capitulos_numericos:
                    capitulos_numericos.sort(key=lambda x: float(x) if isinstance(x, (int, float)) else 0)
                    ultimos_capitulos = capitulos_numericos[-2:]  # Últimos 2
                    
                    for cap_numero in ultimos_capitulos:
                        capitulo = {
                            "numero": cap_numero,
                            "data_upload": None,
                            "status": "baixado"  # Assume que capítulos já existentes foram baixados
                        }
                        new_obra["capitulos"].append(capitulo)
                
            except Exception as e:
                self.reporter.add_warning(f"Erro ao processar capítulos: {e}", old_obra)
        
        # Adiciona metadados extras se disponíveis
        if "numero_de_pulos" in old_obra:
            new_obra["numero_pulos_config"] = old_obra["numero_de_pulos"]
        
        return new_obra
    
    def load_or_create_scan_data(self, scan_name: str, base_url: str = "") -> Dict[str, Any]:
        """
        Carrega dados existentes do scan ou cria novo
        
        Args:
            scan_name: Nome do scan
            base_url: URL base do scan
            
        Returns:
            Dados do scan no novo formato
        """
        scan_file = self.data_dir / f"{scan_name}.json"
        
        if scan_file.exists():
            # Carrega dados existentes
            try:
                with open(scan_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.reporter.add_warning(f"Erro ao carregar {scan_file}: {e}")
        
        # Cria novo arquivo de scan com scape_time
        return {
            "scan_info": {
                "name": scan_name,
                "base_url": base_url,
                "last_check": None,
                "active": True,
                "scape_time": 30,  # Tempo em minutos para esperar antes de postar capítulos
                "description": f"Migrado de obras_mapeadas.json em {datetime.now().strftime('%Y-%m-%d')}"
            },
            "obras": [],
            "metadata": {
                "version": "2.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "total_obras": 0
            }
        }
    
    def save_scan_data(self, scan_name: str, scan_data: Dict[str, Any]) -> bool:
        """
        Salva dados do scan
        
        Args:
            scan_name: Nome do scan
            scan_data: Dados para salvar
            
        Returns:
            True se salvou com sucesso
        """
        scan_file = self.data_dir / f"{scan_name}.json"
        
        try:
            # Atualiza metadata
            scan_data["metadata"]["updated_at"] = datetime.now(timezone.utc).isoformat()
            scan_data["metadata"]["total_obras"] = len(scan_data["obras"])
            
            # Salva arquivo
            with open(scan_file, 'w', encoding='utf-8') as f:
                json.dump(scan_data, f, indent=2, ensure_ascii=False, default=str)
            
            return True
            
        except Exception as e:
            self.reporter.add_error(f"Erro ao salvar {scan_file}: {e}")
            return False
    
    def create_backup(self, source_file: Path) -> Optional[Path]:
        """
        Cria backup do arquivo original
        
        Args:
            source_file: Arquivo original
            
        Returns:
            Caminho do backup criado ou None se falhou
        """
        if not source_file.exists():
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"obras_mapeadas_backup_{timestamp}.json"
            
            shutil.copy2(source_file, backup_file)
            self.reporter.backup_files.append(str(backup_file))
            
            return backup_file
            
        except Exception as e:
            self.reporter.add_error(f"Erro ao criar backup: {e}")
            return None
    
    def validate_migrated_data(self) -> bool:
        """
        Valida dados migrados
        
        Returns:
            True se dados são válidos
        """
        try:
            valid = True
            
            # Lista todos os arquivos de scan criados
            for scan_file in self.data_dir.glob("*.json"):
                if scan_file.name.startswith("backup_"):
                    continue
                
                try:
                    with open(scan_file, 'r', encoding='utf-8') as f:
                        scan_data = json.load(f)
                    
                    # Validações básicas
                    required_fields = ["scan_info", "obras", "metadata"]
                    for field in required_fields:
                        if field not in scan_data:
                            self.reporter.add_error(f"Campo obrigatório '{field}' não encontrado em {scan_file}")
                            valid = False
                    
                    # Valida scan_info
                    if "scan_info" in scan_data:
                        scan_info = scan_data["scan_info"]
                        if not scan_info.get("name"):
                            self.reporter.add_error(f"scan_info.name vazio em {scan_file}")
                            valid = False
                    
                    # Valida obras
                    if "obras" in scan_data:
                        obras = scan_data["obras"]
                        if not isinstance(obras, list):
                            self.reporter.add_error(f"obras deve ser lista em {scan_file}")
                            valid = False
                        else:
                            for i, obra in enumerate(obras):
                                if not obra.get("id") or not obra.get("titulo"):
                                    self.reporter.add_error(f"Obra {i} inválida em {scan_file}")
                                    valid = False
                
                except Exception as e:
                    self.reporter.add_error(f"Erro ao validar {scan_file}: {e}")
                    valid = False
            
            return valid
            
        except Exception as e:
            self.reporter.add_error(f"Erro durante validação: {e}")
            return False
    
    def migrate(self, old_file: Path, dry_run: bool = False) -> Dict[str, Any]:
        """
        Executa migração completa
        
        Args:
            old_file: Arquivo obras_mapeadas.json antigo
            dry_run: Se True, apenas simula a migração
            
        Returns:
            Relatório da migração
        """
        try:
            print(f"🚀 Iniciando migração de {old_file}")
            print(f"   Modo: {'DRY RUN (simulação)' if dry_run else 'MIGRAÇÃO REAL'}")
            print()
            
            # Verifica se arquivo existe
            if not old_file.exists():
                raise MigrationError(f"Arquivo não encontrado: {old_file}")
            
            # Cria backup se não for dry run
            if not dry_run:
                backup_file = self.create_backup(old_file)
                if backup_file:
                    print(f"✅ Backup criado: {backup_file}")
                else:
                    print("⚠️ Não foi possível criar backup")
            
            # Carrega dados antigos
            print("📖 Carregando dados antigos...")
            with open(old_file, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
            
            self.reporter.total_obras = len(old_data)
            print(f"   Total de obras encontradas: {self.reporter.total_obras}")
            print()
            
            # Agrupa obras por scan
            scan_grupos = {}
            unknown_count = 0
            
            print("🔍 Detectando scans por URL...")
            for obra in old_data:
                url = obra.get("link_download", "")
                scan_name = self.detect_scan_from_url(url)
                
                if scan_name == "unknown":
                    unknown_count += 1
                
                if scan_name not in scan_grupos:
                    scan_grupos[scan_name] = []
                
                scan_grupos[scan_name].append(obra)
            
            print(f"   Scans detectados: {list(scan_grupos.keys())}")
            print(f"   Obras sem URL identificável: {unknown_count}")
            print()
            
            # Processa cada scan
            for scan_name, obras in scan_grupos.items():
                print(f"📦 Processando scan '{scan_name}' ({len(obras)} obras)...")
                
                # Determina URL base
                base_url = ""
                for obra in obras:
                    url = obra.get("link_download", "")
                    if url:
                        try:
                            parsed = urlparse(url)
                            base_url = f"{parsed.scheme}://{parsed.netloc}"
                            break
                        except:
                            pass
                
                # Carrega ou cria dados do scan
                scan_data = self.load_or_create_scan_data(scan_name, base_url)
                
                # Converte obras
                existing_titles = {obra.get("titulo", "").lower() for obra in scan_data["obras"]}
                added_count = 0
                
                for old_obra in obras:
                    try:
                        new_obra = self.convert_obra_to_new_format(old_obra)
                        
                        # Verifica duplicatas por título
                        if new_obra["titulo"].lower() in existing_titles:
                            self.reporter.add_warning(f"Obra duplicada ignorada: {new_obra['titulo']}", old_obra)
                            self.reporter.skipped_obras += 1
                            continue
                        
                        # Adiciona obra
                        scan_data["obras"].append(new_obra)
                        existing_titles.add(new_obra["titulo"].lower())
                        added_count += 1
                        self.reporter.migrated_obras += 1
                        
                    except Exception as e:
                        self.reporter.add_error(f"Erro ao converter obra: {e}", old_obra)
                
                # Salva scan se não for dry run
                if not dry_run:
                    if self.save_scan_data(scan_name, scan_data):
                        print(f"   ✅ {added_count} obras adicionadas ao arquivo {scan_name}.json")
                    else:
                        print(f"   ❌ Erro ao salvar {scan_name}.json")
                else:
                    print(f"   🔍 [DRY RUN] {added_count} obras seriam adicionadas")
                
                self.reporter.update_scan_stats(scan_name, added_count)
            
            print()
            
            # Validação final se não for dry run
            if not dry_run:
                print("✅ Validando dados migrados...")
                if self.validate_migrated_data():
                    print("   ✅ Validação passou!")
                else:
                    print("   ⚠️ Problemas encontrados na validação")
            
            # Gera relatório
            report = self.reporter.generate_report()
            
            print()
            print("📊 RESUMO DA MIGRAÇÃO:")
            summary = report["migration_summary"]
            print(f"   ✅ Total de obras: {summary['total_obras']}")
            print(f"   ✅ Obras migradas: {summary['migrated_obras']}")
            print(f"   ⚠️ Obras ignoradas: {summary['skipped_obras']}")
            print(f"   📈 Taxa de sucesso: {summary['success_rate']:.1f}%")
            print(f"   ⏱️ Duração: {summary['duration_seconds']:.1f}s")
            print()
            
            if report["scan_distribution"]:
                print("📦 DISTRIBUIÇÃO POR SCAN:")
                for scan, count in report["scan_distribution"].items():
                    print(f"   - {scan}: {count} obras")
                print()
            
            if report["warnings"]:
                print(f"⚠️ {len(report['warnings'])} avisos durante migração")
            
            if report["errors"]:
                print(f"❌ {len(report['errors'])} erros durante migração")
            
            print(f"🎯 Status final: {report['status']}")
            
            return report
            
        except Exception as e:
            self.reporter.add_error(f"Erro crítico durante migração: {e}")
            return self.reporter.generate_report()


def main():
    """Função principal do script"""
    parser = argparse.ArgumentParser(description="Migra obras_mapeadas.json para novo formato distribuído")
    parser.add_argument(
        "source",
        help="Caminho para obras_mapeadas.json original",
        type=Path
    )
    parser.add_argument(
        "--py-web-root",
        help="Diretório raiz do py_web",
        type=Path,
        default=Path(__file__).parent.parent
    )
    parser.add_argument(
        "--dry-run",
        help="Apenas simula migração sem alterar arquivos",
        action="store_true"
    )
    parser.add_argument(
        "--report-file",
        help="Salva relatório em arquivo JSON",
        type=Path
    )
    
    args = parser.parse_args()
    
    try:
        # Executa migração
        migrator = OldFormatMigrator(args.py_web_root)
        report = migrator.migrate(args.source, dry_run=args.dry_run)
        
        # Salva relatório se solicitado
        if args.report_file:
            with open(args.report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"📄 Relatório salvo em: {args.report_file}")
        
        # Código de saída baseado no resultado
        if report["status"] == "SUCCESS":
            sys.exit(0)
        elif report["status"] == "PARTIAL":
            sys.exit(1)
        else:
            sys.exit(2)
            
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
        sys.exit(3)


if __name__ == "__main__":
    main()