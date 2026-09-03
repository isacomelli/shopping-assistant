"""
scraper publico de precos do buscape, por nome de produto.

este modulo pesquisa um produto no buscape e devolve a lista de
lojas encontradas com o respectivo preco, para servir de ponto de
partida do fluxo automatico. a partir da lista de lojas, a pesquisa
automatica em services/pesquisa_produto.py tenta casar cada loja com
um parceiro livelo ja cadastrado manualmente, ver o comentario no
topo de database/db.py sobre por que esse cadastro e manual.

sobre como a extracao funciona, o navegador so e usado para abrir a
pagina e coletar o html renderizado, atraves de pagina.content(). a
partir dai, todo o trabalho de achar loja, preco e link do produto
acontece fora do navegador, na funcao parsear_html_buscape, usando o
beautifulsoup para navegar pelas tags e atributos de cada cartao de
resultado, em vez de regex em cima do texto inteiro do cartao. isso
tem duas vantagens, primeiro, fica mais facil de ajustar quando o
layout do site mudar, porque cada campo tem seu proprio seletor
isolado, segundo, da para reprocessar um html ja salvo em disco sem
precisar abrir o navegador de novo, veja debug_scraper.py, opcao
--reparsear.

uma observacao importante sobre confiabilidade, o robots.txt do
buscape atualmente nao permite acesso automatizado, e o site tambem
usa protecao contra navegador automatizado, entao e esperado que esta
consulta falhe de vez em quando, ou sempre, dependendo de como o site
estiver se comportando no momento. este scraper nao tenta nenhuma
tecnica agressiva de disfarce, tipo imitar a assinatura tls de um
chrome real, so um user agent realista e a ocultacao do sinal mais
comum de automacao.

sobre os seletores abaixo, como nao foi possivel abrir o buscape ao
vivo para inspecionar o html real, eles sao um ponto de partida
razoavel, nao algo validado contra o site. o html completo de toda
busca, com sucesso ou falha, e salvo em ultimo_html_buscape.html, ao
lado deste arquivo. quando a busca nao trouxer os cartoes ou os
precos certos, abra esse arquivo num navegador, use inspecionar
elemento num cartao de produto, e ajuste os seletores logo abaixo dos
imports, sem precisar mexer no resto do arquivo.

quando a consulta falhar por completo, tipo pagina bloqueada, o
caminho mais confiavel continua sendo cadastrar a oferta manualmente
na calculadora, atraves do botao editar variaveis.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL_BUSCA = "https://www.buscape.com.br/search?q={termo}"
URL_BASE = "https://www.buscape.com.br"

CAMINHO_DEBUG_HTML = Path(__file__).parent / "debug_buscape.html"

# html completo da ultima busca, sucesso ou falha, sempre sobrescrito.
# serve para ajustar os seletores abaixo sem precisar abrir o
# navegador de novo, veja parsear_html_buscape e debug_scraper.py
CAMINHO_ULTIMO_HTML = Path(__file__).parent / "ultimo_html_buscape.html"

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
    "#onetrust-accept-btn-handler",
]

# cartao de produto de um resultado de busca. cada seletor abaixo e
# uma lista separada por virgula de possibilidades, o beautifulsoup
# usa a primeira que encontrar dentro do cartao. ajuste estes valores
# conforme o html real salvo em ultimo_html_buscape.html
SELETOR_CARTAO_RESULTADO = "[data-testid='product-card'], li[data-testid='result-item'], article"
SELETOR_NOME_PRODUTO = "[data-testid='product-name'], h2, h3"
SELETOR_LOJA = "[data-testid='seller-name'], [class*='seller'], [class*='store'], [class*='Store']"
SELETOR_PRECO_PRINCIPAL = "[data-testid='price-value'], [class*='Price'] strong, [class*='price'] strong, [class*='Price'], [class*='price']"
SELETOR_PRECO_PIX = "[data-testid='price-pix'], [class*='pix'], [class*='Pix']"
SELETOR_LINK_PRODUTO = "a"

PADRAO_PRECO = re.compile(r"R\$\s*([\d.]+,\d{2})")


class ErroScraperBuscape(Exception):
    """
    erro especifico do scraper do buscape, para diferenciar falha de
    rede ou de bloqueio de bot de um erro generico de programacao.
    """


@dataclass
class OfertaBuscape:
    loja: str
    preco: float
    url_produto: str = ""

    # preco no pix e no cartao, quando o scraper conseguir distinguir
    # os dois na mesma pesquisa. quando nao conseguir, os dois campos
    # abaixo repetem o valor de preco, e distincao_pix_cartao_confiavel
    # fica False, para quem consome este dado saber que precisa
    # confirmar os dois valores manualmente.
    preco_pix: float = 0.0
    preco_cartao: float = 0.0
    distincao_pix_cartao_confiavel: bool = False

    def __post_init__(self):
        if not self.preco_pix:
            self.preco_pix = self.preco
        if not self.preco_cartao:
            self.preco_cartao = self.preco


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


def _extrair_preco_de_texto(texto):
    """
    dentro de um elemento ja localizado pela tag certa, tipo o span
    do preco, ainda precisa converter "R$ 2.399,00" para 2399.0, esta
    funcao cuida so dessa conversao, sem precisar caçar o preco no
    meio de um texto solto.
    """
    if not texto:
        return None
    encontrado = PADRAO_PRECO.search(texto)
    if not encontrado:
        return None
    return float(encontrado.group(1).replace(".", "").replace(",", "."))


def _texto_do_seletor(cartao, seletor):
    """
    devolve o texto do primeiro elemento que casar com o seletor css
    dentro do cartao, ou string vazia se nao encontrar nada.
    """
    elemento = cartao.select_one(seletor)
    return elemento.get_text(strip=True) if elemento else ""


def _extrair_loja(cartao, url_produto):
    texto_loja = _texto_do_seletor(cartao, SELETOR_LOJA)
    if texto_loja:
        return texto_loja

    # sem elemento de loja reconhecivel pela tag, cai para o dominio
    # da url do produto como aproximacao
    padrao_dominio = re.search(r"https?://(?:www\.)?([^./]+)\.", url_produto)
    if padrao_dominio:
        return padrao_dominio.group(1).capitalize()

    return "loja nao identificada"


def _extrair_oferta_do_cartao(cartao):
    """
    monta uma OfertaBuscape a partir de um cartao de resultado ja
    localizado pelo beautifulsoup, lendo cada campo do seu proprio
    seletor, em vez de vasculhar o texto inteiro do cartao.

    devolve none quando o cartao nao tiver um preco reconhecivel,
    sinal de que provavelmente nao e um cartao de produto de verdade,
    tipo um banner de propaganda que casou com o mesmo seletor.
    """
    preco_texto = _texto_do_seletor(cartao, SELETOR_PRECO_PRINCIPAL)
    preco = _extrair_preco_de_texto(preco_texto)
    if preco is None:
        return None

    link = cartao.select_one(SELETOR_LINK_PRODUTO)
    url_produto = link.get("href", "") if link else ""
    if url_produto and url_produto.startswith("/"):
        url_produto = f"{URL_BASE}{url_produto}"

    loja = _extrair_loja(cartao, url_produto)

    texto_pix = _texto_do_seletor(cartao, SELETOR_PRECO_PIX)
    preco_pix_extraido = _extrair_preco_de_texto(texto_pix)

    if preco_pix_extraido is not None and preco_pix_extraido != preco:
        preco_pix, preco_cartao, distincao_confiavel = preco_pix_extraido, preco, True
    else:
        preco_pix, preco_cartao, distincao_confiavel = preco, preco, False

    return OfertaBuscape(
        loja=loja,
        preco=preco,
        url_produto=url_produto,
        preco_pix=preco_pix,
        preco_cartao=preco_cartao,
        distincao_pix_cartao_confiavel=distincao_confiavel,
    )


def parsear_html_buscape(html):
    """
    extrai a lista de ofertas a partir do html bruto de uma pagina de
    busca do buscape, navegando pelas tags de cada cartao de
    resultado com o beautifulsoup, em vez de regex sobre o texto
    inteiro da pagina.

    esta funcao e pura, nao depende do playwright nem de rede, entao
    da para chamar direto com um html salvo em disco, tanto para
    ajustar os seletores quanto para reprocessar uma busca antiga sem
    consultar o site de novo. veja debug_scraper.py, opcao
    --reparsear.

    devolve a tupla, lista de cartoes encontrados pelo
    SELETOR_CARTAO_RESULTADO, lista de OfertaBuscape com preco
    reconhecido. as duas listas separadas ajudam a diferenciar dois
    tipos de problema, seletor de cartao errado, nenhum cartao
    encontrado, ou seletor de preco errado, cartoes encontrados mas
    sem oferta.
    """
    soup = BeautifulSoup(html, "html.parser")
    cartoes = soup.select(SELETOR_CARTAO_RESULTADO)

    ofertas = []
    for cartao in cartoes:
        oferta = _extrair_oferta_do_cartao(cartao)
        if oferta:
            ofertas.append(oferta)

    return cartoes, ofertas


def buscar_ofertas_buscape(nome_produto, max_resultados=10, timeout_ms=45000, headless=True,
                            salvar_debug_em_falha=True):
    """
    pesquisa um produto no buscape e devolve a lista de ofertas
    encontradas, uma por loja, ordenada como o site devolveu.

    levanta ErroScraperBuscape quando a pesquisa nao encontra nenhum
    cartao de resultado, ou encontra cartoes mas nenhum preco dentro
    deles, dentro do tempo limite. o chamador decide se mostra esse
    erro ao usuario ou cai de volta para o cadastro manual.
    """
    url = URL_BUSCA.format(termo=nome_produto.replace(" ", "+"))

    # toda a leitura do html precisa acontecer enquanto o navegador
    # ainda esta aberto, pagina.content() e a unica coisa lida do
    # playwright, o resto do parsing acontece depois, fora do bloco
    # "with sync_playwright()", em cima do texto do html ja salvo em
    # memoria, entao nao ha risco do erro "event loop is closed"
    html_pagina = ""

    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        contexto = navegador.new_context(
            user_agent=USER_AGENT,
            locale="pt-BR",
            viewport={"width": 1366, "height": 900},
        )
        contexto.add_init_script(SCRIPT_ANTI_DETECCAO)
        pagina = contexto.new_page()

        try:
            pagina.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            _fechar_banner_cookies(pagina)
            pagina.wait_for_timeout(1500)

            try:
                pagina.wait_for_selector(SELETOR_CARTAO_RESULTADO, timeout=timeout_ms, state="attached")
            except Exception:
                pass

            html_pagina = pagina.content()
        except Exception as erro:
            contexto.close()
            navegador.close()
            raise ErroScraperBuscape(
                f"nao foi possivel abrir a busca do buscape para {nome_produto}, detalhe tecnico, {erro}"
            )

        contexto.close()
        navegador.close()

    if html_pagina:
        CAMINHO_ULTIMO_HTML.write_text(html_pagina, encoding="utf-8")

    cartoes, ofertas = parsear_html_buscape(html_pagina)

    if not cartoes:
        if salvar_debug_em_falha and html_pagina:
            CAMINHO_DEBUG_HTML.write_text(html_pagina, encoding="utf-8")
        raise ErroScraperBuscape(
            "a busca abriu, mas nenhum cartao de resultado foi encontrado com o "
            f"seletor atual, {SELETOR_CARTAO_RESULTADO!r}. isso costuma acontecer "
            "quando o buscape bloqueia o navegador automatizado ou muda o layout. "
            f"o html completo foi salvo em {CAMINHO_ULTIMO_HTML}, abra esse "
            "arquivo, inspecione um cartao de produto e ajuste "
            "SELETOR_CARTAO_RESULTADO em scrapers/buscape.py. cadastre a oferta "
            "manualmente na calculadora enquanto isso"
        )

    if not ofertas:
        if salvar_debug_em_falha and html_pagina:
            CAMINHO_DEBUG_HTML.write_text(html_pagina, encoding="utf-8")
        raise ErroScraperBuscape(
            f"{len(cartoes)} cartoes de resultado foram encontrados, mas nenhum "
            "preco foi reconhecido dentro deles. revise SELETOR_PRECO_PRINCIPAL "
            f"em scrapers/buscape.py, o html completo esta em {CAMINHO_ULTIMO_HTML}"
        )

    return ofertas[:max_resultados]


if __name__ == "__main__":
    resultado = buscar_ofertas_buscape("geladeira electrolux", headless=False)
    print(f"{len(resultado)} ofertas encontradas")
    for oferta in resultado:
        print(oferta)
