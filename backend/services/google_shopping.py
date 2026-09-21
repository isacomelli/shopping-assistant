"""Scraper público de ofertas do Google Shopping, usado como fonte principal da pesquisa automática."""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus, unquote, urlparse
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from services.normalizacao_lojas import normalizar_e_filtrar_ofertas

# a aba Produtos do Google usa udm=28, o parâmetro tbm=shop fica como alternativa caso o formato antigo volte a ser servido
URLS_BUSCA_SHOPPING = [
    "https://www.google.com/search?udm=28&hl=pt-BR&gl=BR&q={termo}",
    "https://www.google.com/search?tbm=shop&hl=pt-BR&gl=BR&q={termo}",
]

# a API do Serper só é usada quando a variável de ambiente SERPER_API_KEY estiver preenchida
URL_API_SERPER = "https://google.serper.dev/shopping"
TIMEOUT_API_SEGUNDOS = 20

# no Docker esta pasta é montada no computador, assim os HTMLs de depuração aparecem no projeto
DIRETORIO_DEBUG = Path(os.environ.get("DIRETORIO_DEBUG", Path(__file__).parent.parent / "scrapers"))
CAMINHO_DEBUG_HTML = DIRETORIO_DEBUG / "debug_google_shopping.html"
CAMINHO_ULTIMO_HTML = DIRETORIO_DEBUG / "ultimo_html_google_shopping.html"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

SCRIPT_ANTI_DETECCAO = "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"

SELETORES_BANNER_COOKIES = [
    "button:has-text('Aceitar tudo')",
    "button:has-text('Aceito')",
    "button[aria-label*='Aceitar' i]",
    "#L2AGLb",
]

# o Google mostra preços sem centavos, como R$ 1.398, então os centavos são opcionais
PADRAO_PRECO = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{2}))?")
PADRAO_CASHBACK = re.compile(r"(\d+(?:[.,]\d+)?)\s*%\s*de\s*cashback", re.IGNORECASE)

PREFIXOS_LINHA_SECUNDARIA = (
    "grátis", "gratis", "frete", "entrega", "patrocinado", "méliuz", "meliuz",
    "ganhe", "ativar", "sem cashback", "nota da loja", "em até", "em ate",
    "ou ", "de r$", "devolução", "devolucao", "retirada", "parcel", "usado",
)

# marcadores específicos da página de verificação do Google, a palavra recaptcha sozinha gera falso positivo
MARCADORES_BLOQUEIO = ("/sorry/", 'id="captcha-form"', "g-recaptcha", "tráfego incomum", "unusual traffic")

# limite de texto para um cartão de produto, evita subir até containers que englobam a página inteira
LIMITE_TEXTO_CARTAO = 400
LIMITE_TEXTO_PRECO = 30
LIMITE_TAMANHO_NOME_LOJA = 40


class ErroScraperGoogleShopping(Exception):
    """Erro específico do scraper do Google Shopping, usado para bloqueio por captcha ou ausência de resultados."""


@dataclass
class OfertaGoogleShopping:
    loja: str
    preco: float
    url_produto: str = ""
    nome_produto: str = ""
    imagem_produto: str = ""

    # o Google raramente detalha Pix e parcelamento no cartão de resultado, então o preço anunciado vale para os dois
    preco_pix: float = 0.0
    preco_cartao: float = 0.0
    confianca_pix_cartao: bool = False
    parcelas: int = 1
    valor_parcela: float = 0.0

    # cashback do Méliuz exibido pelo próprio Google no cartão, quando existir
    cashback_pct: float = 0.0

    # nivel de confianca entre o nome do produto encontrado e o termo pesquisado, preenchido por services/normalizacao_lojas.py, fica vazio ate esse ponto do pipeline
    confianca_nome: str = ""

    origem: str = "google_shopping"

    def __post_init__(self):
        self.preco = round(float(self.preco), 2)
        self.preco_pix = round(float(self.preco_pix), 2)
        self.preco_cartao = round(float(self.preco_cartao), 2)
        if not self.preco_pix and not self.preco_cartao:
            self.preco_pix = self.preco
            self.preco_cartao = self.preco


