"""
pagina de pesquisa e calculo do preco real de um produto.

fluxo principal, assim que voce cria um produto novo, a pagina ja
dispara a pesquisa automatica no buscape, tenta casar cada loja
encontrada com um parceiro livelo cadastrado manualmente, e calcula o
preco efetivo de cada uma com os valores padrao, milheiro de R$ 15,
bonus de transferencia de 80% e 6 parcelas.

cada resultado automatico tem um botao editar variaveis, que abre o
formulario manual ja preenchido com os dados daquela loja, para voce
ajustar qualquer campo, tipo pontos por real, cupom ou frete, e
recalcular antes de salvar.

o valor dos pontos de cada oferta e calculado pelo metodo do
milheiro, juntando os pontos do site parceiro, livelo ou esfera, com
os pontos ganhos direto no cartao selecionado. no pix nao existe
cartao envolvido, entao so o site parceiro pontua, ver
engine/price_engine.py para o passo a passo completo da conta.
"""

import streamlit as st

from database import db
from engine.price_engine import Oferta, ranquear_ofertas, simular_parcelamento
from scrapers.buscape import ErroScraperBuscape, buscar_ofertas_buscape
from services.pesquisa_produto import (
    BONUS_TRANSFERENCIA_PADRAO_PESQUISA,
    PARCELAS_PADRAO_PESQUISA,
    VALOR_MILHEIRO_PADRAO_PESQUISA,
    pesquisar_produto_automaticamente,
)
from utils.ui import renderizar_grafico_linha_svg, renderizar_tabela_html

st.set_page_config(page_title="Calculadora", layout="wide")

db.inicializar_banco()

st.title("Calculadora de Compra Inteligente")

config = db.obter_configuracoes()
produtos = db.listar_produtos()

st.header("1. Escolha ou crie um produto")

nomes_produtos = [produto["nome"] for produto in produtos]

indice_padrao = 0
if "produto_selecionado_nome" in st.session_state and st.session_state["produto_selecionado_nome"] in nomes_produtos:
    indice_padrao = nomes_produtos.index(st.session_state["produto_selecionado_nome"]) + 1

opcao = st.selectbox("Produto", ["Novo produto"] + nomes_produtos, index=indice_padrao)

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
        criar = st.form_submit_button("Criar produto e pesquisar automaticamente")
        if criar and nome_novo.strip():
            produto_id = db.adicionar_produto(nome_novo.strip(), categoria_nova, orcamento_novo, preco_alvo_novo)
            st.session_state["produto_selecionado_nome"] = nome_novo.strip()
            st.session_state["disparar_pesquisa_automatica"] = True
            st.success(f"Produto {nome_novo} criado, buscando ofertas automaticamente.")
            st.rerun()
    st.stop()

produto_atual = next(produto for produto in produtos if produto["nome"] == opcao)
produto_id = produto_atual["id"]
st.session_state["produto_selecionado_nome"] = opcao

st.caption(
    f"Categoria, {produto_atual['categoria'] or 'sem categoria'}, "
    f"preço alvo, R$ {produto_atual['preco_alvo'] or 0:.2f}, "
    f"orçamento, R$ {produto_atual['orcamento'] or 0:.2f}."
)

st.header("2. Pesquisa automática")
st.caption(
    "Busca o produto no BuscaPé e tenta casar cada loja encontrada com um "
    "parceiro Livelo já cadastrado manualmente, na tela inicial. Valores "
    f"padrão, milheiro R$ {VALOR_MILHEIRO_PADRAO_PESQUISA:.2f}, bônus de "
    f"transferência {BONUS_TRANSFERENCIA_PADRAO_PESQUISA:.0f}%, "
    f"{PARCELAS_PADRAO_PESQUISA}x no cartão."
)

parceiros_livelo = db.listar_parceiros_livelo()
nomes_parceiros = [parceiro["nome"] for parceiro in parceiros_livelo]

col_busca_1, col_busca_2 = st.columns([1, 3])
with col_busca_1:
    pesquisar_agora = st.button("Pesquisar automaticamente no BuscaPé")

disparo_automatico = st.session_state.pop("disparar_pesquisa_automatica", False)

if pesquisar_agora or disparo_automatico:
    with st.spinner("consultando o buscape, isso pode levar um minuto"):
        try:
            resultados_automaticos = pesquisar_produto_automaticamente(
                nome_produto=produto_atual["nome"],
                parceiros_cadastrados=parceiros_livelo,
                cdi_mensal=float(config["cdi_mensal"]),
                cotacao_dolar=float(config["cotacao_dolar"]),
                pontos_por_dolar_cartao_padrao=float(config["pontos_dolar_cartao_padrao"]),
            )
            st.session_state[f"resultados_automaticos_{produto_id}"] = resultados_automaticos
        except ErroScraperBuscape as erro:
            st.error(
                "não foi possível pesquisar automaticamente agora, o BuscaPé pode "
                "ter bloqueado o acesso automatizado ou mudado o layout. cadastre "
                f"a oferta manualmente abaixo enquanto isso. detalhe técnico, {erro}"
            )

resultados_automaticos = st.session_state.get(f"resultados_automaticos_{produto_id}")

prefill = st.session_state.pop("prefill_oferta", None)

