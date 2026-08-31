"""
pagina da wishlist, a lista de produtos que faltam comprar para o
apartamento, com orcamento, preco alvo, melhor oferta encontrada e
status.
"""

import streamlit as st

from database import db

st.set_page_config(page_title="Wishlist", layout="wide")

db.inicializar_banco()

st.title("Wishlist da Reforma")

config = db.obter_configuracoes()
produtos = db.listar_produtos()

if config["orcamento_mudanca"] > 0:
    total_comprado = 0.0
    for produto in produtos:
        if produto["status"] == "comprado":
            ofertas = db.listar_ofertas_por_produto(produto["id"])
            if ofertas:
                total_comprado += min(oferta["preco_efetivo"] or 0 for oferta in ofertas)

    st.header("Orçamento Geral da Mudança")
    proporcao = min(total_comprado / config["orcamento_mudanca"], 1.0)
    st.progress(proporcao)
    st.write(
        f"Comprado, R$ {total_comprado:.2f}, de um orçamento de "
        f"R$ {config['orcamento_mudanca']:.2f}, restam R$ {max(config['orcamento_mudanca'] - total_comprado, 0):.2f}."
    )

st.header("Itens da Lista")

if not produtos:
    st.info("Nenhum produto cadastrado ainda, adicione um na tela da Calculadora.")
else:
    rotulos_status = {"comprar": "Comprar", "esperar": "Esperar promoção", "comprado": "Comprado"}

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
                st.caption(produto["categoria"] or "Sem categoria")
            with col2:
                st.write(f"Orçamento, R$ {produto['orcamento'] or 0:.2f}")
                st.write(f"Preço alvo, R$ {produto['preco_alvo'] or 0:.2f}")
            with col3:
                if melhor_preco is not None:
                    st.write(f"Melhor preço, R$ {melhor_preco:.2f}")
                    st.write(f"Em {melhor_loja}")
                    if produto["preco_alvo"] and melhor_preco <= produto["preco_alvo"]:
                        st.success("Abaixo da meta")
                else:
                    st.write("Sem ofertas cadastradas")
            with col4:
                novo_status = st.selectbox(
                    "Status",
                    list(rotulos_status.keys()),
                    format_func=lambda chave: rotulos_status[chave],
                    index=list(rotulos_status.keys()).index(produto["status"]),
                    key=f"status_{produto['id']}",
                )
                if novo_status != produto["status"]:
                    db.atualizar_status_produto(produto["id"], novo_status)
                    st.rerun()
