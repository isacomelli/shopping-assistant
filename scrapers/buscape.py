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
partir dai, todo o trabalho de achar loja, preco, link e parcelamento
acontece fora do navegador, na funcao parsear_html_buscape, usando o
beautifulsoup para navegar pelas tags de cada cartao de resultado,
pelos atributos data-testid e data-area, em vez de classes css com
hash, tipo Price_OrqProductCard_Price__TNBZB, que mudam a cada deploy
do buscape, ou de regex em cima do texto inteiro do cartao.

os seletores abaixo foram conferidos contra um html real de uma busca
salva em ultimo_html_buscape.html, entao nao sao mais um chute, mas
continuam podendo quebrar se o buscape mudar o layout. quando isso
acontecer, o html completo de toda busca, com sucesso ou falha, fica
salvo em ultimo_html_buscape.html, ao lado deste arquivo, abra esse
arquivo num navegador, use inspecionar elemento num cartao de
produto, e ajuste os seletores logo abaixo dos imports, sem precisar
mexer no resto do arquivo.

sobre a distincao entre pix e cartao, a pagina de busca do buscape nao
mostra um preco de pix separado, so um preco unico por cartao de
resultado, mais um campo de parcelamento, tipo "10x de R$ 206,53", com
um segundo campo indicando se e "sem juros". a partir desses dois
dados, sem depender de nenhuma tag especifica de pix, que nao existe
nesta pagina, este modulo tenta inferir se a oferta representa um
unico preco ou duas opcoes de pagamento, seguindo esta regra,

tem parcelamento, e parcelas vezes valor da parcela e igual ao preco
anunciado, dentro de uma pequena tolerancia de arredondamento, a
oferta tem um unico preco, o do cartao, sem pix reconhecido
separadamente

tem parcelamento, e parcelas vezes valor da parcela e diferente do
preco anunciado, a oferta tem duas opcoes de pagamento, pix e cartao,
o menor dos dois valores e o pix, o maior e o cartao parcelado

nao tem parcelamento reconhecido no cartao, o caso fica indefinido, o
preco anunciado e usado tanto para pix quanto para cartao, e o calculo
trata esse preco como se fosse pix, para nao superestimar pontos de
cartao numa compra que pode ser a vista

essa inferencia fica isolada em _determinar_precos_pix_cartao, para
poder ser testada e ajustada sem mexer no resto do parsing.

sobre o robots.txt do buscape, ele atualmente nao permite acesso
automatizado, e o site tambem usa protecao contra navegador
automatizado, entao e esperado que esta consulta falhe de vez em
quando, ou sempre, dependendo de como o site estiver se comportando
no momento. este scraper nao tenta nenhuma tecnica agressiva de
disfarce, tipo imitar a assinatura tls de um chrome real, so um user
agent realista e a ocultacao do sinal mais comum de automacao.

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

# cartao de produto de um resultado de busca. estes seletores usam
# data-testid e data-area, atributos estaveis colocados pelo proprio
# buscape para identificar cada pedaco do cartao, em vez de classes
# css com hash, que mudam a cada deploy do site
SELETOR_CARTAO_RESULTADO = '[data-testid="product-card"]'
SELETOR_NOME_PRODUTO = '[data-testid="product-card::name"]'
SELETOR_PRECO_PRINCIPAL = '[data-testid="product-card::price"]'
SELETOR_LOJA = '[data-area="merchant"] span'
SELETOR_LINK_PRODUTO = 'a[data-testid="product-card::card"]'
SELETOR_PARCELAMENTO = '[data-testid="product-card::installment"] span'
SELETOR_JUROS_PARCELAMENTO = '[data-testid="product-card::interest"]'

PADRAO_PRECO = re.compile(r"R\$\s*([\d.]+,\d{2})")
PADRAO_PARCELAMENTO = re.compile(r"(\d+)\s*x\s*de\s*R\$\s*([\d.]+,\d{2})", re.IGNORECASE)


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
    nome_produto: str = ""

    # preco no pix e no cartao, inferidos a partir do preco anunciado
    # e do parcelamento, seguindo a regra descrita no topo deste
    # arquivo. confianca_pix_cartao fica True somente
    # quando o scraper conseguiu identificar duas opcoes de
    # pagamento distintas, pix e cartao, a partir do parcelamento
    preco_pix: float = 0.0
    preco_cartao: float = 0.0
    confianca_pix_cartao: bool = False

    # parcelamento anunciado no cartao de resultado, quando houver.
    # parcelas fica em 1 quando o cartao nao anuncia nenhum
    # parcelamento, o que nao quer dizer que a loja so aceita a vista
    parcelas: int = 1
    valor_parcela: float = 0.0
    parcelas_sem_juros: bool = False

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
    dentro de um elemento ja localizado pela tag certa, tipo o div
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

    # sem o span da loja, cai para o dominio da url do produto como
    # aproximacao, so deve acontecer se o buscape mudar o layout do
    # rodape do cartao
    padrao_dominio = re.search(r"https?://(?:www\.)?([^./]+)\.", url_produto)
    if padrao_dominio:
        return padrao_dominio.group(1).capitalize()

    return "loja nao identificada"


