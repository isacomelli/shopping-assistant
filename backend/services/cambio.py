"""
busca a cotacao atual do dolar numa api publica e gratuita, sem
necessidade de chave de acesso.

isso e opcional, o usuario tambem pode digitar a cotacao manualmente
na tela de perfil.
"""

import requests

URL_COTACAO = "https://economia.awesomeapi.com.br/last/USD-BRL"


def buscar_cotacao_dolar():
    """
    devolve a cotacao de venda do dolar em reais, ou none se a
    consulta falhar por qualquer motivo.
    """
    try:
        resposta = requests.get(URL_COTACAO, timeout=10)
        resposta.raise_for_status()
        dados = resposta.json()
        return float(dados["USDBRL"]["bid"])
    except Exception:
        return None
