"""
pagina de pesquisa e calculo do preco real de um produto.

o fluxo agora comeca, opcionalmente, por uma busca automatica no
buscape. essa busca devolve um pequeno conjunto de lojas com preco,
e so a partir dai o app consulta livelo e meliuz, loja a loja, em vez
de baixar o catalogo inteiro de parceiros. essa mudanca de ordem foi
combinada porque a listagem completa da livelo e a pagina mais visada
por protecao anti bot do site, enquanto consultar uma loja especifica
se parece mais com a navegacao de uma pessoa real, ver
scrapers/livelo.py e scrapers/buscape.py para os detalhes.

quando a busca automatica falhar, por bloqueio do site ou por
qualquer outro motivo, o cadastro manual de uma oferta continua
funcionando normalmente, exatamente como antes.

sobre pontos e milhas, o valor dos pontos de cada oferta e calculado
pelo metodo do milheiro, juntando os pontos do site parceiro (livelo
ou esfera) com os pontos ganhos direto no cartao selecionado, ver
engine/price_engine.py para o passo a passo da conta.
"""

import streamlit as st

from database import db
from engine.price_engine import Oferta, ranquear_ofertas, simular_parcelamento
from scrapers.buscape import ErroScraperBuscape, buscar_ofertas_buscape
from scrapers.livelo import ErroScraperLivelo, buscar_parceiro_por_loja
from scrapers.meliuz import ErroScraperMeliuz, buscar_cashback_por_loja
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

st.header("2. Buscar ofertas automaticamente (via BuscaPé)")
st.caption(
    "Esta busca consulta o BuscaPé pelo nome do produto e traz um pequeno conjunto de "
    "lojas com preço. Como o site pode bloquear o navegador automatizado a qualquer "
    "momento, se a busca falhar, cadastre a oferta manualmente na seção 3, abaixo."
)

col_busca_1, col_busca_2 = st.columns([3, 1])
with col_busca_1:
    termo_busca_produto = st.text_input(
        "Termo de busca", value=produto_atual["nome"], key="termo_busca_buscape",
    )
with col_busca_2:
    st.write("")
    st.write("")
    buscar_agora = st.button("Buscar no BuscaPé")

if buscar_agora and termo_busca_produto.strip():
    with st.spinner("Consultando o BuscaPé, isso pode levar cerca de um minuto..."):
        try:
            resultados = buscar_ofertas_buscape(termo_busca_produto.strip())
            st.session_state["resultados_buscape"] = resultados
            st.success(f"{len(resultados)} oferta(s) encontrada(s).")
        except ErroScraperBuscape as erro:
            st.session_state.pop("resultados_buscape", None)
            st.error(f"Não foi possível concluir a busca automática. Detalhe técnico, {erro}")

resultados_buscape = st.session_state.get("resultados_buscape", [])

if resultados_buscape:
    renderizar_tabela_html(
        [
            {"loja": oferta.loja, "preço encontrado": f"R$ {oferta.preco:.2f}"}
            for oferta in resultados_buscape
        ],
        colunas=[("loja", "Loja"), ("preço encontrado", "Preço Encontrado")],
    )

    nomes_lojas_encontradas = [oferta.loja for oferta in resultados_buscape]
    loja_escolhida_nome = st.selectbox(
        "Escolher uma loja encontrada para completar o formulário abaixo",
        nomes_lojas_encontradas,
        key="loja_escolhida_buscape",
    )

    if st.button("Consultar Livelo e Méliuz para esta loja e preencher o formulário"):
        oferta_escolhida = next(oferta for oferta in resultados_buscape if oferta.loja == loja_escolhida_nome)

        with st.spinner(f"Consultando parceiros de pontos e cashback para {loja_escolhida_nome}..."):
            cache_livelo = db.obter_cache_parceiro_loja(loja_escolhida_nome, "livelo")
            if cache_livelo:
                pontos_livelo = cache_livelo["pontos_por_real"] or 0.0
                mensagem_livelo = "valor obtido do cache das últimas 24 horas"
            else:
                try:
                    resultado_livelo = buscar_parceiro_por_loja(loja_escolhida_nome)
                    db.salvar_cache_parceiro_loja(
                        loja_escolhida_nome, "livelo",
                        encontrado=resultado_livelo.encontrado,
                        pontos_por_real=resultado_livelo.pontos_por_real,
                        moeda_padrao=resultado_livelo.moeda_padrao,
                        regras_extras="; ".join(resultado_livelo.regras_extras),
                        url_consultada=resultado_livelo.url_consultada,
                    )
                    pontos_livelo = resultado_livelo.pontos_por_real if resultado_livelo.encontrado else 0.0
                    mensagem_livelo = resultado_livelo.mensagem or "consulta feita agora, direto no site da Livelo"
                except ErroScraperLivelo as erro:
                    pontos_livelo = 0.0
                    mensagem_livelo = f"não foi possível consultar a Livelo agora, detalhe técnico, {erro}"

            cache_meliuz = db.obter_cache_parceiro_loja(loja_escolhida_nome, "meliuz")
            if cache_meliuz:
                cashback_meliuz = cache_meliuz["cashback_pct"] or 0.0
                mensagem_meliuz = "valor obtido do cache das últimas 24 horas"
            else:
                try:
                    resultado_meliuz = buscar_cashback_por_loja(loja_escolhida_nome)
                    db.salvar_cache_parceiro_loja(
                        loja_escolhida_nome, "meliuz",
                        encontrado=resultado_meliuz.encontrado,
                        cashback_pct=resultado_meliuz.cashback_pct,
                        url_consultada=resultado_meliuz.url_consultada,
                    )
                    cashback_meliuz = resultado_meliuz.cashback_pct if resultado_meliuz.encontrado else 0.0
                    mensagem_meliuz = resultado_meliuz.mensagem or "consulta feita agora, direto no site do Méliuz"
                except ErroScraperMeliuz as erro:
                    cashback_meliuz = 0.0
                    mensagem_meliuz = f"não foi possível consultar o Méliuz agora, detalhe técnico, {erro}"

        st.session_state["sugestao_loja"] = loja_escolhida_nome
        st.session_state["sugestao_preco_cartao"] = oferta_escolhida.preco
        st.session_state["sugestao_pontos_livelo"] = pontos_livelo
        st.session_state["sugestao_cashback_meliuz"] = cashback_meliuz
        st.session_state["mensagem_livelo"] = mensagem_livelo
        st.session_state["mensagem_meliuz"] = mensagem_meliuz
        st.success("Formulário preenchido com as sugestões encontradas, revise antes de salvar.")
        st.rerun()

