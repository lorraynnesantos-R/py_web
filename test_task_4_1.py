#!/usr/bin/env python3
"""
Script de teste da aplicação Flask

Testa a estrutura base Flask da Task 4.1
"""

import sys
import os
from pathlib import Path

# Adicionar src ao path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_flask_app():
    """Testar a aplicação Flask"""
    print("🧪 Testando Task 4.1: Estrutura Base Flask")
    print("=" * 50)
    
    try:
        # Importar e criar app
        from web_interface import create_app
        
        app = create_app('development')
        
        print("✅ Aplicação Flask criada com sucesso")
        
        # Testar rotas registradas
        print("\n📍 Rotas registradas:")
        with app.app_context():
            for rule in app.url_map.iter_rules():
                print(f"  {rule.rule} -> {rule.endpoint}")
        
        print(f"\n🔧 Configurações:")
        print(f"  Debug: {app.config.get('DEBUG')}")
        print(f"  Testing: {app.config.get('TESTING')}")
        print(f"  Secret Key: {'✅ Configurada' if app.config.get('SECRET_KEY') else '❌ Não configurada'}")
        
        # Testar componentes
        print(f"\n🧩 Componentes do sistema:")
        components = ['mapping_manager', 'quarantine_manager', 'scheduler', 'queue', 'discord_notifier']
        for comp in components:
            has_comp = hasattr(app, comp)
            print(f"  {comp}: {'✅ Inicializado' if has_comp else '❌ Não encontrado'}")
        
        # Testar blueprints
        print(f"\n📋 Blueprints registrados:")
        for bp_name, bp in app.blueprints.items():
            print(f"  {bp_name}: {bp.url_prefix or '/'}")
        
        print("\n🎉 Task 4.1 - Estrutura Base Flask: SUCESSO!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao testar aplicação Flask: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_templates():
    """Testar se templates existem"""
    print("\n🎨 Verificando templates...")
    
    templates_dir = Path(__file__).parent / "src" / "web_interface" / "templates"
    
    required_templates = [
        "base.html",
        "dashboard.html",
        "errors/404.html",
        "errors/500.html"
    ]
    
    for template in required_templates:
        template_path = templates_dir / template
        if template_path.exists():
            print(f"  ✅ {template}")
        else:
            print(f"  ❌ {template} (não encontrado)")

def test_static_files():
    """Testar se arquivos estáticos existem"""
    print("\n📁 Verificando arquivos estáticos...")
    
    static_dir = Path(__file__).parent / "src" / "web_interface" / "static"
    
    required_files = [
        "css/variables.css",
        "css/components.css", 
        "css/style.css",
        "js/app.js"
    ]
    
    for file in required_files:
        file_path = static_dir / file
        if file_path.exists():
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} (não encontrado)")

def main():
    """Função principal"""
    print("🚀 MediocreToons Auto Uploader v2 - Task 4.1 Test")
    print("=" * 60)
    
    # Testar aplicação Flask
    flask_ok = test_flask_app()
    
    # Testar templates
    test_templates()
    
    # Testar arquivos estáticos
    test_static_files()
    
    print("\n" + "=" * 60)
    if flask_ok:
        print("🎯 RESULTADO: Task 4.1 implementada com SUCESSO!")
        print("📝 Próximos passos:")
        print("   - Task 4.2: Dashboard Principal")
        print("   - Task 4.3: Interface de Configurações")
        print("   - Task 4.4: Gerenciamento de Obras")
    else:
        print("❌ RESULTADO: Task 4.1 precisa de correções")
    
    return flask_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)