"""
tela inicial do assistente de compras da reforma.

aqui fica o perfil financeiro, cdi, valor dos pontos, cotacao do
dolar, e os cartoes de credito cadastrados. as outras telas ficam na
pasta pages e aparecem automaticamente no menu lateral do streamlit.
"""

import streamlit as st

from database import db
from services.cambio import buscar_cotacao_dolar

st.set_page_config(page_title="Assistente de Compras da Reforma", layout="wide")

db.inicializar_banco()

st.title("Assistente de Compras da Reforma")
st.write(
    "use o menu lateral para acessar a calculadora, a wishlist, o "
    "historico de precos e a lista de parceiros da livelo."
)

st.header("Perfil financeiro")

config = db.obter_configuracoes()

col_cotacao_1, col_cotacao_2 = st.columns([3, 1])
with col_cotacao_2:
    if st.button("buscar cotacao do dolar agora"):
        cotacao_atual = buscar_cotacao_dolar()
        if cotacao_atual:
            st.session_state["cotacao_dolar_sugerida"] = cotacao_atual
            st.success(f"cotacao encontrada, r$ {cotacao_atual:.2f}")
        else:
            st.warning("nao foi possivel buscar a cotacao agora, digite manualmente")

cotacao_padrao = st.session_state.get("cotacao_dolar_sugerida", config["cotacao_dolar"])

with st.form("form_perfil"):
    col1, col2 = st.columns(2)
    with col1:
        cdi_mensal = st.number_input(
            "cdi mensal (%)", value=float(config["cdi_mensal"]), step=0.01, format="%.2f",
        )
        valor_livelo = st.number_input(
            "valor do ponto livelo (r$)", value=float(config["valor_livelo"]), step=0.001, format="%.3f",
        )
        valor_esfera = st.number_input(
            "valor do ponto esfera (r$)", value=float(config["valor_esfera"]), step=0.001, format="%.3f",
        )
    with col2:
        cotacao_dolar = st.number_input(
            "cotacao do dolar (r$)", value=float(cotacao_padrao), step=0.01, format="%.2f",
        )
        orcamento_mudanca = st.number_input(
            "orcamento total da mudanca (r$)", value=float(config["orcamento_mudanca"]), step=100.0, format="%.2f",
        )

    enviado = st.form_submit_button("salvar perfil")
    if enviado:
        db.salvar_configuracoes(cdi_mensal, valor_livelo, valor_esfera, cotacao_dolar, orcamento_mudanca)
        st.success("perfil salvo")
        st.rerun()

st.header("Cartoes cadastrados")
st.caption(
    "cadastre aqui os cartoes que voce usa para comprar, com a taxa de "
    "pontos por dolar gasto ou o cashback, para entrarem no calculo."
)

cartoes = db.listar_cartoes()
if cartoes:
    st.dataframe(
        [
            {
                "cartao": cartao["nome"],
                "pontos por dolar": cartao["pontos_por_dolar"],
                "cashback (%)": cartao["cashback_pct"],
            }
            for cartao in cartoes
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("nenhum cartao cadastrado ainda")

with st.form("form_cartao", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        nome_cartao = st.text_input("nome do cartao")
    with col2:
        pontos_dolar = st.number_input("pontos por dolar gasto", min_value=0.0, step=0.5)
    with col3:
        cashback_cartao = st.number_input("cashback (%)", min_value=0.0, step=0.5)

    enviado_cartao = st.form_submit_button("adicionar cartao")
    if enviado_cartao:
        if nome_cartao.strip():
            db.adicionar_cartao(nome_cartao.strip(), pontos_dolar, cashback_cartao)
            st.success(f"cartao {nome_cartao} adicionado")
            st.rerun()
        else:
            st.warning("digite o nome do cartao")
