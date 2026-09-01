"""
pagina de parceiros da livelo.

le a lista publica de parceiros do compre e pontue sob demanda,
quando voce clica no botao, sem login e sem acessar conta nenhuma.
"""

import streamlit as st

from database import db
from scrapers.livelo import ErroScraperLivelo, buscar_parceiros_livelo
from utils.ui import renderizar_tabela_html

st.set_page_config(page_title="Parceiros Livelo", layout="wide")

db.inicializar_banco()

st.title("Parceiros Livelo")
st.write(
    "esta lista vem da pagina publica de parceiros do compre e pontue "
    "da livelo, sem precisar entrar em nenhuma conta."
)

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("atualizar lista agora"):
        with st.spinner("lendo a pagina publica de parceiros da livelo, isso pode levar um minuto"):
            try:
                parceiros = buscar_parceiros_livelo()
                db.salvar_parceiros_livelo(parceiros)
                st.success(f"{len(parceiros)} parceiros atualizados")
            except ErroScraperLivelo as erro:
                st.error(
                    "nao foi possivel atualizar agora, o site pode ter mudado, "
                    "bloqueado o acesso automatizado, ou estar indisponivel no "
                    f"momento. detalhe tecnico, {erro}"
                )

parceiros_salvos = db.listar_parceiros_livelo()

if not parceiros_salvos:
    st.info("nenhum parceiro salvo ainda, clique em atualizar lista agora")
    st.stop()

termo_busca = st.text_input("buscar parceiro pelo nome")

if termo_busca.strip():
    parceiros_filtrados = db.buscar_parceiro_livelo_por_nome(termo_busca.strip())
else:
    parceiros_filtrados = parceiros_salvos

st.caption(f"{len(parceiros_filtrados)} parceiros, atualizado pela ultima vez em {parceiros_salvos[0]['atualizado_em']}")

renderizar_tabela_html(
    [
        {
            "parceiro": parceiro["nome"],
            "pontos por real ou dólar": parceiro["pontos_padrao"],
            "moeda": parceiro["moeda_padrao"],
            "pontos clube": parceiro["pontos_clube"],
            "em promoção": "Sim" if parceiro["em_promocao"] else "Não",
            "pontos anteriores": parceiro["pontos_anteriores"],
        }
        for parceiro in parceiros_filtrados
    ],
    colunas=[
        ("parceiro", "Parceiro"),
        ("pontos por real ou dólar", "Pontos por Real ou Dólar"),
        ("moeda", "Moeda"),
        ("pontos clube", "Pontos Clube"),
        ("em promoção", "Em Promoção"),
        ("pontos anteriores", "Pontos Anteriores"),
    ],
)
