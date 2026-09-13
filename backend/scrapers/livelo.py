"""
scraper publico de parceiros da livelo.

este modulo segue a mesma separacao de responsabilidades do scraper do buscape, ver scrapers/buscape.py. o navegador so e usado para abrir a pagina publica de parceiros do compre e pontue, sem autenticacao e sem login em conta, e coletar o html renderizado, atraves de pagina.content(). a partir dai, todo o trabalho de achar cada parceiro, seu codigo, nome e taxa de pontos acontece fora do navegador, na funcao parsear_html_livelo, usando o beautifulsoup. 

um detalhe importante, o nome do parceiro nao aparece mais como texto visivel no card, so no atributo alt da logo, tipo <img alt="Logo Magalu">, texto de atributo que link.get_text() nao enxerga. por isso o nome vem de _extrair_nome, lendo o alt da imagem, com o slug da propria url como plano b, ver esse comentario la para os detalhes.

essa separacao traz o mesmo beneficio que tem no buscape, dá para reprocessar um html ja salvo em disco sem abrir o navegador de novo, util tanto para ajustar as expressoes regulares quanto para conferir rapidamente o que uma coleta antiga trouxe, veja debug_scraper.py, opcao --reparsear.

este modulo nao acessa dados privados de nenhum usuario, apenas as taxas de pontuacao e promocoes publicadas em https://www.livelo.com.br/juntar-pontos/todos-os-parceiros

dois pontos importantes sobre como este scraper funciona.
primeiro, a lista de parceiros carrega aos poucos conforme a pagina e rolada, entao o scraper simula rolagem ate o final antes de coletar o html, do contrario so os primeiros parceiros aparecem.
segundo, o site pode mudar a qualquer momento, ou bloquear o acesso automatizado, como ja acontece hoje atraves do akamai a nivel de dominio, ver o comentario no topo de database/db.py. o html da ultima coleta, sucesso ou falha, fica sempre salvo em ultimo_html_livelo.html, ao lado deste arquivo, para poder ser reprocessado sem precisar de rede. quando a coleta falhar por completo, o mesmo html tambem e salvo em debug_livelo.html, para facilitar achar esse caso especifico depois.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL_PARCEIROS = "https://www.livelo.com.br/juntar-pontos/todos-os-parceiros"

CAMINHO_DEBUG_HTML = Path(__file__).parent / "debug_livelo.html"

# html completo da ultima coleta, sucesso ou falha, sempre sobrescrito. serve para ajustar as expressoes regulares abaixo sem precisar abrir o navegador de novo, veja parsear_html_livelo e debug_scraper.py
CAMINHO_ULTIMO_HTML = Path(__file__).parent / "ultimo_html_livelo.html"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

SCRIPT_ANTI_DETECCAO = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""

# seletor css do link de cada parceiro, funciona tanto para o playwright quanto para o beautifulsoup, ja que os dois aceitam a mesma sintaxe de seletor
SELETOR_LINK_PARCEIRO = 'a[href*="/juntar-pontos/parceiros/"]'

SELETORES_BANNER_COOKIES = [
    "#onetrust-accept-btn-handler",
    "button#onetrust-accept-btn-handler",
    "button[aria-label*='aceitar' i]",
    "button:has-text('Aceitar')",
]

PADRAO_CODIGO = re.compile(r"/parceiros/[^/]+/([A-Za-z0-9]+)$")
PADRAO_SLUG = re.compile(r"/parceiros/([^/]+)/[A-Za-z0-9]+$")
PADRAO_PONTOS = re.compile(r"(\d+)\s*ponto[s]?\s*por\s*(r\$|u\$)\s*([\d.,]+)", re.IGNORECASE)
PADRAO_EM_PROMOCAO = re.compile(r"^\s*(promoção|nova)", re.IGNORECASE)
PADRAO_ERAM = re.compile(r"eram\s*(\d+)\s*ponto[s]?", re.IGNORECASE)
PADRAO_PREFIXO_LOGO = re.compile(r"^logo\s+", re.IGNORECASE)


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
    # apelido derivado do slug da propria url, tipo "magalu" em .../parceiros/magalu/MZL, usado como candidato extra no casamento de nomes em services/casamento_lojas.py, mesmo quando o nome principal vier certo
    alias: str = ""


class ErroScraperLivelo(Exception):
    """
    erro especifico do scraper, para diferenciar falha de rede ou de bloqueio de bot de um erro generico de programacao.
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


