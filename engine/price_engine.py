"""
motor de calculo do preco efetivo de uma compra.

este modulo e proposital mente puro, sem dependencia de banco de dados,
scraper ou interface, para poder ser testado isoladamente com pytest.

a ideia central, dado um preco pix e um preco no cartao parcelado, alem
de pontos, cashback e cdi, calcular quanto a compra realmente custa
depois de considerar todos os beneficios envolvidos.
"""

from dataclasses import dataclass, field


@dataclass
class Oferta:
    """
    representa uma oferta de compra, seja ela online, parceira de
    pontos, loja fisica ou negociacao presencial.
    """

    loja: str
    preco_pix: float
    preco_cartao: float
    parcelas: int = 1
    pontos_por_real: float = 0.0
    valor_ponto: float = 0.0
    moeda_pontos: str = "R$"
    cotacao_dolar: float = 1.0
    cashback_pct: float = 0.0
    frete: float = 0.0
    cupom: float = 0.0
    tipo: str = "online"
    observacoes: str = ""


@dataclass
class ResultadoOferta:
    """
    resultado do calculo de uma oferta, com o detalhamento de cada
    componente para poder mostrar "por que essa opcao ganhou".
    """

    loja: str
    tipo: str
    preco_anunciado: float

    pontos_valor_pix: float
    cashback_valor_pix: float
    preco_efetivo_pix: float

    rendimento_parcelamento: float
    pontos_valor_cartao: float
    cashback_valor_cartao: float
    preco_efetivo_cartao: float

    melhor_forma_pagamento: str
    preco_efetivo: float
    economia_vs_anunciado: float


def valor_presente_parcelas(preco_total, parcelas, cdi_mensal_pct):
    """
    calcula o valor presente de n parcelas iguais e sem juros,
    descontadas pelo cdi mensal.

    quanto maior o numero de parcelas, menor o valor presente, ou
    seja, maior o beneficio de parcelar em vez de pagar tudo agora.
    """
    if parcelas <= 1:
        return preco_total

    taxa = cdi_mensal_pct / 100
    parcela = preco_total / parcelas

    valor_presente = 0.0
    for mes in range(1, parcelas + 1):
        valor_presente += parcela / ((1 + taxa) ** mes)

    return valor_presente


def calcular_rendimento_parcelamento(preco_cartao, parcelas, cdi_mensal_pct):
    """
    quanto voce ganha, em reais, por poder parcelar em vez de pagar
    tudo a vista no cartao.
    """
    if parcelas <= 1:
        return 0.0
    vp = valor_presente_parcelas(preco_cartao, parcelas, cdi_mensal_pct)
    return preco_cartao - vp


def calcular_valor_pontos(base_valor, pontos_por_real, valor_ponto, moeda_pontos="R$", cotacao_dolar=1.0):
    """
    calcula quanto valem, em reais, os pontos ganhos numa compra.

    se o programa pontua por dolar de turismo, a base e convertida
    antes de multiplicar pela taxa de pontos.
    """
    if pontos_por_real <= 0 or valor_ponto <= 0:
        return 0.0

    base = base_valor
    if moeda_pontos.upper() in ("U$", "US$", "USD"):
        base = base_valor / cotacao_dolar

    pontos_ganhos = base * pontos_por_real
    return pontos_ganhos * valor_ponto


def calcular_valor_cashback(base_valor, cashback_pct):
    """
    calcula quanto volta em cashback sobre o valor pago.
    """
    if cashback_pct <= 0:
        return 0.0
    return base_valor * (cashback_pct / 100)


def calcular_oferta(oferta: Oferta, cdi_mensal_pct: float) -> ResultadoOferta:
    """
    calcula o preco efetivo de uma oferta, tanto pagando pix quanto
    pagando parcelado no cartao, e devolve qual das duas formas de
    pagamento sai mais barata.
    """
    preco_anunciado = oferta.preco_cartao

    pontos_valor_pix = calcular_valor_pontos(
        oferta.preco_pix, oferta.pontos_por_real, oferta.valor_ponto,
        oferta.moeda_pontos, oferta.cotacao_dolar,
    )
    cashback_valor_pix = calcular_valor_cashback(oferta.preco_pix, oferta.cashback_pct)
    preco_efetivo_pix = (
        oferta.preco_pix - pontos_valor_pix - cashback_valor_pix + oferta.frete - oferta.cupom
    )

    rendimento_parcelamento = calcular_rendimento_parcelamento(
        oferta.preco_cartao, oferta.parcelas, cdi_mensal_pct,
    )
    pontos_valor_cartao = calcular_valor_pontos(
        oferta.preco_cartao, oferta.pontos_por_real, oferta.valor_ponto,
        oferta.moeda_pontos, oferta.cotacao_dolar,
    )
    cashback_valor_cartao = calcular_valor_cashback(oferta.preco_cartao, oferta.cashback_pct)
    preco_efetivo_cartao = (
        oferta.preco_cartao
        - rendimento_parcelamento
        - pontos_valor_cartao
        - cashback_valor_cartao
        + oferta.frete
        - oferta.cupom
    )

    if preco_efetivo_pix <= preco_efetivo_cartao:
        melhor_forma_pagamento = "pix"
        preco_efetivo = preco_efetivo_pix
    else:
        melhor_forma_pagamento = f"cartao {oferta.parcelas}x"
        preco_efetivo = preco_efetivo_cartao

    economia_vs_anunciado = preco_anunciado - preco_efetivo

    return ResultadoOferta(
        loja=oferta.loja,
        tipo=oferta.tipo,
        preco_anunciado=preco_anunciado,
        pontos_valor_pix=pontos_valor_pix,
        cashback_valor_pix=cashback_valor_pix,
        preco_efetivo_pix=preco_efetivo_pix,
        rendimento_parcelamento=rendimento_parcelamento,
        pontos_valor_cartao=pontos_valor_cartao,
        cashback_valor_cartao=cashback_valor_cartao,
        preco_efetivo_cartao=preco_efetivo_cartao,
        melhor_forma_pagamento=melhor_forma_pagamento,
        preco_efetivo=preco_efetivo,
        economia_vs_anunciado=economia_vs_anunciado,
    )


def ranquear_ofertas(ofertas, cdi_mensal_pct):
    """
    calcula todas as ofertas e devolve a lista ordenada da mais barata
    para a mais cara, considerando o preco efetivo.
    """
    resultados = [calcular_oferta(oferta, cdi_mensal_pct) for oferta in ofertas]
    return sorted(resultados, key=lambda r: r.preco_efetivo)


def simular_parcelamento(preco_pix, preco_cartao, cdi_mensal_pct, max_parcelas=12):
    """
    simula o custo efetivo do cartao para 1 ate max_parcelas parcelas,
    util para responder "a partir de quantas vezes compensa parcelar".
    """
    resultados = []
    for parcelas in range(1, max_parcelas + 1):
        rendimento = calcular_rendimento_parcelamento(preco_cartao, parcelas, cdi_mensal_pct)
        custo_efetivo = preco_cartao - rendimento
        resultados.append({"parcelas": parcelas, "custo_efetivo": round(custo_efetivo, 2)})
    return resultados
