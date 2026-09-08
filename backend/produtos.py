"""
rotas da wishlist, os produtos que faltam comprar para o apartamento.
"""

from fastapi import APIRouter, HTTPException

from database import db

from schemas import ProdutoCreate, ProdutoOut, ProdutoStatusUpdate, ProdutoUpdate

router = APIRouter(prefix="/produtos", tags=["produtos"])


def _com_melhor_oferta(produto):
    """
    junta o produto com o melhor preco efetivo ja encontrado entre as
    ofertas salvas, do jeito que a wishlist do streamlit mostrava.
    """
    ofertas = db.listar_ofertas_por_produto(produto["id"])
    precos_efetivos = [
        (oferta["preco_efetivo"], oferta["loja"])
        for oferta in ofertas
        if oferta["preco_efetivo"] is not None
    ]
    saida = dict(produto)
    if precos_efetivos:
        melhor_preco, melhor_loja = min(precos_efetivos, key=lambda item: item[0])
        saida["melhor_preco_efetivo"] = melhor_preco
        saida["melhor_loja"] = melhor_loja
    else:
        saida["melhor_preco_efetivo"] = None
        saida["melhor_loja"] = None
    return saida


@router.get("", response_model=list[ProdutoOut])
def listar_produtos():
    return [_com_melhor_oferta(produto) for produto in db.listar_produtos()]


@router.get("/{produto_id}", response_model=ProdutoOut)
def obter_produto(produto_id: int):
    produto = db.obter_produto(produto_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return _com_melhor_oferta(produto)


@router.post("", response_model=ProdutoOut, status_code=201)
def criar_produto(payload: ProdutoCreate):
    if not payload.nome.strip():
        raise HTTPException(status_code=422, detail="Informe o nome do produto.")
    produto_id = db.adicionar_produto(
        payload.nome.strip(), payload.categoria.strip(), payload.orcamento, payload.preco_alvo,
    )
    return _com_melhor_oferta(db.obter_produto(produto_id))


@router.put("/{produto_id}", response_model=ProdutoOut)
def atualizar_produto(produto_id: int, payload: ProdutoUpdate):
    if not db.obter_produto(produto_id):
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    if not payload.nome.strip():
        raise HTTPException(status_code=422, detail="Informe o nome do produto.")
    db.atualizar_produto(
        produto_id, payload.nome.strip(), payload.categoria.strip(),
        payload.orcamento, payload.preco_alvo,
    )
    return _com_melhor_oferta(db.obter_produto(produto_id))


@router.put("/{produto_id}/status", response_model=ProdutoOut)
def atualizar_status_produto(produto_id: int, payload: ProdutoStatusUpdate):
    if not db.obter_produto(produto_id):
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    db.atualizar_status_produto(produto_id, payload.status)
    return _com_melhor_oferta(db.obter_produto(produto_id))


@router.delete("/{produto_id}", status_code=204)
def excluir_produto(produto_id: int):
    if not db.obter_produto(produto_id):
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    db.excluir_produto(produto_id)
