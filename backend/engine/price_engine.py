"""
motor de calculo do preco efetivo de uma compra.

este modulo e proposital mente puro, sem dependencia de banco de dados,
scraper ou interface, para poder ser testado isoladamente com pytest.

sobre o calculo de milhas, ele segue a mesma logica de uma planilha
que ja era usada antes deste app, resumida abaixo.

pontos acumulados no site parceiro = pontos por real vezes valor do produto
pontos acumulados no cartao = (valor do produto dividido pela cotacao do dolar) vezes pontos por dolar do cartao
milhas acumuladas no site parceiro = pontos do site parceiro mais (pontos do site parceiro vezes percentual de transferencia bonificada)
valor em milhas = (valor estimado do milheiro vezes milhas totais) dividido por 1000

um detalhe importante, no pix nao existe cartao envolvido, entao a
compra so gera pontos no site parceiro, sem o acumulo extra do cartao.
ja no cartao parcelado, os dois acumulos contam ao mesmo tempo, o
ponto do site parceiro e o ponto do proprio cartao.

quando uma oferta nao tiver valor_milheiro preenchido, o calculo cai
de volta para um valor fixo por ponto, atraves de valor_ponto, util
para programas mais simples de cashback ou pontos sem conversao para
milhas.
"""

from dataclasses import dataclass


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
    tipo: str = "online"
    observacoes: str = ""

    # site parceiro, tipo livelo ou esfera
    pontos_por_real: float = 0.0

    # cartao de credito usado na compra parcelada
    cotacao_dolar: float = 1.0
    pontos_por_dolar_cartao: float = 0.0

    # conversao para milhas
    percentual_bonus_transferencia: float = 0.0
    valor_milheiro: float = 0.0

    # metodo alternativo, valor fixo por ponto, usado quando
    # valor_milheiro nao estiver preenchido
    valor_ponto: float = 0.0

    # cashback e ajustes de preco
    cashback_pct: float = 0.0
    frete: float = 0.0
    cupom: float = 0.0


@dataclass
class ResultadoOferta:
    """
    resultado do calculo de uma oferta, com o detalhamento de cada
    componente para poder mostrar por que essa opcao ganhou.
    """

    loja: str
    tipo: str
    preco_anunciado: float

    valor_pontos_pix: float
    cashback_valor_pix: float
    preco_efetivo_pix: float

    rendimento_parcelamento: float
    valor_pontos_cartao: float
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


def calcular_pontos_parceiro(base_valor, pontos_por_real):
    """
    pontos acumulados no site parceiro, tipo livelo ou esfera,
    aplicando a taxa de pontos por real sobre o valor gasto.
    """
    if pontos_por_real <= 0:
        return 0.0
    return base_valor * pontos_por_real


def calcular_pontos_cartao(base_valor, cotacao_dolar, pontos_por_dolar_cartao):
    """
    pontos acumulados direto no cartao de credito, convertendo o
    valor gasto para dolar antes de aplicar a taxa por dolar.
    """
    if pontos_por_dolar_cartao <= 0 or cotacao_dolar <= 0:
        return 0.0
    return (base_valor / cotacao_dolar) * pontos_por_dolar_cartao


def calcular_milhas_parceiro_bonificadas(pontos_parceiro, percentual_bonus):
    """
    milhas do site parceiro depois de aplicar o bonus de transferencia
    vigente na promocao, quando houver.
    """
    return pontos_parceiro * (1 + percentual_bonus / 100)


def calcular_valor_em_milhas(milhas_totais, valor_milheiro):
    """
    valor em reais de um total de milhas, dado o valor estimado do
    milheiro.
    """
    if valor_milheiro <= 0:
        return 0.0
    return (valor_milheiro * milhas_totais) / 1000


def calcular_valor_milhas_pix(base_valor, pontos_por_real, percentual_bonus, valor_milheiro):
    """
    valor em reais das milhas geradas por uma compra no pix.

    no pix nao existe cartao de credito envolvido, entao so o site
    parceiro pontua, sem o acumulo extra de pontos do cartao.
    """
    pontos_parceiro = calcular_pontos_parceiro(base_valor, pontos_por_real)
    milhas_totais = calcular_milhas_parceiro_bonificadas(pontos_parceiro, percentual_bonus)
    return calcular_valor_em_milhas(milhas_totais, valor_milheiro)


