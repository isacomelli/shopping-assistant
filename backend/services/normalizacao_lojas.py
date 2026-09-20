"""
modulo de normalizacao, deduplicacao e classificacao de confianca dos resultados de busca de produtos, usado tanto pelo google shopping quanto pelo buscape antes de qualquer oferta chegar ao motor de calculo.

este modulo nao sabe nada sobre livelo, meliuz ou preco efetivo, ele so decide tres coisas, qual e o nome canonico de cada loja, se um resultado encontrado e claramente outra coisa, tipo um acessorio, peca de reposicao ou item usado, que deveria ser descartado antes de entrar no ranking, e o quanto o nome do produto encontrado bate com o termo pesquisado, para o restante do aplicativo poder mostrar essa confianca em vez de simplesmente esconder a oferta.
"""

import re
import unicodedata

# mapa de normalizacao, a chave e qualquer variacao do nome como ela pode aparecer no google shopping ou no buscape, ja normalizada por _chave_normalizada, o valor e o nome canonico que o restante do aplicativo deve usar, inclusive no casamento com parceiros livelo em services/casamento_lojas.py
MAPA_NORMALIZACAO_LOJAS = {
    "magalu": "Magazine Luiza",
    "magazine luiza": "Magazine Luiza",
    "casasbahia": "Casas Bahia",
    "casas bahia": "Casas Bahia",
    "mercadolivre": "Mercado Livre",
    "mercado livre": "Mercado Livre",
    "ml": "Mercado Livre",
    "amazon": "Amazon",
    "amazon.com.br": "Amazon",
    "amazon brasil": "Amazon",
    "ponto": "Ponto",
    "pontofrio": "Ponto",
    "ponto frio": "Ponto",
    "fastshop": "Fast Shop",
    "fast shop": "Fast Shop",
    "leroymerlin": "Leroy Merlin",
    "leroy merlin": "Leroy Merlin",
    "shopee": "Shopee",
    "aliexpress": "AliExpress",
    "shein": "Shein",
    "kabum": "Kabum",
    "kabum!": "Kabum",
    "carrefour": "Carrefour",
    "extra": "Extra",
    "samsclub": "Sams Club",
    "sams club": "Sams Club",
    "paodeacucar": "Pão de Açúcar",
    "pao de acucar": "Pão de Açúcar",
    "bemol": "Bemol",
    "madeiramadeira": "MadeiraMadeira",
    "madeira madeira": "MadeiraMadeira",
    "mobly": "Mobly",
    "tokstok": "Tok&Stok",
    "tok stok": "Tok&Stok",
    "tok&stok": "Tok&Stok",
    "hm": "H&M",
    "h&m": "H&M",
    "hm home": "H&M Home",
    "h&m home": "H&M Home",
    "zara": "Zara",
    "zara home": "Zara Home",
    "riachuelo": "Riachuelo",
    "riachuelo home": "Riachuelo Home",
    "westwing": "Westwing",
    "camicado": "Camicado",
    "tramontina": "Tramontina",
    "electrolux": "Electrolux",
    "brastemp": "Brastemp",
    "consul": "Consul",
    "samsung": "Samsung",
    "lg": "LG",
    "dell": "Dell",
    "oster": "Oster",
    "philips": "Philips",
    "britania": "Britânia",
    "mondial": "Mondial",
}

# termos que, quando aparecem no nome do produto encontrado, indicam que o resultado e claramente outra coisa, um acessorio, uma peca de reposicao ou um item incompativel com a pesquisa principal, e nao o produto pesquisado com informacao a mais. este e o unico descarte de vez que este modulo ainda faz, tudo o resto vira classificacao de confianca em vez de remocao
TERMOS_RESULTADO_SECUNDARIO = [
    "filtro de agua",
    "filtro para",
    "puxador",
    "compressor",
    "prateleira",
    "peca de reposicao",
    "peca original",
    "reposicao",
    "acessorio",
    "acessorios",
    "capa para",
    "suporte para",
    "adaptador",
    "mangueira",
    "correia",
    "resistencia para",
    "valvula",
    "usado",
    "seminovo",
    "semi novo",
    "recondicionado",
    "sucata",
    "para retirada de pecas",
]

# sobreposicao minima de palavras em relacao ao termo pesquisado para uma oferta ainda entrar com confianca "parcial", abaixo disso a sobreposicao vira confianca "baixa". nenhum dos dois casos e descartado, so classificado
SOBREPOSICAO_MINIMA_PARCIAL = 0.34

CONFIANCA_EXATO = "exato"
CONFIANCA_INFORMACAO_EXTRA = "informacao_extra"
CONFIANCA_PARCIAL = "parcial"
CONFIANCA_BAIXA = "baixa"


def _remover_acentos(texto):
    forma_normalizada = unicodedata.normalize("NFKD", texto or "")
    return "".join(caractere for caractere in forma_normalizada if not unicodedata.combining(caractere))


def _chave_normalizada(texto):
    sem_acento = _remover_acentos(texto).lower()
    sem_pontuacao = re.sub(r"[^a-z0-9\s]", "", sem_acento)
    return " ".join(sem_pontuacao.split())


def padronizar_nome_loja(nome_loja):
    """
    devolve o nome canonico de uma loja a partir de MAPA_NORMALIZACAO_LOJAS, quando a loja nao estiver cadastrada no mapa, devolve o proprio nome recebido, ja com espacos duplicados removidos, para nao quebrar lojas novas que ainda nao entraram na lista
    """
    if not nome_loja:
        return nome_loja
    chave = _chave_normalizada(nome_loja)
    if chave in MAPA_NORMALIZACAO_LOJAS:
        return MAPA_NORMALIZACAO_LOJAS[chave]
    return " ".join(nome_loja.split())


