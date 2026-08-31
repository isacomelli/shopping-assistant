"""
scraper publico de parceiros da livelo.

este modulo le apenas paginas publicas do compre e pontue, sem
autenticacao e sem login em conta. ele nao acessa dados privados de
nenhum usuario, apenas as taxas de pontuacao e promocoes publicadas
no site.

a partir desta versao, o fluxo principal deixou de ser "baixar a
listagem inteira de parceiros" e passou a ser "consultar um parceiro
especifico, pelo nome da loja", chamada por buscar_parceiro_por_loja.
isso segue o mesmo raciocinio que discutimos, a listagem inteira em
/juntar-pontos/todos-os-parceiros e a pagina mais visada por protecao
anti bot do site, porque e exatamente o tipo de pagina que um
scraper de preco tentaria raspar de uma vez so. ja abrir a pagina de
um parceiro especifico, ou pesquisar por um nome de loja, se parece
mais com a navegacao de uma pessoa real.

mesmo assim, e importante ser honesta sobre o limite disso. a livelo
usa protecao akamai, e mesmo consultas pontuais podem ser bloqueadas,
sobretudo se repetidas com frequencia. por isso o cache por loja em
database/db.py guarda cada resposta por 24 horas, e este modulo nao
tenta nenhuma tecnica agressiva de disfarce de navegador, tipo
imitar a assinatura tls de um chrome real ou alterar dezenas de
sinais de fingerprint. se mesmo assim o bloqueio persistir, a
alternativa mais confiavel continua sendo abrir a pagina manualmente
no seu navegador do dia a dia e colar o html numa das telas do app,
ja que ali nao existe automacao nenhuma para o akamai bloquear.

a funcao antiga, buscar_parceiros_livelo, que baixa a listagem
inteira, foi mantida no fim do arquivo apenas como consulta manual de
apoio, ela nao faz mais parte do fluxo automatico da calculadora.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import sync_playwright

URL_PARCEIROS = "https://www.livelo.com.br/juntar-pontos/todos-os-parceiros"
URL_PARCEIRO_POR_SLUG = "https://www.livelo.com.br/juntar-pontos/parceiros/{slug}"
URL_BUSCA = "https://www.livelo.com.br/busca?q={termo}"

CAMINHO_DEBUG_HTML = Path(__file__).parent / "debug_livelo.html"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

SCRIPT_ANTI_DETECCAO = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""

# seletores de botoes de banner de cookies conhecidos, testados nesta
# ordem, so o primeiro que existir na pagina e clicado
SELETORES_BANNER_COOKIES = [
    "#onetrust-accept-btn-handler",
    "button#onetrust-accept-btn-handler",
    "button[aria-label*='aceitar' i]",
    "button:has-text('Aceitar')",
    "button:has-text('aceitar todos')",
]

PADRAO_CODIGO = re.compile(r"/parceiros/[^/]+/([A-Za-z0-9]+)$")
PADRAO_PONTOS = re.compile(r"(\d+)\s*ponto[s]?\s*por\s*(r\$|u\$)\s*([\d.,]+)", re.IGNORECASE)
PADRAO_EM_PROMOCAO = re.compile(r"^\s*(promoção|nova)", re.IGNORECASE)
PADRAO_ERAM = re.compile(r"eram\s*(\d+)\s*ponto[s]?", re.IGNORECASE)
PADRAO_NOME = re.compile(r"logo\s+(.*?)(?=\s*(?:até\s*)?\d+\s*ponto)", re.IGNORECASE)

# regra por categoria, tipo "3 pontos em eletrodomesticos, 2 pontos no
# restante", usada na pagina de detalhe de um parceiro especifico
PADRAO_REGRA_POR_CATEGORIA = re.compile(
    r"(\d+)\s*ponto[s]?\s*(?:por|em|para)\s*(cada\s*)?(r\$|u\$)?\s*([\d.,]*)\s*(?:em|na|no)?\s*([a-zà-ú\s]{3,40})",
    re.IGNORECASE,
)

SELETOR_LINK_PARCEIRO = 'a[href*="/juntar-pontos/parceiros/"]'


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


@dataclass
class ParceiroLoja:
    """
    resultado da consulta de um unico parceiro, feita pelo nome da
    loja. diferente de ParceiroLivelo, pode representar tambem uma
    consulta sem sucesso, atraves do campo encontrado.
    """

    loja_pesquisada: str
    encontrado: bool
    pontos_por_real: float = 0.0
    moeda_padrao: str = "R$"
    regras_extras: list = field(default_factory=list)
    url_consultada: str = ""
    mensagem: str = ""


class ErroScraperLivelo(Exception):
    """
    erro especifico do scraper, para diferenciar falha de rede ou de
    bloqueio de bot de um erro generico de programacao.
    """


def _remover_acentos(texto):
    forma_normalizada = unicodedata.normalize("NFKD", texto)
    return "".join(caractere for caractere in forma_normalizada if not unicodedata.combining(caractere))


def gerar_slug_loja(nome_loja):
    """
    transforma o nome de uma loja no formato de slug usado nas
    urls de parceiro da livelo, por exemplo "Fast Shop" vira
    "fast-shop". e uma aproximacao, nem sempre bate com o slug real
    cadastrado pela livelo para aquele parceiro.
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


