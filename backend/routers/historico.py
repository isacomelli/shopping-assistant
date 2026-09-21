"""
rotas do historico de precos de um produto.
"""

from fastapi import APIRouter, HTTPException
from database import db
from schemas import HistoricoOut, OfertaOut
from calculo import linha_oferta_para_saida

router = APIRouter(tags=["historico"])


def _produto_ou_404(produto_id):
    produto = db.obter_produto(produto_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return produto


@router.get("/produtos/{produto_id}/historico", response_model=list[HistoricoOut])
def listar_historico(produto_id: int):
    _produto_ou_404(produto_id)
    return db.listar_historico(produto_id)


@router.delete("/produtos/{produto_id}/historico/{registro_id}", status_code=204)
def excluir_historico(produto_id: int, registro_id: int):
    _produto_ou_404(produto_id)
    if not db.excluir_historico(registro_id, produto_id):
        raise HTTPException(status_code=404, detail="Registro de histórico não encontrado.")


@router.get(
    "/produtos/{produto_id}/historico/{registro_id}/oferta",
    response_model=OfertaOut,
)
def obter_oferta_do_historico(produto_id: int, registro_id: int):
    """
    devolve a oferta ligada a um registro de historico, usada quando o front quer abrir direto a edicao daquela oferta na calculadora.
    """
    _produto_ou_404(produto_id)
    oferta = db.encontrar_oferta_do_historico(registro_id, produto_id)
    if not oferta:
        raise HTTPException(
            status_code=404, detail="Nenhuma oferta ligada a este registro de histórico.",
        )
    config = db.obter_configuracoes()
    return linha_oferta_para_saida(oferta, config)
