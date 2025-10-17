#!/usr/bin/env python3
"""
Servidor de demonstração para o Sistema de Design
MediocreToons Auto Uploader v2
"""

from flask import Flask, render_template, jsonify
from pathlib import Path

# Configurar o diretório correto para templates e static
template_dir = Path(__file__).parent / "web_app" / "templates"
static_dir = Path(__file__).parent / "web_app" / "static"

app = Flask(__name__, 
           template_folder=str(template_dir),
           static_folder=str(static_dir),
           static_url_path='/static')

app.secret_key = 'design-demo-key'

@app.route('/')
def index():
    """Dashboard principal com dados mock para demonstração do design"""
    
    # Dados mock para demonstração
    global_stats = {
        'total_scans': 5,
        'total_obras': 247,
        'total_ativas': 201
    }
    
    quarantine_stats = {
        'total_quarantined': 12,
        'auto_quarantines_today': 3
    }
    
    high_error_obras = [
        {
            'titulo': 'One Piece Exemplo para Teste de Design System',
            'scan_name': 'MangaYabu',
            'erros_consecutivos': 8
        },
        {
            'titulo': 'Naruto Exemplo Design',
            'scan_name': 'ScanExemplo',
            'erros_consecutivos': 9
        }
    ]
    
    return render_template('dashboard.html',
                         global_stats=global_stats,
                         quarantine_stats=quarantine_stats,
                         high_error_obras=high_error_obras)

@app.route('/quarantine')
def quarantine_list():
    """Página de quarentena para teste"""
    
    quarantine_stats = {
        'total_quarantined': 12,
        'auto_quarantines_today': 3,
        'manual_quarantines': 2,
        'recovered_today': 1
    }
    
    return render_template('quarantine.html',
                         quarantine_stats=quarantine_stats)

@app.route('/obras')
def obras_list():
    """Mock de página de obras"""
    return "<h1>Obras - Em Desenvolvimento</h1><p><a href='/'>← Voltar ao Dashboard</a></p>"

@app.route('/scans')
def scans_list():
    """Mock de página de scans"""
    return "<h1>Scans - Em Desenvolvimento</h1><p><a href='/'>← Voltar ao Dashboard</a></p>"

@app.route('/logs')
def logs():
    """Mock de página de logs"""
    return "<h1>Logs - Em Desenvolvimento</h1><p><a href='/'>← Voltar ao Dashboard</a></p>"

@app.route('/health')
def health_dashboard():
    """Health Dashboard com dados mock"""
    return render_template('health_dashboard.html')

@app.route('/api/quarantine/stats')
def api_quarantine_stats():
    """API mock para estatísticas de quarentena"""
    return jsonify({
        'success': True,
        'data': {
            'total_quarantined': 12,
            'auto_quarantines_today': 3,
            'manual_quarantines': 2,
            'recovered_today': 1
        }
    })

if __name__ == '__main__':
    print("🎨 Servidor de Demonstração - Sistema de Design MediocreToons v2")
    print("📱 Paleta principal: #ff6b35 (laranja vibrante)")
    print("🌐 Acesse: http://localhost:5000")
    print("💡 Teste as diferentes páginas e interações!")
    
    app.run(debug=True, host='0.0.0.0', port=5000)