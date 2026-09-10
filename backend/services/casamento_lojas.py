"""
modulo de casamento entre nomes de loja.

o buscape mostra o nome comercial completo da loja, por exemplo
"magazine luiza", enquanto a livelo cadastra o parceiro pelo apelido
com que ele e conhecido no mercado, por exemplo "magalu". uma
comparacao por substring sozinha nao resolve esse caso, ja que nenhum
dos dois nomes contem o outro.

este modulo decide se dois nomes se referem a mesma loja em tres
niveis, do mais especifico para o mais generico, parando no primeiro
que bater.

primeiro, grupos de apelidos conhecidos, cadastrados aqui no codigo
em GRUPOS_DE_APELIDOS, cobrindo os casos mais comuns do varejo
brasileiro que uma comparacao de texto sozinha nao resolveria, tipo
"magalu" para "magazine luiza".

segundo, substring nos dois sentidos, apos normalizar acentos,
maiusculas e espacos, o mesmo comportamento simples que ja existia
antes, suficiente para casos como "fast shop" contra "fast shop
oficial".

terceiro, similaridade de texto, usando difflib da biblioteca padrao,
para pegar pequenas variacoes de grafia que nao caem em nenhum dos
dois casos acima, com um limite minimo definido em LIMITE_SIMILARIDADE,
para nao casar lojas diferentes por coincidencia.

quem monta o cadastro de parceiros pode continuar preenchendo o campo
alias com um apelido especifico daquele parceiro, o casamento
considera esse alias como mais um nome candidato, junto do nome
principal. GRUPOS_DE_APELIDOS serve para os casos mais conhecidos do
mercado, que valem para qualquer usuario, sem precisar cadastrar o
alias na mao toda vez.
"""

import unicodedata
from difflib import SequenceMatcher

LIMITE_SIMILARIDADE = 0.82

# grupos de nomes que se referem a mesma loja ou ao mesmo grupo
# varejista, ainda que o nome comercial e o apelido de mercado sejam
# bem diferentes um do outro. cada grupo e uma lista de nomes
# equivalentes, o casamento considera qualquer par de nomes dentro do
# mesmo grupo como a mesma loja, ver _grupo_de_apelidos. esta lista
# cobre os casos mais comuns do varejo online brasileiro, pode crescer
# conforme novos casos aparecerem nas pesquisas
GRUPOS_DE_APELIDOS = [
    ["magalu", "magazine luiza"],
    ["casas bahia", "grupo casas bahia"],
    ["ponto", "ponto frio", "pontofrio"],
    ["extra", "extra.com"],
    ["americanas", "americanas.com", "lojas americanas"],
    ["shoptime", "shop time"],
    ["submarino", "submarino.com"],
    ["kabum", "kabum!"],
    ["fast shop", "fastshop"],
    ["amazon", "amazon.com.br"],
    ["carrefour", "carrefour.com"],
    ["madeiramadeira", "madeira madeira"],
    ["leroy merlin", "leroymerlin"],
]


def normalizar_nome_loja(nome):
    """
    remove acentos, deixa em minusculas e junta espacos repetidos, o
    mesmo tratamento aplicado tanto ao nome cadastrado quanto ao nome
    encontrado na pesquisa, para que a comparacao nao dependa de
    maiusculas, acentuacao ou espacamento.
    """
    forma_normalizada = unicodedata.normalize("NFKD", nome or "")
    sem_acento = "".join(c for c in forma_normalizada if not unicodedata.combining(c))
    return " ".join(sem_acento.strip().lower().split())


def _bate_por_substring(nome_a, nome_b):
    return bool(nome_a) and bool(nome_b) and (nome_a in nome_b or nome_b in nome_a)


def _grupo_de_apelidos(nome_normalizado):
    """
    devolve o grupo de GRUPOS_DE_APELIDOS ao qual o nome normalizado
    pertence, comparando por substring nos dois sentidos contra cada
    apelido do grupo, ja que o nome encontrado na pesquisa pode trazer
    um sufixo extra, tipo "magazine luiza oficial". devolve none
    quando o nome nao pertencer a nenhum grupo cadastrado.
    """
    print(f'{nome_normalizado=}')
    for grupo in GRUPOS_DE_APELIDOS:
        for apelido in grupo:
            if _bate_por_substring(normalizar_nome_loja(apelido), nome_normalizado):
                return grupo
    return None


def nomes_equivalentes(nome_a, nome_b):
    """
    decide se dois nomes de loja se referem ao mesmo lugar, tentando,
    nesta ordem, grupo de apelidos conhecido, substring direto, e por
    ultimo similaridade de texto acima de LIMITE_SIMILARIDADE.

    devolve um booleano simples, sem indicar qual criterio decidiu,
    quem precisar diferenciar o motivo do casamento deve chamar
    _grupo_de_apelidos diretamente.
    """
    normalizado_a = normalizar_nome_loja(nome_a)
    normalizado_b = normalizar_nome_loja(nome_b)

    print(f'{normalizado_a=}')
    print(f'{normalizado_b=}')

    if not normalizado_a or not normalizado_b:
        return False

    if normalizado_a == normalizado_b:
        return True

    grupo_a = _grupo_de_apelidos(normalizado_a)
    print(f'{grupo_a=}')
    if grupo_a is not None:
        for apelido in grupo_a:
            if _bate_por_substring(normalizar_nome_loja(apelido), normalizado_b):
                return True

    if _bate_por_substring(normalizado_a, normalizado_b):
        return True

    similaridade = SequenceMatcher(None, normalizado_a, normalizado_b).ratio()
    return similaridade >= LIMITE_SIMILARIDADE


def encontrar_parceiro_equivalente(nome_loja, parceiros, chave_nome="nome", chave_alias="alias"):
    """
    percorre uma lista de parceiros, tipicamente vinda de
    database.db.listar_parceiros_livelo, e devolve o primeiro cujo
    nome ou alias seja equivalente ao nome da loja informado, segundo
    nomes_equivalentes. devolve none quando nenhum parceiro casar.

    cada parceiro pode ser um dict ou um objeto com atributos, as
    chaves chave_nome e chave_alias indicam onde ler o nome e o alias
    de cada um.
    """
    for parceiro in parceiros:
        if isinstance(parceiro, dict):
            nome = parceiro.get(chave_nome)
            alias = parceiro.get(chave_alias)
        else:
            nome = getattr(parceiro, chave_nome, None)
            alias = getattr(parceiro, chave_alias, None)

        if nome and nomes_equivalentes(nome_loja, nome):
            return parceiro
        if alias and nomes_equivalentes(nome_loja, alias):
            return parceiro

    return None
