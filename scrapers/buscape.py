"""
scraper publico de precos do buscape, por nome de produto.

este modulo pesquisa um produto no buscape e devolve a lista de
lojas encontradas com o respectivo preco, para servir de ponto de
partida do fluxo automatico. a partir da lista de lojas, a pesquisa
automatica em services/pesquisa_produto.py tenta casar cada loja com
um parceiro livelo ja cadastrado manualmente, ver o comentario no
topo de database/db.py sobre por que esse cadastro e manual.

uma observacao importante sobre confiabilidade. o robots.txt do
buscape atualmente nao permite acesso automatizado, e o site tambem
usa protecao contra navegador automatizado, entao e esperado que esta
consulta falhe de vez em quando, ou sempre, dependendo de como o site
estiver se comportando no momento. este scraper nao tenta nenhuma
tecnica agressiva de disfarce, tipo imitar a assinatura tls de um
chrome real, so um user agent realista e a ocultacao do sinal mais
comum de automacao.

quando a consulta falhar, o caminho mais confiavel continua sendo
cadastrar a oferta manualmente na calculadora, atraves do botao
editar variaveis.

como o layout de resultados de busca do buscape pode mudar a
qualquer momento, e como nao foi possivel validar os seletores contra
o site ao vivo no momento em que este scraper foi escrito, trate os
seletores abaixo como um ponto de partida razoavel, nao como algo
testado, e ajuste conforme o html real que aparecer, o html sempre e
salvo em debug_buscape.html quando a busca nao encontra nada.

sobre a distincao entre preco no pix e preco no cartao, o cartao de
resultado do buscape costuma trazer os dois valores juntos quando a
loja anuncia desconto a vista. o padrao PADRAO_PRECO_PIX abaixo tenta
reconhecer essa situacao, mas como o layout nao foi validado ao vivo,
trate a distincao como uma tentativa, nao como garantia, o campo
distincao_pix_cartao_confiavel de cada OfertaBuscape avisa quando os
dois precos vieram apenas do mesmo numero, por falta de um preco pix
reconhecivel separado.
"""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import sync_playwright

URL_BUSCA = "https://www.buscape.com.br/search?q={termo}"

CAMINHO_DEBUG_HTML = Path(__file__).parent / "debug_buscape.html"

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

# cartao de produto de um resultado de busca, ajustar conforme o
# layout real do site no momento do uso
SELETOR_CARTAO_RESULTADO = "[data-testid='product-card'], li[data-testid='result-item'], article"

PADRAO_PRECO = re.compile(r"R\$\s*([\d.]+,\d{2})")

# tenta reconhecer um preco marcado explicitamente como pix ou a vista,
# em qualquer ordem em relacao ao numero, por exemplo "R$ 899,00 no
# Pix" ou "no Pix R$ 899,00"
PADRAO_PRECO_PIX = re.compile(
    r"(?:pix|à vista)[^R$\d]{0,15}R\$\s*([\d.]+,\d{2})"
    r"|R\$\s*([\d.]+,\d{2})[^a-zA-Z]{0,15}(?:no pix|à vista)",
    re.IGNORECASE,
)


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


def _remover_acentos(texto):
    forma_normalizada = unicodedata.normalize("NFKD", texto)
    return "".join(caractere for caractere in forma_normalizada if not unicodedata.combining(caractere))


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


def _extrair_preco(texto):
    encontrado = PADRAO_PRECO.search(texto)
    if not encontrado:
        return None
    return float(encontrado.group(1).replace(".", "").replace(",", "."))


def _extrair_precos_pix_cartao(texto, preco_cartao):
    """
    tenta separar o preco pix do preco cartao dentro do texto do
    cartao de resultado. devolve a tupla, preco pix, preco cartao,
    distincao confiavel.

    quando nenhum preco marcado como pix e encontrado, ou o unico
    numero reconhecido no texto e o proprio preco do cartao, os dois
    valores voltam iguais e a distincao fica marcada como nao
    confiavel, para o restante do fluxo tratar como um so preco.
    """
    encontrado = PADRAO_PRECO_PIX.search(texto)
    if not encontrado:
        return preco_cartao, preco_cartao, False

    grupo_bruto = encontrado.group(1) or encontrado.group(2)
    preco_pix = float(grupo_bruto.replace(".", "").replace(",", "."))

    if preco_pix == preco_cartao:
        return preco_cartao, preco_cartao, False

    return preco_pix, preco_cartao, True


