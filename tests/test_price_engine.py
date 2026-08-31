import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.price_engine import (
    Oferta,
    calcular_oferta,
    calcular_rendimento_parcelamento,
    calcular_valor_cashback,
    calcular_valor_pontos,
    ranquear_ofertas,
    simular_parcelamento,
    valor_presente_parcelas,
)


def test_valor_presente_parcelas_uma_parcela_igual_ao_preco_total():
    assert valor_presente_parcelas(1000, 1, 1.1) == 1000


def test_valor_presente_parcelas_diminui_com_mais_parcelas():
    vp_curto = valor_presente_parcelas(1200, 3, 1.1)
    vp_longo = valor_presente_parcelas(1200, 12, 1.1)
    assert vp_longo < vp_curto < 1200


def test_rendimento_parcelamento_zero_para_parcela_unica():
    assert calcular_rendimento_parcelamento(1000, 1, 1.1) == 0.0


def test_rendimento_parcelamento_positivo_para_varias_parcelas():
    rendimento = calcular_rendimento_parcelamento(1000, 10, 1.1)
    assert rendimento > 0


def test_valor_pontos_em_reais():
    valor = calcular_valor_pontos(1000, pontos_por_real=10, valor_ponto=0.025)
    assert valor == 1000 * 10 * 0.025


def test_valor_pontos_em_dolar_converte_pela_cotacao():
    valor_em_real = calcular_valor_pontos(
        1000, pontos_por_real=3, valor_ponto=0.025, moeda_pontos="U$", cotacao_dolar=5.0,
    )
    valor_esperado = (1000 / 5.0) * 3 * 0.025
    assert round(valor_em_real, 4) == round(valor_esperado, 4)


def test_valor_pontos_zero_sem_taxa_ou_sem_valor_do_ponto():
    assert calcular_valor_pontos(1000, 0, 0.025) == 0.0
    assert calcular_valor_pontos(1000, 10, 0) == 0.0


def test_cashback_calcula_percentual_sobre_o_valor_pago():
    assert calcular_valor_cashback(1000, 8) == 80


def test_calcular_oferta_pix_mais_barato_quando_nao_ha_pontos():
    oferta = Oferta(loja="loja teste", preco_pix=900, preco_cartao=1000, parcelas=1)
    resultado = calcular_oferta(oferta, cdi_mensal_pct=1.1)
    assert resultado.melhor_forma_pagamento == "pix"
    assert resultado.preco_efetivo == 900


def test_calcular_oferta_cartao_pode_ganhar_com_pontos_e_parcelamento():
    oferta = Oferta(
        loja="amazon",
        preco_pix=2279,
        preco_cartao=2399,
        parcelas=10,
        pontos_por_real=10,
        valor_ponto=0.025,
    )
    resultado = calcular_oferta(oferta, cdi_mensal_pct=1.1)

    assert resultado.pontos_valor_cartao > resultado.pontos_valor_pix
    assert resultado.rendimento_parcelamento > 0
    assert resultado.preco_efetivo_cartao < oferta.preco_cartao


def test_frete_aumenta_e_cupom_diminui_o_preco_efetivo():
    base = Oferta(loja="loja", preco_pix=1000, preco_cartao=1000, parcelas=1)
    com_frete = Oferta(loja="loja", preco_pix=1000, preco_cartao=1000, parcelas=1, frete=50)
    com_cupom = Oferta(loja="loja", preco_pix=1000, preco_cartao=1000, parcelas=1, cupom=50)

    resultado_base = calcular_oferta(base, 1.1)
    resultado_frete = calcular_oferta(com_frete, 1.1)
    resultado_cupom = calcular_oferta(com_cupom, 1.1)

    assert resultado_frete.preco_efetivo == resultado_base.preco_efetivo + 50
    assert resultado_cupom.preco_efetivo == resultado_base.preco_efetivo - 50


def test_ranquear_ofertas_ordena_da_mais_barata_para_a_mais_cara():
    ofertas = [
        Oferta(loja="cara", preco_pix=1200, preco_cartao=1200, parcelas=1),
        Oferta(loja="barata", preco_pix=900, preco_cartao=950, parcelas=1),
        Oferta(loja="media", preco_pix=1000, preco_cartao=1000, parcelas=1),
    ]
    ranking = ranquear_ofertas(ofertas, cdi_mensal_pct=1.1)

    nomes_em_ordem = [resultado.loja for resultado in ranking]
    assert nomes_em_ordem == ["barata", "media", "cara"]


def test_simular_parcelamento_gera_uma_linha_por_quantidade_de_parcelas():
    resultado = simular_parcelamento(preco_pix=740, preco_cartao=779, cdi_mensal_pct=1.1, max_parcelas=12)
    assert len(resultado) == 12
    assert resultado[0]["parcelas"] == 1
    assert resultado[-1]["parcelas"] == 12
    assert resultado[0]["custo_efetivo"] == 779


def test_calcular_oferta_usa_milheiro_quando_valor_milheiro_preenchido():
    from engine.price_engine import calcular_valor_pontos_por_milhas

    oferta = Oferta(
        loja="xp",
        preco_pix=1571.00,
        preco_cartao=1651.37,
        parcelas=1,
        pontos_por_real=10,
        cotacao_dolar=5.3,
        pontos_por_dolar_cartao=3,
        percentual_bonus_transferencia=80,
        valor_milheiro=15,
    )
    resultado = calcular_oferta(oferta, cdi_mensal_pct=1.1)

    valor_esperado_pix = calcular_valor_pontos_por_milhas(1571.00, 10, 5.3, 3, 80, 15)
    valor_esperado_cartao = calcular_valor_pontos_por_milhas(1651.37, 10, 5.3, 3, 80, 15)

    assert round(resultado.pontos_valor_pix, 4) == round(valor_esperado_pix, 4)
    assert round(resultado.pontos_valor_cartao, 4) == round(valor_esperado_cartao, 4)


def test_calcular_oferta_ignora_milheiro_quando_valor_milheiro_zero():
    oferta = Oferta(
        loja="loja sem milhas",
        preco_pix=1000,
        preco_cartao=1000,
        pontos_por_real=10,
        valor_ponto=0.025,
        pontos_por_dolar_cartao=3,
        percentual_bonus_transferencia=80,
    )
    resultado = calcular_oferta(oferta, cdi_mensal_pct=1.1)
    assert resultado.pontos_valor_pix == 1000 * 10 * 0.025
