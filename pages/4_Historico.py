"""
pagina de historico de precos, mostra a evolucao do preco efetivo de
um produto ao longo das pesquisas feitas.
"""

import statistics
from datetime import datetime, timedelta

import streamlit as st

from database import db


def _tentar_converter_data(texto):
    """
    converte o timestamp salvo pelo sqlite para datetime, devolvendo
    none se o formato vier diferente do esperado.
    """
    try:
        return datetime.strptime(texto, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


st.set_page_config(page_title="Historico", layout="wide")

db.inicializar_banco()

st.title("Historico de precos")

produtos = db.listar_produtos()

if not produtos:
    st.info("nenhum produto cadastrado ainda")
    st.stop()

nome_escolhido = st.selectbox("produto", [produto["nome"] for produto in produtos])
produto_atual = next(produto for produto in produtos if produto["nome"] == nome_escolhido)

historico = db.listar_historico(produto_atual["id"])

if not historico:
    st.info("ainda nao ha historico registrado para este produto, cadastre ofertas na calculadora")
    st.stop()

st.line_chart(
    {
        "data": [linha["registrado_em"] for linha in historico],
        "preco efetivo": [linha["preco_efetivo"] for linha in historico],
    },
    x="data",
    y="preco efetivo",
)

precos = [linha["preco_efetivo"] for linha in historico if linha["preco_efetivo"] is not None]

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("menor preco ja encontrado", f"r$ {min(precos):.2f}")
with col2:
    trinta_dias_atras = datetime.now() - timedelta(days=30)
    precos_recentes = [
        linha["preco_efetivo"]
        for linha in historico
        if linha["preco_efetivo"] is not None
        and _tentar_converter_data(linha["registrado_em"]) and _tentar_converter_data(linha["registrado_em"]) >= trinta_dias_atras
    ]
    media_recente = statistics.mean(precos_recentes) if precos_recentes else statistics.mean(precos)
    st.metric("media dos ultimos 30 dias", f"r$ {media_recente:.2f}")
with col3:
    preco_atual = precos[-1]
    st.metric("preco atual", f"r$ {preco_atual:.2f}")

if preco_atual < media_recente:
    diferenca_pct = (1 - preco_atual / media_recente) * 100
    st.success(f"vale comprar agora, esta {diferenca_pct:.1f}% abaixo da media dos ultimos 30 dias")
elif preco_atual > media_recente:
    diferenca_pct = (preco_atual / media_recente - 1) * 100
    st.warning(f"esta {diferenca_pct:.1f}% acima da media dos ultimos 30 dias, talvez valha esperar")
else:
    st.info("preco atual esta na media dos ultimos 30 dias")

st.header("Todas as pesquisas registradas")
st.dataframe(
    [
        {
            "data": linha["registrado_em"],
            "loja": linha["loja"],
            "preco anunciado": linha["preco_anunciado"],
            "preco efetivo": linha["preco_efetivo"],
        }
        for linha in reversed(historico)
    ],
    use_container_width=True,
    hide_index=True,
)