def _slug_do_href(href):
    """
    devolve o trecho legivel da url do parceiro, por exemplo "magalu" em .../parceiros/magalu/MZL, ou none quando o href nao seguir esse formato.
    """
    encontrado = PADRAO_SLUG.search(href)
    if not encontrado:
        return None
    return encontrado.group(1)


def _nome_a_partir_do_slug(slug):
    """
    transforma um slug de url, tipo "consorcio-magalu", num nome legivel, "Consorcio Magalu", so para ter algo melhor que o codigo quando a logo nao carregar.
    """
    return " ".join(parte.capitalize() for parte in slug.replace("-", " ").split())


def _extrair_nome(link, codigo, slug):
    """
    o nome do parceiro nao aparece mais como texto visível no card, so no atributo alt da logo, tipo <img alt="Logo Magalu">. get_text() do beautifulsoup nao le atributos, so texto de no, entao o nome precisa vir daqui, e nao de uma expressao regular em cima do texto do link.

    quando a logo nao carregou naquela copia especifica do card, o que acontece as vezes quando o mesmo parceiro aparece mais de uma vez na pagina, cai para o slug da propria url, e so em ultimo caso para o codigo, que nao serve pra casar com o nome da loja no buscape.
    
    Zdevolve o nome e se ele veio de fato da logo, para a deduplicacao em parsear_html_livelo preferir a copia com logo quando as duas existirem.
    """
    img = link.find("img")
    alt = (img.get("alt") or "").strip() if img else ""

    if alt:
        nome = PADRAO_PREFIXO_LOGO.sub("", alt).strip()
        if nome:
            return nome, True

    if slug:
        return _nome_a_partir_do_slug(slug), False

    return codigo, False


def _extrair_parceiro(link):
    """
    monta um ParceiroLivelo a partir de um link de parceiro ja localizado pelo beautifulsoup, lendo o codigo e o apelido da propria url, o nome do atributo alt da logo, e o restante dos dados do texto visivel do card.
    """
    href = link.get("href", "")

    encontrado_codigo = PADRAO_CODIGO.search(href)
    if not encontrado_codigo:
        return None, False
    codigo = encontrado_codigo.group(1).upper()

    slug = _slug_do_href(href)
    alias = slug.replace("-", " ").strip() if slug else ""
    nome, tem_logo = _extrair_nome(link, codigo, slug)

    texto = " ".join(link.get_text(" ", strip=True).split())

    em_promocao = bool(PADRAO_EM_PROMOCAO.match(texto))

    blocos = re.split(r"\bclube\b", texto, flags=re.IGNORECASE)
    pontos_padrao, moeda_padrao = _parse_taxa_pontos(blocos[0])

    pontos_clube = 0.0
    if len(blocos) > 1:
        taxa_clube, _ = _parse_taxa_pontos(blocos[1])
        pontos_clube = taxa_clube or 0.0

    encontrado_eram = PADRAO_ERAM.search(texto)
    pontos_anteriores = float(encontrado_eram.group(1)) if encontrado_eram else 0.0

    if pontos_padrao is None:
        return None, False

    parceiro = ParceiroLivelo(
        codigo=codigo,
        nome=nome,
        url=href,
        pontos_padrao=round(pontos_padrao, 4),
        moeda_padrao=moeda_padrao or "R$",
        pontos_clube=round(pontos_clube, 4),
        em_promocao=em_promocao,
        pontos_anteriores=pontos_anteriores,
        alias=alias,
    )
    return parceiro, tem_logo