def _extrair_parcelamento(cartao):
    """
    le o texto de parcelamento do cartao, por exemplo "10x de R$
    165,70", e devolve a quantidade de parcelas, o valor de cada
    parcela, e se o parcelamento e sem juros.

    quando nao ha nenhum texto de parcelamento reconhecivel no
    cartao, devolve parcelas 1, valor de parcela 0 e sem_juros False,
    sinal para quem chama de que o parcelamento e desconhecido, nao
    de que a compra e a vista.
    """
    texto_parcelamento = _texto_do_seletor(cartao, SELETOR_PARCELAMENTO)
    encontrado = PADRAO_PARCELAMENTO.search(texto_parcelamento)
    if not encontrado:
        return 1, 0.0, False

    parcelas = int(encontrado.group(1))
    valor_parcela = float(encontrado.group(2).replace(".", "").replace(",", "."))

    texto_juros = _texto_do_seletor(cartao, SELETOR_JUROS_PARCELAMENTO)
    sem_juros = "sem juros" in texto_juros.lower()

    return parcelas, valor_parcela, sem_juros


def _determinar_precos_pix_cartao(preco, parcelas, valor_parcela):
    """
    a partir do preco anunciado no cartao de resultado e do
    parcelamento informado, parcelas e valor de cada parcela, decide
    se a oferta representa um unico preco, ou duas opcoes de
    pagamento, pix e cartao.

    sem parcelamento reconhecido, parcelas 1 ou valor_parcela zerado,
    o preco anunciado e usado tanto para pix quanto para cartao, sem
    certeza da distincao, tratado como pix no calculo, para nao
    superestimar pontos de cartao numa compra que pode ser a vista.

    com parcelamento, compara o total das parcelas, parcelas vezes
    valor de cada parcela, com o preco anunciado. os dois batendo,
    dentro de uma pequena tolerancia de arredondamento, a oferta tem
    um unico preco, o do cartao, sem pix reconhecido separadamente.
    os dois nao batendo, a oferta tem duas opcoes de pagamento, pix e
    cartao, o menor dos dois valores e o pix, o maior e o cartao
    parcelado, sem assumir de antemao qual dos dois vem maior no
    html, ja que isso pode variar.
    """
    if parcelas <= 1 or valor_parcela <= 0:
        return preco, preco, False

    total_parcelado = parcelas * valor_parcela
    tolerancia = max(0.5, parcelas * 0.02)

    if abs(total_parcelado - preco) <= tolerancia:
        return preco, preco, False

    preco_pix = min(preco, total_parcelado)
    preco_cartao = max(preco, total_parcelado)
    return preco_pix, preco_cartao, True


def _extrair_oferta_do_cartao(cartao):
    """
    monta uma OfertaBuscape a partir de um cartao de resultado ja
    localizado pelo beautifulsoup, lendo cada campo do seu proprio
    seletor, em vez de vasculhar o texto inteiro do cartao.

    devolve none quando o cartao nao tiver um preco reconhecivel,
    sinal de que provavelmente nao e um cartao de produto de verdade.
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
    nome_produto = _texto_do_seletor(cartao, SELETOR_NOME_PRODUTO)
    parcelas, valor_parcela, parcelas_sem_juros = _extrair_parcelamento(cartao)
    preco_pix, preco_cartao, distincao_confiavel = _determinar_precos_pix_cartao(
        preco, parcelas, valor_parcela,
    )

    return OfertaBuscape(
        loja=loja,
        preco=preco,
        url_produto=url_produto,
        nome_produto=nome_produto,
        parcelas=parcelas,
        valor_parcela=valor_parcela,
        parcelas_sem_juros=parcelas_sem_juros,
        preco_pix=preco_pix,
        preco_cartao=preco_cartao,
        confianca_pix_cartao=distincao_confiavel,
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


def buscar_ofertas_buscape(nome_produto, max_resultados=1000, timeout_ms=45000, headless=True,
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