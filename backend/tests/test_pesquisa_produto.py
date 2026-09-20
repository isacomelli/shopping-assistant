import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import pesquisa_produto
from services.google_shopping import ErroScraperGoogleShopping
from services.pesquisa_produto import (
    buscar_ofertas_combinadas,
    montar_oferta_a_partir_do_buscape,
    pesquisar_produto_automaticamente,
)


@dataclass
class OfertaEncontradaFalsa:
    loja: str
    preco: float
    preco_pix: float
    preco_cartao: float
    confianca_pix_cartao: bool = False
    parcelas: int = 0
    url_produto: str = ""
    imagem_produto: str = ""
    origem: str = "teste"
    nome_produto: str = ""


# lista fixa falsa, no mesmo formato de PARCEIROS_LIVELO_CONHECIDOS
# em services/casamento_lojas.py, so pra nao depender da lista real
# de producao, que muda conforme a livelo ajusta as taxas
PARCEIROS_FALSOS = [
    {"nome": "Amazon", "alias": "Amazon", "codigo": "AMZ", "pontos_padrao": 10.0},
    {"nome": "Fast Shop Oficial", "alias": "Fast Shop", "codigo": "FST", "pontos_padrao": 6.0},
]


def google_vazio(_termo):
    """
    , stub usado nos testes que nao querem exercitar a fonte google shopping, simula a fonte respondendo sem nenhuma oferta encontrada, sem depender de rede nem de playwright
    """
    return []


def google_indisponivel(_termo):
    """
    , stub usado para simular o google shopping bloqueado ou fora do ar, para testar a queda para o buscape complementar
    """
    raise ErroScraperGoogleShopping("captcha exigido pelo google")


def test_buscar_parceiro_para_loja_encontra_por_substring(monkeypatch):
    monkeypatch.setattr(pesquisa_produto, "PARCEIROS_LIVELO_CONHECIDOS", PARCEIROS_FALSOS)
    parceiro = pesquisa_produto.buscar_parceiro_para_loja("Fast Shop")
    assert parceiro is not None
    assert parceiro["nome"] == "Fast Shop Oficial"


def test_buscar_parceiro_para_loja_nao_encontra_quando_nao_ha_parceiro(monkeypatch):
    monkeypatch.setattr(pesquisa_produto, "PARCEIROS_LIVELO_CONHECIDOS", PARCEIROS_FALSOS)
    parceiro = pesquisa_produto.buscar_parceiro_para_loja("Magalu")
    assert parceiro is None


def test_montar_oferta_usa_pontos_do_parceiro_casado(monkeypatch):
    monkeypatch.setattr(pesquisa_produto, "PARCEIROS_LIVELO_CONHECIDOS", PARCEIROS_FALSOS)
    oferta_encontrada = OfertaEncontradaFalsa(
        loja="Amazon", preco=1000, preco_pix=950, preco_cartao=1000, confianca_pix_cartao=True,
    )
    oferta, parceiro, distincao_confiavel = montar_oferta_a_partir_do_buscape(
        oferta_encontrada, cotacao_dolar=5.3, pontos_por_dolar_cartao_padrao=3.0,
    )
    assert parceiro["nome"] == "Amazon"
    assert oferta.pontos_por_real == 10.0
    assert oferta.parcelas == 6
    assert oferta.valor_milheiro == 30.0
    assert oferta.percentual_bonus_transferencia == 80.0
    assert distincao_confiavel is True


def test_montar_oferta_zera_pontos_do_parceiro_quando_parceiro_nao_encontrado(monkeypatch):
    monkeypatch.setattr(pesquisa_produto, "PARCEIROS_LIVELO_CONHECIDOS", PARCEIROS_FALSOS)
    oferta_encontrada = OfertaEncontradaFalsa(loja="Magalu", preco=1000, preco_pix=1000, preco_cartao=1000)
    oferta, parceiro, _ = montar_oferta_a_partir_do_buscape(
        oferta_encontrada, cotacao_dolar=5.3, pontos_por_dolar_cartao_padrao=3.0,
    )
    assert parceiro is None
    assert oferta.pontos_por_real == 0.0


def test_montar_oferta_mantem_pontos_do_cartao_mesmo_sem_parceiro(monkeypatch):
    """
    , os pontos do cartao de credito existem sempre que o pagamento e feito no cartao, independentemente da loja ter parceria com a livelo, so os pontos do site parceiro, pontos_por_real, dependem do casamento
    """
    monkeypatch.setattr(pesquisa_produto, "PARCEIROS_LIVELO_CONHECIDOS", PARCEIROS_FALSOS)
    oferta_encontrada = OfertaEncontradaFalsa(loja="Loja Sem Parceria", preco=1000, preco_pix=1000, preco_cartao=1000)
    oferta, parceiro, _ = montar_oferta_a_partir_do_buscape(
        oferta_encontrada, cotacao_dolar=5.3, pontos_por_dolar_cartao_padrao=3.0,
    )
    assert parceiro is None
    assert oferta.pontos_por_real == 0.0
    assert oferta.pontos_por_dolar_cartao == 3.0