def _converter_preco(encontrado):
    inteiro = encontrado.group(1).replace(".", "")
    centavos = encontrado.group(2) or "00"
    return float(f"{inteiro}.{centavos}")


def _linha_e_ruido(linha):
    """Indica se uma linha de texto do cartão não é nome de produto nem de loja, como preço, frete, nota ou cashback."""
    minuscula = linha.lower().strip()
    if len(minuscula) < 2 or PADRAO_PRECO.search(linha):
        return True
    if minuscula.startswith(PREFIXOS_LINHA_SECUNDARIA):
        return True
    if "cashback" in minuscula or re.search(r"\d+\s*x\b", minuscula):
        return True
    return re.fullmatch(r"[\dR$.,/%()\s]+", linha) is not None


def _linhas_uteis(cartao):
    return [linha.strip() for linha in cartao.stripped_strings if not _linha_e_ruido(linha)]


def _elementos_de_preco(soup):
    """Devolve os elementos mais internos cujo texto é um preço, mesmo quando o símbolo R$ e o valor estão em tags separadas."""
    elementos = []
    for tag in soup.find_all(True):
        texto = tag.get_text(" ", strip=True)
        if len(texto) > LIMITE_TEXTO_PRECO or not PADRAO_PRECO.search(texto):
            continue
        filhos = tag.find_all(True, recursive=False)
        if any(PADRAO_PRECO.search(filho.get_text(" ", strip=True)) for filho in filhos):
            continue
        elementos.append(tag)
    return elementos


def _contar_precos(tag, ids_de_preco):
    total = 1 if id(tag) in ids_de_preco else 0
    return total + sum(1 for descendente in tag.descendants if id(descendente) in ids_de_preco)


def _localizar_cartao(elemento_preco, ids_de_preco):
    """Sobe a partir do preço até o maior bloco que ainda contém um único preço e um link, sem depender de classes CSS."""
    link_pai = elemento_preco.find_parent("a", href=True)
    if link_pai is not None:
        texto_link = link_pai.get_text(" ", strip=True)
        cabe_no_limite = len(texto_link) <= LIMITE_TEXTO_CARTAO
        if cabe_no_limite and _contar_precos(link_pai, ids_de_preco) <= 2 and len(_linhas_uteis(link_pai)) >= 2:
            return link_pai

    cartao = None
    atual = elemento_preco.parent
    while atual is not None and atual.name not in ("body", "html", "[document]"):
        if len(atual.get_text(" ", strip=True)) > LIMITE_TEXTO_CARTAO:
            break
        if _contar_precos(atual, ids_de_preco) > 1:
            break
        if atual.find("a", href=True):
            cartao = atual
        atual = atual.parent
    return cartao


def _normalizar_url(href):
    if href.startswith("/url?q="):
        return unquote(href.split("/url?q=")[1].split("&")[0])
    if href.startswith("/"):
        return f"https://www.google.com{href}"
    return href


def _extrair_dominio(url):
    """Devolve o nome do domínio da loja, ou vazio quando o link aponta para o próprio Google."""
    host = (urlparse(url or "").hostname or "").removeprefix("www.")
    if not host or host.endswith("google.com") or host.endswith("google.com.br"):
        return ""
    return host.split(".")[0].capitalize()


def _extrair_imagem(cartao):
    for imagem in cartao.find_all("img"):
        origem = imagem.get("src") or imagem.get("data-src") or ""
        if origem.startswith("http"):
            return origem
    return ""


