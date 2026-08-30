"""
pagina da wishlist, a lista de produtos que faltam comprar para o
apartamento, com orcamento, preco alvo, melhor oferta encontrada e
status.
"""

import streamlit as st

from database import db

st.set_page_config(page_title="Wishlist", layout="wide")

db.inicializar_banco()

st.title("Wishlist da reforma")

config = db.obter_configuracoes()
produtos = db.listar_produtos()

if config["orcamento_mudanca"] > 0:
    total_comprado = 0.0
    for produto in produtos:
        if produto["status"] == "comprado":
            ofertas = db.listar_ofertas_por_produto(produto["id"])
            if ofertas:
                total_comprado += min(oferta["preco_efetivo"] or 0 for oferta in ofertas)

    st.header("Orcamento geral da mudanca")
    proporcao = min(total_comprado / config["orcamento_mudanca"], 1.0)
    st.progress(proporcao)
    st.write(
        f"comprado, r$ {total_comprado:.2f}, de um orcamento de "
        f"r$ {config['orcamento_mudanca']:.2f}, restam r$ {max(config['orcamento_mudanca'] - total_comprado, 0):.2f}"
    )

st.header("Itens da lista")

if not produtos:
    st.info("nenhum produto cadastrado ainda, adicione um na tela da calculadora")
else:
    rotulos_status = {"comprar": "comprar", "esperar": "esperar promocao", "comprado": "comprado"}

    for produto in produtos:
        ofertas = db.listar_ofertas_por_produto(produto["id"])
        melhor_preco = min((oferta["preco_efetivo"] or float("inf") for oferta in ofertas), default=None)
        melhor_loja = None
        if melhor_preco is not None:
            melhor_oferta = next(oferta for oferta in ofertas if oferta["preco_efetivo"] == melhor_preco)
            melhor_loja = melhor_oferta["loja"]

        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            with col1:
                st.markdown(f"**{produto['nome']}**")
                st.caption(produto["categoria"] or "sem categoria")
            with col2:
                st.write(f"orcamento, r$ {produto['orcamento'] or 0:.2f}")
                st.write(f"preco alvo, r$ {produto['preco_alvo'] or 0:.2f}")
            with col3:
                if melhor_preco is not None:
                    st.write(f"melhor preco, r$ {melhor_preco:.2f}")
                    st.write(f"em {melhor_loja}")
                    if produto["preco_alvo"] and melhor_preco <= produto["preco_alvo"]:
                        st.success("abaixo da meta")
                else:
                    st.write("sem ofertas cadastradas")
            with col4:
                novo_status = st.selectbox(
                    "status",
                    list(rotulos_status.keys()),
                    format_func=lambda chave: rotulos_status[chave],
                    index=list(rotulos_status.keys()).index(produto["status"]),
                    key=f"status_{produto['id']}",
                )
                if novo_status != produto["status"]:
                    db.atualizar_status_produto(produto["id"], novo_status)
                    st.rerun()
