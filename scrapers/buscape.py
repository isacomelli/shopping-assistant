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

sobre a busca em dois guias de navegador, este scraper roda a
mesma pesquisa duas vezes, uma pelo guia normal, com um perfil
salvo em disco ao lado deste arquivo, acumulando cookies entre
execucoes, parecido com uma aba comum do navegador que a pessoa usa
no dia a dia, e outra pelo guia anonimo, aberto do zero em
memoria, sem nenhum cookie previo, parecido com uma aba anonima de
verdade. o motivo, o buscape pode responder de um jeito diferente,
com mais ou menos bloqueio, dependendo do historico do navegador, e
rodar os dois da mais chance de reunir um conjunto completo de
ofertas. no fim, as duas listas sao unidas e as duplicatas removidas.

sobre a paginacao, cada guia percorre ate um numero maximo de
paginas de resultado, MAX_PAGINAS_BUSCA_PADRAO por padrao, clicando
no controle de proxima pagina enquanto ele existir, e parando quando
o controle sumir ou o limite for atingido.

sobre os dois estilos de pagina de busca do buscape, existem produtos
com um estilo "lojas", tipo uma busca por um aquecedor generico, onde
cada cartao de resultado ja e uma oferta pronta, com o nome da loja,
o preco e o parcelamento visiveis direto na busca. existem tambem
produtos com um estilo "modelos", tipo uma busca por "iphone 17",
onde cada cartao de resultado representa uma variacao do produto, sem
loja nem parcelamento proprios, e clicar nesse cartao leva para uma
pagina propria daquele modelo especifico, com o comparativo de lojas
de verdade. nessa pagina propria, a lista de ofertas por loja pode
carregar aos poucos, atras de um botao de "ver mais ofertas", que
precisa ser clicado repetidas vezes ate carregar tudo, a nao ser que
o html ja traga a lista inteira de uma vez, caso em que o botao nem
aparece. este scraper detecta automaticamente qual dos dois estilos
a busca caiu, e trata cada um do jeito certo.

sobre a distincao entre pix e cartao, a regra agora e mais simples do
que antes. quando o cartao de resultado nao traz nenhum parcelamento
reconhecivel, o unico dado confiavel e o preco anunciado, entao o
valor de pix e o valor de cartao ficam zerados, e a distincao fica
marcada como nao confiavel, confianca_pix_cartao False, sinal para
quem usa este scraper de que o preco em si, campo preco, e o unico
numero que pode ser usado, por exemplo cadastrando a oferta manual
com esse valor. quando o cartao de resultado traz um parcelamento
reconhecivel, tipo "10x de R$ 165,70", o preco anunciado vira o valor
de pix, e o total das parcelas, parcelas vezes valor de cada parcela,
vira o valor de cartao, sem nenhuma comparacao entre os dois nem
suposicao de qual e maior, e a distincao fica marcada como confiavel,
confianca_pix_cartao True. todo valor monetario deste modulo e
sempre arredondado para 2 casas decimais.

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

# pasta usada pelo guia normal do playwright, para persistir
# cookies e armazenamento entre execucoes, parecido com uma aba comum
# do navegador que a pessoa usa no dia a dia. o guia anonimo nao
# usa essa pasta, ele abre um guia novo em memoria a cada
# execucao, sem nenhum cookie salvo antes, parecido com uma aba
# anonima de verdade, e tudo que ele acumular e descartado ao fechar
PASTA_PERFIL_NORMAL = Path(__file__).parent / "perfil_navegador_buscape"

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

# estilo lojas, cada cartao de resultado ja e uma oferta com preco e
# loja proprios. estes seletores usam data-testid e data-area,
# atributos estaveis colocados pelo proprio buscape para identificar
# cada pedaco do cartao, em vez de classes css com hash, que mudam a
# cada deploy do site
SELETOR_CARTAO_RESULTADO = '[data-testid="product-card"]'
SELETOR_NOME_PRODUTO = '[data-testid="product-card::name"]'
SELETOR_PRECO_PRINCIPAL = '[data-testid="product-card::price"]'
SELETOR_LOJA = '[data-area="merchant"] span'
SELETOR_LINK_PRODUTO = 'a[data-testid="product-card::card"]'
SELETOR_PARCELAMENTO = '[data-testid="product-card::installment"] span'
SELETOR_JUROS_PARCELAMENTO = '[data-testid="product-card::interest"]'

