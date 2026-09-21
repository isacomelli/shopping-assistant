import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.normalizacao_lojas import (
    CONFIANCA_BAIXA,
    CONFIANCA_EXATO,
    CONFIANCA_INFORMACAO_EXTRA,
    CONFIANCA_PARCIAL,
    classificar_confianca_nome,
    normalizar_e_filtrar_ofertas,
)


def test_classifica_como_exato_quando_nome_e_termo_sao_identicos():
    assert classificar_confianca_nome("Geladeira Electrolux TF39", "geladeira electrolux tf39") == CONFIANCA_EXATO


def test_classifica_como_exato_ignorando_acentuacao_e_maiusculas():
    assert classificar_confianca_nome("Geladeira Elétrolux", "geladeira eletrolux") == CONFIANCA_EXATO


def test_classifica_como_parcial_quando_so_parte_das_palavras_aparece():
    nome = "Aquecedor Komeco 16 Litros"
    termo = "aquecedor komeco 16 litros gas natural inox"
    assert classificar_confianca_nome(nome, termo) == CONFIANCA_PARCIAL


def test_classifica_como_baixa_quando_pouca_sobreposicao():
    nome = "Suporte para geladeira"
    termo = "aquecedor komeco 16 litros gas natural inox"
    assert classificar_confianca_nome(nome, termo) == CONFIANCA_BAIXA


def test_classifica_como_baixa_quando_titulo_abrevia_as_palavras_do_termo():
    """
    reproduz o kit que antes era descartado pelo filtro de qualidade, o titulo real usa GN e 16L em vez de gas natural e litros, e nao menciona inox, entao a sobreposicao fica abaixo do limite de confianca parcial, o resultado correto aqui e baixa, nao informacao_extra
    """
    nome = "Kit Aquecedor Komeco KO16BKDECOR 16L GN + Acess. Ligação"
    termo = "aquecedor komeco 16 litros gas natural inox"
    assert classificar_confianca_nome(nome, termo) == CONFIANCA_BAIXA


def test_classifica_como_informacao_extra_quando_todas_as_palavras_do_termo_aparecem():
    nome = "Geladeira Electrolux TF39 Frost Free Inox 400 Litros"
    termo = "geladeira electrolux tf39"
    assert classificar_confianca_nome(nome, termo) == CONFIANCA_INFORMACAO_EXTRA


def test_normalizar_e_filtrar_ofertas_nao_descarta_mais_por_nome_parcial():
    class OfertaFalsa:
        def __init__(self, loja, preco, nome_produto):
            self.loja = loja
            self.preco = preco
            self.nome_produto = nome_produto
            self.url_produto = ""

    ofertas = [
        OfertaFalsa("Magazine Luiza", 1941.04, "Kit Aquecedor Komeco KO16BKDECOR 16L GN + Acess. Ligação"),
    ]
    resultado = normalizar_e_filtrar_ofertas(ofertas, "aquecedor komeco 16 litros gas natural inox")
    assert len(resultado) == 1
    assert resultado[0].confianca_nome == CONFIANCA_BAIXA


def test_normalizar_e_filtrar_ofertas_ainda_descarta_acessorio_e_peca_de_reposicao():
    class OfertaFalsa:
        def __init__(self, loja, preco, nome_produto):
            self.loja = loja
            self.preco = preco
            self.nome_produto = nome_produto
            self.url_produto = ""

    ofertas = [
        OfertaFalsa("Loja X", 89.9, "Suporte para aquecedor Komeco 16 litros"),
    ]
    resultado = normalizar_e_filtrar_ofertas(ofertas, "aquecedor komeco 16 litros gas natural inox")
    assert resultado == []
