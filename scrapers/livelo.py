"""
scraper publico de parceiros da livelo.

este modulo le apenas a pagina publica de parceiros do compre e
pontue, sem autenticacao e sem login em conta. ele nao acessa dados
privados de nenhum usuario, apenas as taxas de pontuacao e promocoes
publicadas em

https://www.livelo.com.br/juntar-pontos/todos-os-parceiros

dois pontos importantes sobre como este scraper funciona.

primeiro, a lista de parceiros carrega aos poucos conforme a pagina e
rolada, entao o scraper simula rolagem ate o final antes de coletar
os links, do contrario so os primeiros parceiros aparecem no html.

segundo, o site pode mudar a qualquer momento, ou bloquear o acesso
automatizado. quando a coleta falhar, o html da pagina e salvo em
debug_livelo.html, ao lado deste arquivo, para ajudar a entender o
que aconteceu antes de mexer no codigo.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import sync_playwright

URL_PARCEIROS = "https://www.livelo.com.br/juntar-pontos/todos-os-parceiros"

CAMINHO_DEBUG_HTML = Path(__file__).parent / "debug_livelo.html"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

SCRIPT_ANTI_DETECCAO = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""

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


def buscar_parceiros_livelo(timeout_ms=60000, headless=True, salvar_debug_em_falha=True):
    """
    abre a pagina publica de parceiros da livelo num navegador
    headless e devolve a lista completa de parceiros encontrados.
    nao faz login, nao acessa conta nenhuma.

    levanta ErroScraperLivelo quando a pagina nao traz nenhum
    parceiro reconhecivel dentro do tempo limite, o chamador decide
    se mostra esse erro ao usuario.
    """
    links = []
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
            # domcontentloaded em vez de networkidle, porque a pagina
            # da livelo mantem chamadas de fundo continuas, o que
            # fazia o networkidle nunca resolver e estourar o timeout
            pagina.goto(URL_PARCEIROS, timeout=timeout_ms, wait_until="domcontentloaded")

            _fechar_banner_cookies(pagina)

            try:
                pagina.wait_for_selector(SELETOR_LINK_PARCEIRO, timeout=timeout_ms, state="attached")
            except Exception:
                links = []
            else:
                _rolar_ate_carregar_tudo(pagina)
                links = pagina.query_selector_all(SELETOR_LINK_PARCEIRO)

            html_pagina = pagina.content()
        except Exception as erro:
            contexto.close()
            navegador.close()
            raise ErroScraperLivelo(
                f"nao foi possivel abrir a pagina da livelo, detalhe tecnico, {erro}"
            )

        contexto.close()
        navegador.close()

    if not links:
        if salvar_debug_em_falha and html_pagina:
            CAMINHO_DEBUG_HTML.write_text(html_pagina, encoding="utf-8")
        raise ErroScraperLivelo(
            "a pagina abriu, mas nenhum parceiro apareceu a tempo. isso costuma "
            "acontecer quando o site bloqueia o navegador automatizado, mostra um "
            "banner novo por cima da lista, ou muda o layout. o html da pagina foi "
            f"salvo em {CAMINHO_DEBUG_HTML} para conferencia"
        )

    parceiros_brutos = []
    for link in links:
        href = link.get_attribute("href") or ""
        texto = link.inner_text()
        parceiro = _extrair_parceiro(href, texto)
        if parceiro:
            parceiros_brutos.append(parceiro)

    if not parceiros_brutos:
        if salvar_debug_em_falha and html_pagina:
            CAMINHO_DEBUG_HTML.write_text(html_pagina, encoding="utf-8")
        raise ErroScraperLivelo(
            "a pagina carregou e tinha links de parceiro, mas nenhum foi "
            "reconhecido. o layout provavelmente mudou, revise as expressoes "
            f"regulares em scrapers/livelo.py, o html foi salvo em {CAMINHO_DEBUG_HTML}"
        )

    vistos = set()
    parceiros_unicos = []
    for parceiro in parceiros_brutos:
        if parceiro.codigo not in vistos:
            vistos.add(parceiro.codigo)
            parceiros_unicos.append(parceiro)

    return parceiros_unicos


if __name__ == "__main__":
    resultado = buscar_parceiros_livelo(headless=False)
    print(f"{len(resultado)} parceiros encontrados")
    for parceiro in resultado[:10]:
        print(parceiro)