# estilo modelos, cada cartao de resultado representa uma variacao de
# produto, tipo cada modelo de iphone, e leva para uma pagina propria
# daquele modelo, com o comparativo de lojas de verdade. o link usado
# para navegar ate essa pagina e o mesmo seletor de link do estilo
# lojas, ja que os dois estilos reaproveitam o mesmo componente de
# cartao, so muda o que tem dentro dele
SELETOR_LINK_MODELO = SELETOR_LINK_PRODUTO

# na pagina propria de um modelo, o comparativo de lojas tende a
# reaproveitar o mesmo componente de cartao usado na busca no estilo
# lojas, entao por padrao a extracao de ofertas dessa pagina usa os
# mesmos seletores de SELETOR_CARTAO_RESULTADO. se o buscape usar um
# componente diferente nessa pagina propria, ajuste esta constante
SELETOR_CARTAO_OFERTA_DETALHE = SELETOR_CARTAO_RESULTADO

# botao de ver mais ofertas na pagina propria de um modelo, chute
# inicial, caso o buscape mude o texto ou o layout deste botao,
# ajuste aqui, o html da pagina de detalhe tambem fica salvo em
# debug_buscape.html quando a extracao falhar por completo
SELETORES_BOTAO_VER_MAIS_OFERTAS = [
    "button:has-text('Ver mais ofertas')",
    "button:has-text('ver mais ofertas')",
    "button:has-text('Ver todas as ofertas')",
    "a:has-text('Ver mais ofertas')",
]

# controle de proxima pagina dos resultados de busca, chute inicial,
# caso o buscape mude o controle de paginacao, ajuste aqui
SELETORES_PROXIMA_PAGINA = [
    "a[aria-label='Próxima página']",
    "a[aria-label='Proxima pagina']",
    "button[aria-label='Próxima página']",
    "button[aria-label='Proxima pagina']",
    "a:has-text('Próxima')",
    "a:has-text('Proxima')",
    "button:has-text('Próxima')",
    "button:has-text('Proxima')",
    "a[rel='next']",
]

PADRAO_PRECO = re.compile(r"R\$\s*([\d.]+,\d{2})")
PADRAO_PARCELAMENTO = re.compile(r"(\d+)\s*x\s*de\s*R\$\s*([\d.]+,\d{2})", re.IGNORECASE)

