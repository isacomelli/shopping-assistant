import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.pesquisa_produto import (
    casar_parceiro_livelo,
    montar_oferta_a_partir_do_buscape,
    pesquisar_produto_automaticamente,
)


@dataclass
class OfertaBuscapeFalsa:
    loja: str
    preco: float
    preco_pix: float
    preco_cartao: float
    distincao_pix_cartao_confiavel: bool = False


PARCEIROS_FALSOS = [
    {"nome": "Amazon", "pontos_padrao": 10.0},
    {"nome": "Fast Shop Oficial", "pontos_padrao": 6.0},
]


def test_casar_parceiro_livelo_encontra_por_substring():
    parceiro = casar_parceiro_livelo("Fast Shop", PARCEIROS_FALSOS)
    assert parceiro is not None
    assert parceiro["nome"] == "Fast Shop Oficial"


def test_casar_parceiro_livelo_nao_encontra_quando_nao_ha_parceiro():
    parceiro = casar_parceiro_livelo("Magalu", PARCEIROS_FALSOS)
    assert parceiro is None


def test_montar_oferta_usa_pontos_do_parceiro_casado():
    oferta_buscape = OfertaBuscapeFalsa(
        loja="Amazon", preco=1000, preco_pix=950, preco_cartao=1000, distincao_pix_cartao_confiavel=True,
    )
    oferta, parceiro, distincao_confiavel = montar_oferta_a_partir_do_buscape(
        oferta_buscape, PARCEIROS_FALSOS, cotacao_dolar=5.3, pontos_por_dolar_cartao_padrao=3.0,
    )
    assert parceiro["nome"] == "Amazon"
    assert oferta.pontos_por_real == 10.0
    assert oferta.parcelas == 6
    assert oferta.valor_milheiro == 15.0
    assert oferta.percentual_bonus_transferencia == 80.0
    assert distincao_confiavel is True


def test_montar_oferta_zera_pontos_quando_parceiro_nao_encontrado():
    oferta_buscape = OfertaBuscapeFalsa(loja="Magalu", preco=1000, preco_pix=1000, preco_cartao=1000)
    oferta, parceiro, _ = montar_oferta_a_partir_do_buscape(
        oferta_buscape, PARCEIROS_FALSOS, cotacao_dolar=5.3, pontos_por_dolar_cartao_padrao=3.0,
    )
    assert parceiro is None
    assert oferta.pontos_por_real == 0.0


def test_pesquisar_produto_automaticamente_ranqueia_do_mais_barato_para_o_mais_caro():
    def buscador_falso(nome_produto):
        return [
            OfertaBuscapeFalsa(loja="Fast Shop Oficial", preco=1200, preco_pix=1150, preco_cartao=1200),
            OfertaBuscapeFalsa(loja="Amazon", preco=1000, preco_pix=950, preco_cartao=1000),
            OfertaBuscapeFalsa(loja="Magalu", preco=1100, preco_pix=1100, preco_cartao=1100),
        ]

    resultados = pesquisar_produto_automaticamente(
        "geladeira teste",
        parceiros_cadastrados=PARCEIROS_FALSOS,
        cdi_mensal=1.1,
        cotacao_dolar=5.3,
        pontos_por_dolar_cartao_padrao=3.0,
        buscador_buscape=buscador_falso,
    )

    assert len(resultados) == 3
    precos_em_ordem = [r.resultado.preco_efetivo for r in resultados]
    assert precos_em_ordem == sorted(precos_em_ordem)

    resultado_amazon = next(r for r in resultados if r.oferta.loja == "Amazon")
    assert resultado_amazon.parceiro_encontrado is True

    resultado_magalu = next(r for r in resultados if r.oferta.loja == "Magalu")
    assert resultado_magalu.parceiro_encontrado is False
    assert resultado_magalu.oferta.pontos_por_real == 0.0
