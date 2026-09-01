"""
tela inicial do assistente de compras da reforma.

aqui fica o perfil financeiro, cdi, cotacao do dolar e os parametros
padrao do calculo de milhas, os cartoes de credito cadastrados, e o
cadastro manual dos parceiros Livelo.

sobre o cadastro de parceiros Livelo, ele e manual porque o site da
livelo bloqueia qualquer acesso automatizado a nivel de dominio,
atraves do akamai, o bloqueio acontece antes mesmo do conteudo da
pagina carregar, entao nao importa qual pagina do site e consultada,
o resultado e sempre access denied. cadastrar aqui uma vez por
parceiro, com o nome exatamente como ele costuma aparecer nos
resultados do buscape, e o que permite a pesquisa automatica da
Calculadora casar cada loja encontrada com a pontuacao Livelo certa,
sem precisar digitar isso de novo a cada pesquisa.

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

st.header("Parceiros Livelo")
st.caption(
    "Cadastro manual, atualizado por você de vez em quando, porque o site "
    "da Livelo bloqueia qualquer acesso automatizado. Use aqui exatamente "
    "o nome como a loja costuma aparecer nas buscas, por exemplo Amazon "
    "ou Fast Shop, para a pesquisa automática da Calculadora conseguir "
    "casar a loja encontrada com a pontuação certa."
)

parceiros_livelo = db.listar_parceiros_livelo()
if parceiros_livelo:
    renderizar_tabela_html(
        [
            {
                "parceiro": parceiro["nome"],
                "pontos por real ou dólar": parceiro["pontos_padrao"],
                "moeda": parceiro["moeda_padrao"],
                "atualizado em": parceiro["atualizado_em"],
            }
            for parceiro in parceiros_livelo
        ],
        colunas=[
            ("parceiro", "Parceiro"),
            ("pontos por real ou dólar", "Pontos por Real ou Dólar"),
            ("moeda", "Moeda"),
            ("atualizado em", "Atualizado em"),
        ],
    )
else:
    st.info("Nenhum parceiro Livelo cadastrado ainda.")

with st.form("form_parceiro_livelo", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        nome_parceiro = st.text_input("Nome do parceiro, igual aparece no BuscaPé")
    with col2:
        pontos_parceiro = st.number_input("Pontos por real (ou por dólar)", min_value=0.0, step=0.5)
    with col3:
        moeda_parceiro = st.selectbox("Moeda da taxa", ["R$", "U$"])

    enviado_parceiro = st.form_submit_button("Cadastrar ou atualizar parceiro")
    if enviado_parceiro:
        if nome_parceiro.strip():
            db.adicionar_parceiro_livelo_manual(nome_parceiro.strip(), pontos_parceiro, moeda_parceiro)
            st.success(f"Parceiro {nome_parceiro} cadastrado com sucesso.")
            st.rerun()
        else:
            st.warning("Digite o nome do parceiro.")

if parceiros_livelo:
    with st.expander("Remover um parceiro cadastrado"):
        nome_para_remover = st.selectbox(
            "Parceiro", [parceiro["nome"] for parceiro in parceiros_livelo], key="remover_parceiro_livelo",
        )
        if st.button("Remover parceiro selecionado"):
            parceiro_para_remover = next(p for p in parceiros_livelo if p["nome"] == nome_para_remover)
            db.remover_parceiro_livelo(parceiro_para_remover["codigo"])
            st.success(f"Parceiro {nome_para_remover} removido.")
            st.rerun()