def calcular_valor_milhas_cartao(base_valor, pontos_por_real, cotacao_dolar,
                                  pontos_por_dolar_cartao, percentual_bonus, valor_milheiro):
    """
    valor em reais das milhas geradas por uma compra parcelada no
    cartao, somando o acumulo do site parceiro, ja com o bonus de
    transferencia, com o acumulo direto do proprio cartao.
    """
    pontos_parceiro = calcular_pontos_parceiro(base_valor, pontos_por_real)
    pontos_cartao = calcular_pontos_cartao(base_valor, cotacao_dolar, pontos_por_dolar_cartao)
    milhas_parceiro_bonificadas = calcular_milhas_parceiro_bonificadas(pontos_parceiro, percentual_bonus)
    milhas_totais = milhas_parceiro_bonificadas + pontos_cartao
    return calcular_valor_em_milhas(milhas_totais, valor_milheiro)


def calcular_valor_pontos_fixo(base_valor, pontos_por_real, valor_ponto):
    """
    metodo alternativo mais simples, um valor fixo por ponto, sem
    conversao para milhas. usado quando a oferta nao tiver
    valor_milheiro preenchido.
    """
    if pontos_por_real <= 0 or valor_ponto <= 0:
        return 0.0
    return base_valor * pontos_por_real * valor_ponto


def calcular_valor_cashback(base_valor, cashback_pct):
    """
    calcula quanto volta em cashback sobre o valor pago.
    """
    if cashback_pct <= 0:
        return 0.0
    return base_valor * (cashback_pct / 100)


def _calcular_valor_pontos_pix(oferta):
    if oferta.valor_milheiro > 0:
        return calcular_valor_milhas_pix(
            oferta.preco_pix, oferta.pontos_por_real,
            oferta.percentual_bonus_transferencia, oferta.valor_milheiro,
        )
    return calcular_valor_pontos_fixo(oferta.preco_pix, oferta.pontos_por_real, oferta.valor_ponto)


def _calcular_valor_pontos_cartao(oferta):
    if oferta.valor_milheiro > 0:
        return calcular_valor_milhas_cartao(
            oferta.preco_cartao, oferta.pontos_por_real, oferta.cotacao_dolar,
            oferta.pontos_por_dolar_cartao, oferta.percentual_bonus_transferencia,
            oferta.valor_milheiro,
        )
    return calcular_valor_pontos_fixo(oferta.preco_cartao, oferta.pontos_por_real, oferta.valor_ponto)


def calcular_oferta(oferta: Oferta, cdi_mensal_pct: float) -> ResultadoOferta:
    """
    calcula o preco efetivo de uma oferta, tanto pagando pix quanto
    pagando parcelado no cartao, e devolve qual das duas formas de
    pagamento sai mais barata.
    """
    preco_anunciado = oferta.preco_cartao

    valor_pontos_pix = _calcular_valor_pontos_pix(oferta)
    cashback_valor_pix = calcular_valor_cashback(oferta.preco_pix, oferta.cashback_pct)
    preco_efetivo_pix = (
        oferta.preco_pix - valor_pontos_pix - cashback_valor_pix + oferta.frete - oferta.cupom
    )

    rendimento_parcelamento = calcular_rendimento_parcelamento(
        oferta.preco_cartao, oferta.parcelas, cdi_mensal_pct,
    )
    valor_pontos_cartao = _calcular_valor_pontos_cartao(oferta)
    cashback_valor_cartao = calcular_valor_cashback(oferta.preco_cartao, oferta.cashback_pct)
    preco_efetivo_cartao = (
        oferta.preco_cartao
        - rendimento_parcelamento
        - valor_pontos_cartao
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
        valor_pontos_pix=valor_pontos_pix,
        cashback_valor_pix=cashback_valor_pix,
        preco_efetivo_pix=preco_efetivo_pix,
        rendimento_parcelamento=rendimento_parcelamento,
        valor_pontos_cartao=valor_pontos_cartao,
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
    util para responder a partir de quantas vezes compensa parcelar.
    """
    resultados = []
    for parcelas in range(1, max_parcelas + 1):
        rendimento = calcular_rendimento_parcelamento(preco_cartao, parcelas, cdi_mensal_pct)
        custo_efetivo = preco_cartao - rendimento
        resultados.append({"parcelas": parcelas, "custo_efetivo": round(custo_efetivo, 2)})
    return resultados
