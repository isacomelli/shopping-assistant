"""
rotas de ofertas de um produto, cadastro manual, edicao, exclusao,
pesquisa automatica no buscape e simulador de parcelamento.
"""

from fastapi import APIRouter, HTTPException

from database import db
from engine.price_engine import calcular_oferta, simular_parcelamento
from scrapers.buscape import ErroScraperBuscape
from scrapers.livelo import ErroScraperLivelo, buscar_parceiros_livelo
from services.pesquisa_produto import pesquisar_produto_automaticamente

from calculo import linha_oferta_para_saida, oferta_do_payload, resultado_como_dict
from schemas import (
    OfertaCreate,
    OfertaOut,
    OfertaUpdate,
    ParceiroLiveloOut,
    ParcelaSimuladaOut,
    ResultadoAutomaticoOut,
    SimulacaoParcelamentoIn,
)

router = APIRouter(tags=["ofertas"])


def _produto_ou_404(produto_id):
    produto = db.obter_produto(produto_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return produto


@router.get("/produtos/{produto_id}/ofertas", response_model=list[OfertaOut])
def listar_ofertas(produto_id: int):
    _produto_ou_404(produto_id)
    config = db.obter_configuracoes()
    ofertas = db.listar_ofertas_por_produto(produto_id)
    saida = [linha_oferta_para_saida(oferta, config) for oferta in ofertas]
    saida.sort(key=lambda item: item["resultado"]["preco_efetivo"])
    return saida


@router.post("/produtos/{produto_id}/ofertas", response_model=OfertaOut, status_code=201)
def criar_oferta(produto_id: int, payload: OfertaCreate):
    _produto_ou_404(produto_id)
    if not payload.loja.strip() or payload.preco_pix <= 0 or payload.preco_cartao <= 0:
        raise HTTPException(
            status_code=422,
            detail="Preencha ao menos a loja, o preço no Pix e o preço no cartão.",
        )
    config = db.obter_configuracoes()
    oferta = oferta_do_payload(payload, config)
    resultado = calcular_oferta(oferta, float(config["rendimento_mensal"]))

    oferta_id = db.adicionar_oferta(
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
        observacoes=payload.observacoes,
        validade=payload.validade,
        confianca=payload.confianca,
        preco_efetivo=resultado.preco_efetivo,
        preco=oferta.preco,
        url_produto=oferta.url_produto,
    )
    db.registrar_historico(
        produto_id, oferta.loja, oferta.preco_cartao, resultado.preco_efetivo,
        preco=oferta.preco, preco_pix=oferta.preco_pix,
        preco_cartao=oferta.preco_cartao, parcelas=oferta.parcelas,
        oferta_id=oferta_id,
    )

    nova = next(
        item for item in db.listar_ofertas_por_produto(produto_id) if item["id"] == oferta_id
    )
    return linha_oferta_para_saida(nova, config)


@router.put("/produtos/{produto_id}/ofertas/{oferta_id}", response_model=OfertaOut)
def atualizar_oferta(produto_id: int, oferta_id: int, payload: OfertaUpdate):
    _produto_ou_404(produto_id)
    if not payload.loja.strip() or payload.preco_pix <= 0 or payload.preco_cartao <= 0:
        raise HTTPException(
            status_code=422,
            detail="Preencha ao menos a loja, o preço no Pix e o preço no cartão.",
        )
    config = db.obter_configuracoes()
    oferta = oferta_do_payload(payload, config)
    resultado = calcular_oferta(oferta, float(config["rendimento_mensal"]))

    atualizada = db.atualizar_oferta(
        oferta_id=oferta_id,
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
        observacoes=payload.observacoes,
        validade=payload.validade,
        confianca=payload.confianca,
        preco_efetivo=resultado.preco_efetivo,
        preco=oferta.preco,
    )
    if not atualizada:
        raise HTTPException(status_code=404, detail="Oferta não encontrada.")

    db.registrar_historico(
        produto_id, oferta.loja, oferta.preco_cartao, resultado.preco_efetivo,
        preco=oferta.preco, preco_pix=oferta.preco_pix,
        preco_cartao=oferta.preco_cartao, parcelas=oferta.parcelas,
        oferta_id=oferta_id,
    )

    linha = next(
        item for item in db.listar_ofertas_por_produto(produto_id) if item["id"] == oferta_id
    )
    return linha_oferta_para_saida(linha, config)


@router.delete("/produtos/{produto_id}/ofertas/{oferta_id}", status_code=204)
def excluir_oferta(produto_id: int, oferta_id: int):
    _produto_ou_404(produto_id)
    if not db.excluir_oferta(oferta_id, produto_id):
        raise HTTPException(status_code=404, detail="Oferta não encontrada.")


@router.post("/produtos/{produto_id}/pesquisar", response_model=list[ResultadoAutomaticoOut])
def pesquisar_automaticamente(produto_id: int):
    """
    dispara a pesquisa automatica no buscape para o produto e registra
    cada loja encontrada como oferta e como historico de preco, do
    mesmo jeito que o botao da calculadora do streamlit fazia.
    """
    produto = _produto_ou_404(produto_id)
    config = db.obter_configuracoes()

    try:
        resultados_automaticos = pesquisar_produto_automaticamente(
            nome_produto=produto["nome"],
            rendimento_mensal=float(config["rendimento_mensal"]),
            cotacao_dolar=float(config["cotacao_dolar"]),
            pontos_por_dolar_cartao_padrao=float(config["pontos_dolar_cartao_padrao"]),
            valor_milheiro=float(config["valor_milheiro_padrao"]),
        )
    except ErroScraperBuscape as erro:
        raise HTTPException(
            status_code=502, detail=f"Não foi possível consultar o Buscapé agora, {erro}",
        )

    saida = []
    for item in resultados_automaticos:
        oferta = item.oferta
        resultado = item.resultado
        oferta_id = db.registrar_oferta_pesquisa(
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
            url_produto=item.url_produto,
        )
        db.registrar_historico(
            produto_id, oferta.loja, oferta.preco_cartao, resultado.preco_efetivo,
            preco=oferta.preco, preco_pix=oferta.preco_pix,
            preco_cartao=oferta.preco_cartao, parcelas=oferta.parcelas,
            oferta_id=oferta_id,
        )
        saida.append({
            "loja": oferta.loja,
            "tipo": oferta.tipo,
            "preco_pix": oferta.preco_pix,
            "preco_cartao": oferta.preco_cartao,
            "parcelas": oferta.parcelas,
            "pontos_por_real": oferta.pontos_por_real,
            "parceiro_encontrado": item.parceiro_encontrado,
            "parceiro_nome": item.parceiro_nome,
            "confianca_pix_cartao": item.confianca_pix_cartao,
            "url_produto": item.url_produto,
            "resultado": resultado_como_dict(resultado),
        })

    saida.sort(key=lambda item: item["resultado"]["preco_efetivo"])
    return saida


@router.post("/simular-parcelamento", response_model=list[ParcelaSimuladaOut])
def simular(payload: SimulacaoParcelamentoIn):
    return simular_parcelamento(
        payload.preco_pix, payload.preco_cartao, payload.rendimento_mensal, payload.max_parcelas,
    )


@router.get("/parceiros-livelo", response_model=list[ParceiroLiveloOut])
def listar_parceiros_livelo():
    return db.listar_parceiros_livelo()


@router.post("/parceiros-livelo/atualizar", response_model=list[ParceiroLiveloOut])
def atualizar_parceiros_livelo():
    """
    roda o scraper da livelo, que le a pagina publica de todos os
    parceiros, e grava o resultado na tabela livelo_parceiros,
    substituindo a taxa de pontos de cada parceiro ja cadastrado e
    criando os que ainda nao existiam. e essa gravacao que faltava,
    o scraper em scrapers/livelo.py so devolvia a lista em memoria,
    sem nunca chamar db.salvar_parceiros_livelo.

    depois de chamar essa rota, a pesquisa automatica em
    services/pesquisa_produto.py passa a casar as lojas do buscape
    contra parceiros atualizados, atraves de
    db.buscar_parceiro_livelo_por_nome.

    roda de forma sincrona, num navegador headless, o que pode levar
    alguns segundos, ja que a pagina da livelo carrega a lista aos
    poucos conforme a rolagem.
    """
    try:
        parceiros = buscar_parceiros_livelo()
    except ErroScraperLivelo as erro:
        raise HTTPException(
            status_code=502, detail=f"Não foi possível atualizar os parceiros da Livelo agora, {erro}",
        )

    db.salvar_parceiros_livelo(parceiros)
    return db.listar_parceiros_livelo()
