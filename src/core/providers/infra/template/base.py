from typing import List
from core.download.application.use_cases import DownloadUseCase
from core.providers.domain.entities import Chapter, Pages, Manga
from core.providers.domain.provider_repository import ProviderRepository

class Base(ProviderRepository):
    name = ''
    lang = ''
    domain = ['']
    has_login = False

    def login() -> None:
        raise NotImplementedError()

    def getManga(link: str) -> Manga:
        raise NotImplementedError()

    def getChapters(id: str) -> List[Chapter]:
        raise NotImplementedError()
    
    def getPages(ch: Chapter) -> Pages:
        raise NotImplementedError()
    
    def get_update(self) -> List[dict]:
        """
        Método opcional para verificação otimizada de updates
        
        Este método deve ser implementado por providers que suportam
        busca de obras com novos capítulos diretamente da página inicial
        ou página de recentes, evitando verificação individual.
        
        Returns:
            Lista de dicionários com informações de obras que têm novos capítulos:
            [
                {
                    'titulo': str,
                    'url_relativa': str,
                    'capitulos': [
                        {
                            'numero': float,
                            'url': str,
                            'data_upload': str (opcional)
                        }
                    ]
                }
            ]
            
        Raises:
            NotImplementedError: Se o provider não suporta este método
        """
        raise NotImplementedError(
            f"Provider {self.name} não implementa get_update(). "
            "Use verificação individual com getChapters()."
        )
    
    def download(self, pages: Pages, fn: any, headers=None, cookies=None):
        return DownloadUseCase().execute(pages=pages, fn=fn, headers=headers, cookies=cookies)
