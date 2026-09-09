"""
rotas do perfil financeiro, rendimento mensal liquido, cotacao do
dolar, valor do milheiro padrao e os cartoes de credito cadastrados.
"""

from fastapi import APIRouter, HTTPException

from database import db
from services.cambio import buscar_cotacao_dolar

from schemas import CartaoCreate, CartaoOut, CotacaoDolarOut, PerfilOut, PerfilUpdate

router = APIRouter(prefix="/perfil", tags=["perfil"])


@router.get("", response_model=PerfilOut)
def obter_perfil():
    return db.obter_configuracoes()


@router.put("", response_model=PerfilOut)
def salvar_perfil(payload: PerfilUpdate):
    db.salvar_configuracoes(
        payload.rendimento_mensal, payload.cotacao_dolar, payload.valor_milheiro_padrao,
    )
    return db.obter_configuracoes()


@router.get("/cotacao-dolar", response_model=CotacaoDolarOut)
def obter_cotacao_dolar_atual():
    """
    consulta a cotacao do dolar numa api publica, usada para sugerir o
    valor no formulario de perfil. se a consulta falhar, o front cai
    de volta para o valor ja salvo no perfil.
    """
    cotacao = buscar_cotacao_dolar()
    return {"cotacao_dolar": cotacao, "encontrada": cotacao is not None}


@router.get("/cartoes", response_model=list[CartaoOut])
def listar_cartoes():
    return db.listar_cartoes()


@router.post("/cartoes", response_model=list[CartaoOut], status_code=201)
def adicionar_cartao(payload: CartaoCreate):
    if not payload.nome.strip():
        raise HTTPException(status_code=422, detail="Informe o nome do cartão.")
    db.adicionar_cartao(payload.nome.strip(), payload.pontos_por_dolar, payload.cashback_pct)
    return db.listar_cartoes()


@router.delete("/cartoes/{cartao_id}", response_model=list[CartaoOut])
def remover_cartao(cartao_id: int):
    db.remover_cartao(cartao_id)
    return db.listar_cartoes()
