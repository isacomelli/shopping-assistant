"""
pagina de pesquisa e calculo do preco real de um produto.

o valor dos pontos de cada oferta e calculado pelo metodo do
milheiro, juntando os pontos do site parceiro, livelo ou esfera, com
os pontos ganhos direto no cartao selecionado. no pix nao existe
cartao envolvido, entao so o site parceiro pontua, ver
engine/price_engine.py para o passo a passo completo da conta.
"""

import streamlit as st

from database import db
from engine.price_engine import Oferta, ranquear_ofertas, simular_parcelamento
from utils.ui import renderizar_grafico_linha_svg, renderizar_tabela_html

st.set_page_config(page_title="Calculadora", layout="wide")

db.inicializar_banco()

st.title("Calculadora de Compra Inteligente")

config = db.obter_configuracoes()
produtos = db.listar_produtos()

st.header("1. Escolha ou crie um produto")

nomes_produtos = [produto["nome"] for produto in produtos]
opcao = st.selectbox(
    "Produto", ["Novo produto"] + nomes_produtos, index=0,
)

if opcao == "Novo produto":
    with st.form("form_novo_produto"):
        col1, col2, col3 = st.columns(3)
        with col1:
            nome_novo = st.text_input("Nome do produto")
        with col2:
            categoria_nova = st.text_input("Categoria")
        with col3:
            preco_alvo_novo = st.number_input("Preço alvo (R$)", min_value=0.0, step=50.0)
        orcamento_novo = st.number_input("Orçamento máximo (R$)", min_value=0.0, step=50.0)
        criar = st.form_submit_button("Criar produto")
        if criar and nome_novo.strip():
            produto_id = db.adicionar_produto(nome_novo.strip(), categoria_nova, orcamento_novo, preco_alvo_novo)
            st.success(f"Produto {nome_novo} criado com sucesso.")
            st.rerun()
    st.stop()

produto_atual = next(produto for produto in produtos if produto["nome"] == opcao)
produto_id = produto_atual["id"]

st.caption(
    f"Categoria, {produto_atual['categoria'] or 'sem categoria'}, "
    f"preço alvo, R$ {produto_atual['preco_alvo'] or 0:.2f}, "
    f"orçamento, R$ {produto_atual['orcamento'] or 0:.2f}."
)

st.header("2. Adicionar uma oferta")

parceiros_livelo = db.listar_parceiros_livelo()
nomes_parceiros = [parceiro["nome"] for parceiro in parceiros_livelo]

cartoes_cadastrados = db.listar_cartoes()
nomes_cartoes = [cartao["nome"] for cartao in cartoes_cadastrados]

