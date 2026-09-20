"""
, rotas de ofertas de um produto, cadastro manual, edicao, exclusao, pesquisa automatica e simulador de parcelamento.

, a pesquisa automatica usa o google shopping como fonte principal, com o buscape como fonte complementar, ver services/pesquisa_produto.py, e reaproveita um cache local em sqlite, ver database/db.py, obter_cache_pesquisa e salvar_cache_pesquisa, para evitar bater nas fontes de busca de novo quando o mesmo termo for pesquisado dentro de um intervalo curto, o parametro atualizar da rota de pesquisa ignora o cache e forca uma consulta nova
"""

from fastapi import APIRouter, HTTPException
from database import db
from engine.price_engine import calcular_oferta, simular_parcelamento
from services.casamento_lojas import PARCEIROS_LIVELO_CONHECIDOS
from services.google_shopping import ErroScraperGoogleShopping
from services.pesquisa_produto import pesquisar_produto_automaticamente
from calculo import linha_oferta_para_saida, oferta_do_payload, resultado_como_dict
from schemas import (
    OfertaCreate,
    OfertaOut,
    OfertaUpdate,
    ParceiroLiveloOut,
    ParcelaSimuladaOut,
    PesquisaAutomaticaOut,
    SimulacaoParcelamentoIn,
)

router = APIRouter(tags=["ofertas"])


def _produto_ou_404(produto_id):
    produto = db.obter_produto(produto_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return produto


def _parceiros_para_pesquisa_automatica():
    """
    monta a lista de parceiros livelo usada para casar cada loja encontrada na pesquisa automatica, priorizando os parceiros ja atualizados na tabela livelo_parceiros do banco, atraves do botao "atualizar parceiros da livelo", e caindo para o snapshot fixo de PARCEIROS_LIVELO_CONHECIDOS por baixo, para os parceiros que a tabela ainda nao tiver.

    como encontrar_parceiro_equivalente devolve o primeiro parceiro que bater, colocar os parceiros do banco primeiro nesta lista garante que uma taxa de pontos ou uma logo atualizada substitua a versao antiga do snapshot fixo, sem precisar remover a entrada antiga do codigo
    """
    parceiros_atualizados = db.listar_parceiros_livelo()
    return parceiros_atualizados + PARCEIROS_LIVELO_CONHECIDOS


def _resultado_automatico_para_dict(item, resultado):
    return {
        "loja": item.oferta.loja,
        "tipo": item.oferta.tipo,
        "preco_pix": item.oferta.preco_pix,
        "preco_cartao": item.oferta.preco_cartao,
        "parcelas": item.oferta.parcelas,
        "pontos_por_real": item.oferta.pontos_por_real,
        "parceiro_encontrado": item.parceiro_encontrado,
        "parceiro_nome": item.parceiro_nome,
        "confianca_pix_cartao": item.confianca_pix_cartao,
        "url_produto": item.url_produto,
        "logo_url": item.logo_url,
        "imagem_produto": item.imagem_produto,
        "origem": item.origem,
        "resultado": resultado_como_dict(resultado),
    }


def _executar_pesquisa_e_gravar(produto, config):
    """
    dispara a pesquisa automatica de verdade, google shopping mais buscape complementar, e registra cada loja encontrada como oferta e como historico de preco, devolvendo a lista ja em formato de dicionario, pronta tanto para a resposta da rota quanto para salvar no cache
    """
    resultados_automaticos = pesquisar_produto_automaticamente(
        nome_produto=produto["nome"],
        rendimento_mensal=float(config["rendimento_mensal"]),
        cotacao_dolar=float(config["cotacao_dolar"]),
        pontos_por_dolar_cartao_padrao=float(config["pontos_dolar_cartao_padrao"]),
        incluir_buscape_complementar=True,
        valor_milheiro=float(config["valor_milheiro_padrao"]),
        percentual_bonus_transferencia=float(config["percentual_bonus_transferencia_padrao"]),
        parcelas_quando_nao_confirmado=int(config["parcelas_padrao"]),
        parceiros_conhecidos=_parceiros_para_pesquisa_automatica(),
    )

    saida = []
    for item in resultados_automaticos:
        oferta = item.oferta
        resultado = item.resultado
        oferta_id = db.registrar_oferta_pesquisa(
            produto_id=produto["id"],
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
            logo_url=item.logo_url,
            imagem_produto=item.imagem_produto,
            origem=item.origem,
        )
        db.registrar_historico(
            produto["id"], oferta.loja, oferta.preco_cartao, resultado.preco_efetivo,
            preco=oferta.preco, preco_pix=oferta.preco_pix,
            preco_cartao=oferta.preco_cartao, parcelas=oferta.parcelas,
            oferta_id=oferta_id, origem=item.origem,
        )
        saida.append(_resultado_automatico_para_dict(item, resultado))

    saida.sort(key=lambda item: item["resultado"]["preco_efetivo"])
    return saida


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
        origem="manual",
    )
    db.registrar_historico(
        produto_id, oferta.loja, oferta.preco_cartao, resultado.preco_efetivo,
        preco=oferta.preco, preco_pix=oferta.preco_pix,
        preco_cartao=oferta.preco_cartao, parcelas=oferta.parcelas,
        oferta_id=oferta_id, origem="manual",
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
        oferta_id=oferta_id, origem="manual",
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


@router.post("/produtos/{produto_id}/pesquisar", response_model=PesquisaAutomaticaOut)
def pesquisar_automaticamente(produto_id: int, atualizar: bool = False):
    """
    dispara a pesquisa automatica de ofertas para o produto e registra cada loja encontrada como oferta e como historico de preco, quando atualizar for False, o padrao, e existir um cache valido para o nome do produto, o cache e reaproveitado e nenhuma fonte externa e consultada, quando atualizar for True, o cache existente e ignorado e uma nova pesquisa e sempre disparada
    """
    produto = _produto_ou_404(produto_id)
    config = db.obter_configuracoes()

    if not atualizar:
        cache = db.obter_cache_pesquisa(produto["nome"])
        if cache:
            return {"resultados": cache["ofertas"], "veio_do_cache": True, "fontes_com_erro": {}}

    try:
        saida = _executar_pesquisa_e_gravar(produto, config)
    except ErroScraperGoogleShopping as erro:
        raise HTTPException(
            status_code=502, detail=f"Não foi possível consultar as fontes de busca agora, {erro}",
        )

    db.salvar_cache_pesquisa(produto["nome"], saida, origem="combinado")
    return {"resultados": saida, "veio_do_cache": False, "fontes_com_erro": {}}


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
    roda o scraper da livelo, que le a pagina publica de todos os parceiros, e grava o resultado na tabela livelo_parceiros, substituindo a taxa de pontos de cada parceiro ja cadastrado e criando os que ainda nao existiam.

    depois de chamar essa rota, a pesquisa automatica em services/pesquisa_produto.py passa a casar as lojas encontradas contra parceiros atualizados, atraves de db.buscar_parceiro_livelo_por_nome, roda de forma sincrona, num navegador headless, o que pode levar alguns segundos, ja que a pagina da livelo carrega a lista aos poucos conforme a rolagem
    """
    from scrapers.livelo import ErroScraperLivelo, buscar_parceiros_livelo

    try:
        parceiros = buscar_parceiros_livelo()
    except ErroScraperLivelo as erro:
        raise HTTPException(
            status_code=502, detail=f"Não foi possível atualizar os parceiros da Livelo agora, {erro}",
        )

    db.salvar_parceiros_livelo(parceiros)
    return db.listar_parceiros_livelo()