def test_montar_oferta_usa_logo_do_parceiro_casado(monkeypatch):
    monkeypatch.setattr(pesquisa_produto, "PARCEIROS_LIVELO_CONHECIDOS", PARCEIROS_FALSOS)
    oferta_encontrada = OfertaEncontradaFalsa(
        loja="Amazon", preco=1000, preco_pix=950, preco_cartao=1000, confianca_pix_cartao=True,
    )
    oferta, _, _ = montar_oferta_a_partir_do_buscape(
        oferta_encontrada, cotacao_dolar=5.3, pontos_por_dolar_cartao_padrao=3.0,
    )
    assert oferta.logo_url == "https://partners-profile.livelo.com.br/amz/image.jpeg"


def test_montar_oferta_sem_logo_quando_parceiro_nao_encontrado(monkeypatch):
    monkeypatch.setattr(pesquisa_produto, "PARCEIROS_LIVELO_CONHECIDOS", PARCEIROS_FALSOS)
    oferta_encontrada = OfertaEncontradaFalsa(loja="Magalu", preco=1000, preco_pix=1000, preco_cartao=1000)
    oferta, _, _ = montar_oferta_a_partir_do_buscape(
        oferta_encontrada, cotacao_dolar=5.3, pontos_por_dolar_cartao_padrao=3.0,
    )
    assert oferta.logo_url == ""


def test_montar_oferta_usa_parcelas_reais_da_fonte_quando_confirmadas(monkeypatch):
    """
    , quando a fonte confirma um parcelamento de verdade, tipo 10x, esse numero real deve prevalecer sobre o padrao do perfil, ja que o preco_cartao da propria oferta ja foi calculado em cima dessas mesmas 10 parcelas
    """
    monkeypatch.setattr(pesquisa_produto, "PARCEIROS_LIVELO_CONHECIDOS", PARCEIROS_FALSOS)
    oferta_encontrada = OfertaEncontradaFalsa(
        loja="Amazon", preco=1630.21, preco_pix=1499.79, preco_cartao=1630.21,
        confianca_pix_cartao=True, parcelas=10,
    )
    oferta, _, _ = montar_oferta_a_partir_do_buscape(
        oferta_encontrada, cotacao_dolar=5.3, pontos_por_dolar_cartao_padrao=3.0,
        parcelas_quando_nao_confirmado=6,
    )
    assert oferta.parcelas == 10


def test_montar_oferta_usa_parcelas_do_perfil_quando_fonte_nao_confirma(monkeypatch):
    monkeypatch.setattr(pesquisa_produto, "PARCEIROS_LIVELO_CONHECIDOS", PARCEIROS_FALSOS)
    oferta_encontrada = OfertaEncontradaFalsa(
        loja="Amazon", preco=1000, preco_pix=1000, preco_cartao=1000, confianca_pix_cartao=False,
    )
    oferta, _, _ = montar_oferta_a_partir_do_buscape(
        oferta_encontrada, cotacao_dolar=5.3, pontos_por_dolar_cartao_padrao=3.0,
        parcelas_quando_nao_confirmado=12,
    )
    assert oferta.parcelas == 12


def test_buscar_ofertas_combinadas_usa_google_shopping_como_fonte_principal():
    def google_com_resultado(_termo):
        return [OfertaEncontradaFalsa(loja="Fast Shop", preco=1000, preco_pix=1000, preco_cartao=1000)]

    ofertas, erros = buscar_ofertas_combinadas(
        "produto teste",
        incluir_buscape_complementar=False,
        buscar_ofertas_google_shopping=google_com_resultado,
    )
    assert len(ofertas) == 1
    assert ofertas[0].origem == "google_shopping"
    assert erros == {}


def test_buscar_ofertas_combinadas_soma_buscape_como_fonte_complementar():
    def google_com_resultado(_termo):
        return [OfertaEncontradaFalsa(loja="Fast Shop", preco=1000, preco_pix=1000, preco_cartao=1000)]

    def buscape_com_resultado(_termo):
        return [OfertaEncontradaFalsa(loja="Leroy Merlin", preco=800, preco_pix=800, preco_cartao=800)]

    ofertas, erros = buscar_ofertas_combinadas(
        "produto teste",
        incluir_buscape_complementar=True,
        buscar_ofertas_google_shopping=google_com_resultado,
        buscar_ofertas_buscape=buscape_com_resultado,
    )
    lojas_encontradas = {oferta.loja for oferta in ofertas}
    assert lojas_encontradas == {"Fast Shop", "Leroy Merlin"}
    assert erros == {}


def test_buscar_ofertas_combinadas_cai_para_buscape_quando_google_falha():
    def buscape_com_resultado(_termo):
        return [OfertaEncontradaFalsa(loja="Amazon", preco=900, preco_pix=900, preco_cartao=900)]

    ofertas, erros = buscar_ofertas_combinadas(
        "produto teste",
        incluir_buscape_complementar=True,
        buscar_ofertas_google_shopping=google_indisponivel,
        buscar_ofertas_buscape=buscape_com_resultado,
    )
    assert len(ofertas) == 1
    assert ofertas[0].loja == "Amazon"
    assert "google_shopping" in erros