def _extrair_regras_do_texto(texto):
    """
    varre o texto de uma pagina de parceiro atras de todas as regras
    do tipo "n pontos por r$/u$ x em categoria", devolvendo uma lista
    de descricoes legiveis, uma por regra encontrada. a regra
    principal, sem categoria especifica, fica no pontos_por_real do
    ParceiroLoja, as demais entram em regras_extras.
    """
    regras = []
    for encontrado in PADRAO_REGRA_POR_CATEGORIA.finditer(texto):
        pontos, _, moeda, base, categoria = encontrado.groups()
        categoria = categoria.strip().rstrip(".,")
        if not categoria or len(categoria) < 3:
            continue
        moeda_formatada = moeda.upper() if moeda else "R$"
        base_formatada = base if base else "1"
        regras.append(f"{pontos} pontos por {moeda_formatada} {base_formatada} em {categoria}")
    return regras


def _consultar_pagina_parceiro(pagina, url, timeout_ms):
    """
    abre uma pagina de parceiro especifica e devolve o texto puro
    dela, ou string vazia se o conteudo esperado nao aparecer a
    tempo.
    """
    pagina.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
    _fechar_banner_cookies(pagina)
    try:
        pagina.wait_for_selector("body", timeout=timeout_ms, state="attached")
    except Exception:
        return ""
    pagina.wait_for_timeout(1500)
    return pagina.inner_text("body")


def buscar_parceiro_por_loja(nome_loja, timeout_ms=45000, headless=True, salvar_debug_em_falha=True):
    """
    consulta a livelo pela taxa de pontos de uma unica loja, sem
    baixar a listagem inteira de parceiros.

    tenta primeiro o slug adivinhado a partir do nome da loja, e se
    a pagina nao trouxer nenhuma taxa reconhecida, tenta a busca
    interna do site com o nome da loja. sempre devolve um
    ParceiroLoja, com encontrado=False quando nada foi localizado, em
    vez de levantar excecao, para o chamador poder seguir o fluxo
    normalmente mesmo quando aquela loja simplesmente nao e parceira.

    levanta ErroScraperLivelo apenas quando o proprio navegador falha
    em abrir, por exemplo por bloqueio total do akamai.
    """
    slug = gerar_slug_loja(nome_loja)
    url_direta = URL_PARCEIRO_POR_SLUG.format(slug=slug)
    url_busca = URL_BUSCA.format(termo=nome_loja.replace(" ", "+"))

    texto_pagina = ""
    url_usada = url_direta

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
            texto_pagina = _consultar_pagina_parceiro(pagina, url_direta, timeout_ms)

            if not PADRAO_PONTOS.search(texto_pagina):
                url_usada = url_busca
                texto_pagina = _consultar_pagina_parceiro(pagina, url_busca, timeout_ms)
        except Exception as erro:
            contexto.close()
            navegador.close()
            raise ErroScraperLivelo(
                f"nao foi possivel abrir a pagina da livelo para {nome_loja}, detalhe tecnico, {erro}"
            )

        contexto.close()
        navegador.close()

    encontrado_pontos = PADRAO_PONTOS.search(texto_pagina)
    if not encontrado_pontos:
        if salvar_debug_em_falha and texto_pagina:
            CAMINHO_DEBUG_HTML.write_text(texto_pagina, encoding="utf-8")
        return ParceiroLoja(
            loja_pesquisada=nome_loja,
            encontrado=False,
            url_consultada=url_usada,
            mensagem=(
                "nenhuma taxa de pontos foi encontrada para esta loja, ela pode nao "
                "ser parceira da livelo, ou a pagina pode ter bloqueado a consulta"
            ),
        )

    pontos = float(encontrado_pontos.group(1))
    moeda = encontrado_pontos.group(2).upper()
    base = float(encontrado_pontos.group(3).replace(".", "").replace(",", "."))
    pontos_por_real = round(pontos / base, 4) if base else 0.0

    regras_extras = _extrair_regras_do_texto(texto_pagina)

    return ParceiroLoja(
        loja_pesquisada=nome_loja,
        encontrado=True,
        pontos_por_real=pontos_por_real,
        moeda_padrao=moeda or "R$",
        regras_extras=regras_extras,
        url_consultada=url_usada,
    )