def _extrair_oferta_do_cartao(cartao):
    """Monta uma oferta a partir de um cartão, devolvendo None quando não houver preço, link ou nome reconhecíveis."""
    link = cartao if cartao.name == "a" and cartao.get("href") else cartao.find("a", href=True)
    if link is None:
        return None
    url_produto = _normalizar_url(link.get("href", ""))

    texto_cartao = cartao.get_text(" ", strip=True)
    preco_encontrado = PADRAO_PRECO.search(texto_cartao)
    if preco_encontrado is None:
        return None

    linhas = _linhas_uteis(cartao)
    if not linhas:
        return None
    nome_produto = max(linhas, key=len)
    posicao_nome = linhas.index(nome_produto)
    candidatas_loja = linhas[posicao_nome + 1:] + linhas[:posicao_nome]
    loja = next((linha for linha in candidatas_loja if len(linha) <= LIMITE_TAMANHO_NOME_LOJA), "")
    loja = loja or _extrair_dominio(url_produto) or "Loja não identificada"

    cashback_encontrado = PADRAO_CASHBACK.search(texto_cartao)
    cashback_pct = float(cashback_encontrado.group(1).replace(",", ".")) if cashback_encontrado else 0.0

    return OfertaGoogleShopping(
        loja=loja,
        preco=_converter_preco(preco_encontrado),
        url_produto=url_produto,
        nome_produto=nome_produto,
        imagem_produto=_extrair_imagem(cartao),
        cashback_pct=cashback_pct,
    )


