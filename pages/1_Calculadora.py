"""
pagina de pesquisa e calculo do preco real de um produto.

fluxo principal, assim que voce cria um produto novo, a pagina ja
dispara a pesquisa automatica no buscape e, para cada loja encontrada,
consulta a busca publica da Livelo para verificar se existe parceria e
qual a taxa de pontos. quando a loja e parceira, o resultado traz a
pontuacao por real ou por dolar; caso contrario, a loja aparece sem
pontuacao e continua no ranking normalmente.

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

import json
import re
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from database import db
from engine.price_engine import Oferta, calcular_oferta, ranquear_ofertas, simular_parcelamento
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


def _salvar_resultados_pesquisa(nome_produto, resultados):
    pasta_saida = Path(__file__).parent.parent / "debug_output"
    pasta_saida.mkdir(exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^a-z0-9]+", "_", nome_produto.lower()).strip("_")[:80]
    caminho = pasta_saida / f"site_{slug}_{carimbo}.json"
    caminho.write_text(
        json.dumps([asdict(resultado) for resultado in resultados], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return caminho


def _formatar_data_brasilia(data_texto):
    if not data_texto:
        return "não informada"
    try:
        data_utc = datetime.strptime(data_texto, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return data_utc.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return str(data_texto)

def _mostrar_memoria_calculo(oferta, resultado, cdi_mensal):
    """Mostra as entradas e as fórmulas que formam cada preço efetivo."""

    st.markdown("**Entradas usadas**")
    st.write(
        f"Pix: R\$ {oferta.preco_pix:.2f}"
        f"\nCartão: R\$ {oferta.preco_cartao:.2f} ({oferta.parcelas}x)",
        f"\nLivelo/Esfera: {oferta.pontos_por_real:.2f} ponto(s)/R\$"
        f"\nFrete: R\$ {oferta.frete:.2f}"
        f"\nCupom: R\$ {oferta.cupom:.2f}"
    )

    pontos_parceiro_pix = oferta.preco_pix * oferta.pontos_por_real
    milhas_parceiro_pix = pontos_parceiro_pix * (1 + oferta.percentual_bonus_transferencia / 100)
    pontos_parceiro_cartao = oferta.preco_cartao * oferta.pontos_por_real
    milhas_parceiro_cartao = pontos_parceiro_cartao * (1 + oferta.percentual_bonus_transferencia / 100)
    pontos_cartao = (
        oferta.preco_cartao / oferta.cotacao_dolar * oferta.pontos_por_dolar_cartao
        if oferta.cotacao_dolar > 0 else 0.0
    )
    cashback_pix = oferta.preco_pix * oferta.cashback_pct / 100
    cashback_cartao = oferta.preco_cartao * oferta.cashback_pct / 100

    with st.expander("Memória de cálculo do Pix"):
        st.write(
            f"Pontos do parceiro: {oferta.preco_pix:.2f} x {oferta.pontos_por_real:.2f} "
            f"= {pontos_parceiro_pix:.2f}."
        )
        st.write(
            f"Milhas após bônus: {pontos_parceiro_pix:.2f} x "
            f"(1 + {oferta.percentual_bonus_transferencia:.0f}/100) "
            f"= {milhas_parceiro_pix:.2f}."
        )
        valor_pontos_pix = resultado.valor_pontos_pix
        if oferta.valor_milheiro > 0:
            st.write(
                f"Valor dos pontos: {milhas_parceiro_pix:.2f} x R\$ {oferta.valor_milheiro:.2f} "
                f"/ 1.000 = R\$ {valor_pontos_pix:.2f}."
            )
        else:
            st.write(
                f"Valor dos pontos: {oferta.preco_pix:.2f} x {oferta.pontos_por_real:.2f} "
                f"x R\$ {oferta.valor_ponto:.4f} = R\$ {valor_pontos_pix:.2f}."
            )
        st.write(
            f"Preço efetivo Pix: R\$ {oferta.preco_pix:.2f} - R\$ {valor_pontos_pix:.2f} "
            f"- R\$ {cashback_pix:.2f} + R\$ {oferta.frete:.2f} - R\$ {oferta.cupom:.2f} "
            f"= R\$ {resultado.preco_efetivo_pix:.2f}."
        )

    with st.expander("Memória de cálculo do cartão"):
        rendimento = resultado.rendimento_parcelamento
        st.write(
            f"Pontos do parceiro: {oferta.preco_cartao:.2f} x {oferta.pontos_por_real:.2f} "
            f"= {pontos_parceiro_cartao:.2f}; após bônus = {milhas_parceiro_cartao:.2f}."
        )
        st.write(
            f"Pontos do cartão: R\$ {oferta.preco_cartao:.2f} / {oferta.cotacao_dolar:.2f} "
            f"x {oferta.pontos_por_dolar_cartao:.2f} = {pontos_cartao:.2f}."
        )
        if oferta.valor_milheiro > 0:
            st.write(
                f"Valor dos pontos: ({milhas_parceiro_cartao:.2f} + {pontos_cartao:.2f}) x "
                f"R\$ {oferta.valor_milheiro:.2f} / 1.000 = R\$ {resultado.valor_pontos_cartao:.2f}."
            )
        else:
            st.write(
                f"Valor dos pontos: {oferta.preco_cartao:.2f} x {oferta.pontos_por_real:.2f} "
                f"x R\$ {oferta.valor_ponto:.4f} = R\$ {resultado.valor_pontos_cartao:.2f}."
            )
        st.write(
            f"Rendimento do parcelamento, valor presente de {oferta.parcelas} parcelas "
            f"a {cdi_mensal:.2f}% ao mês = R\$ {rendimento:.2f}."
        )
        st.write(
            f"Preço efetivo cartão: R\$ {oferta.preco_cartao:.2f} - R\$ {rendimento:.2f} "
            f"- R\$ {resultado.valor_pontos_cartao:.2f} - R\$ {cashback_cartao:.2f} "
            f"+ R\$ {oferta.frete:.2f} - R\$ {oferta.cupom:.2f} "
            f"= R\$ {resultado.preco_efetivo_cartao:.2f}."
        )

    st.info(
            f"Comparação final: Pix R\$ {resultado.preco_efetivo_pix:.2f} versus cartão "
            f"R\$ {resultado.preco_efetivo_cartao:.2f}. Melhor opção, "
            f"{resultado.melhor_forma_pagamento}; preço anunciado, R\$ {resultado.preco_anunciado:.2f}; "
            f"economia, R\$ {resultado.economia_vs_anunciado:.2f}."
        )

st.title("Calculadora de Compra Inteligente")

config = db.obter_configuracoes()
produtos = db.listar_produtos()

nomes_produtos = [produto["nome"] for produto in produtos]

indice_padrao = 0
if "produto_selecionado_nome" in st.session_state and st.session_state["produto_selecionado_nome"] in nomes_produtos:
    indice_padrao = nomes_produtos.index(st.session_state["produto_selecionado_nome"]) + 1

if not nomes_produtos:
    st.info("Nenhum produto cadastrado. Crie um produto na Wishlist.")
    st.stop()

opcao = st.selectbox("Produto", nomes_produtos, index=max(indice_padrao - 1, 0))

produto_atual = next(produto for produto in produtos if produto["nome"] == opcao)
produto_id = produto_atual["id"]
st.session_state["produto_selecionado_nome"] = opcao

st.caption(
    f"Categoria: {produto_atual['categoria'] or 'sem categoria'}"
    f"  |  Preço alvo: R\$ {produto_atual['preco_alvo'] or 0:.2f}"
    f"  |  Orçamento: R\$ {produto_atual['orcamento'] or 0:.2f}"
)

# st.caption(
#     f"Busca o produto no Buscapé e, para cada loja encontrada, consulta a busca pública da Livelo para verificar parceria e taxa de pontos. lojas sem parceria aparecem sem pontuação. Valores padrão: milheiro R$ {VALOR_MILHEIRO_PADRAO_PESQUISA:.2f}, bônus de transferência {BONUS_TRANSFERENCIA_PADRAO_PESQUISA:.0f}%; o parcelamento extraído do Buscapé é usado quando disponível, com fallback em {PARCELAS_PADRAO_PESQUISA}x."
# )

# parceiros livelo carregados do arquivo html no startup do app
parceiros_livelo = db.listar_parceiros_livelo()
nomes_parceiros = [p["nome"] for p in parceiros_livelo]

oferta_em_edicao_id = st.session_state.get("oferta_em_edicao_id")

ofertas_salvas = db.listar_ofertas_por_produto(produto_id)

if not ofertas_salvas:
    st.info("Nenhuma oferta cadastrada ainda para este produto.")

if st.button("Reorganizar ranking"):
    st.success("Ranking reorganizado com os valores atuais das ofertas.")

ofertas_para_calculo = [
    (
        oferta,
        Oferta(
            loja=oferta["loja"],
            preco_pix=oferta["preco_pix"],
            preco_cartao=oferta["preco_cartao"],
            preco=oferta.get("preco", oferta["preco_cartao"]),
            parcelas=oferta["parcelas"],
            pontos_por_real=oferta["pontos_por_real"],
            cotacao_dolar=float(config["cotacao_dolar"]),
            cashback_pct=oferta["cashback_pct"],
            frete=oferta["frete"],
            cupom=oferta["cupom"],
            tipo=oferta["tipo"],
            pontos_por_dolar_cartao=oferta["pontos_por_dolar_cartao"],
            percentual_bonus_transferencia=oferta["percentual_bonus_transferencia"],
            valor_milheiro=float(config["valor_milheiro_padrao"]),
        ),
    )
    for oferta in ofertas_salvas
]

ranking = sorted(
    [
        (oferta_salva, oferta, calcular_oferta(oferta, float(config["cdi_mensal"])))
        for oferta_salva, oferta in ofertas_para_calculo
    ],
    key=lambda item: item[2].preco_efetivo,
)

preco_alvo = float(produto_atual["preco_alvo"] or 0)
if preco_alvo > 0:
    ranking = [item for item in ranking if item[2].preco_efetivo <= preco_alvo]
    if not ranking:
        st.info("Nenhuma oferta está dentro do preço alvo deste produto.")

medalhas = ["1º lugar", "2º lugar", "3º lugar"]

for posicao, (oferta_salva, oferta, resultado) in enumerate(ranking):
    rotulo = medalhas[posicao] if posicao < len(medalhas) else f"{posicao + 1}º lugar"
    with st.expander(
        f"{rotulo}: {resultado.loja}, preço efetivo: R$ {resultado.preco_efetivo:.2f} ({resultado.melhor_forma_pagamento})",
        expanded=(oferta_em_edicao_id == oferta_salva["id"]),
    ):
        data_oferta = oferta_salva["atualizada_em"] or oferta_salva["criado_em"]
        st.caption(f"Oferta encontrada/atualizada em: {_formatar_data_brasilia(data_oferta)}")
        col_editar, col_excluir = st.columns(2)
        with col_editar:
            editar_oferta = st.button("Editar oferta", key=f"editar_ranking_{oferta_salva['id']}")
        with col_excluir:
            excluir_oferta = st.button("Excluir oferta", key=f"excluir_ranking_{oferta_salva['id']}")

        if excluir_oferta:
            db.excluir_oferta(oferta_salva["id"], produto_id)
            st.rerun()

        if editar_oferta:
            st.session_state["oferta_em_edicao_id"] = oferta_salva["id"]
            st.rerun()

        if oferta_em_edicao_id == oferta_salva["id"]:
            with st.form(f"form_editar_oferta_{oferta_salva['id']}"):
                st.subheader("Editar oferta")
                edit_col1, edit_col2, edit_col3 = st.columns(3)
                with edit_col1:
                    edit_loja = st.text_input("Loja", value=oferta_salva["loja"])
                    tipos_oferta = ["online", "parceiro de pontos", "loja física", "negociação"]
                    edit_tipo = st.selectbox("Tipo de oferta", tipos_oferta, index=tipos_oferta.index(oferta_salva["tipo"]))
                with edit_col2:
                    edit_preco_pix = st.number_input("Preço no Pix (R$)", min_value=0.0, step=10.0, value=float(oferta_salva["preco_pix"]))
                    edit_preco_cartao = st.number_input("Preço no cartão (R$)", min_value=0.0, step=10.0, value=float(oferta_salva["preco_cartao"]))
                with edit_col3:
                    edit_parcelas = st.number_input("Número de parcelas", min_value=1, max_value=24, value=int(oferta_salva["parcelas"]))
                    edit_frete = st.number_input("Frete (R$)", min_value=0.0, step=10.0, value=float(oferta_salva["frete"]))

                edit_col4, edit_col5, edit_col6 = st.columns(3)
                with edit_col4:
                    edit_pontos_real = st.number_input("Pontos por real", min_value=0.0, step=0.5, value=float(oferta_salva["pontos_por_real"]))
                    edit_bonus = st.number_input("Bônus de transferência (%)", min_value=0.0, step=5.0, value=float(oferta_salva["percentual_bonus_transferencia"]))
                with edit_col5:
                    edit_pontos_dolar = st.number_input("Pontos por dólar no cartão", min_value=0.0, step=0.5, value=float(oferta_salva["pontos_por_dolar_cartao"]))
                    edit_cashback = st.number_input("Cashback (%)", min_value=0.0, step=0.5, value=float(oferta_salva["cashback_pct"]))
                with edit_col6:
                    edit_milheiro = st.number_input("Valor do milheiro (R$)", min_value=0.0, step=1.0, value=float(config["valor_milheiro_padrao"]))
                    edit_cupom = st.number_input("Cupom (R$)", min_value=0.0, step=10.0, value=float(oferta_salva["cupom"]))

                edit_col7, edit_col8 = st.columns(2)
                with edit_col7:
                    edit_observacoes = st.text_area("Observações", value=oferta_salva["observacoes"] or "")
                with edit_col8:
                    edit_validade = st.text_input("Validade", value=oferta_salva["validade"] or "")
                    confiancas = ["confirmada", "até domingo", "expirada"]
                    edit_confianca = st.selectbox("Confiança", confiancas, index=confiancas.index(oferta_salva["confianca"]))

                salvar_edicao = st.form_submit_button("Salvar edição")
                cancelar_edicao = st.form_submit_button("Cancelar")
                if salvar_edicao:
                    oferta_editada = Oferta(
                        loja=edit_loja.strip(), preco_pix=edit_preco_pix, preco_cartao=edit_preco_cartao,
                        parcelas=int(edit_parcelas), pontos_por_real=edit_pontos_real,
                        cotacao_dolar=float(config["cotacao_dolar"]), pontos_por_dolar_cartao=edit_pontos_dolar,
                        percentual_bonus_transferencia=edit_bonus, valor_milheiro=edit_milheiro,
                        cashback_pct=edit_cashback, frete=edit_frete, cupom=edit_cupom, tipo=edit_tipo,
                    )
                    resultado_editado = calcular_oferta(oferta_editada, float(config["cdi_mensal"]))
                    db.atualizar_oferta(
                        oferta_id=oferta_salva["id"], produto_id=produto_id, loja=oferta_editada.loja,
                        tipo=oferta_editada.tipo, preco_pix=edit_preco_pix, preco_cartao=edit_preco_cartao,
                        parcelas=int(edit_parcelas), pontos_por_real=edit_pontos_real,
                        pontos_por_dolar_cartao=edit_pontos_dolar, percentual_bonus_transferencia=edit_bonus,
                        valor_milheiro=edit_milheiro, cashback_pct=edit_cashback, frete=edit_frete,
                        cupom=edit_cupom, observacoes=edit_observacoes, validade=edit_validade,
                        confianca=edit_confianca, preco_efetivo=resultado_editado.preco_efetivo,
                        preco=edit_preco_pix,
                    )
                    st.session_state.pop("oferta_em_edicao_id", None)
                    st.rerun()
                if cancelar_edicao:
                    st.session_state.pop("oferta_em_edicao_id", None)
                    st.rerun()
        _mostrar_memoria_calculo(oferta, resultado, float(config["cdi_mensal"]))


pesquisar_agora = st.button("Atualizar ofertas automaticamente no Buscapé")
disparar_pesquisa = st.session_state.pop("disparar_pesquisa_automatica", False) or pesquisar_agora

if disparar_pesquisa:
    with st.spinner("Consultando o Buscapé, isso pode levar um minuto.", show_time=True):
        while True:
            try:
                resultados_automaticos = pesquisar_produto_automaticamente(
                    nome_produto=produto_atual["nome"],
                    cdi_mensal=float(config["cdi_mensal"]),
                    cotacao_dolar=float(config["cotacao_dolar"]),
                    pontos_por_dolar_cartao_padrao=float(config["pontos_dolar_cartao_padrao"]),
                    valor_milheiro=float(config["valor_milheiro_padrao"]),
                )
                for resultado_automatico in resultados_automaticos:
                    oferta = resultado_automatico.oferta
                    resultado = resultado_automatico.resultado
                    db.registrar_oferta_pesquisa(
                        produto_id=produto_id,
                        loja=oferta.loja,
                        tipo=oferta.tipo,
                        preco_pix=oferta.preco_pix,
                        preco_cartao=oferta.preco_cartao,
                        preco=oferta.preco,
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
                        url_produto=getattr(resultado_automatico, "url_produto", ""),
                    )
                    db.registrar_historico(
                        produto_id, oferta.loja, oferta.preco_cartao, resultado.preco_efetivo,
                        preco=oferta.preco, preco_pix=oferta.preco_pix,
                        preco_cartao=oferta.preco_cartao, parcelas=oferta.parcelas,
                    )
                _salvar_resultados_pesquisa(produto_atual["nome"], resultados_automaticos)
                st.success(f"{len(resultados_automaticos)} oferta(s) atualizada(s) no ranking.")
                st.rerun()
            except ErroScraperBuscape:
                time.sleep(1)


st.header("3. Adicionar ou editar uma oferta manualmente")

cartoes_cadastrados = db.listar_cartoes()
nomes_cartoes = [cartao["nome"] for cartao in cartoes_cadastrados]

prefill = {}

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
        frete = st.number_input(
            "Frete (R$)", min_value=0.0, step=10.0, value=float(prefill.get("frete", 0.0)),
        )

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
        cupom = st.number_input(
            "Cupom de desconto (R$)", min_value=0.0, step=10.0, value=float(prefill.get("cupom", 0.0)),
        )

    st.subheader("Detalhes extras")
    col7, col8 = st.columns(2)
    with col7:
        observacoes = st.text_area("Observações", value=prefill.get("observacoes", ""))
    with col8:
        validade = st.text_input("Validade da oferta, se houver", value=prefill.get("validade", ""))
        opcoes_confianca = ["confirmada", "até domingo", "expirada"]
        confianca = st.selectbox(
            "Confiança", opcoes_confianca,
            index=opcoes_confianca.index(prefill.get("confianca", "confirmada")),
        )

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
                pontos_por_real=pontos_por_real_sugerido,
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

            dados_oferta = {
                "produto_id": produto_id,
                "loja": oferta.loja,
                "tipo": oferta.tipo,
                "preco_pix": oferta.preco_pix,
                "preco_cartao": oferta.preco_cartao,
                "parcelas": oferta.parcelas,
                "pontos_por_real": oferta.pontos_por_real,
                "pontos_por_dolar_cartao": pontos_por_dolar_cartao,
                "percentual_bonus_transferencia": percentual_bonus_transferencia,
                "valor_milheiro": valor_milheiro,
                "cashback_pct": cashback_pct,
                "frete": frete,
                "cupom": cupom,
                "observacoes": observacoes,
                "validade": validade,
                "confianca": confianca,
                "preco_efetivo": resultado.preco_efetivo,
            }
            db.adicionar_oferta(**dados_oferta)
            db.registrar_historico(
                produto_id, oferta.loja, oferta.preco_cartao, resultado.preco_efetivo,
                preco=oferta.preco, preco_pix=oferta.preco_pix,
                preco_cartao=oferta.preco_cartao, parcelas=oferta.parcelas,
            )
            st.success(f"Oferta da {loja} salva, preço efetivo R$ {resultado.preco_efetivo:.2f}.")
            st.rerun()