def _extrair_loja(texto, url_produto):
    """
    tenta descobrir o nome da loja a partir do texto do cartao de
    resultado, como nem sempre da pra confiar num seletor fixo para
    isso, usa o dominio da url do produto como aproximacao quando o
    texto nao trouxer nada reconhecivel.
    """
    padrao_vendido_por = re.search(r"(?:vendido por|em)\s+([A-Za-zÀ-ú0-9&\s]{2,30})", texto, re.IGNORECASE)
    if padrao_vendido_por:
        return padrao_vendido_por.group(1).strip()

    padrao_dominio = re.search(r"https?://(?:www\.)?([^./]+)\.", url_produto)
    if padrao_dominio:
        return padrao_dominio.group(1).capitalize()

    return "loja nao identificada"


def buscar_ofertas_buscape(nome_produto, max_resultados=10, timeout_ms=45000, headless=True,
                            salvar_debug_em_falha=True):
    """
    pesquisa um produto no buscape e devolve a lista de ofertas
    encontradas, uma por loja, ordenada como o site devolveu.

    levanta ErroScraperBuscape quando a pesquisa nao encontra nenhum
    resultado dentro do tempo limite, o chamador decide se mostra
    esse erro ao usuario ou cai de volta para o cadastro manual.
    """
    url = URL_BUSCA.format(termo=nome_produto.replace(" ", "+"))

    # toda a leitura dos cartoes, inner_text, get_attribute, precisa
    # acontecer enquanto o navegador ainda esta aberto. um erro comum
    # aqui e guardar so os elementos (cartoes) e tentar ler o texto
    # deles depois que o bloco "with sync_playwright()" ja fechou o
    # navegador, isso derruba com "event loop is closed", porque o
    # elemento so existe enquanto a conexao com o navegador esta viva.
    ofertas = []
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
                cartoes = []
            else:
                cartoes = pagina.query_selector_all(SELETOR_CARTAO_RESULTADO)

            for cartao in cartoes[:max_resultados]:
                texto = cartao.inner_text()
                preco = _extrair_preco(texto)
                if preco is None:
                    continue

                link = cartao.query_selector("a")
                url_produto = link.get_attribute("href") if link else ""
                if url_produto and url_produto.startswith("/"):
                    url_produto = f"https://www.buscape.com.br{url_produto}"

                loja = _extrair_loja(texto, url_produto or "")
                preco_pix, preco_cartao, distincao_confiavel = _extrair_precos_pix_cartao(texto, preco)

                ofertas.append(
                    OfertaBuscape(
                        loja=loja,
                        preco=preco,
                        url_produto=url_produto or "",
                        preco_pix=preco_pix,
                        preco_cartao=preco_cartao,
                        distincao_pix_cartao_confiavel=distincao_confiavel,
                    )
                )

            html_pagina = pagina.content()
        except Exception as erro:
            contexto.close()
            navegador.close()
            raise ErroScraperBuscape(
                f"nao foi possivel abrir a busca do buscape para {nome_produto}, detalhe tecnico, {erro}"
            )

        contexto.close()
        navegador.close()

    if not cartoes:
        if salvar_debug_em_falha and html_pagina:
            CAMINHO_DEBUG_HTML.write_text(html_pagina, encoding="utf-8")
        raise ErroScraperBuscape(
            "a busca abriu, mas nenhum resultado apareceu a tempo. isso costuma "
            "acontecer quando o buscape bloqueia o navegador automatizado, muda o "
            "layout, ou o termo pesquisado nao encontrou nada. o html da pagina "
            f"foi salvo em {CAMINHO_DEBUG_HTML} para conferencia, cadastre a "
            "oferta manualmente na calculadora enquanto isso"
        )

    if not ofertas:
        if salvar_debug_em_falha and html_pagina:
            CAMINHO_DEBUG_HTML.write_text(html_pagina, encoding="utf-8")
        raise ErroScraperBuscape(
            "a busca encontrou cartoes de resultado, mas nenhum preco foi "
            "reconhecido dentro deles. o layout provavelmente mudou, revise o "
            "PADRAO_PRECO e o SELETOR_CARTAO_RESULTADO em scrapers/buscape.py, o "
            f"html foi salvo em {CAMINHO_DEBUG_HTML}"
        )

    return ofertas


if __name__ == "__main__":
    resultado = buscar_ofertas_buscape("geladeira electrolux", headless=False)
    print(f"{len(resultado)} ofertas encontradas")
    for oferta in resultado:
        print(oferta)
