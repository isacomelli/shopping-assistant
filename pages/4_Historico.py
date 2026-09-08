"""
pagina de historico de precos, mostra a evolucao do preco efetivo de
um produto ao longo das pesquisas feitas.
"""

import statistics
from datetime import datetime, timedelta

import streamlit as st

from database import db
from utils.ui import renderizar_grafico_linha_svg


def _tentar_converter_data(texto):
    """
    converte o timestamp salvo pelo sqlite para datetime, devolvendo
    none se o formato vier diferente do esperado.
    """
    try:
        return datetime.strptime(texto, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def _data_do_registro(texto):
    data = _tentar_converter_data(texto)
    return data.date() if data else None


def _formatar_data(texto):
    data = _data_do_registro(texto)
    return data.strftime("%d/%m/%Y") if data else "não informada"


def _menor_preco_por_dia(linhas):
    menores = {}
    for linha in linhas:
        preco = linha["preco_efetivo"]
        data = _tentar_converter_data(linha["registrado_em"])
        if preco is None or data is None:
            continue
        dia = data.date()
        if dia not in menores or preco < menores[dia]:
            menores[dia] = preco
    return sorted(menores.items())


st.set_page_config(page_title="Histórico", layout="wide")

db.inicializar_banco()

st.title("Histórico de Preços")

produtos = db.listar_produtos()

if not produtos:
    st.info("Nenhum produto cadastrado ainda.")
    st.stop()

nome_escolhido = st.selectbox("Produto", [produto["nome"] for produto in produtos])
produto_atual = next(produto for produto in produtos if produto["nome"] == nome_escolhido)

historico = db.listar_historico(produto_atual["id"])

if not historico:
    st.info("Ainda não há histórico registrado para este produto, cadastre ofertas na Calculadora.")
    st.stop()

menores_por_dia = _menor_preco_por_dia(historico)
renderizar_grafico_linha_svg(
    rotulos=[dia.strftime("%d/%m/%Y") for dia, _ in menores_por_dia],
    valores=[preco for _, preco in menores_por_dia],
    mostrar_valores=True,
)

precos = [linha["preco_efetivo"] for linha in historico if linha["preco_efetivo"] is not None]

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Menor preço já encontrado", f"R$ {min(precos):.2f}")
with col2:
    trinta_dias_atras = datetime.now() - timedelta(days=30)
    precos_recentes = [
        linha["preco_efetivo"]
        for linha in historico
        if linha["preco_efetivo"] is not None
        and _data_do_registro(linha["registrado_em"])
        and _data_do_registro(linha["registrado_em"]) >= trinta_dias_atras.date()
    ]
    media_recente = statistics.mean(precos_recentes) if precos_recentes else statistics.mean(precos)
    st.metric("Média dos últimos 30 dias", f"R$ {media_recente:.2f}")
with col3:
    menor_preco_30_dias = min(precos_recentes) if precos_recentes else min(precos)
    st.metric("Menor preço dos últimos 30 dias", f"R$ {menor_preco_30_dias:.2f}")

if menor_preco_30_dias < media_recente:
    diferenca_pct = (1 - menor_preco_30_dias / media_recente) * 100
    st.success(f"Vale comprar agora, está {diferenca_pct:.1f}% abaixo da média dos últimos 30 dias.")
elif menor_preco_30_dias > media_recente:
    diferenca_pct = (menor_preco_30_dias / media_recente - 1) * 100
    st.warning(f"Está {diferenca_pct:.1f}% acima da média dos últimos 30 dias, talvez valha esperar.")
else:
    st.info("Preço atual está na média dos últimos 30 dias.")

st.header("Todas as Pesquisas Registradas")
if "historico_ordenacao" not in st.session_state:
    st.session_state["historico_ordenacao"] = "data"
    st.session_state["historico_ordenacao_reversa"] = True


def _alternar_ordenacao(chave):
    if st.session_state["historico_ordenacao"] == chave:
        st.session_state["historico_ordenacao_reversa"] = not st.session_state["historico_ordenacao_reversa"]
    else:
        st.session_state["historico_ordenacao"] = chave
        st.session_state["historico_ordenacao_reversa"] = False


ordenacao = st.session_state["historico_ordenacao"]
indicador = " ↓" if st.session_state["historico_ordenacao_reversa"] else " ↑"
cabecalho = st.columns([2.2, 1.7, 1.7, 1.7, 0.6, 0.4])
with cabecalho[0]:
    if st.button(f"Data{indicador if ordenacao == 'data' else ''}", key="ordenar_historico_data"):
        _alternar_ordenacao("data")
        st.rerun()
with cabecalho[1]:
    if st.button(f"Loja{indicador if ordenacao == 'loja' else ''}", key="ordenar_historico_loja"):
        _alternar_ordenacao("loja")
        st.rerun()
with cabecalho[2]:
    if st.button(f"Anunciado{indicador if ordenacao == 'anunciado' else ''}", key="ordenar_historico_anunciado"):
        _alternar_ordenacao("anunciado")
        st.rerun()
with cabecalho[3]:
    if st.button(f"Efetivo{indicador if ordenacao == 'efetivo' else ''}", key="ordenar_historico_efetivo"):
        _alternar_ordenacao("efetivo")
        st.rerun()
with cabecalho[4]:
    st.write("Editar")
with cabecalho[5]:
    st.write("Excluir")
    st.write("")

funcoes_ordenacao = {
    "data": lambda linha: _data_do_registro(linha["registrado_em"]) or datetime.min.date(),
    "loja": lambda linha: (linha["loja"] or "").lower(),
    "anunciado": lambda linha: linha["preco_anunciado"] or 0,
    "efetivo": lambda linha: linha["preco_efetivo"] or 0,
}
historico_exibido = sorted(
    historico,
    key=funcoes_ordenacao[ordenacao],
    reverse=st.session_state["historico_ordenacao_reversa"],
)

for linha in historico_exibido:
    col_data, col_loja, col_anunciado, col_efetivo, col_editar, col_excluir = st.columns(
        [2.2, 1.7, 1.7, 1.7, 0.6, 0.4]
    )
    col_data.write(_formatar_data(linha["registrado_em"]))
    col_loja.write(linha["loja"])
    col_anunciado.write(f"{linha['preco_anunciado']:.2f}")
    col_efetivo.write(f"{linha['preco_efetivo']:.2f}")
    oferta = db.encontrar_oferta_do_historico(linha["id"], produto_atual["id"])
    if col_editar.button("Editar", key=f"editar_historico_{linha['id']}") and oferta:
        st.session_state["produto_selecionado_nome"] = produto_atual["nome"]
        st.session_state["oferta_em_edicao_id"] = oferta["id"]
        st.switch_page("pages/1_Calculadora.py")
    if col_excluir.button("X", key=f"excluir_historico_{linha['id']}", help="Excluir registro"):
        db.excluir_historico(linha["id"], produto_atual["id"])
        st.rerun()
