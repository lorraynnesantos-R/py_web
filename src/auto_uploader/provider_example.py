"""
Exemplo de implementação do método get_update() em um provider

Este arquivo demonstra como um provider pode implementar o método
get_update() para verificação otimizada de updates.
"""

from typing import List
from src.core.providers.infra.template.base import Base


class ExampleProvider(Base):
    """
    Exemplo de provider que implementa get_update() para verificação otimizada
    """
    
    name = 'example_provider'
    lang = 'pt_BR'
    domain = ['example.com']
    has_login = False
    
    def get_update(self) -> List[dict]:
        """
        Implementação exemplo do método get_update()
        
        Este método busca obras com novos capítulos diretamente da página
        inicial ou seção de recentes do site, evitando verificação individual.
        
        Returns:
            Lista de obras com novos capítulos
        """
        try:
            # Simulação de busca na página inicial/recentes
            # Em implementação real, faria requests para o site
            
            # Exemplo de retorno
            return [
                {
                    'titulo': 'Manga Exemplo 1',
                    'url_relativa': '/manga-exemplo-1',
                    'capitulos': [
                        {
                            'numero': 125.0,
                            'url': '/manga-exemplo-1/cap-125',
                            'data_upload': '2025-10-15'
                        },
                        {
                            'numero': 126.0, 
                            'url': '/manga-exemplo-1/cap-126',
                            'data_upload': '2025-10-15'
                        }
                    ]
                },
                {
                    'titulo': 'Manga Exemplo 2',
                    'url_relativa': '/manga-exemplo-2',
                    'capitulos': [
                        {
                            'numero': 45.5,
                            'url': '/manga-exemplo-2/cap-45-5',
                            'data_upload': '2025-10-15'
                        }
                    ]
                }
            ]
            
        except Exception as e:
            # Em caso de erro, lançar NotImplementedError para usar fallback
            raise NotImplementedError(f"Erro na verificação otimizada: {e}")
    
    def getManga(self, link: str):
        """Implementação padrão getManga"""
        # Implementação específica do provider
        pass
    
    def getChapters(self, id: str):
        """Implementação padrão getChapters"""
        # Implementação específica do provider
        pass
    
    def getPages(self, ch):
        """Implementação padrão getPages"""
        # Implementação específica do provider
        pass


class LegacyProvider(Base):
    """
    Exemplo de provider legado que NÃO implementa get_update()
    
    O sistema automaticamente detectará que este provider não suporta
    verificação otimizada e usará o método fallback.
    """
    
    name = 'legacy_provider'
    lang = 'pt_BR'
    domain = ['legacy.com']
    has_login = False
    
    # NÃO implementa get_update() - usará fallback automático
    
    def getManga(self, link: str):
        """Implementação padrão getManga"""
        pass
    
    def getChapters(self, id: str):
        """Implementação padrão getChapters"""
        pass
    
    def getPages(self, ch):
        """Implementação padrão getPages"""
        pass


# Documentação de implementação
"""
GUIA DE IMPLEMENTAÇÃO DO MÉTODO get_update()

Para implementar verificação otimizada de updates em um provider:

1. ADICIONE o método get_update() na sua classe provider:

    def get_update(self) -> List[dict]:
        # Sua implementação aqui
        
2. RETORNE uma lista de dicionários com a estrutura:
    [
        {
            'titulo': str,              # Nome da obra
            'url_relativa': str,        # URL relativa da obra
            'capitulos': [              # Lista de novos capítulos
                {
                    'numero': float,    # Número do capítulo
                    'url': str,         # URL do capítulo
                    'data_upload': str  # Data (opcional)
                }
            ]
        }
    ]

3. ESTRATÉGIAS comuns de implementação:
   - Buscar página inicial/home do site
   - Usar seção "Últimos capítulos" ou "Recentes"
   - Usar API do site se disponível
   - Usar RSS/feeds se disponível

4. TRATAMENTO de erros:
   - Se der erro, lance NotImplementedError
   - O sistema automaticamente usará fallback
   - Sempre prefira fallback a retornar dados incorretos

5. PERFORMANCE:
   - Uma requisição deve cobrir múltiplas obras
   - Evite fazer uma requisição por obra
   - Use cache quando possível
   - Respeite rate limits do site

6. TESTES:
   - Sempre teste com dados reais
   - Verifique se os números de capítulos estão corretos
   - Confirme se as URLs estão válidas

BENEFÍCIOS:
- Muito mais rápido que verificação individual
- Menos requisições ao site (melhor para rate limits)
- Detecção automática de novos capítulos
- Fallback automático em caso de problema
"""