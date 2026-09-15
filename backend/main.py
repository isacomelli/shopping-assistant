"""
ponto de entrada da api do assistente de compras da reforma.

roda com, a partir da pasta backend,

    uvicorn main:app --reload --port 8000

a documentacao interativa fica em http://localhost:8000/docs
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import db
from routers import calculadora, historico, ofertas, perfil, produtos

ORIGENS_PERMITIDAS = os.environ.get(
    "CORS_ORIGENS", "http://localhost:3000",
).split(",")

app = FastAPI(
    title="Assistente de Compras da Reforma",
    description=(
        "API do motor de calculo de custo efetivo de compra, considerando pix, cartao parcelado, pontos e cashback."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENS_PERMITIDAS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def inicializar():
    db.inicializar_banco()


@app.get("/saude", tags=["saude"])
def saude():
    return {"status": "ok"}


app.include_router(perfil.router)
app.include_router(produtos.router)
app.include_router(ofertas.router)
app.include_router(historico.router)
app.include_router(calculadora.router)