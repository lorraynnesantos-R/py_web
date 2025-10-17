#!/usr/bin/env python3
"""
Script para executar a aplicação Flask contornando problemas de imports
"""

import sys
import os
from pathlib import Path

# Adicionar diretórios ao path para resolver imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir / "src"))

# Definir variáveis de ambiente necessárias
os.environ['PYTHONPATH'] = str(current_dir)
os.environ['FLASK_ENV'] = 'development'
os.environ['FLASK_DEBUG'] = '1'

try:
    from src.web_interface.app import create_app
    
    # Criar e executar app
    app = create_app('development')
    
    print("🚀 Iniciando aplicação Flask...")
    print("📍 Acesse: http://localhost:5000")
    print("🗂️  Mapeamento: http://localhost:5000/mapping")
    print("⚙️  Configurações: http://localhost:5000/config")
    print("📊 Dashboard: http://localhost:5000/dashboard")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False  # Evita problemas de import duplo
    )
    
except Exception as e:
    print(f"❌ Erro ao executar aplicação: {e}")
    import traceback
    traceback.print_exc()