"""
funcoes de apoio que ligam as linhas do banco ao motor de calculo.

fica tudo num lugar so para as rotas em backend/ nao precisarem remontar o dataclass Oferta toda vez, do jeito que a pagina da calculadora do streamlit fazia antes.
"""

from dataclasses import asdict
from engine.price_engine import Oferta, calcular_oferta


def oferta_da_linha(linha_oferta, config):
    """
    monta um Oferta do motor de calculo a partir de uma linha salva no banco, usando a cotacao do dolar e o valor do milheiro cadastrados no perfil.
    """
    return Oferta(
        loja=linha_oferta["loja"],
        preco_pix=linha_oferta["preco_pix"],
        preco_cartao=linha_oferta["preco_cartao"],
        preco=linha_oferta["preco"] or linha_oferta["preco_cartao"],
        parcelas=linha_oferta["parcelas"],
        tipo=linha_oferta["tipo"],
        pontos_por_real=linha_oferta["pontos_por_real"],
        cotacao_dolar=float(config["cotacao_dolar"]),
        pontos_por_dolar_cartao=linha_oferta["pontos_por_dolar_cartao"],
        percentual_bonus_transferencia=linha_oferta["percentual_bonus_transferencia"],
        valor_milheiro=linha_oferta["valor_milheiro"] or float(config["valor_milheiro_padrao"]),
        cashback_pct=linha_oferta["cashback_pct"],
        frete=linha_oferta["frete"],
        cupom=linha_oferta["cupom"],
        url_produto=linha_oferta["url_produto"] or "",
        logo_url=linha_oferta["logo_url"] or "",
    )


def oferta_do_payload(payload, config):
    """
    monta um Oferta do motor de calculo a partir do corpo recebido nas
    rotas de criar ou editar oferta manualmente. o formulario manual
    nao pede um preco bruto separado, entao preco cai de volta para o
    preco no cartao, do mesmo jeito que oferta_da_linha faz quando o
    valor salvo esta vazio.
    """
    return Oferta(
        loja=payload.loja.strip(),
        preco=payload.preco_cartao,
        preco_pix=payload.preco_pix,
        preco_cartao=payload.preco_cartao,
        parcelas=payload.parcelas,
        tipo=payload.tipo,
        pontos_por_real=payload.pontos_por_real,
        cotacao_dolar=float(config["cotacao_dolar"]),
        pontos_por_dolar_cartao=payload.pontos_por_dolar_cartao,
        percentual_bonus_transferencia=payload.percentual_bonus_transferencia,
        valor_milheiro=payload.valor_milheiro or float(config["valor_milheiro_padrao"]),
        cashback_pct=payload.cashback_pct,
        frete=payload.frete,
        cupom=payload.cupom,
    )


def resultado_como_dict(resultado):
    """
    converte o dataclass ResultadoOferta num dict pronto para entrar
    num schema de resposta, descartando os campos que ja aparecem em
    outro lugar do payload, tipo loja, tipo e preco_anunciado.
    """
    dados = asdict(resultado)
    for chave in ("loja", "tipo", "preco_anunciado"):
        dados.pop(chave, None)
    return dados


def linha_oferta_para_saida(linha_oferta, config):
    """
    junta os dados salvos de uma oferta com o resultado do calculo feito na hora, pronto para servir na rota de listagem.
    """
    oferta = oferta_da_linha(linha_oferta, config)
    resultado = calcular_oferta(oferta, float(config["rendimento_mensal"]))
    saida = dict(linha_oferta)
    saida["resultado"] = resultado_como_dict(resultado)
    return saida