import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import db
from services import pesquisa_produto
from services.pesquisa_produto import (
    montar_oferta_a_partir_do_buscape,
    pesquisar_produto_automaticamente,
)


@dataclass
class OfertaBuscapeFalsa:
    loja: str
    preco: float
    preco_pix: float
    preco_cartao: float
    confianca_pix_cartao: bool = False
    parcelas: int = 0
    url_produto: str = ""


PARCEIROS_FALSOS = [
    {"nome": "Amazon", "alias": "Amazon", "pontos_padrao": 10.0},
    {"nome": "Fast Shop Oficial", "alias": "Fast Shop", "pontos_padrao": 6.0},
]


def _parceiro_falso_por_nome(nome_loja):
    """
    reproduz a busca por substring feita por
    db.buscar_parceiro_livelo_por_nome, sem depender do banco de
    dados nem de arquivo em disco.
    """
    alvo = nome_loja.strip().lower()
    for parceiro in PARCEIROS_FALSOS:
        nome_p = parceiro["nome"].lower()
        alias_p = parceiro["alias"].lower()
        if nome_p == alvo or nome_p in alvo or alvo in nome_p or alvo in alias_p or alias_p in alvo:
            return parceiro
    return None


def test_buscar_parceiro_para_loja_encontra_por_substring(monkeypatch):
    monkeypatch.setattr(db, "buscar_parceiro_livelo_por_nome", _parceiro_falso_por_nome)
    parceiro = pesquisa_produto.buscar_parceiro_para_loja("Fast Shop")
    assert parceiro is not None
    assert parceiro["nome"] == "Fast Shop Oficial"


def test_buscar_parceiro_para_loja_nao_encontra_quando_nao_ha_parceiro(monkeypatch):
    monkeypatch.setattr(db, "buscar_parceiro_livelo_por_nome", _parceiro_falso_por_nome)
    parceiro = pesquisa_produto.buscar_parceiro_para_loja("Magalu")
    assert parceiro is None


def test_montar_oferta_usa_pontos_do_parceiro_casado(monkeypatch):
    monkeypatch.setattr(db, "buscar_parceiro_livelo_por_nome", _parceiro_falso_por_nome)
    oferta_buscape = OfertaBuscapeFalsa(
        loja="Amazon", preco=1000, preco_pix=950, preco_cartao=1000, confianca_pix_cartao=True,
    )
    oferta, parceiro, distincao_confiavel = montar_oferta_a_partir_do_buscape(
        oferta_buscape, cotacao_dolar=5.3, pontos_por_dolar_cartao_padrao=3.0,
    )
    assert parceiro["nome"] == "Amazon"
    assert oferta.pontos_por_real == 10.0
    assert oferta.parcelas == 6
    assert oferta.valor_milheiro == 30.0
    assert oferta.percentual_bonus_transferencia == 80.0
    assert distincao_confiavel is True


def test_montar_oferta_zera_pontos_quando_parceiro_nao_encontrado(monkeypatch):
    monkeypatch.setattr(db, "buscar_parceiro_livelo_por_nome", _parceiro_falso_por_nome)
    oferta_buscape = OfertaBuscapeFalsa(loja="Magalu", preco=1000, preco_pix=1000, preco_cartao=1000)
    oferta, parceiro, _ = montar_oferta_a_partir_do_buscape(
        oferta_buscape, cotacao_dolar=5.3, pontos_por_dolar_cartao_padrao=3.0,
    )
    assert parceiro is None
    assert oferta.pontos_por_real == 0.0


def test_pesquisar_produto_automaticamente_ranqueia_do_mais_barato_para_o_mais_caro(monkeypatch):
    monkeypatch.setattr(db, "buscar_parceiro_livelo_por_nome", _parceiro_falso_por_nome)

    def buscador_falso(nome_produto):
        return [
            OfertaBuscapeFalsa(loja="Fast Shop Oficial", preco=1200, preco_pix=1150, preco_cartao=1200),
            OfertaBuscapeFalsa(loja="Amazon", preco=1000, preco_pix=950, preco_cartao=1000),
            OfertaBuscapeFalsa(loja="Magalu", preco=1100, preco_pix=1100, preco_cartao=1100),
        ]

    resultados = pesquisar_produto_automaticamente(
        "geladeira teste",
        rendimento_mensal=1.1,
        cotacao_dolar=5.3,
        pontos_por_dolar_cartao_padrao=3.0,
        buscar_ofertas_buscape=buscador_falso,
    )

    assert len(resultados) == 3
    precos_em_ordem = [r.resultado.preco_efetivo for r in resultados]
    assert precos_em_ordem == sorted(precos_em_ordem)

    resultado_amazon = next(r for r in resultados if r.oferta.loja == "Amazon")
    assert resultado_amazon.parceiro_encontrado is True

    resultado_magalu = next(r for r in resultados if r.oferta.loja == "Magalu")
    assert resultado_magalu.parceiro_encontrado is False
    assert resultado_magalu.oferta.pontos_por_real == 0.0
