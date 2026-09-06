"""
scraper publico de parceiros da livelo, por loja.

este modulo segue a mesma separacao de responsabilidades do scraper
do buscape, ver scrapers/buscape.py. o navegador so e usado para
abrir a pagina publica de busca da livelo para o nome de uma loja, sem
autenticacao e sem login em conta, e coletar o html renderizado,
atraves de pagina.content(). a partir dai, todo o trabalho de achar
o parceiro, seu codigo, nome e taxa de pontos acontece fora do
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
taxas de pontuacao e promocoes publicadas na busca de

https://www.livelo.com.br/busca?query=NOME_DA_LOJA

sobre a mudanca de abordagem, este scraper antes abria a pagina de
todos os parceiros, em juntar-pontos/todos-os-parceiros, e listava
tudo de uma vez. essa pagina passou a ser bloqueada pelo akamai a
nivel de dominio, sem contorno viavel, entao a abordagem atual e
consultar a busca da livelo uma loja por vez, usando o nome de loja ja
encontrado pelo buscape, ver services/pesquisa_produto.py. o fluxo
automatico passa a ser, buscape encontra as lojas com oferta, e para
cada loja encontrada, este modulo consulta se ela e parceira livelo e
qual a taxa de pontos.

um ponto importante, nao encontrar nenhum parceiro para uma loja
pesquisada e o resultado normal e esperado na maioria das buscas, ja
que a maior parte das lojas do buscape nao e parceira livelo. por
isso, resultado vazio nao e tratado como falha do scraper, so como
uma loja sem parceria, e o nome da loja continua aparecendo
normalmente no ranking de ofertas do buscape, sem a informacao de
pontos. falha de verdade, ErroScraperLivelo, e reservada para quando a
pagina de busca nao abrir ou nao carregar dentro do tempo limite, por
exemplo por bloqueio de bot ou queda de rede.

o html da ultima busca, sucesso ou falha, fica sempre salvo em
ultimo_html_livelo.html, ao lado deste arquivo, para poder ser
reprocessado sem precisar de rede.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL_BUSCA_LOJA = "https://www.livelo.com.br/busca?query={termo}"

URL_TODOS_OS_PARCEIROS = "https://www.livelo.com.br/juntar-pontos/todos-os-parceiros"

CAMINHO_DEBUG_HTML = Path(__file__).parent / "debug_livelo.html"

# html completo da ultima busca, sucesso ou falha, sempre
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
# mesma sintaxe de seletor. o mesmo componente de card de parceiro e
# reaproveitado tanto na pagina de todos os parceiros quanto na busca,
# entao o seletor continua o mesmo de antes
SELETOR_LINK_PARCEIRO = 'a[href*="/juntar-pontos/parceiros/"]'

SELETORES_BANNER_COOKIES = [
    "#onetrust-accept-btn-handler",
    "button#onetrust-accept-btn-handler",
    "button[aria-label*='aceitar' i]",
    "button:has-text('Aceitar')",
]

PADRAO_CODIGO = re.compile(r"/parceiros/[^/]+/([A-Za-z0-9]+)$")

# ajustado para capturar "até X pontos" também, que aparece na pagina
# de todos os parceiros
PADRAO_PONTOS = re.compile(
    r"(?:at[eé]\s+)?(\d+)\s*ponto[s]?\s*por\s*(r\$|u\$)\s*([\d.,]+)",
    re.IGNORECASE,
)

PADRAO_EM_PROMOCAO = re.compile(r"^\s*(promoção|nova)", re.IGNORECASE)
PADRAO_ERAM = re.compile(r"eram\s*(\d+)\s*ponto[s]?", re.IGNORECASE)

# regex da busca por loja, onde o texto vem "logo NOME"
PADRAO_NOME = re.compile(r"logo\s+(.*?)(?=\s*(?:at[eé]\s*)?\d+\s*ponto)", re.IGNORECASE)

# extrai o slug do parceiro da url, ex: /parceiros/mercado-livre/MCL
PADRAO_SLUG_PARCEIRO = re.compile(r"/parceiros/([^/]+)/[A-Za-z0-9]+$")


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
    erro especifico do scraper, reservado para falha de navegacao de
    verdade, pagina que nao abre ou nao carrega dentro do tempo
    limite, para diferenciar isso de uma loja pesquisada que
    simplesmente nao e parceira livelo, o que nao e um erro.
    """


