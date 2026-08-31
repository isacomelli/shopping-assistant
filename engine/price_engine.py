"""
motor de calculo do preco efetivo de uma compra.

este modulo e proposital mente puro, sem dependencia de banco de dados,
scraper ou interface, para poder ser testado isoladamente com pytest.

a ideia central, dado um preco pix e um preco no cartao parcelado, alem
de pontos, cashback e cdi, calcular quanto a compra realmente custa
depois de considerar todos os beneficios envolvidos.

sobre pontos e milhas, existem dois jeitos de estimar o valor dos
pontos de uma oferta. o primeiro, mais antigo, e informar diretamente
quanto vale cada ponto em reais, atraves de valor_ponto. o segundo,
mais fiel a forma como voce realmente usa livelo, esfera e cartao xp,
e o calculo por milheiro, descrito logo abaixo, que reproduz a mesma
conta feita antes numa planilha.

calculo por milheiro, passo a passo
pontos acumulados no site parceiro = pontos por real x valor da compra
pontos acumulados no cartao = (valor da compra / cotacao do dolar) x pontos por dolar do cartao
milhas do site parceiro, com bonus de transferencia = pontos do site parceiro x (1 + bonus)
milhas totais = milhas do site parceiro com bonus + pontos acumulados no cartao
valor em milhas = (valor do milheiro x milhas totais) / 1000

quando uma oferta tem valor_milheiro maior que zero, o calculo de
pontos passa a usar esse metodo em vez do valor_ponto fixo.
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

    # campos do calculo por milheiro, ver docstring do modulo
    pontos_por_dolar_cartao: float = 0.0
    percentual_bonus_transferencia: float = 0.0
    valor_milheiro: float = 0.0


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
    calcula quanto valem, em reais, os pontos ganhos numa compra,
    a partir de um valor fixo por ponto.

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


def calcular_pontos_parceiro(base_valor, pontos_por_real):
    """
    pontos acumulados no site parceiro, tipo livelo ou esfera,
    aplicando a taxa de pontos por real sobre o valor da compra.
    """
    if pontos_por_real <= 0:
        return 0.0
    return base_valor * pontos_por_real


def calcular_pontos_cartao(base_valor, cotacao_dolar, pontos_por_dolar_cartao):
    """
    pontos acumulados direto no cartao de credito, convertendo o
    valor da compra para dolar antes de aplicar a taxa por dolar
    gasto.
    """
    if pontos_por_dolar_cartao <= 0 or cotacao_dolar <= 0:
        return 0.0
    return (base_valor / cotacao_dolar) * pontos_por_dolar_cartao


def calcular_milhas_totais(pontos_parceiro, pontos_cartao, percentual_bonus):
    """
    milhas totais depois de transferir os pontos do site parceiro
    para o programa de milhas com bonus de transferencia, somadas
    aos pontos ganhos direto no cartao.

    como o cartao costuma ter parceria direta com o programa de
    pontos, os pontos do cartao entram sem o bonus de transferencia,
    reproduzindo a mesma conta feita antes na planilha.
    """
    milhas_parceiro_bonificadas = pontos_parceiro * (1 + percentual_bonus / 100)
    return milhas_parceiro_bonificadas + pontos_cartao


def calcular_valor_em_milhas(milhas_totais, valor_milheiro):
    """
    valor em reais de um total de milhas, dado o valor estimado do
    milheiro.
    """
    if valor_milheiro <= 0:
        return 0.0
    return (valor_milheiro * milhas_totais) / 1000


def calcular_valor_pontos_por_milhas(
    base_valor,
    pontos_por_real,
    cotacao_dolar,
    pontos_por_dolar_cartao,
    percentual_bonus,
    valor_milheiro,
):
    """
    estima quanto vale, em reais, o total de milhas geradas por uma
    compra, juntando os pontos do site parceiro, ja com o bonus de
    transferencia, com os pontos ganhos direto no cartao de credito.

    esse e o metodo recomendado para livelo, esfera e cartoes com
    parceria de milhas, veja a docstring do modulo para o passo a
    passo completo.
    """
    if valor_milheiro <= 0:
        return 0.0

    pontos_parceiro = calcular_pontos_parceiro(base_valor, pontos_por_real)
    pontos_cartao = calcular_pontos_cartao(base_valor, cotacao_dolar, pontos_por_dolar_cartao)
    milhas_totais = calcular_milhas_totais(pontos_parceiro, pontos_cartao, percentual_bonus)

    return calcular_valor_em_milhas(milhas_totais, valor_milheiro)


def _calcular_valor_pontos_da_oferta(oferta, base_valor):
    """
    escolhe o metodo de calculo dos pontos de uma oferta, por
    milheiro quando valor_milheiro estiver preenchido, ou pelo valor
    fixo por ponto caso contrario.
    """
    if oferta.valor_milheiro > 0:
        return calcular_valor_pontos_por_milhas(
            base_valor,
            oferta.pontos_por_real,
            oferta.cotacao_dolar,
            oferta.pontos_por_dolar_cartao,
            oferta.percentual_bonus_transferencia,
            oferta.valor_milheiro,
        )

    return calcular_valor_pontos(
        base_valor, oferta.pontos_por_real, oferta.valor_ponto,
        oferta.moeda_pontos, oferta.cotacao_dolar,
    )


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

    pontos_valor_pix = _calcular_valor_pontos_da_oferta(oferta, oferta.preco_pix)
    cashback_valor_pix = calcular_valor_cashback(oferta.preco_pix, oferta.cashback_pct)
    preco_efetivo_pix = (
        oferta.preco_pix - pontos_valor_pix - cashback_valor_pix + oferta.frete - oferta.cupom
    )

    rendimento_parcelamento = calcular_rendimento_parcelamento(
        oferta.preco_cartao, oferta.parcelas, cdi_mensal_pct,
    )
    pontos_valor_cartao = _calcular_valor_pontos_da_oferta(oferta, oferta.preco_cartao)
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
