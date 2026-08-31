"""
pagina de consulta de parceiros por loja especifica.

esta pagina deixou de depender da listagem completa de parceiros da
livelo como fluxo principal, ja que aquela pagina e a mais visada por
protecao anti bot do site, ver scrapers/livelo.py. agora a consulta e
feita por loja, do mesmo jeito que o fluxo automatico da calculadora
usa, e o resultado fica guardado em cache por 24 horas.

a listagem completa antiga foi mantida no final da pagina, apenas
como um recurso manual avancado, para quando fizer sentido revisar o
catalogo inteiro de uma vez, sabendo que ela costuma ser bloqueada
com mais frequencia.

sobre a esfera, como o site so mostra os parceiros depois de login
numa conta pessoal, esta pagina nao inclui consulta automatica para
ela, os pontos esfera continuam sendo cadastrados manualmente na
calculadora.
"""

import streamlit as st

from database import db
from scrapers.livelo import ErroScraperLivelo, buscar_parceiro_por_loja, buscar_parceiros_livelo
from scrapers.meliuz import ErroScraperMeliuz, buscar_cashback_por_loja
from utils.ui import renderizar_tabela_html

st.set_page_config(page_title="Parceiros por Loja", layout="wide")

db.inicializar_banco()

st.title("Parceiros por Loja")
st.write(
    "Consulte a taxa de pontos da Livelo ou o percentual de cashback do Méliuz para "
    "uma loja específica. A consulta é feita sob demanda e o resultado fica guardado "
    "por 24 horas, para não precisar abrir o navegador de novo em toda pesquisa."
)

st.header("Consultar Livelo")

col_livelo_1, col_livelo_2 = st.columns([3, 1])
with col_livelo_1:
    nome_loja_livelo = st.text_input("Nome da loja", key="nome_loja_livelo")
with col_livelo_2:
    st.write("")
    st.write("")
    consultar_livelo = st.button("Consultar Livelo")

if consultar_livelo and nome_loja_livelo.strip():
    cache = db.obter_cache_parceiro_loja(nome_loja_livelo.strip(), "livelo")
    if cache:
        st.info(
            f"Resultado do cache das últimas 24 horas, {cache['pontos_por_real']} pontos por "
            f"{cache['moeda_padrao']}, consultado em {cache['atualizado_em']}."
        )
    else:
        with st.spinner("Consultando a página da Livelo, isso pode levar cerca de um minuto..."):
            try:
                resultado = buscar_parceiro_por_loja(nome_loja_livelo.strip())
                db.salvar_cache_parceiro_loja(
                    nome_loja_livelo.strip(), "livelo",
                    encontrado=resultado.encontrado,
                    pontos_por_real=resultado.pontos_por_real,
                    moeda_padrao=resultado.moeda_padrao,
                    regras_extras="; ".join(resultado.regras_extras),
                    url_consultada=resultado.url_consultada,
                )
                if resultado.encontrado:
                    st.success(
                        f"{resultado.pontos_por_real} pontos por {resultado.moeda_padrao} "
                        f"para {nome_loja_livelo}."
                    )
                    if resultado.regras_extras:
                        st.caption("Regras adicionais encontradas na página, " + "; ".join(resultado.regras_extras))
                else:
                    st.warning(resultado.mensagem)
            except ErroScraperLivelo as erro:
                st.error(f"Não foi possível concluir a consulta. Detalhe técnico, {erro}")

st.header("Consultar Méliuz")

col_meliuz_1, col_meliuz_2 = st.columns([3, 1])
with col_meliuz_1:
    nome_loja_meliuz = st.text_input("Nome da loja", key="nome_loja_meliuz")
with col_meliuz_2:
    st.write("")
    st.write("")
    consultar_meliuz = st.button("Consultar Méliuz")

if consultar_meliuz and nome_loja_meliuz.strip():
    cache = db.obter_cache_parceiro_loja(nome_loja_meliuz.strip(), "meliuz")
    if cache:
        st.info(
            f"Resultado do cache das últimas 24 horas, {cache['cashback_pct']}% de cashback, "
            f"consultado em {cache['atualizado_em']}."
        )
    else:
        with st.spinner("Consultando a página do Méliuz, isso pode levar cerca de um minuto..."):
            try:
                resultado = buscar_cashback_por_loja(nome_loja_meliuz.strip())
                db.salvar_cache_parceiro_loja(
                    nome_loja_meliuz.strip(), "meliuz",
                    encontrado=resultado.encontrado,
                    cashback_pct=resultado.cashback_pct,
                    url_consultada=resultado.url_consultada,
                )
                if resultado.encontrado:
                    st.success(f"{resultado.cashback_pct}% de cashback para {nome_loja_meliuz}.")
                else:
                    st.warning(resultado.mensagem)
            except ErroScraperMeliuz as erro:
                st.error(f"Não foi possível concluir a consulta. Detalhe técnico, {erro}")

st.divider()
st.header("Listagem completa da Livelo (avançado, manual)")
st.caption(
    "Este recurso baixa o catálogo inteiro de parceiros de uma só vez. É a página mais "
    "visada por proteção contra navegador automatizado do site, então é comum que a "
    "atualização abaixo falhe mesmo quando a consulta por loja, acima, funciona "
    "normalmente. Prefira a consulta por loja sempre que possível."
)

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("Atualizar lista completa agora"):
        with st.spinner("Lendo a página pública de parceiros da Livelo, isso pode levar um minuto..."):
            try:
                parceiros = buscar_parceiros_livelo()
                db.salvar_parceiros_livelo(parceiros)
                st.success(f"{len(parceiros)} parceiros atualizados.")
            except Exception as erro:
                st.error(
                    "Não foi possível atualizar agora, o site pode ter mudado, estar "
                    "indisponível ou ter bloqueado o navegador automatizado. Detalhe "
                    f"técnico, {erro}"
                )

parceiros_salvos = db.listar_parceiros_livelo()

if not parceiros_salvos:
    st.info("Nenhum parceiro salvo ainda, clique em Atualizar lista completa agora.")
    st.stop()

termo_busca = st.text_input("Buscar parceiro pelo nome, na lista já salva")

if termo_busca.strip():
    parceiros_filtrados = db.buscar_parceiro_livelo_por_nome(termo_busca.strip())
else:
    parceiros_filtrados = parceiros_salvos

st.caption(f"{len(parceiros_filtrados)} parceiros, atualizado pela última vez em {parceiros_salvos[0]['atualizado_em']}.")

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