def _nome_do_slug(href):
    """
    extrai o nome do parceiro a partir do slug da url, ex:
    mercado-livre -> Mercado Livre
    """
    encontrado = PADRAO_SLUG_PARCEIRO.search(href)
    if not encontrado:
        return None
    slug = encontrado.group(1)
    return " ".join(palavra.capitalize() for palavra in slug.split("-"))


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

    # tenta extrair o nome do texto primeiro (funciona na pagina de busca)
    encontrado_nome = PADRAO_NOME.search(texto)
    if encontrado_nome:
        nome = encontrado_nome.group(1).strip()
    else:
        # fallback para pagina de todos os parceiros, onde o nome nao
        # esta no texto do card, mas sim no slug da url
        nome = _nome_do_slug(href) or codigo

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
    extrai a lista de parceiros a partir do html bruto de uma pagina
    de busca da livelo, sem depender do playwright nem de rede, util
    tanto para ajustar as expressoes regulares quanto para
    reprocessar uma busca antiga sem consultar o site de novo, veja
    debug_scraper.py, opcao --reparsear.

    devolve lista vazia quando a busca nao trouxer nenhum parceiro
    reconhecivel, o que e o resultado normal para uma loja sem
    parceria com a livelo, nao uma falha de extracao.

    deduplica pelo codigo do parceiro, mantendo a primeira ocorrencia
    encontrada, ja que a mesma busca pode listar o mesmo parceiro mais
    de uma vez em situacoes raras de layout.
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


def _rolar_ate_carregar_tudo(pagina, tentativas_sem_mudanca=3, tentativas_maximas=20):
    """
    rola a pagina de busca ate o final repetidas vezes, ate a altura
    da pagina parar de aumentar, caso o resultado da busca carregue
    aos poucos. numa busca por loja, o resultado costuma ser pequeno,
    entao o numero de tentativas e bem menor do que era na antiga
    pagina de todos os parceiros.
    """
    altura_anterior = 0
    sem_mudanca = 0

    for _ in range(tentativas_maximas):
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


def _montar_url_busca(nome_loja):
    return URL_BUSCA_LOJA.format(termo=quote_plus(nome_loja))


def _coletar_html_busca_loja(nome_loja, timeout_ms, headless):
    """
    abre a pagina publica de busca da livelo para o nome de loja
    informado, rola ate carregar tudo, e devolve o html renderizado,
    sem fazer nenhuma extracao aqui, isso fica por conta de
    parsear_html_livelo. nao faz login, nao acessa conta nenhuma.
    """
    url_busca = _montar_url_busca(nome_loja)

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
            # domcontentloaded em vez de networkidle, pelo mesmo
            # motivo de antes, o site da livelo mantem chamadas de
            # fundo continuas, o que fazia o networkidle nunca
            # resolver e estourar o timeout
            pagina.goto(url_busca, timeout=timeout_ms, wait_until="domcontentloaded")

            _fechar_banner_cookies(pagina)

            try:
                pagina.wait_for_selector(SELETOR_LINK_PARCEIRO, timeout=timeout_ms, state="attached")
            except Exception:
                # ausencia do seletor aqui e esperada quando a loja
                # pesquisada nao e parceira livelo, a busca carrega
                # normalmente, so nao traz nenhum card de parceiro
                pass
            else:
                _rolar_ate_carregar_tudo(pagina)

            html_pagina = pagina.content()
        except Exception as erro:
            guia.close()
            navegador.close()
            raise ErroScraperLivelo(
                f"nao foi possivel abrir a busca da livelo para {nome_loja}, "
                f"detalhe tecnico, {erro}"
            )

        guia.close()
        navegador.close()

    return html_pagina