def _tokens_relevantes(texto):
    """
    devolve o conjunto de palavras com mais de dois caracteres do texto informado, ja normalizadas, usado tanto para medir sobreposicao entre o termo pesquisado e o nome de um resultado quanto para decidir se o nome traz informacao extra
    """
    chave = _chave_normalizada(texto)
    return {palavra for palavra in chave.split() if len(palavra) > 2}


def _e_resultado_secundario(nome_produto_encontrado):
    """
    decide se um nome de produto encontrado e claramente outra coisa, e nao o produto pesquisado com informacao a mais, comparando contra TERMOS_RESULTADO_SECUNDARIO. diferente da classificacao de confianca abaixo, isto continua descartando o resultado de vez, ja que um acessorio, uma peca de reposicao ou um item usado nao e o mesmo produto, so um resultado relacionado
    """
    chave_resultado = _chave_normalizada(nome_produto_encontrado)
    if not chave_resultado:
        return True
    return any(termo_secundario in chave_resultado for termo_secundario in TERMOS_RESULTADO_SECUNDARIO)


def classificar_confianca_nome(nome_produto_encontrado, termo_pesquisado, sobreposicao_minima=SOBREPOSICAO_MINIMA_PARCIAL):
    """
    classifica o quanto o nome do produto encontrado bate com o termo pesquisado, em vez de decidir sozinho se a oferta entra ou nao no ranking. a comparacao ignora maiuscula, minuscula, acento, hifen e pontuacao, atraves de _chave_normalizada, entao "KO-16DI" e "ko 16 di" contam como o mesmo texto.

    CONFIANCA_EXATO, o nome normalizado e identico ao termo pesquisado normalizado.
    CONFIANCA_INFORMACAO_EXTRA, todas as palavras do termo pesquisado aparecem no nome encontrado, so que o nome traz palavras a mais, o caso mais comum sendo um kit com acessorio de ligacao junto, tipo "... + Acess. Ligação".
    CONFIANCA_PARCIAL, so parte das palavras do termo aparecem no nome, o suficiente para passar de sobreposicao_minima. cai aqui tanto um nome abreviado, tipo "GN" em vez de "gas natural", quanto uma variacao de modelo proxima, este modulo nao distingue os dois casos.
    CONFIANCA_BAIXA, pouca ou nenhuma sobreposicao de palavras com o termo pesquisado. mesmo assim a oferta nao e descartada aqui, quem decide o que fazer com uma confianca baixa e a camada de cima, tipicamente a tela.
    """
    chave_termo = _chave_normalizada(termo_pesquisado)
    chave_nome = _chave_normalizada(nome_produto_encontrado)

    if not chave_nome:
        return CONFIANCA_BAIXA
    if not chave_termo or chave_nome == chave_termo:
        return CONFIANCA_EXATO

    tokens_termo = _tokens_relevantes(termo_pesquisado)
    tokens_nome = _tokens_relevantes(nome_produto_encontrado)

    if tokens_termo and tokens_termo.issubset(tokens_nome):
        return CONFIANCA_INFORMACAO_EXTRA

    if not tokens_termo:
        return CONFIANCA_EXATO

    sobreposicao = len(tokens_termo & tokens_nome) / len(tokens_termo)
    if sobreposicao >= sobreposicao_minima:
        return CONFIANCA_PARCIAL

    return CONFIANCA_BAIXA


def _chave_deduplicacao(oferta):
    """
    monta a chave de deduplicacao de uma oferta, priorizando a url do produto, quando disponivel, e caindo para loja padronizada mais preco quando a url nao existir
    """
    url_produto = getattr(oferta, "url_produto", "") or ""
    if url_produto:
        return url_produto
    loja_padronizada = padronizar_nome_loja(getattr(oferta, "loja", ""))
    preco = getattr(oferta, "preco", 0.0)
    return f"{_chave_normalizada(loja_padronizada)}|{preco:.2f}"


def normalizar_e_filtrar_ofertas(ofertas, termo_pesquisado):
    """
    aplica, nesta ordem, a padronizacao do nome da loja de cada oferta, o descarte dos resultados claramente secundarios, tipo acessorio ou peca de reposicao, a classificacao de confianca do nome contra o termo pesquisado, gravada na propria oferta em oferta.confianca_nome, e por ultimo a deduplicacao por url ou por loja mais preco.

    nenhuma oferta e mais descartada so por o nome nao bater 100% com o termo pesquisado, ela entra no ranking do mesmo jeito, so que marcada com a confianca calculada, quem decide o que fazer com uma confianca baixa e a camada de cima
    """
    ofertas_filtradas = []
    for oferta in ofertas:
        oferta.loja = padronizar_nome_loja(oferta.loja)
        nome_produto_encontrado = getattr(oferta, "nome_produto", "") or oferta.loja
        if _e_resultado_secundario(nome_produto_encontrado):
            continue
        oferta.confianca_nome = classificar_confianca_nome(nome_produto_encontrado, termo_pesquisado)
        ofertas_filtradas.append(oferta)

    vistas = set()
    ofertas_unicas = []
    for oferta in ofertas_filtradas:
        chave = _chave_deduplicacao(oferta)
        if chave in vistas:
            continue
        vistas.add(chave)
        ofertas_unicas.append(oferta)

    return ofertas_unicas