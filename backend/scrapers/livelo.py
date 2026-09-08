"""
scraper publico de parceiros da livelo.

este modulo segue a mesma separacao de responsabilidades do scraper
do buscape, ver scrapers/buscape.py. o navegador so e usado para
abrir a pagina publica de parceiros do compre e pontue, sem
autenticacao e sem login em conta, e coletar o html renderizado,
atraves de pagina.content(). a partir dai, todo o trabalho de achar
cada parceiro, seu codigo, nome e taxa de pontos acontece fora do
navegador, na funcao parsear_html_livelo, usando o beautifulsoup para
selecionar os links de parceiro e expressoes regulares para ler o
texto de cada link, ja que a livelo nao expoe atributos estaveis tipo
data-testid ou data-area nesses links, so o texto corrido do cartao.

essa separacao traz o mesmo beneficio que tem no buscape, dá para
reprocessar um html ja salvo em disco sem abrir o navegador de novo,
util tanto para ajustar as expressoes regulares quanto para conferir
rapidamente o que uma coleta antiga trouxe, veja debug_scraper.py,
opcao --reparsear.

este modulo nao acessa dados privados de nenhum usuario, apenas as
taxas de pontuacao e promocoes publicadas em

https://www.livelo.com.br/juntar-pontos/todos-os-parceiros

dois pontos importantes sobre como este scraper funciona.

primeiro, a lista de parceiros carrega aos poucos conforme a pagina e
rolada, entao o scraper simula rolagem ate o final antes de coletar o
html, do contrario so os primeiros parceiros aparecem.

segundo, o site pode mudar a qualquer momento, ou bloquear o acesso
automatizado, como ja acontece hoje atraves do akamai a nivel de
dominio, ver o comentario no topo de database/db.py. o html da
ultima coleta, sucesso ou falha, fica sempre salvo em
ultimo_html_livelo.html, ao lado deste arquivo, para poder ser
reprocessado sem precisar de rede. quando a coleta falhar por
completo, o mesmo html tambem e salvo em debug_livelo.html, para
facilitar achar esse caso especifico depois.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL_PARCEIROS = "https://www.livelo.com.br/juntar-pontos/todos-os-parceiros"

CAMINHO_DEBUG_HTML = Path(__file__).parent / "debug_livelo.html"

# html completo da ultima coleta, sucesso ou falha, sempre
# sobrescrito. serve para ajustar as expressoes regulares abaixo sem
# precisar abrir o navegador de novo, veja parsear_html_livelo e
# debug_scraper.py
CAMINHO_ULTIMO_HTML = Path(__file__).parent / "ultimo_html_livelo.html"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

SCRIPT_ANTI_DETECCAO = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""

# seletor css do link de cada parceiro, funciona tanto para o
# playwright quanto para o beautifulsoup, ja que os dois aceitam a
# mesma sintaxe de seletor
SELETOR_LINK_PARCEIRO = 'a[href*="/juntar-pontos/parceiros/"]'

SELETORES_BANNER_COOKIES = [
    "#onetrust-accept-btn-handler",
    "button#onetrust-accept-btn-handler",
    "button[aria-label*='aceitar' i]",
    "button:has-text('Aceitar')",
]

PADRAO_CODIGO = re.compile(r"/parceiros/[^/]+/([A-Za-z0-9]+)$")
PADRAO_PONTOS = re.compile(r"(\d+)\s*ponto[s]?\s*por\s*(r\$|u\$)\s*([\d.,]+)", re.IGNORECASE)
PADRAO_EM_PROMOCAO = re.compile(r"^\s*(promoção|nova)", re.IGNORECASE)
PADRAO_ERAM = re.compile(r"eram\s*(\d+)\s*ponto[s]?", re.IGNORECASE)
PADRAO_NOME = re.compile(r"logo\s+(.*?)(?=\s*(?:até\s*)?\d+\s*ponto)", re.IGNORECASE)


@dataclass
class ParceiroLivelo:
    codigo: str
    nome: str
    url: str
    pontos_padrao: float
    moeda_padrao: str
    pontos_clube: float
    em_promocao: bool
    pontos_anteriores: float


class ErroScraperLivelo(Exception):
    """
    erro especifico do scraper, para diferenciar falha de rede ou de
    bloqueio de bot de um erro generico de programacao.
    """


def _parse_taxa_pontos(trecho):
    encontrado = PADRAO_PONTOS.search(trecho)
    if not encontrado:
        return None, None

    pontos = float(encontrado.group(1))
    moeda = encontrado.group(2).upper()
    base = float(encontrado.group(3).replace(".", "").replace(",", "."))

    if base == 0:
        return None, None

    return pontos / base, moeda


def _extrair_parceiro(href, texto_completo):
    """
    monta um ParceiroLivelo a partir do href e do texto de um link de
    parceiro ja localizado, seja pelo playwright ou pelo
    beautifulsoup, sem se importar com quem coletou esse texto.
    """
    encontrado_codigo = PADRAO_CODIGO.search(href)
    if not encontrado_codigo:
        return None
    codigo = encontrado_codigo.group(1).upper()

    texto = " ".join((texto_completo or "").split())

    em_promocao = bool(PADRAO_EM_PROMOCAO.match(texto))

    encontrado_nome = PADRAO_NOME.search(texto)
    nome = encontrado_nome.group(1).strip() if encontrado_nome else codigo

    blocos = re.split(r"\bclube\b", texto, flags=re.IGNORECASE)
    pontos_padrao, moeda_padrao = _parse_taxa_pontos(blocos[0])

    pontos_clube = 0.0
    if len(blocos) > 1:
        taxa_clube, _ = _parse_taxa_pontos(blocos[1])
        pontos_clube = taxa_clube or 0.0

    encontrado_eram = PADRAO_ERAM.search(texto)
    pontos_anteriores = float(encontrado_eram.group(1)) if encontrado_eram else 0.0

    if pontos_padrao is None:
        return None

    return ParceiroLivelo(
        codigo=codigo,
        nome=nome,
        url=href,
        pontos_padrao=round(pontos_padrao, 4),
        moeda_padrao=moeda_padrao or "R$",
        pontos_clube=round(pontos_clube, 4),
        em_promocao=em_promocao,
        pontos_anteriores=pontos_anteriores,
    )


def parsear_html_livelo(html):
    """
    extrai a lista de parceiros a partir do html bruto da pagina de
    parceiros da livelo, sem depender do playwright nem de rede, util
    tanto para ajustar as expressoes regulares quanto para
    reprocessar uma coleta antiga sem consultar o site de novo, veja
    debug_scraper.py, opcao --reparsear.

    deduplica pelo codigo do parceiro, mantendo a primeira ocorrencia
    encontrada, ja que a mesma pagina pode listar o mesmo parceiro
    mais de uma vez em situacoes raras de layout.
    """
    soup = BeautifulSoup(html, "html.parser")

    parceiros_brutos = []
    for link in soup.select(SELETOR_LINK_PARCEIRO):
        href = link.get("href", "")
        texto = link.get_text(" ", strip=True)
        parceiro = _extrair_parceiro(href, texto)
        if parceiro:
            parceiros_brutos.append(parceiro)

    vistos = set()
    parceiros_unicos = []
    for parceiro in parceiros_brutos:
        if parceiro.codigo not in vistos:
            vistos.add(parceiro.codigo)
            parceiros_unicos.append(parceiro)

    return parceiros_unicos


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


def _rolar_ate_carregar_tudo(pagina, tentativas_sem_mudanca=3):
    """
    a lista de parceiros e carregada aos poucos, entao rola a pagina
    ate o final repetidas vezes, ate a altura da pagina parar de
    aumentar, sinal de que tudo ja foi carregado.
    """
    altura_anterior = 0
    sem_mudanca = 0

    for _ in range(60):
        pagina.mouse.wheel(0, 2500)
        pagina.wait_for_timeout(350)
        altura_atual = pagina.evaluate("document.body.scrollHeight")

        if altura_atual == altura_anterior:
            sem_mudanca += 1
            if sem_mudanca >= tentativas_sem_mudanca:
                break
        else:
            sem_mudanca = 0

        altura_anterior = altura_atual


def _coletar_html_pagina_parceiros(timeout_ms, headless):
    """
    abre a pagina publica de parceiros da livelo num navegador
    headless, rola ate carregar tudo, e devolve o html renderizado,
    sem fazer nenhuma extracao aqui, isso fica por conta de
    parsear_html_livelo. nao faz login, nao acessa conta nenhuma.
    """
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
            # domcontentloaded em vez de networkidle, porque a pagina
            # da livelo mantem chamadas de fundo continuas, o que
            # fazia o networkidle nunca resolver e estourar o timeout
            pagina.goto(URL_PARCEIROS, timeout=timeout_ms, wait_until="domcontentloaded")

            _fechar_banner_cookies(pagina)

            try:
                pagina.wait_for_selector(SELETOR_LINK_PARCEIRO, timeout=timeout_ms, state="attached")
            except Exception:
                pass
            else:
                _rolar_ate_carregar_tudo(pagina)

            html_pagina = pagina.content()
        except Exception as erro:
            guia.close()
            navegador.close()
            raise ErroScraperLivelo(
                f"nao foi possivel abrir a pagina da livelo, detalhe tecnico, {erro}"
            )

        guia.close()
        navegador.close()

    return html_pagina


def buscar_parceiros_livelo(timeout_ms=60000, headless=True, salvar_debug_em_falha=True):
    """
    abre a pagina publica de parceiros da livelo e devolve a lista
    completa de parceiros encontrados, combinando a coleta do html
    pelo playwright com a extracao pura em parsear_html_livelo.

    o html da coleta e sempre salvo em ultimo_html_livelo.html, sucesso
    ou falha, e adicionalmente em debug_livelo.html quando nenhum
    parceiro for reconhecido, para facilitar achar esse caso depois.

    levanta ErroScraperLivelo quando a pagina nao trouxer nenhum
    parceiro reconhecivel dentro do tempo limite, o chamador decide
    se mostra esse erro ao usuario.
    """
    html_pagina = _coletar_html_pagina_parceiros(timeout_ms, headless)

    if html_pagina:
        CAMINHO_ULTIMO_HTML.write_text(html_pagina, encoding="utf-8")

    parceiros = parsear_html_livelo(html_pagina) if html_pagina else []

    if not parceiros:
        if salvar_debug_em_falha and html_pagina:
            CAMINHO_DEBUG_HTML.write_text(html_pagina, encoding="utf-8")
        raise ErroScraperLivelo(
            "a pagina abriu, mas nenhum parceiro foi reconhecido a tempo. isso "
            "costuma acontecer quando o site bloqueia o navegador automatizado, "
            "mostra um banner novo por cima da lista, ou muda o layout. o html "
            f"foi salvo em {CAMINHO_ULTIMO_HTML}, e tambem em {CAMINHO_DEBUG_HTML}, "
            "para conferencia. reprocesse esse html com "
            "python debug_scraper.py livelo qualquer --reparsear "
            "scrapers/ultimo_html_livelo.html enquanto ajusta os seletores"
        )

    return parceiros


if __name__ == "__main__":
    resultado = buscar_parceiros_livelo(headless=False)
    print(f"{len(resultado)} parceiros encontrados")
    for parceiro in resultado[:10]:
        print(parceiro)