def parsear_html_livelo(html):
    """
    extrai a lista de parceiros a partir do html bruto da pagina de parceiros da livelo, sem depender do playwright nem de rede, util tanto para ajustar a extracao quanto para reprocessar uma coleta antiga sem consultar o site de novo, veja debug_scraper.py, opcao --reparsear.
    
    deduplica pelo codigo do parceiro. quando o mesmo codigo aparece mais de uma vez, o que acontece as vezes por causa do layout da pagina, prefere a copia cuja logo carregou, ja que e dela que vem o nome de verdade, usado depois no casamento com o buscape.
    """
    soup = BeautifulSoup(html, "html.parser")

    parceiros_por_codigo = {}
    for link in soup.select(SELETOR_LINK_PARCEIRO):
        parceiro, tem_logo = _extrair_parceiro(link)
        if not parceiro:
            continue

        existente = parceiros_por_codigo.get(parceiro.codigo)
        if existente is None:
            parceiros_por_codigo[parceiro.codigo] = (parceiro, tem_logo)
        elif tem_logo and not existente[1]:
            parceiros_por_codigo[parceiro.codigo] = (parceiro, tem_logo)

    return [parceiro for parceiro, _ in parceiros_por_codigo.values()]


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
    a lista de parceiros e carregada aos poucos, entao rola a pagina ate o final repetidas vezes, ate a altura da pagina parar de aumentar, sinal de que tudo ja foi carregado.
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
    abre a pagina publica de parceiros da livelo num navegador headless, rola ate carregar tudo, e devolve o html renderizado, sem fazer nenhuma extracao aqui, isso fica por conta de parsear_html_livelo. nao faz login, nao acessa conta nenhuma.
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
            # domcontentloaded em vez de networkidle, porque a pagina da livelo mantem chamadas de fundo continuas, o que fazia o networkidle nunca resolver e estourar o timeout
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
    abre a pagina publica de parceiros da livelo e devolve a lista completa de parceiros encontrados, combinando a coleta do html pelo playwright com a extracao pura em parsear_html_livelo.
    
    o html da coleta e sempre salvo em ultimo_html_livelo.html, sucesso ou falha, e adicionalmente em debug_livelo.html quando nenhum parceiro for reconhecido, para facilitar achar esse caso depois.
    
    levanta ErroScraperLivelo quando a pagina nao trouxer nenhum parceiro reconhecivel dentro do tempo limite, o chamador decide se mostra esse erro ao usuario.
    """
    html_pagina = _coletar_html_pagina_parceiros(timeout_ms, headless)

    if html_pagina:
        CAMINHO_ULTIMO_HTML.write_text(html_pagina, encoding="utf-8")

    parceiros = parsear_html_livelo(html_pagina) if html_pagina else []

    if not parceiros:
        if salvar_debug_em_falha and html_pagina:
            CAMINHO_DEBUG_HTML.write_text(html_pagina, encoding="utf-8")
        raise ErroScraperLivelo(
            f"a pagina abriu, mas nenhum parceiro foi reconhecido a tempo. isso costuma acontecer quando o site bloqueia o navegador automatizado, mostra um banner novo por cima da lista, ou muda o layout. o html foi salvo em {CAMINHO_ULTIMO_HTML}, e tambem em {CAMINHO_DEBUG_HTML}, para conferencia. reprocesse esse html com python debug_scraper.py livelo qualquer --reparsear scrapers/ultimo_html_livelo.html enquanto ajusta os seletores"
        )

    return parceiros


if __name__ == "__main__":
    resultado = buscar_parceiros_livelo(headless=False)
    print(f"{len(resultado)} parceiros encontrados")
    for parceiro in resultado:
        print(parceiro)