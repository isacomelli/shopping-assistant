"""
pagina da wishlist, a lista de produtos que faltam comprar para o
apartamento, com orcamento por item, preco alvo, melhor oferta
encontrada e status.
"""

import streamlit as st

from database import db

st.set_page_config(page_title="Wishlist", layout="wide")

db.inicializar_banco()

st.title("Wishlist")

produtos = db.listar_produtos()

st.header("Adicionar produto")

with st.form("form_novo_produto_wishlist"):
    col_novo_1, col_novo_2 = st.columns(2)
    with col_novo_1:
        nome_novo = st.text_input("Nome do produto")
        categoria_nova = st.text_input("Categoria")
    with col_novo_2:
        preco_alvo_novo = st.number_input("Preço alvo (R$)", min_value=0.0, step=50.0)
        orcamento_novo = st.number_input("Orçamento máximo (R$)", min_value=0.0, step=50.0)
    criar = st.form_submit_button("Criar produto")
    if criar:
        if not nome_novo.strip():
            st.warning("Informe o nome do produto.")
        else:
            db.adicionar_produto(
                nome_novo.strip(), categoria_nova.strip(), orcamento_novo, preco_alvo_novo,
            )
            st.session_state["produto_selecionado_nome"] = nome_novo.strip()
            st.session_state["disparar_pesquisa_automatica"] = True
            st.switch_page("pages/1_Calculadora.py")

st.header("Itens da Lista")

if not produtos:
    st.info("Nenhum produto cadastrado ainda.")
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
                st.write(f"Orçamento: R$ {produto['orcamento'] or 0:.2f}")
                st.write(f"Preço alvo: R$ {produto['preco_alvo'] or 0:.2f}")
            with col3:
                if melhor_preco is not None:
                    st.write(f"Melhor preço, R$ {melhor_preco:.2f} ({melhor_loja})")
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

            with st.expander("Editar produto"):
                with st.form(f"form_editar_produto_{produto['id']}"):
                    nome_editado = st.text_input("Nome", value=produto["nome"])
                    categoria_editada = st.text_input(
                        "Categoria", value=produto["categoria"] or ""
                    )
                    col_edicao_1, col_edicao_2 = st.columns(2)
                    with col_edicao_1:
                        preco_alvo_editado = st.number_input(
                            "Preço alvo (R$)", min_value=0.0, step=50.0,
                            value=float(produto["preco_alvo"] or 0),
                        )
                    with col_edicao_2:
                        orcamento_editado = st.number_input(
                            "Orçamento máximo (R$)", min_value=0.0, step=50.0,
                            value=float(produto["orcamento"] or 0),
                        )
                    salvar_produto = st.form_submit_button("Salvar alterações")
                    if salvar_produto and nome_editado.strip():
                        db.atualizar_produto(
                            produto["id"], nome_editado.strip(), categoria_editada.strip(),
                            orcamento_editado, preco_alvo_editado,
                        )
                        if st.session_state.get("produto_selecionado_nome") == produto["nome"]:
                            st.session_state["produto_selecionado_nome"] = nome_editado.strip()
                        st.rerun()

                if st.button("Excluir produto", key=f"excluir_produto_{produto['id']}"):
                    db.excluir_produto(produto["id"])
                    if st.session_state.get("produto_selecionado_nome") == produto["nome"]:
                        st.session_state.pop("produto_selecionado_nome", None)
                    st.rerun()
