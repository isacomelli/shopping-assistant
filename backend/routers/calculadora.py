"""
rota da calculadora livre, pensada para simular o custo efetivo de qualquer compra do dia a dia, sem precisar cadastrar um produto na wishlist nem gravar nada no banco.

reaproveita o mesmo motor de calculo e as mesmas regras de valores padrao do perfil ja usadas no cadastro manual de uma oferta, atraves de calculo.oferta_do_payload, entao um numero digitado aqui segue exatamente a mesma logica de custo efetivo do restante do aplicativo.
"""

from fastapi import APIRouter
from database import db
from engine.price_engine import calcular_oferta
from calculo import oferta_do_payload, resultado_como_dict
from schemas import CalculoLivreOut, OfertaCreate

router = APIRouter(prefix="/calculadora", tags=["calculadora"])


@router.post("/calcular", response_model=CalculoLivreOut)
def calcular_livre(payload: OfertaCreate):
    """
    calcula o preco efetivo de uma compra qualquer a partir dos valores informados, sem exigir produto nem loja cadastrados e sem gravar nenhuma oferta ou historico. os campos nao informados no payload caem de volta para o perfil financeiro, do mesmo jeito que o cadastro manual de oferta em routers/ofertas.py.
    """
    config = db.obter_configuracoes()
    oferta = oferta_do_payload(payload, config)
    resultado = calcular_oferta(oferta, float(config["rendimento_mensal"]))
    return {"resultado": resultado_como_dict(resultado)}