if "sugestao_loja" in st.session_state:
    st.info(
        f"Sugestão para {st.session_state['sugestao_loja']}, "
        f"Livelo, {st.session_state.get('mensagem_livelo', '')}, "
        f"Méliuz, {st.session_state.get('mensagem_meliuz', '')}."
    )

st.header("3. Adicionar uma oferta")

parceiros_livelo = db.listar_parceiros_livelo()
nomes_parceiros = [parceiro["nome"] for parceiro in parceiros_livelo]

cartoes_cadastrados = db.listar_cartoes()
nomes_cartoes = [cartao["nome"] for cartao in cartoes_cadastrados]

with st.form("form_oferta", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        loja = st.text_input("Loja", value=st.session_state.get("sugestao_loja", ""))
        tipo = st.selectbox("Tipo de oferta", ["online", "parceiro de pontos", "loja física", "negociação"])
    with col2:
        preco_pix = st.number_input("Preço no Pix (R$)", min_value=0.0, step=10.0)
        preco_cartao = st.number_input(
            "Preço no cartão (R$)", min_value=0.0, step=10.0,
            value=float(st.session_state.get("sugestao_preco_cartao", 0.0)),
        )
    with col3:
        parcelas = st.number_input("Número de parcelas", min_value=1, max_value=24, value=1)
        frete = st.number_input("Frete (R$)", min_value=0.0, step=10.0)

    st.subheader("Pontos e milhas")
    st.caption(
        "O valor dos pontos é calculado pelo método do milheiro, somando os "
        "pontos do site parceiro com os pontos do cartão selecionado."
    )
    col4, col5, col6 = st.columns(3)
    with col4:
        pontos_por_real_sugerido = float(st.session_state.get("sugestao_pontos_livelo", 0.0))
        if pontos_por_real_sugerido <= 0 and parceiros_livelo:
            parceiro_selecionado = st.selectbox(
                "Parceiro Livelo ou Esfera (lista manual, opcional)", ["nenhum"] + nomes_parceiros,
            )
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
            cashback_padrao = float(st.session_state.get("sugestao_cashback_meliuz", 0.0))
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
            for chave in (
                "sugestao_loja", "sugestao_preco_cartao", "sugestao_pontos_livelo",
                "sugestao_cashback_meliuz", "mensagem_livelo", "mensagem_meliuz",
            ):
                st.session_state.pop(chave, None)
            st.success(f"Oferta da {loja} salva, preço efetivo R$ {resultado.preco_efetivo:.2f}.")
            st.rerun()

st.header("4. Ranking das ofertas cadastradas")

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
            st.write(f"Preço Pix, R$ {resultado.preco_efetivo_pix + resultado.pontos_valor_pix + resultado.cashback_valor_pix:.2f}")
            st.write(f"Valor dos pontos/milhas, -R$ {resultado.pontos_valor_pix:.2f}")
            st.write(f"Cashback, -R$ {resultado.cashback_valor_pix:.2f}")
            st.write(f"Preço efetivo Pix, R$ {resultado.preco_efetivo_pix:.2f}")
        with col2:
            st.markdown("**Pagando parcelado no cartão**")
            st.write(f"Preço anunciado, R$ {resultado.preco_anunciado:.2f}")
            st.write(f"Rendimento do parcelamento, -R$ {resultado.rendimento_parcelamento:.2f}")
            st.write(f"Valor dos pontos/milhas, -R$ {resultado.pontos_valor_cartao:.2f}")
            st.write(f"Cashback, -R$ {resultado.cashback_valor_cartao:.2f}")
            st.write(f"Preço efetivo cartão, R$ {resultado.preco_efetivo_cartao:.2f}")

        st.markdown(f"**Economia em relação ao preço anunciado, R$ {resultado.economia_vs_anunciado:.2f}**")

st.header("5. Simulador, a partir de quantas parcelas compensa")

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