MAX_PAGINAS_BUSCA_PADRAO = 5
MAX_CLIQUES_VER_MAIS_OFERTAS = 20


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

    # preco no pix e no cartao, seguindo a regra descrita no topo
    # deste arquivo. confianca_pix_cartao fica True somente quando o
    # scraper reconheceu um parcelamento no cartao de resultado, e
    # False quando so o preco anunciado foi encontrado, caso em que
    # preco_pix e preco_cartao ficam zerados de proposito
    preco_pix: float = 0.0
    preco_cartao: float = 0.0
    confianca_pix_cartao: bool = False

    # parcelamento anunciado no cartao de resultado, quando houver.
    # parcelas fica em 1 quando o cartao nao anuncia nenhum
    # parcelamento, o que nao quer dizer que a loja so aceita a vista
    parcelas: int = 1
    valor_parcela: float = 0.0
    parcelas_sem_juros: bool = False

    # so para depuracao, marca se esta oferta veio da aba normal ou
    # da aba anonima, nao muda nenhum calculo
    guia: str = ""

    def __post_init__(self):
        # todo valor monetario deste modulo fica sempre com 2 casas
        # decimais, para nao aparecer numero tipo 1999.999999999998
        # em nenhuma tela
        self.preco = round(float(self.preco), 2)
        self.preco_pix = round(float(self.preco_pix), 2)
        self.preco_cartao = round(float(self.preco_cartao), 2)
        self.valor_parcela = round(float(self.valor_parcela), 2)


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
    sinal para quem chama de que o parcelamento e desconhecido.
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
    a partir do preco anunciado e do parcelamento reconhecido no
    cartao de resultado, decide os valores de pix e de cartao.

    sem nenhum parcelamento reconhecido, parcelas 1 ou valor_parcela
    zerado, o unico dado confiavel e o preco anunciado, entao pix e
    cartao ficam zerados, e a distincao fica marcada como nao
    confiavel, quem usa este scraper deve usar o campo preco puro
    nesse caso, por exemplo cadastrando a oferta manual com esse
    valor.

    com parcelamento reconhecido, o preco anunciado vira o valor de
    pix, e o total das parcelas, parcelas vezes valor de cada
    parcela, vira o valor de cartao, sem nenhuma comparacao entre os
    dois nem suposicao de qual e maior, e a distincao fica marcada
    como confiavel.
    """
    if parcelas <= 1 or valor_parcela <= 0:
        return 0.0, 0.0, False

    preco_pix = round(preco, 2)
    preco_cartao = round(parcelas * valor_parcela, 2)
    return preco_pix, preco_cartao, True


def _extrair_oferta_do_cartao(cartao, guia=""):
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
        guia=guia,
    )


def _detectar_estilo_pagina(soup):
    """
    decide se uma pagina de busca do buscape esta no estilo lojas,
    onde cada cartao de resultado ja e uma oferta com preco e loja
    proprios, tipo uma busca por um aquecedor generico, ou no estilo
    modelos, onde cada cartao representa uma variacao de produto,
    tipo cada modelo de iphone, sem loja nem parcelamento proprios, e
    clicar em cada cartao leva para uma pagina propria daquele
    modelo especifico.

    a heuristica usada, um cartao no estilo lojas sempre tem o nome
    da loja no seletor SELETOR_LOJA, um cartao no estilo modelos nao
    tem esse dado, so o preco a partir de e o link para a pagina
    propria do modelo.
    """
    cartoes = soup.select(SELETOR_CARTAO_RESULTADO)
    if not cartoes:
        return "vazio"

    algum_cartao_tem_loja = any(cartao.select_one(SELETOR_LOJA) for cartao in cartoes)
    if algum_cartao_tem_loja:
        return "lojas"

    return "modelos"


def _extrair_links_modelo(soup):
    """
    a partir de uma pagina de busca no estilo modelos, coleta o link
    e o nome de cada variacao de produto encontrada, tipo cada modelo
    de iphone, para depois abrir a pagina propria de cada um e
    coletar as ofertas de verdade por loja.
    """
    links = []
    for cartao in soup.select(SELETOR_CARTAO_RESULTADO):
        link = cartao.select_one(SELETOR_LINK_MODELO)
        if not link:
            continue
        href = link.get("href", "")
        if href.startswith("/"):
            href = f"{URL_BASE}{href}"
        nome = _texto_do_seletor(cartao, SELETOR_NOME_PRODUTO)
        if href:
            links.append((href, nome))
    return links


def _ir_para_proxima_pagina(pagina, timeout_ms):
    """
    tenta clicar no controle de proxima pagina dos resultados de
    busca, devolve True quando conseguiu clicar em algo, False quando
    nenhum dos seletores conhecidos foi encontrado, sinal de que a
    busca chegou na ultima pagina, ou de que o buscape mudou o
    controle de paginacao, o que precisaria de ajuste manual aqui.
    """
    for seletor in SELETORES_PROXIMA_PAGINA:
        try:
            botao = pagina.locator(seletor).first
            if botao.is_visible(timeout=1500) and botao.is_enabled():
                botao.click(timeout=3000)
                pagina.wait_for_timeout(1500)
                return True
        except Exception:
            continue
    return False


def _clicar_ver_mais_ofertas_ate_completar(pagina, max_cliques=MAX_CLIQUES_VER_MAIS_OFERTAS):
    """
    na pagina propria de um modelo, tipo um iphone 17 pro max em
    particular, a lista de ofertas por loja pode carregar aos poucos,
    atras de um botao de ver mais ofertas. esta funcao clica nesse
    botao repetidas vezes, ate ele sumir da tela, parar de responder,
    ou ate o limite de max_cliques ser atingido, o que evita um loop
    infinito caso o botao nunca desapareca por algum bug da pagina.

    quando o html ja trouxer todas as ofertas de uma vez, sem nenhum
    botao de ver mais, esta funcao simplesmente nao encontra nada
    para clicar e devolve na hora, sem erro.
    """
    cliques = 0
    while cliques < max_cliques:
        clicou = False
        for seletor in SELETORES_BOTAO_VER_MAIS_OFERTAS:
            try:
                botao = pagina.locator(seletor).first
                if botao.is_visible(timeout=1200):
                    botao.click(timeout=3000)
                    pagina.wait_for_timeout(1200)
                    clicou = True
                    cliques += 1
                    break
            except Exception:
                continue
        if not clicou:
            break


def _coletar_ofertas_da_pagina_modelo(pagina, url_modelo, nome_modelo, timeout_ms, guia):
    """
    abre a pagina propria de um modelo especifico, clica no botao de
    ver mais ofertas ate carregar tudo, e devolve a lista de ofertas
    por loja encontradas nessa pagina.
    """
    pagina.goto(url_modelo, timeout=timeout_ms, wait_until="domcontentloaded")
    _fechar_banner_cookies(pagina)
    pagina.wait_for_timeout(1500)
    _clicar_ver_mais_ofertas_ate_completar(pagina)

    html_pagina = pagina.content()
    soup = BeautifulSoup(html_pagina, "html.parser")
    cartoes = soup.select(SELETOR_CARTAO_OFERTA_DETALHE)

    ofertas = []
    for cartao in cartoes:
        oferta = _extrair_oferta_do_cartao(cartao, guia=guia)
        if oferta:
            if not oferta.nome_produto:
                oferta.nome_produto = nome_modelo
            ofertas.append(oferta)
    return ofertas, html_pagina


def _abrir_navegador_e_guia(playwright, headless, usar_perfil_persistente):
    """
    abre o navegador e devolve o guia certo, dependendo do modo
    pedido. o guia normal usa um perfil salvo em disco, ao lado
    deste arquivo, acumulando cookies entre execucoes, parecido com
    uma aba comum do navegador. o guia anonimo abre em memoria,
    sem nenhum cookie salvo antes, parecido com uma aba anonima de
    verdade, e tudo que ele acumular e descartado ao fechar.

    devolve a tupla, navegador ou None quando o guia for
    persistente, e o proprio guia, ja que o playwright expoe um
    guia persistente sem precisar de um objeto de navegador
    separado.
    """
    if usar_perfil_persistente:
        PASTA_PERFIL_NORMAL.mkdir(exist_ok=True)
        guia = playwright.chromium.launch_persistent_context(
            str(PASTA_PERFIL_NORMAL),
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
            user_agent=USER_AGENT,
            locale="pt-BR",
            viewport={"width": 1366, "height": 900},
        )
        return None, guia

    navegador = playwright.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
    guia = navegador.new_context(
        user_agent=USER_AGENT,
        locale="pt-BR",
        viewport={"width": 1366, "height": 900},
    )
    return navegador, guia


def _coletar_ofertas_em_guia(playwright, termo, headless, timeout_ms, max_paginas,
                                  nome_guia, usar_perfil_persistente):
    """
    executa a busca completa dentro de um unico guia de
    navegador, normal ou anonimo, incluindo a paginacao dos
    resultados de busca, e, quando o estilo da pagina for modelos, a
    visita em cada pagina propria de modelo com o clique repetido em
    ver mais ofertas.

    devolve a tupla, lista de OfertaBuscape encontradas, html da
    primeira pagina de busca, usado so para salvar em disco e ajudar
    a depurar quando algo der errado.
    """
    navegador, guia = _abrir_navegador_e_guia(playwright, headless, usar_perfil_persistente)
    guia.add_init_script(SCRIPT_ANTI_DETECCAO)
    pagina = guia.new_page()

    url = URL_BUSCA.format(termo=termo.replace(" ", "+"))
    ofertas_coletadas = []
    html_primeira_pagina = ""

    try:
        pagina.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        _fechar_banner_cookies(pagina)
        pagina.wait_for_timeout(1500)

        try:
            pagina.wait_for_selector(SELETOR_CARTAO_RESULTADO, timeout=timeout_ms, state="attached")
        except Exception:
            pass

        html_primeira_pagina = pagina.content()
        soup = BeautifulSoup(html_primeira_pagina, "html.parser")
        estilo = _detectar_estilo_pagina(soup)

        if estilo == "vazio":
            return [], html_primeira_pagina

        if estilo == "lojas":
            pagina_atual = 1
            while True:
                html_atual = pagina.content()
                soup_atual = BeautifulSoup(html_atual, "html.parser")
                for cartao in soup_atual.select(SELETOR_CARTAO_RESULTADO):
                    oferta = _extrair_oferta_do_cartao(cartao, guia=nome_guia)
                    if oferta:
                        ofertas_coletadas.append(oferta)

                if pagina_atual >= max_paginas:
                    break
                if not _ir_para_proxima_pagina(pagina, timeout_ms):
                    break
                pagina_atual += 1

        else:
            links_modelo = []
            pagina_atual = 1
            while True:
                html_atual = pagina.content()
                soup_atual = BeautifulSoup(html_atual, "html.parser")
                links_modelo.extend(_extrair_links_modelo(soup_atual))

                if pagina_atual >= max_paginas:
                    break
                if not _ir_para_proxima_pagina(pagina, timeout_ms):
                    break
                pagina_atual += 1

            urls_ja_visitadas = set()
            for url_modelo, nome_modelo in links_modelo:
                if url_modelo in urls_ja_visitadas:
                    continue
                urls_ja_visitadas.add(url_modelo)
                try:
                    ofertas_modelo, _ = _coletar_ofertas_da_pagina_modelo(
                        pagina, url_modelo, nome_modelo, timeout_ms, nome_guia,
                    )
                    ofertas_coletadas.extend(ofertas_modelo)
                except Exception:
                    continue
    finally:
        guia.close()
        if navegador:
            navegador.close()

    return ofertas_coletadas, html_primeira_pagina


def _normalizar_texto(texto):
    return " ".join((texto or "").strip().lower().split())


def _chave_deduplicacao(oferta):
    """
    monta uma chave para identificar se duas ofertas coletadas,
    possivelmente uma pela aba normal e outra pela aba anonima, ou
    uma pela pagina 1 e outra repetida na pagina 2, representam a
    mesma oferta de verdade. usa o link do produto quando disponivel,
    ja que e o dado mais especifico, e cai para loja mais preco mais
    nome do produto quando o link nao existir.
    """
    if oferta.url_produto:
        return oferta.url_produto
    return f"{_normalizar_texto(oferta.loja)}|{oferta.preco:.2f}|{_normalizar_texto(oferta.nome_produto)}"


def _unir_ofertas(*listas_de_ofertas):
    """
    junta as listas de ofertas vindas de cada guia, aba normal e
    aba anonima, removendo duplicatas pela chave de deduplicacao,
    mantendo a primeira ocorrencia encontrada.
    """
    vistas = set()
    ofertas_unicas = []
    for lista in listas_de_ofertas:
        for oferta in lista:
            chave = _chave_deduplicacao(oferta)
            if chave in vistas:
                continue
            vistas.add(chave)
            ofertas_unicas.append(oferta)
    return ofertas_unicas


def parsear_html_buscape(html):
    """
    extrai a lista de ofertas a partir do html bruto de uma unica
    pagina de busca do buscape, sem depender do playwright nem de
    rede, util tanto para ajustar os seletores quanto para
    reprocessar uma busca antiga sem consultar o site de novo, veja
    debug_scraper.py, opcao --reparsear.

    funciona direto para paginas no estilo lojas, onde o proprio
    cartao de busca ja e uma oferta. para paginas no estilo modelos,
    tipo iphone 17, este html sozinho nao basta, porque as ofertas de
    verdade ficam na pagina propria de cada modelo, que so pode ser
    visitada com o navegador, entao a funcao devolve os cartoes
    encontrados e uma lista vazia de ofertas, use
    buscar_ofertas_buscape para o fluxo completo desse estilo.

    devolve a tupla, lista de cartoes encontrados pelo
    SELETOR_CARTAO_RESULTADO, lista de OfertaBuscape com preco
    reconhecido.
    """
    soup = BeautifulSoup(html, "html.parser")
    cartoes = soup.select(SELETOR_CARTAO_RESULTADO)

    if not cartoes:
        return cartoes, []

    estilo = _detectar_estilo_pagina(soup)
    if estilo == "modelos":
        return cartoes, []

    ofertas = []
    for cartao in cartoes:
        oferta = _extrair_oferta_do_cartao(cartao)
        if oferta:
            ofertas.append(oferta)

    return cartoes, ofertas


def buscar_ofertas_buscape(nome_produto, max_resultados=1000, timeout_ms=45000, headless=True,
                            salvar_debug_em_falha=True, max_paginas=MAX_PAGINAS_BUSCA_PADRAO):
    """
    pesquisa um produto no buscape e devolve a lista unificada de
    ofertas encontradas, combinando duas passagens de busca, uma pelo
    guia normal, com perfil salvo em disco, e outra pelo guia
    anonimo, sem nenhum cookie previo. dentro de cada guia,
    percorre ate max_paginas paginas de resultado, e, quando o
    produto pesquisado usar o estilo de pagina modelos, tipo iphone
    17, visita a pagina propria de cada modelo encontrado e clica em
    ver mais ofertas ate carregar a lista completa daquele modelo.

    levanta ErroScraperBuscape quando nenhuma das duas passagens
    encontrar nenhuma oferta, dentro do tempo limite. o chamador
    decide se mostra esse erro ao usuario ou cai de volta para o
    cadastro manual.
    """
    with sync_playwright() as playwright:
        try:
            ofertas_normal, html_normal = _coletar_ofertas_em_guia(
                playwright, nome_produto, headless, timeout_ms, max_paginas,
                nome_guia="normal", usar_perfil_persistente=True,
            )
        except Exception as erro:
            raise ErroScraperBuscape(
                f"nao foi possivel abrir a busca do buscape na aba normal para "
                f"{nome_produto}, detalhe tecnico, {erro}"
            )

        try:
            ofertas_anonimo, html_anonimo = _coletar_ofertas_em_guia(
                playwright, nome_produto, headless, timeout_ms, max_paginas,
                nome_guia="anonimo", usar_perfil_persistente=False,
            )
        except Exception as erro:
            raise ErroScraperBuscape(
                f"nao foi possivel abrir a busca do buscape na aba anonima para "
                f"{nome_produto}, detalhe tecnico, {erro}"
            )

    html_para_debug = html_normal or html_anonimo
    if html_para_debug:
        CAMINHO_ULTIMO_HTML.write_text(html_para_debug, encoding="utf-8")

    ofertas = _unir_ofertas(ofertas_normal, ofertas_anonimo)

    if not ofertas:
        if salvar_debug_em_falha and html_para_debug:
            CAMINHO_DEBUG_HTML.write_text(html_para_debug, encoding="utf-8")
        raise ErroScraperBuscape(
            "a busca abriu tanto na aba normal quanto na aba anonima, mas "
            "nenhuma oferta foi reconhecida em nenhuma das duas, nem no "
            "estilo lojas nem no estilo modelos. isso costuma acontecer "
            "quando o buscape bloqueia o navegador automatizado ou muda o "
            f"layout. o html da primeira pagina foi salvo em {CAMINHO_ULTIMO_HTML}, "
            "abra esse arquivo, inspecione um cartao de produto e ajuste os "
            "seletores em scrapers/buscape.py. cadastre a oferta manualmente "
            "na calculadora enquanto isso"
        )

    return ofertas[:max_resultados]


if __name__ == "__main__":
    resultado = buscar_ofertas_buscape("geladeira electrolux", headless=False)
    print(f"{len(resultado)} ofertas encontradas")
    for oferta in resultado:
        print(oferta)