if resultados_automaticos:
    if not nomes_parceiros:
        st.warning(
            "nenhum parceiro Livelo cadastrado ainda, então nenhuma loja pontuou "
            "automaticamente. cadastre os parceiros na tela inicial, seção "
            "Parceiros Livelo, e pesquise de novo."
        )

    for resultado_automatico in resultados_automaticos:
        oferta = resultado_automatico.oferta
        resultado = resultado_automatico.resultado

        rotulo_parceiro = (
            f"parceiro Livelo casado, {resultado_automatico.parceiro_nome}"
            if resultado_automatico.parceiro_encontrado
            else "nenhum parceiro Livelo casado, pontuação zerada"
        )

        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.markdown(f"**{oferta.loja}**")
                st.caption(rotulo_parceiro)
                if not resultado_automatico.confianca_pix_cartao:
                    st.caption(
                        "não foi possível distinguir preço Pix de preço cartão "
                        "automaticamente, os dois valores abaixo partiram do "
                        "mesmo preço encontrado."
                    )
            with col2:
                st.write(f"Preço efetivo, R$ {resultado.preco_efetivo:.2f}")
                st.write(f"Melhor forma de pagamento, {resultado.melhor_forma_pagamento}")
                st.write(f"Economia vs anunciado, R$ {resultado.economia_vs_anunciado:.2f}")
            with col3:
                if st.button("Editar variáveis", key=f"editar_{oferta.loja}_{resultado.preco_anunciado}"):
                    st.session_state["prefill_oferta"] = {
                        "loja": oferta.loja,
                        "tipo": "online",
                        "preco_pix": oferta.preco_pix,
                        "preco_cartao": oferta.preco_cartao,
                        "parcelas": oferta.parcelas,
                        "pontos_por_real": oferta.pontos_por_real,
                        "pontos_por_dolar_cartao": oferta.pontos_por_dolar_cartao,
                        "percentual_bonus_transferencia": oferta.percentual_bonus_transferencia,
                        "valor_milheiro": oferta.valor_milheiro,
                    }
                    st.rerun()

            with st.expander("Ver detalhamento da conta"):
                col4, col5 = st.columns(2)
                with col4:
                    st.markdown("**Pagando no Pix**")
                    st.write(f"Preço Pix, R$ {oferta.preco_pix:.2f}")
                    st.write(f"Valor dos pontos/milhas, -R$ {resultado.valor_pontos_pix:.2f}")
                    st.write(f"Preço efetivo Pix, R$ {resultado.preco_efetivo_pix:.2f}")
                with col5:
                    st.markdown(f"**Pagando parcelado, {oferta.parcelas}x**")
                    st.write(f"Preço anunciado, R$ {resultado.preco_anunciado:.2f}")
                    st.write(f"Rendimento do parcelamento, -R$ {resultado.rendimento_parcelamento:.2f}")
                    st.write(f"Valor dos pontos/milhas, -R$ {resultado.valor_pontos_cartao:.2f}")
                    st.write(f"Preço efetivo cartão, R$ {resultado.preco_efetivo_cartao:.2f}")

            if st.button("Salvar esta oferta como está", key=f"salvar_{oferta.loja}_{resultado.preco_anunciado}"):
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
                    observacoes="cadastrada pela pesquisa automática",
                    validade="",
                    confianca="confirmada",
                    preco_efetivo=resultado.preco_efetivo,
                )
                db.registrar_historico(produto_id, oferta.loja, oferta.preco_cartao, resultado.preco_efetivo)
                st.success(f"Oferta da {oferta.loja} salva, preço efetivo R$ {resultado.preco_efetivo:.2f}.")
                st.rerun()

st.header("3. Adicionar ou editar uma oferta manualmente")

cartoes_cadastrados = db.listar_cartoes()
nomes_cartoes = [cartao["nome"] for cartao in cartoes_cadastrados]

prefill = prefill or {}

with st.form("form_oferta", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        loja = st.text_input("Loja", value=prefill.get("loja", ""))
        opcoes_tipo = ["online", "parceiro de pontos", "loja física", "negociação"]
        tipo = st.selectbox(
            "Tipo de oferta", opcoes_tipo, index=opcoes_tipo.index(prefill.get("tipo", "online")),
        )
    with col2:
        preco_pix = st.number_input(
            "Preço no Pix (R$)", min_value=0.0, step=10.0, value=float(prefill.get("preco_pix", 0.0)),
        )
        preco_cartao = st.number_input(
            "Preço no cartão (R$)", min_value=0.0, step=10.0, value=float(prefill.get("preco_cartao", 0.0)),
        )
    with col3:
        parcelas = st.number_input(
            "Número de parcelas", min_value=1, max_value=24, value=int(prefill.get("parcelas", PARCELAS_PADRAO_PESQUISA)),
        )
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
        pontos_por_real_sugerido = float(prefill.get("pontos_por_real", 0.0))
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
            pontos_dolar_cartao_padrao = float(prefill.get("pontos_por_dolar_cartao", config["pontos_dolar_cartao_padrao"]))
            cashback_padrao = 0.0
        pontos_por_dolar_cartao = st.number_input(
            "Pontos por dólar no cartão", min_value=0.0, value=pontos_dolar_cartao_padrao, step=0.5,
        )
        cashback_pct = st.number_input("Cashback (%)", min_value=0.0, value=cashback_padrao, step=0.5)
    with col6:
        percentual_bonus_transferencia = st.number_input(
            "Bônus de transferência para milhas (%)",
            min_value=0.0,
            value=float(prefill.get("percentual_bonus_transferencia", BONUS_TRANSFERENCIA_PADRAO_PESQUISA)),
            step=5.0,
            help="Bônus vigente na promoção de transferência para TudoAzul, Smiles ou LATAM Pass.",
        )
        valor_milheiro = st.number_input(
            "Valor do milheiro (R$)",
            min_value=0.0,
            value=float(prefill.get("valor_milheiro", config["valor_milheiro_padrao"])),
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
