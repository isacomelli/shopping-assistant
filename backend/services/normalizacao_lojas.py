"""
modulo de normalizacao, deduplicacao e filtro de qualidade dos resultados de busca de produtos, usado tanto pelo google shopping quanto pelo buscape antes de qualquer oferta chegar ao motor de calculo.

este modulo nao sabe nada sobre livelo, meliuz ou preco efetivo, ele so decide duas coisas, qual e o nome canonico de cada loja, e se um resultado encontrado e realmente o produto pesquisado ou apenas um acessorio, peca de reposicao ou anuncio sem preco, que deveria ser descartado antes de entrar no ranking.
"""

import re
import unicodedata
from dataclasses import dataclass

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

# termos que, quando aparecem no nome do produto encontrado, indicam que o resultado e um acessorio, uma peca de reposicao ou um item incompativel com a pesquisa principal, e nao o produto em si
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


def _remover_acentos(texto):
    forma_normalizada = unicodedata.normalize("NFKD", texto or "")
    return "".join(caractere for caractere in forma_normalizada if not unicodedata.combining(caractere))


def _chave_normalizada(texto):
    sem_acento = _remover_acentos(texto).lower()
    sem_pontuacao = re.sub(r"[^a-z0-9\s]", "", sem_acento)
    return " ".join(sem_pontuacao.split())


def padronizar_nome_loja(nome_loja):
    """
    devolve o nome canonico de uma loja a partir de mapa_normalizacao_lojas, quando a loja nao estiver cadastrada no mapa, devolve o proprio nome recebido, ja com espacos duplicados removidos, para nao quebrar lojas novas que ainda nao entraram na lista
    """
    if not nome_loja:
        return nome_loja
    chave = _chave_normalizada(nome_loja)
    if chave in MAPA_NORMALIZACAO_LOJAS:
        return MAPA_NORMALIZACAO_LOJAS[chave]
    return " ".join(nome_loja.split())


def _tokens_relevantes(texto):
    """
    devolve o conjunto de palavras com mais de dois caracteres do texto informado, ja normalizadas, usado para medir sobreposicao entre o termo pesquisado e o nome de um resultado
    """
    chave = _chave_normalizada(texto)
    return {palavra for palavra in chave.split() if len(palavra) > 2}


def resultado_parece_produto_principal(nome_produto_encontrado, termo_pesquisado, sobreposicao_minima=0.34):
    """
    decide se um resultado encontrado provavelmente e o produto principal pesquisado, e nao um acessorio ou peca de reposicao, combinando dois criterios, a ausencia de termos de TERMOS_RESULTADO_SECUNDARIO no nome do resultado, e uma sobreposicao minima de palavras entre o termo pesquisado e o nome encontrado
    """
    chave_resultado = _chave_normalizada(nome_produto_encontrado)
    if not chave_resultado:
        return False

    for termo_secundario in TERMOS_RESULTADO_SECUNDARIO:
        if termo_secundario in chave_resultado:
            return False

    tokens_pesquisa = _tokens_relevantes(termo_pesquisado)
    if not tokens_pesquisa:
        return True

    tokens_resultado = _tokens_relevantes(nome_produto_encontrado)
    sobreposicao = len(tokens_pesquisa & tokens_resultado) / len(tokens_pesquisa)
    return sobreposicao >= sobreposicao_minima


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
    aplica, nesta ordem, a padronizacao do nome da loja de cada oferta, o filtro de resultados secundarios com base no nome do produto encontrado, e a deduplicacao por url ou por loja mais preco, devolvendo a lista final pronta para seguir para o enriquecimento com livelo e meliuz
    """
    ofertas_filtradas = []
    for oferta in ofertas:
        oferta.loja = padronizar_nome_loja(oferta.loja)
        nome_produto_encontrado = getattr(oferta, "nome_produto", "") or oferta.loja
        if not resultado_parece_produto_principal(nome_produto_encontrado, termo_pesquisado):
            continue
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
