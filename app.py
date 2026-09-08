"""
tela inicial do assistente de compras da reforma.

aqui fica o perfil financeiro, cdi, cotacao do dolar e os parametros
padrao do calculo de milhas, e os cartoes de credito cadastrados.

a pesquisa automatica na Calculadora consulta a livelo direto por
loja, ver services/pesquisa_produto.py e scrapers/livelo.py, nao
existe mais cadastro manual de parceiro aqui.

as outras telas ficam na pasta pages e aparecem automaticamente no
menu lateral do streamlit.
"""

import streamlit as st

from database import db
from services.cambio import buscar_cotacao_dolar
from utils.ui import renderizar_tabela_html

st.set_page_config(page_title="Assistente de Compras da Reforma", layout="wide")

db.inicializar_banco()

st.title("Assistente de Compras da Reforma")
st.write(
    "Utilize o menu lateral para acessar a Calculadora, a Wishlist e o "
    "Histórico de Preços."
)

st.header("Perfil Financeiro")

config = db.obter_configuracoes()


@st.cache_data(ttl=3600, show_spinner=False)
def _buscar_cotacao_automatica():
    """
    busca a cotacao do dolar em cache por uma hora, para nao precisar
    de um botao manual toda vez que a tela abre. se a busca falhar,
    devolve none e o campo cai de volta para o ultimo valor salvo.
    """
    return buscar_cotacao_dolar()


col_cotacao_1, col_cotacao_2 = st.columns([3, 1])
with col_cotacao_2:
    if st.button("Atualizar cotação agora"):
        _buscar_cotacao_automatica.clear()
        cotacao_atual = _buscar_cotacao_automatica()
        if cotacao_atual:
            st.session_state["cotacao_dolar_sugerida"] = cotacao_atual
            st.success(f"Cotação encontrada, R$ {cotacao_atual:.2f}.")
        else:
            st.warning("Não foi possível buscar a cotação agora, digite manualmente.")

if "cotacao_dolar_sugerida" not in st.session_state:
    cotacao_automatica = _buscar_cotacao_automatica()
    if cotacao_automatica:
        st.session_state["cotacao_dolar_sugerida"] = cotacao_automatica

cotacao_padrao = st.session_state.get("cotacao_dolar_sugerida", config["cotacao_dolar"])

with st.form("form_perfil"):
    col1, col2 = st.columns(2)
    with col1:
        cdi_mensal = st.number_input(
            "CDI mensal (%)", value=float(config["cdi_mensal"]), step=0.01, format="%.2f",
        )
        valor_milheiro_padrao = st.number_input(
            "Valor padrão do milheiro (R$)",
            value=float(config["valor_milheiro_padrao"]),
            step=1.0,
            format="%.2f",
            help="Usado como sugestão ao cadastrar uma oferta, sempre pode ser ajustado por oferta.",
        )
    with col2:
        cotacao_dolar = st.number_input(
            "Cotação do dólar (R$)", value=float(cotacao_padrao), step=0.01, format="%.2f",
            help="Preenchida automaticamente ao abrir a tela, edite se quiser usar outro valor.",
        )
        pontos_dolar_cartao_padrao = st.number_input(
            "Pontos por dólar padrão no cartão",
            value=float(config["pontos_dolar_cartao_padrao"]),
            step=0.5,
            help="Taxa de pontuação usada como sugestão para o cartão selecionado na Calculadora.",
        )

    enviado = st.form_submit_button("Salvar perfil")
    if enviado:
        db.salvar_configuracoes(cdi_mensal, cotacao_dolar, valor_milheiro_padrao, pontos_dolar_cartao_padrao)
        st.success("Perfil salvo com sucesso.")
        st.rerun()

st.header("Cartões Cadastrados")
st.caption(
    "Cadastre aqui os cartões que você usa para comprar, com a taxa de "
    "pontos por dólar gasto ou o cashback, para entrarem no cálculo."
)

cartoes = db.listar_cartoes()
if cartoes:
    renderizar_tabela_html(
        [
            {
                "cartão": cartao["nome"],
                "pontos por dólar": cartao["pontos_por_dolar"],
                "cashback (%)": cartao["cashback_pct"],
            }
            for cartao in cartoes
        ],
        colunas=[
            ("cartão", "Cartão"),
            ("pontos por dólar", "Pontos por Dólar"),
            ("cashback (%)", "Cashback (%)"),
        ],
    )
else:
    st.info("Nenhum cartão cadastrado ainda.")

with st.form("form_cartao", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        nome_cartao = st.text_input("Nome do cartão")
    with col2:
        pontos_dolar = st.number_input("Pontos por dólar gasto", min_value=0.0, step=0.5)
    with col3:
        cashback_cartao = st.number_input("Cashback (%)", min_value=0.0, step=0.5)

    enviado_cartao = st.form_submit_button("Adicionar cartão")
    if enviado_cartao:
        if nome_cartao.strip():
            db.adicionar_cartao(nome_cartao.strip(), pontos_dolar, cashback_cartao)
            st.success(f"Cartão {nome_cartao} adicionado com sucesso.")
            st.rerun()
        else:
            st.warning("Digite o nome do cartão.")