def parsear_html_google_shopping(html):
    """Extrai as ofertas do HTML bruto da aba de produtos do Google, sem depender de rede nem do Playwright."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    elementos = _elementos_de_preco(soup)
    ids_de_preco = {id(elemento) for elemento in elementos}

    ofertas = []
    cartoes_vistos = set()
    for elemento in elementos:
        cartao = _localizar_cartao(elemento, ids_de_preco)
        if cartao is None or id(cartao) in cartoes_vistos:
            continue
        cartoes_vistos.add(id(cartao))
        oferta = _extrair_oferta_do_cartao(cartao)
        if oferta:
            ofertas.append(oferta)
    return ofertas


def _ofertas_do_serper(dados):
    """Converte a resposta JSON da API do Serper em ofertas, ignorando itens sem preço, loja ou link."""
    ofertas = []
    for item in dados.get("shopping", []):
        preco_encontrado = PADRAO_PRECO.search(str(item.get("price", "")))
        loja = str(item.get("source", "")).strip()
        url_produto = str(item.get("link", "")).strip()
        if preco_encontrado is None or not loja or not url_produto:
            continue
        ofertas.append(
            OfertaGoogleShopping(
                loja=loja,
                preco=_converter_preco(preco_encontrado),
                url_produto=url_produto,
                nome_produto=str(item.get("title", "")).strip(),
                imagem_produto=str(item.get("imageUrl", "")).strip(),
            )
        )
    return ofertas


def _buscar_via_api_serper(nome_produto, chave_api):
    """Consulta o Google Shopping pela API do Serper, que não sofre bloqueio de captcha."""
    resposta = requests.post(
        URL_API_SERPER,
        headers={"X-API-KEY": chave_api, "Content-Type": "application/json"},
        json={"q": nome_produto, "gl": "br", "hl": "pt-br", "num": 100},
        timeout=TIMEOUT_API_SEGUNDOS,
    )
    resposta.raise_for_status()
    return _ofertas_do_serper(resposta.json())


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


def _rolar_pagina(pagina, vezes=3):
    """Rola a página algumas vezes para o Google carregar mais resultados."""
    for _ in range(vezes):
        pagina.mouse.wheel(0, 2500)
        pagina.wait_for_timeout(800)


def _html_indica_bloqueio(html, url):
    conteudo = f"{url} {html}".lower()
    return any(marcador in conteudo for marcador in MARCADORES_BLOQUEIO)


def _descrever_pagina(html, url):
    """Resume título e endereço final da página, para o erro mostrar o que o navegador realmente recebeu."""
    titulo = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    texto_titulo = " ".join(titulo.group(1).split())[:80] if titulo else "sem título"
    return f"título '{texto_titulo}', endereço final {url[:120]}"


def _salvar_html(caminho, html):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(html, encoding="utf-8")


def _abrir_navegador(playwright, headless):
    """Prefere o Chromium completo em modo headless novo, que se parece mais com um Chrome comum, e cai para o padrão se não houver suporte."""
    argumentos = ["--disable-blink-features=AutomationControlled"]
    try:
        return playwright.chromium.launch(channel="chromium", headless=headless, args=argumentos)
    except Exception:
        return playwright.chromium.launch(headless=headless, args=argumentos)


def _coletar_html_de_url(url, headless, timeout_ms):
    """Abre uma URL de busca num navegador headless e devolve o HTML já renderizado, junto da URL final."""
    with sync_playwright() as playwright:
        navegador = _abrir_navegador(playwright, headless)
        contexto = navegador.new_context(
            user_agent=USER_AGENT,
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            viewport={"width": 1366, "height": 900},
        )
        contexto.add_init_script(SCRIPT_ANTI_DETECCAO)
        pagina = contexto.new_page()
        try:
            pagina.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            _fechar_banner_cookies(pagina)
            try:
                pagina.wait_for_function(
                    r"document.body && /R\$\s*\d/.test(document.body.innerText)",
                    timeout=timeout_ms,
                )
            except Exception:
                pass
            _rolar_pagina(pagina)
            return pagina.content(), pagina.url
        finally:
            contexto.close()
            navegador.close()


def _buscar_via_navegador(nome_produto, timeout_ms, headless, motivos):
    """Tenta cada URL de busca no navegador, acumulando os motivos de falha, e devolve as ofertas normalizadas ou lista vazia."""
    termo = quote_plus(nome_produto)
    for modelo_url in URLS_BUSCA_SHOPPING:
        try:
            html, url_final = _coletar_html_de_url(modelo_url.format(termo=termo), headless, timeout_ms)
        except Exception as erro:
            motivos.append(f"falha ao abrir a busca, {erro}")
            continue

        _salvar_html(CAMINHO_ULTIMO_HTML, html)
        descricao = _descrever_pagina(html, url_final)

        ofertas_brutas = parsear_html_google_shopping(html)
        if not ofertas_brutas:
            if _html_indica_bloqueio(html, url_final):
                motivos.append(f"o Google exigiu verificação de captcha, {descricao}")
                return []
            motivos.append(f"a página abriu, mas nenhuma oferta com preço foi reconhecida, {descricao}")
            continue

        ofertas = normalizar_e_filtrar_ofertas(ofertas_brutas, nome_produto)
        if ofertas:
            return ofertas
        motivos.append(
            f"{len(ofertas_brutas)} resultados encontrados, mas todos foram descartados pelo filtro de qualidade"
        )
    return []


def buscar_ofertas_google_shopping(nome_produto, timeout_ms=30000, headless=True, salvar_debug_em_falha=True):
    """Pesquisa um produto no Google Shopping, pela API do Serper quando houver chave e pelo navegador nos demais casos, levantando erro com o motivo quando nada for encontrado."""
    motivos = []

    chave_api = os.environ.get("SERPER_API_KEY", "").strip()
    if chave_api:
        try:
            ofertas_brutas = _buscar_via_api_serper(nome_produto, chave_api)
            ofertas = normalizar_e_filtrar_ofertas(ofertas_brutas, nome_produto)
            if ofertas:
                return ofertas
            motivos.append(f"a API retornou {len(ofertas_brutas)} resultados, mas nenhum passou no filtro de qualidade")
        except Exception as erro:
            motivos.append(f"falha na API do Serper, {erro}")

    ofertas = _buscar_via_navegador(nome_produto, timeout_ms, headless, motivos)
    if ofertas:
        return ofertas

    if salvar_debug_em_falha and CAMINHO_ULTIMO_HTML.exists():
        _salvar_html(CAMINHO_DEBUG_HTML, CAMINHO_ULTIMO_HTML.read_text(encoding="utf-8"))
    raise ErroScraperGoogleShopping(
        f"nenhuma oferta obtida para {nome_produto}, {'; '.join(motivos)}. HTML salvo em {CAMINHO_ULTIMO_HTML}"
    )


if __name__ == "__main__":
    resultado = buscar_ofertas_google_shopping("geladeira electrolux", headless=False)
    print(f"{len(resultado)} ofertas encontradas")
    for oferta in resultado:
        print(oferta)