def test_buscar_ofertas_combinadas_levanta_erro_quando_nenhuma_fonte_encontra_nada():
    import pytest

    with pytest.raises(ErroScraperGoogleShopping):
        buscar_ofertas_combinadas(
            "produto teste",
            incluir_buscape_complementar=True,
            buscar_ofertas_google_shopping=google_indisponivel,
            buscar_ofertas_buscape=google_vazio,
        )


def test_pesquisar_produto_automaticamente_ranqueia_do_mais_barato_para_o_mais_caro(monkeypatch):
    monkeypatch.setattr(pesquisa_produto, "PARCEIROS_LIVELO_CONHECIDOS", PARCEIROS_FALSOS)

    def google_com_resultados(_termo):
        return [
            OfertaEncontradaFalsa(loja="Fast Shop Oficial", preco=1200, preco_pix=1150, preco_cartao=1200),
            OfertaEncontradaFalsa(loja="Amazon", preco=1000, preco_pix=950, preco_cartao=1000),
            OfertaEncontradaFalsa(loja="Magalu", preco=1100, preco_pix=1100, preco_cartao=1100),
        ]

    resultados = pesquisar_produto_automaticamente(
        "geladeira teste",
        rendimento_mensal=1.1,
        cotacao_dolar=5.3,
        pontos_por_dolar_cartao_padrao=3.0,
        incluir_buscape_complementar=False,
        buscar_ofertas_google_shopping=google_com_resultados,
    )

    assert len(resultados) == 3
    precos_em_ordem = [r.resultado.preco_efetivo for r in resultados]
    assert precos_em_ordem == sorted(precos_em_ordem)

    resultado_amazon = next(r for r in resultados if r.oferta.loja == "Amazon")
    assert resultado_amazon.parceiro_encontrado is True
    assert resultado_amazon.origem == "google_shopping"

    resultado_magalu = next(r for r in resultados if r.oferta.loja == "Magalu")
    assert resultado_magalu.parceiro_encontrado is False
    assert resultado_magalu.oferta.pontos_por_real == 0.0
    assert resultado_magalu.oferta.pontos_por_dolar_cartao == 3.0


def test_pesquisar_produto_automaticamente_combina_fontes_e_marca_origem(monkeypatch):
    monkeypatch.setattr(pesquisa_produto, "PARCEIROS_LIVELO_CONHECIDOS", PARCEIROS_FALSOS)

    def google_com_resultado(_termo):
        return [OfertaEncontradaFalsa(loja="Amazon", preco=1000, preco_pix=1000, preco_cartao=1000)]

    def buscape_com_resultado(_termo):
        return [OfertaEncontradaFalsa(loja="Fast Shop", preco=1100, preco_pix=1100, preco_cartao=1100)]

    resultados = pesquisar_produto_automaticamente(
        "produto teste",
        rendimento_mensal=1.1,
        cotacao_dolar=5.3,
        pontos_por_dolar_cartao_padrao=3.0,
        incluir_buscape_complementar=True,
        buscar_ofertas_google_shopping=google_com_resultado,
        buscar_ofertas_buscape=buscape_com_resultado,
    )

    origens = {resultado.oferta.loja: resultado.origem for resultado in resultados}
    assert origens["Amazon"] == "google_shopping"
    assert origens["Fast Shop"] == "buscape"


def test_buscar_parceiro_para_loja_prioriza_parceiros_conhecidos_informado(monkeypatch):
    """
    , quando parceiros_conhecidos e informado, tipicamente vindo da tabela livelo_parceiros
    do banco ja atualizada pelo botao "atualizar parceiros da livelo", ele deve ganhar de
    PARCEIROS_LIVELO_CONHECIDOS, mesmo que o mesmo nome exista nos dois, ver
    routers/ofertas.py _parceiros_para_pesquisa_automatica.
    """
    monkeypatch.setattr(pesquisa_produto, "PARCEIROS_LIVELO_CONHECIDOS", PARCEIROS_FALSOS)
    parceiros_do_banco = [
        {"nome": "Amazon", "alias": "amazon", "pontos_padrao": 25.0, "logo_url": "https://exemplo.com/amazon.png"},
    ]
    parceiro = pesquisa_produto.buscar_parceiro_para_loja("Amazon", parceiros_do_banco)
    assert parceiro["pontos_padrao"] == 25.0
    assert parceiro["logo_url"] == "https://exemplo.com/amazon.png"


def test_buscar_parceiro_para_loja_sem_parceiros_conhecidos_cai_para_lista_fixa(monkeypatch):
    monkeypatch.setattr(pesquisa_produto, "PARCEIROS_LIVELO_CONHECIDOS", PARCEIROS_FALSOS)
    parceiro = pesquisa_produto.buscar_parceiro_para_loja("Amazon")
    assert parceiro["pontos_padrao"] == 10.0