# a partir daqui, o scraper antigo, que baixa a listagem publica
# inteira de parceiros. mantido apenas para consulta manual, na
# pagina de parceiros livelo, quando fizer sentido revisar o catalogo
# completo de uma vez

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
    encontrado_codigo = PADRAO_CODIGO.search(href)
    if not encontrado_codigo:
        return None
    codigo = encontrado_codigo.group(1).upper()

    texto = " ".join(texto_completo.split())

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


def _tentar_carregar_parceiros(pagina, timeout_ms):
    pagina.goto(URL_PARCEIROS, timeout=timeout_ms, wait_until="domcontentloaded")

    _fechar_banner_cookies(pagina)

    try:
        pagina.wait_for_selector(SELETOR_LINK_PARCEIRO, timeout=timeout_ms, state="attached")
    except Exception:
        return []

    altura_anterior = 0
    for _ in range(20):
        pagina.mouse.wheel(0, 2000)
        pagina.wait_for_timeout(300)
        altura_atual = pagina.evaluate("document.body.scrollHeight")
        if altura_atual == altura_anterior:
            break
        altura_anterior = altura_atual

    return pagina.query_selector_all(SELETOR_LINK_PARCEIRO)


def buscar_parceiros_livelo(timeout_ms=90000, headless=True, salvar_debug_em_falha=True, tentativas=2):
    """
    abre a pagina publica de parceiros da livelo num navegador e
    devolve a lista completa de parceiros encontrados. nao faz login,
    nao acessa conta nenhuma.

    esta funcao consulta a pagina de listagem completa, a mais visada
    por protecao anti bot do site, entao e normal que ela seja
    bloqueada com mais frequencia do que buscar_parceiro_por_loja.
    use como apoio manual, nao como parte do fluxo automatico de
    pesquisa de produto.
    """
    links = []
    ultima_pagina_html = ""

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
            for tentativa in range(1, tentativas + 1):
                links = _tentar_carregar_parceiros(pagina, timeout_ms)
                ultima_pagina_html = pagina.content()
                if links:
                    break
        finally:
            contexto.close()
            navegador.close()

    if not links:
        if salvar_debug_em_falha and ultima_pagina_html:
            CAMINHO_DEBUG_HTML.write_text(ultima_pagina_html, encoding="utf-8")
        raise ErroScraperLivelo(
            "a pagina abriu, mas nenhum parceiro apareceu a tempo, mesmo depois de "
            f"{tentativas} tentativa(s). isso costuma acontecer quando o site "
            "bloqueia o navegador automatizado, mostra um banner novo por cima da "
            "lista, ou muda o layout. o html da pagina foi salvo em "
            f"{CAMINHO_DEBUG_HTML} para voce conferir o que veio. se o html "
            "mostrar a lista de parceiros normalmente, o motivo mais provavel e o "
            "seletor a[href*=\"/juntar-pontos/parceiros/\"] ter mudado."
        )

    parceiros_brutos = []
    for link in links:
        href = link.get_attribute("href") or ""
        texto = link.inner_text()
        parceiro = _extrair_parceiro(href, texto)
        if parceiro:
            parceiros_brutos.append(parceiro)

    if not parceiros_brutos:
        if salvar_debug_em_falha and ultima_pagina_html:
            CAMINHO_DEBUG_HTML.write_text(ultima_pagina_html, encoding="utf-8")
        raise ErroScraperLivelo(
            "a pagina carregou e tinha links de parceiro, mas nenhum foi "
            "reconhecido. o layout provavelmente mudou, revise as expressoes "
            "regulares em scrapers/livelo.py, o html foi salvo em "
            f"{CAMINHO_DEBUG_HTML}"
        )

    vistos = set()
    parceiros_unicos = []
    for parceiro in parceiros_brutos:
        if parceiro.codigo not in vistos:
            vistos.add(parceiro.codigo)
            parceiros_unicos.append(parceiro)

    return parceiros_unicos


if __name__ == "__main__":
    resultado = buscar_parceiro_por_loja("Fast Shop", headless=False)
    print(resultado)
