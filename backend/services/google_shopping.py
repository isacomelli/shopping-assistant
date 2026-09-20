"""
Scraper publico de ofertas no google shopping, por nome de produto, fonte principal de busca do aplicativo, substituindo o buscape como origem primaria e trazendo uma quantidade muito maior de lojas para o comparativo, incluindo lojas que o buscape nunca lista, como leroy merlin, shopee, aliexpress e mercado livre.

Este modulo segue a mesma separacao de responsabilidades usada em scrapers/buscape.py, o navegador so abre a pagina de resultados da aba shopping do google e coleta o html renderizado, atraves de pagina.content(), e toda a extracao de nome, loja, preco, url e imagem acontece fora do navegador, na funcao parsear_html_google_shopping, usando o beautifulsoup.

Sobre selecao de bloqueio, o google costuma exigir verificacao de captcha para trafego automatizado com muita frequencia, mais agressivo que o buscape, por isso este modulo nunca deve ser a unica fonte tentada silenciosamente, o orquestrador em services/pesquisa_produto.py trata uma falha aqui como sinal para tambem consultar o buscape como fonte complementar, e nao como erro fatal da pesquisa inteira.

Quando a consulta falhar por completo, o html da ultima tentativa fica salvo em disco, do mesmo jeito que o scraper do buscape, para facilitar o ajuste dos seletores sem precisar depender de rede.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from services.normalizacao_lojas import normalizar_e_filtrar_ofertas

URL_BUSCA_SHOPPING = "https://www.google.com/search?tbm=shop&hl=pt-BR&gl=BR&q={termo}"

CAMINHO_DEBUG_HTML = Path(__file__).parent.parent / "scrapers" / "debug_google_shopping.html"
CAMINHO_ULTIMO_HTML = Path(__file__).parent.parent / "scrapers" / "ultimo_html_google_shopping.html"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

SCRIPT_ANTI_DETECCAO = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""

SELETORES_BANNER_COOKIES = [
    "button:has-text('Aceitar tudo')",
    "button:has-text('Aceito')",
    "button[aria-label*='Aceitar' i]",
    "#L2AGLb",
]

# seletor do cartao de cada resultado na aba shopping, o google usa classes com hash que mudam com frequencia, entao a extracao real, dentro de _extrair_oferta_do_cartao, nao depende so deste seletor, ela tambem confirma a presenca de um link de produto e de um preco reconhecivel antes de aceitar o cartao como uma oferta valida
SELETOR_CARTAO_RESULTADO = "div.sh-dgr__grid-result, div.sh-dlr__list-result, div[data-docid]"

PADRAO_PRECO = re.compile(r"R\$\s*([\d.]+,\d{2})")


class ErroScraperGoogleShopping(Exception):
    """
    Erro especifico do scraper do google shopping, para diferenciar falha de rede ou bloqueio por captcha de um erro generico de programacao
    """


@dataclass
class OfertaGoogleShopping:
    loja: str
    preco: float
    url_produto: str = ""
    nome_produto: str = ""
    imagem_produto: str = ""

    # o google shopping raramente detalha pix e parcelamento no proprio cartao de resultado, entao estes campos ficam vazios na maior parte das ofertas, e o preco anunciado e usado como preco unico ate uma etapa posterior, como o enriquecimento manual ou o casamento com a propria pagina da loja, preencher esses valores com mais precisao
    preco_pix: float = 0.0
    preco_cartao: float = 0.0
    confianca_pix_cartao: bool = False
    parcelas: int = 1
    valor_parcela: float = 0.0

    origem: str = "google_shopping"

    def __post_init__(self):
        self.preco = round(float(self.preco), 2)
        self.preco_pix = round(float(self.preco_pix), 2)
        self.preco_cartao = round(float(self.preco_cartao), 2)
        if not self.preco_pix and not self.preco_cartao:
            self.preco_pix = self.preco
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
    if not texto:
        return None
    encontrado = PADRAO_PRECO.search(texto)
    if not encontrado:
        return None
    return float(encontrado.group(1).replace(".", "").replace(",", "."))


def _extrair_loja_do_cartao(cartao):
    """
    O nome da loja no cartao de resultado do google shopping costuma vir num pequeno texto proximo ao preco, sem um atributo estavel proprio, entao a extracao tenta alguns padroes textuais comuns antes de cair para o dominio do link do produto
    """
    candidatos = cartao.select("div.aULzUe, div.IuHnof, span.aULzUe, div.merchant-title")
    for candidato in candidatos:
        texto = candidato.get_text(strip=True)
        if texto:
            return texto
    return ""


def _extrair_dominio(url):
    padrao_dominio = re.search(r"https?://(?:www\.)?([^./]+)\.", url or "")
    if padrao_dominio:
        return padrao_dominio.group(1).capitalize()
    return "loja nao identificada"


def _extrair_oferta_do_cartao(cartao):
    """
    Monta uma OfertaGoogleShopping a partir de um cartao de resultado, devolvendo none quando o cartao nao tiver um preco reconhecivel ou nenhum link de produto, sinal de que provavelmente e um bloco de filtro ou de publicidade sem oferta de verdade
    """
    link = cartao.select_one("a")
    if not link:
        return None
    url_produto = link.get("href", "")
    if url_produto.startswith("/url?q="):
        url_produto = url_produto.split("/url?q=")[1].split("&")[0]
    elif url_produto.startswith("/"):
        url_produto = f"https://www.google.com{url_produto}"

    texto_cartao = cartao.get_text(" ", strip=True)
    preco = _extrair_preco_de_texto(texto_cartao)
    if preco is None:
        return None

    nome_elemento = cartao.select_one("h3, h4, div.tAxDx, div.Xjkr3b")
    nome_produto = nome_elemento.get_text(strip=True) if nome_elemento else ""

    loja = _extrair_loja_do_cartao(cartao) or _extrair_dominio(url_produto)

    imagem_elemento = cartao.select_one("img")
    imagem_produto = imagem_elemento.get("src", "") if imagem_elemento else ""

    return OfertaGoogleShopping(
        loja=loja,
        preco=preco,
        url_produto=url_produto,
        nome_produto=nome_produto,
        imagem_produto=imagem_produto,
    )


def parsear_html_google_shopping(html):
    """
    Extrai a lista de ofertas a partir do html bruto da aba shopping do google, sem depender do playwright nem de rede, util tanto para ajustar os seletores quanto para reprocessar uma busca antiga sem consultar o site de novo
    """
    soup = BeautifulSoup(html, "html.parser")
    cartoes = soup.select(SELETOR_CARTAO_RESULTADO)

    ofertas = []
    for cartao in cartoes:
        oferta = _extrair_oferta_do_cartao(cartao)
        if oferta:
            ofertas.append(oferta)
    return ofertas


def _coletar_html_busca(termo, headless, timeout_ms):
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

        url = URL_BUSCA_SHOPPING.format(termo=termo.replace(" ", "+"))
        try:
            pagina.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            _fechar_banner_cookies(pagina)
            pagina.wait_for_timeout(1500)
            try:
                pagina.wait_for_selector(SELETOR_CARTAO_RESULTADO, timeout=timeout_ms, state="attached")
            except Exception:
                pass
            html = pagina.content()
        finally:
            guia.close()
            navegador.close()

    return html


def buscar_ofertas_google_shopping(nome_produto, timeout_ms=30000, headless=True, salvar_debug_em_falha=True):
    """
    Pesquisa um produto na aba shopping do google e devolve a lista de ofertas encontradas, ja padronizadas e filtradas por services/normalizacao_lojas.normalizar_e_filtrar_ofertas, levanta ErroScraperGoogleShopping quando a pagina nao trouxer nenhuma oferta reconhecivel, o chamador, em services/pesquisa_produto.py, decide se cai para o buscape como fonte complementar
    """
    try:
        html = _coletar_html_busca(nome_produto, headless, timeout_ms)
    except Exception as erro:
        raise ErroScraperGoogleShopping(
            f"nao foi possivel abrir a busca do google shopping para {nome_produto}, detalhe tecnico, {erro}"
        )

    if html:
        CAMINHO_ULTIMO_HTML.write_text(html, encoding="utf-8")

    ofertas_brutas = parsear_html_google_shopping(html) if html else []

    if not ofertas_brutas:
        if salvar_debug_em_falha and html:
            CAMINHO_DEBUG_HTML.write_text(html, encoding="utf-8")
        raise ErroScraperGoogleShopping(
            f"a busca abriu, mas nenhuma oferta foi reconhecida para {nome_produto}, isso costuma acontecer quando o google exige verificacao de captcha para trafego automatizado, o html foi salvo em {CAMINHO_ULTIMO_HTML} para conferencia, o orquestrador deve cair para o buscape como fonte complementar enquanto isso"
        )

    return normalizar_e_filtrar_ofertas(ofertas_brutas, nome_produto)


if __name__ == "__main__":
    resultado = buscar_ofertas_google_shopping("geladeira electrolux", headless=False)
    print(f"{len(resultado)} ofertas encontradas")
    for oferta in resultado:
        print(oferta)