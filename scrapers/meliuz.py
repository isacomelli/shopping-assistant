"""
scraper publico de cashback do meliuz, por loja especifica.

diferente da livelo, o meliuz nao exige login para consultar o
percentual de cashback de uma loja, entao esta consulta e tao simples
quanto uma pessoa buscando a loja no site do meliuz antes de comprar.

sobre a esfera, ao pesquisar como o programa funciona, a lista de
lojas parceiras so fica visivel depois de entrar com cpf e senha na
conta. por esse motivo este projeto nao inclui um scraper de esfera,
nao faz sentido automatizar uma consulta que exige login numa conta
pessoal. os pontos esfera de uma oferta continuam sendo cadastrados
manualmente na calculadora, do mesmo jeito que ja funcionava antes.

assim como no scraper da livelo, este modulo nao usa nenhuma tecnica
agressiva de disfarce de navegador, apenas um user agent realista e a
ocultacao do sinal mais comum de automacao. se o meliuz passar a
bloquear essas consultas, a alternativa e cadastrar o cashback
manualmente na calculadora, o campo ja existe para isso.
"""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import sync_playwright

URL_LOJA_POR_SLUG = "https://www.meliuz.com.br/{slug}"
URL_BUSCA = "https://www.meliuz.com.br/busca?utf8=%E2%9C%93&q={termo}"

CAMINHO_DEBUG_HTML = Path(__file__).parent / "debug_meliuz.html"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

SCRIPT_ANTI_DETECCAO = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""

SELETORES_BANNER_COOKIES = [
    "button:has-text('Aceitar')",
    "button:has-text('aceitar todos')",
    "button[aria-label*='aceitar' i]",
]

# cobre formatos como "ate 8% de cashback", "8% de volta", "8% de
# cashback"
PADRAO_CASHBACK = re.compile(
    r"(?:até\s*)?([\d]+(?:[.,]\d+)?)\s*%\s*(?:de\s*)?(?:cashback|de volta|de retorno)",
    re.IGNORECASE,
)


class ErroScraperMeliuz(Exception):
    """
    erro especifico do scraper do meliuz, para diferenciar falha de
    rede ou de bloqueio de um erro generico de programacao.
    """


@dataclass
class CashbackLoja:
    loja_pesquisada: str
    encontrado: bool
    cashback_pct: float = 0.0
    url_consultada: str = ""
    mensagem: str = ""


def _remover_acentos(texto):
    forma_normalizada = unicodedata.normalize("NFKD", texto)
    return "".join(caractere for caractere in forma_normalizada if not unicodedata.combining(caractere))


def gerar_slug_loja(nome_loja):
    """
    aproximacao do slug usado pelo meliuz para a pagina de uma loja,
    por exemplo "Fast Shop" vira "fast-shop". nem sempre bate com o
    slug real cadastrado pelo meliuz.
    """
    sem_acento = _remover_acentos(nome_loja).lower()
    sem_acento = re.sub(r"[^a-z0-9\s-]", "", sem_acento)
    return re.sub(r"\s+", "-", sem_acento.strip())


def _fechar_banner_cookies(pagina):
    for seletor in SELETORES_BANNER_COOKIES:
        try:
            botao = pagina.locator(seletor).first
            if botao.is_visible(timeout=2000):
                botao.click(timeout=2000)
                pagina.wait_for_timeout(500)
                return
        except Exception:
            continue


def _consultar_pagina(pagina, url, timeout_ms):
    pagina.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
    _fechar_banner_cookies(pagina)
    try:
        pagina.wait_for_selector("body", timeout=timeout_ms, state="attached")
    except Exception:
        return ""
    pagina.wait_for_timeout(1500)
    return pagina.inner_text("body")


def buscar_cashback_por_loja(nome_loja, timeout_ms=45000, headless=True, salvar_debug_em_falha=True):
    """
    consulta o meliuz pelo percentual de cashback de uma unica loja.

    tenta primeiro o slug adivinhado a partir do nome da loja, e se a
    pagina nao trouxer nenhum percentual reconhecido, tenta a busca
    interna do site. sempre devolve um CashbackLoja, com
    encontrado=False quando nada foi localizado, em vez de levantar
    excecao, ja que a loja pode simplesmente nao ser parceira.
    """
    slug = gerar_slug_loja(nome_loja)
    url_direta = URL_LOJA_POR_SLUG.format(slug=slug)
    url_busca = URL_BUSCA.format(termo=nome_loja.replace(" ", "+"))

    texto_pagina = ""
    url_usada = url_direta

    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        guia = navegador.new_context(
            user_agent=USER_AGENT,
            locale="pt-BR",
            viewport={"width": 1366, "height": 900},
        )
        guia.add_init_script(SCRIPT_ANTI_DETECCAO)
        pagina = guia.new_page()

        try:
            texto_pagina = _consultar_pagina(pagina, url_direta, timeout_ms)

            if not PADRAO_CASHBACK.search(texto_pagina):
                url_usada = url_busca
                texto_pagina = _consultar_pagina(pagina, url_busca, timeout_ms)
        except Exception as erro:
            guia.close()
            navegador.close()
            raise ErroScraperMeliuz(
                f"nao foi possivel abrir a pagina do meliuz para {nome_loja}, detalhe tecnico, {erro}"
            )

        guia.close()
        navegador.close()

    encontrado = PADRAO_CASHBACK.search(texto_pagina)
    if not encontrado:
        if salvar_debug_em_falha and texto_pagina:
            CAMINHO_DEBUG_HTML.write_text(texto_pagina, encoding="utf-8")
        return CashbackLoja(
            loja_pesquisada=nome_loja,
            encontrado=False,
            url_consultada=url_usada,
            mensagem=(
                "nenhum percentual de cashback foi encontrado para esta loja, ela "
                "pode nao ser parceira do meliuz, ou a pagina pode ter mudado"
            ),
        )

    cashback_pct = float(encontrado.group(1).replace(",", "."))

    return CashbackLoja(
        loja_pesquisada=nome_loja,
        encontrado=True,
        cashback_pct=cashback_pct,
        url_consultada=url_usada,
    )


if __name__ == "__main__":
    resultado = buscar_cashback_por_loja("Fast Shop", headless=False)
    print(resultado)
