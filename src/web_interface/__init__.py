"""
Pacote da Interface Web

Interface web Flask para o MediocreToons Auto Uploader v2.
Implementa dashboard, configurações, mapeamento, logs e fila.
"""

from .app import create_app

__all__ = ['create_app']