def buscar_parceiro_livelo(nome_loja, timeout_ms=60000, headless=True):
    """
    pesquisa o nome de uma loja na busca publica da livelo e devolve
    a lista de parceiros reconhecidos nesse resultado, normalmente
    zero ou um parceiro. o nome da loja costuma vir do resultado do
    buscape, ver services/pesquisa_produto.py, que casa cada loja
    encontrada com a busca livelo correspondente.

    lista vazia e o resultado normal quando a loja pesquisada nao for
    parceira livelo, nao e tratado como erro. o html da busca e sempre
    salvo em ultimo_html_livelo.html, sucesso ou falha, para
    conferencia ou reprocessamento offline.

    levanta ErroScraperLivelo somente quando a pagina de busca nao
    abrir ou nao carregar dentro do tempo limite, por exemplo por
    bloqueio de bot ou queda de rede, o chamador decide se mostra esse
    erro ao usuario ou segue sem a informacao de pontos para aquela
    loja.
    """
    html_pagina = _coletar_html_busca_loja(nome_loja, timeout_ms, headless)

    if html_pagina:
        CAMINHO_ULTIMO_HTML.write_text(html_pagina, encoding="utf-8")

    return parsear_html_livelo(html_pagina) if html_pagina else []


# =============================================================================
# NOVAS FUNCOES: download automatico e carregamento do arquivo manual
# =============================================================================

def baixar_html_livelo(url=None, timeout=30):
    """
    tenta baixar o html da pagina de todos os parceiros da livelo
    via requests, com headers realistas de browser. se conseguir,
    salva no arquivo ultimo_html_livelo.html e devolve o html. se o
    akamai bloquear (403, 406, etc.) ou qualquer outro erro
    acontecer, devolve None e o chamador usa o arquivo manual como
    fallback.

    isso nao e scraping, e apenas um download http de uma pagina
    publica e estatica.
    """
    if url is None:
        url = URL_TODOS_OS_PARCEIROS

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    try:
        resposta = requests.get(url, headers=headers, timeout=timeout)
        if resposta.status_code == 200:
            html = resposta.text
            CAMINHO_ULTIMO_HTML.write_text(html, encoding="utf-8")
            return html
    except Exception:
        pass

    return None


def carregar_parceiros_do_arquivo(caminho=None):
    """
    le o arquivo html salvo manualmente da pagina de todos os
    parceiros da livelo e devolve a lista de ParceiroLivelo
    encontrados. se o arquivo nao existir ou estiver vazio, devolve
    lista vazia.
    """
    if caminho is None:
        caminho = CAMINHO_ULTIMO_HTML

    try:
        html = Path(caminho).read_text(encoding="utf-8")
    except Exception:
        return []

    return parsear_html_livelo(html)


def buscar_parceiro_por_nome(nome_loja, parceiros):
    """
    busca um parceiro pelo nome da loja dentro de uma lista ja
    carregada em memoria. util para casar lojas do buscape com
    parceiros sem bater no site da livelo.
    """
    from database.db import _casar_nome_loja
    return _casar_nome_loja(nome_loja, parceiros)


if __name__ == "__main__":
    # teste: primeiro tenta baixar automatico, depois fallback no arquivo
    html = baixar_html_livelo()
    if html:
        print("download automatico funcionou")
    else:
        print("download automatico falhou, usando arquivo manual")

    parceiros = carregar_parceiros_do_arquivo()
    print(f"{len(parceiros)} parceiro(s) encontrado(s)")
    for p in parceiros[:5]:
        print(f"  {p.codigo}: {p.nome} - {p.pontos_padrao} pts/{p.moeda_padrao}")