with st.form("form_oferta", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        loja = st.text_input("Loja")
        tipo = st.selectbox("Tipo de oferta", ["online", "parceiro de pontos", "loja física", "negociação"])
    with col2:
        preco_pix = st.number_input("Preço no Pix (R$)", min_value=0.0, step=10.0)
        preco_cartao = st.number_input("Preço no cartão (R$)", min_value=0.0, step=10.0)
    with col3:
        parcelas = st.number_input("Número de parcelas", min_value=1, max_value=24, value=1)
        frete = st.number_input("Frete (R$)", min_value=0.0, step=10.0)

    st.subheader("Pontos e milhas")
    st.caption(
        "O valor dos pontos é calculado pelo método do milheiro, somando os "
        "pontos do site parceiro com os pontos do cartão selecionado. No Pix, "
        "só o site parceiro pontua, já que não existe cartão envolvido."
    )
    col4, col5, col6 = st.columns(3)
    with col4:
        parceiro_selecionado = st.selectbox(
            "Parceiro Livelo ou Esfera (opcional, preenche o campo abaixo)", ["nenhum"] + nomes_parceiros,
        )
        pontos_por_real_sugerido = 0.0
        if parceiro_selecionado != "nenhum":
            parceiro_info = next(p for p in parceiros_livelo if p["nome"] == parceiro_selecionado)
            pontos_por_real_sugerido = float(parceiro_info["pontos_padrao"])
        pontos_por_real = st.number_input(
            "Pontos por real no site parceiro", min_value=0.0, value=pontos_por_real_sugerido, step=0.5,
        )
    with col5:
        cartao_selecionado = st.selectbox(
            "Cartão usado na compra", ["nenhum"] + nomes_cartoes,
        )
        if cartao_selecionado != "nenhum":
            cartao_info = next(c for c in cartoes_cadastrados if c["nome"] == cartao_selecionado)
            pontos_dolar_cartao_padrao = float(cartao_info["pontos_por_dolar"])
            cashback_padrao = float(cartao_info["cashback_pct"])
        else:
            pontos_dolar_cartao_padrao = float(config["pontos_dolar_cartao_padrao"])
            cashback_padrao = 0.0
        pontos_por_dolar_cartao = st.number_input(
            "Pontos por dólar no cartão", min_value=0.0, value=pontos_dolar_cartao_padrao, step=0.5,
        )
        cashback_pct = st.number_input("Cashback (%)", min_value=0.0, value=cashback_padrao, step=0.5)
    with col6:
        percentual_bonus_transferencia = st.number_input(
            "Bônus de transferência para milhas (%)",
            min_value=0.0,
            value=0.0,
            step=5.0,
            help="Bônus vigente na promoção de transferência para TudoAzul, Smiles ou LATAM Pass.",
        )
        valor_milheiro = st.number_input(
            "Valor do milheiro (R$)",
            min_value=0.0,
            value=float(config["valor_milheiro_padrao"]),
            step=1.0,
        )
        cupom = st.number_input("Cupom de desconto (R$)", min_value=0.0, step=10.0)

    st.subheader("Detalhes extras")
    col7, col8 = st.columns(2)
    with col7:
        observacoes = st.text_area("Observações")
    with col8:
        validade = st.text_input("Validade da oferta, se houver")
        confianca = st.selectbox("Confiança", ["confirmada", "até domingo", "expirada"])

    salvar_oferta = st.form_submit_button("Calcular e salvar oferta")

    if salvar_oferta:
        if not loja.strip() or preco_pix <= 0 or preco_cartao <= 0:
            st.warning("Preencha ao menos a loja, o preço no Pix e o preço no cartão.")
        else:
            oferta = Oferta(
                loja=loja.strip(),
                preco_pix=preco_pix,
                preco_cartao=preco_cartao,
                parcelas=int(parcelas),
                pontos_por_real=pontos_por_real,
                cotacao_dolar=float(config["cotacao_dolar"]),
                cashback_pct=cashback_pct,
                frete=frete,
                cupom=cupom,
                tipo=tipo,
                pontos_por_dolar_cartao=pontos_por_dolar_cartao,
                percentual_bonus_transferencia=percentual_bonus_transferencia,
                valor_milheiro=valor_milheiro,
            )
            resultado = ranquear_ofertas([oferta], float(config["cdi_mensal"]))[0]

            db.adicionar_oferta(
                produto_id=produto_id,
                loja=oferta.loja,
                tipo=oferta.tipo,
                preco_pix=oferta.preco_pix,
                preco_cartao=oferta.preco_cartao,
                parcelas=oferta.parcelas,
                pontos_por_real=oferta.pontos_por_real,
                pontos_por_dolar_cartao=oferta.pontos_por_dolar_cartao,
                percentual_bonus_transferencia=oferta.percentual_bonus_transferencia,
                valor_milheiro=oferta.valor_milheiro,
                cashback_pct=oferta.cashback_pct,
                frete=oferta.frete,
                cupom=oferta.cupom,
                observacoes=observacoes,
                validade=validade,
                confianca=confianca,
                preco_efetivo=resultado.preco_efetivo,
            )
            db.registrar_historico(produto_id, oferta.loja, oferta.preco_cartao, resultado.preco_efetivo)
            st.success(f"Oferta da {loja} salva, preço efetivo R$ {resultado.preco_efetivo:.2f}.")
            st.rerun()

st.header("3. Ranking das ofertas cadastradas")

ofertas_salvas = db.listar_ofertas_por_produto(produto_id)

if not ofertas_salvas:
    st.info("Nenhuma oferta cadastrada ainda para este produto.")
    st.stop()

ofertas_para_calculo = [
    Oferta(
        loja=oferta["loja"],
        preco_pix=oferta["preco_pix"],
        preco_cartao=oferta["preco_cartao"],
        parcelas=oferta["parcelas"],
        pontos_por_real=oferta["pontos_por_real"],
        cotacao_dolar=float(config["cotacao_dolar"]),
        cashback_pct=oferta["cashback_pct"],
        frete=oferta["frete"],
        cupom=oferta["cupom"],
        tipo=oferta["tipo"],
        pontos_por_dolar_cartao=oferta["pontos_por_dolar_cartao"],
        percentual_bonus_transferencia=oferta["percentual_bonus_transferencia"],
        valor_milheiro=oferta["valor_milheiro"],
    )
    for oferta in ofertas_salvas
]

ranking = ranquear_ofertas(ofertas_para_calculo, float(config["cdi_mensal"]))

medalhas = ["1º lugar", "2º lugar", "3º lugar"]

for posicao, resultado in enumerate(ranking):
    rotulo = medalhas[posicao] if posicao < len(medalhas) else f"{posicao + 1}º lugar"
    with st.expander(
        f"{rotulo}, {resultado.loja}, preço efetivo R$ {resultado.preco_efetivo:.2f}, "
        f"melhor forma de pagamento, {resultado.melhor_forma_pagamento}",
        expanded=(posicao == 0),
    ):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Pagando no Pix**")
            st.write(f"Preço Pix, R$ {resultado.preco_efetivo_pix + resultado.valor_pontos_pix + resultado.cashback_valor_pix:.2f}")
            st.write(f"Valor dos pontos/milhas, -R$ {resultado.valor_pontos_pix:.2f}")
            st.write(f"Cashback, -R$ {resultado.cashback_valor_pix:.2f}")
            st.write(f"Preço efetivo Pix, R$ {resultado.preco_efetivo_pix:.2f}")
        with col2:
            st.markdown("**Pagando parcelado no cartão**")
            st.write(f"Preço anunciado, R$ {resultado.preco_anunciado:.2f}")
            st.write(f"Rendimento do parcelamento, -R$ {resultado.rendimento_parcelamento:.2f}")
            st.write(f"Valor dos pontos/milhas, -R$ {resultado.valor_pontos_cartao:.2f}")
            st.write(f"Cashback, -R$ {resultado.cashback_valor_cartao:.2f}")
            st.write(f"Preço efetivo cartão, R$ {resultado.preco_efetivo_cartao:.2f}")

        st.markdown(f"**Economia em relação ao preço anunciado, R$ {resultado.economia_vs_anunciado:.2f}**")

st.header("4. Simulador, a partir de quantas parcelas compensa")

if ofertas_salvas:
    oferta_base = ofertas_para_calculo[0]
    simulacao = simular_parcelamento(
        oferta_base.preco_pix, oferta_base.preco_cartao, float(config["cdi_mensal"]), max_parcelas=12,
    )
    renderizar_grafico_linha_svg(
        rotulos=[f"{linha['parcelas']}x" for linha in simulacao],
        valores=[linha["custo_efetivo"] for linha in simulacao],
    )
    st.caption(f"Simulação baseada na primeira oferta cadastrada, {oferta_base.loja}.")
