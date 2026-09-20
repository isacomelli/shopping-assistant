"""
, modelos pydantic usados nas rotas da api.

, este arquivo so descreve o formato dos dados que entram e saem pela api, a regra de negocio continua inteira em engine/price_engine.py, database/db.py e services/
"""

from typing import Optional

from pydantic import BaseModel, Field


# perfil financeiro

class PerfilOut(BaseModel):
    rendimento_mensal: float
    cotacao_dolar: float
    valor_milheiro_padrao: float
    percentual_bonus_transferencia_padrao: float
    parcelas_padrao: int


class PerfilUpdate(BaseModel):
    rendimento_mensal: float
    cotacao_dolar: float
    valor_milheiro_padrao: float
    percentual_bonus_transferencia_padrao: float
    parcelas_padrao: int


class CotacaoDolarOut(BaseModel):
    cotacao_dolar: Optional[float]
    encontrada: bool


# cartoes

class CartaoOut(BaseModel):
    id: int
    nome: str
    pontos_por_dolar: float
    cashback_pct: float


class CartaoCreate(BaseModel):
    nome: str
    pontos_por_dolar: float = 0.0
    cashback_pct: float = 0.0


# produtos, a wishlist da reforma

class ProdutoOut(BaseModel):
    id: int
    nome: str
    categoria: Optional[str]
    orcamento: Optional[float]
    preco_alvo: Optional[float]
    status: str
    criado_em: Optional[str]
    melhor_preco_efetivo: Optional[float] = None
    melhor_loja: Optional[str] = None


class ProdutoCreate(BaseModel):
    nome: str
    categoria: str = ""
    orcamento: float = 0.0
    preco_alvo: float = 0.0


class ProdutoUpdate(BaseModel):
    nome: str
    categoria: str = ""
    orcamento: float = 0.0
    preco_alvo: float = 0.0


class ProdutoStatusUpdate(BaseModel):
    status: str


# ofertas

class OfertaCreate(BaseModel):
    loja: str
    tipo: str = "online"
    preco_pix: float
    preco_cartao: float
    parcelas: int = 1
    pontos_por_real: float = 0.0
    pontos_por_dolar_cartao: float = 0.0
    percentual_bonus_transferencia: float = 0.0
    valor_milheiro: float = 0.0
    cashback_pct: float = 0.0
    frete: float = 0.0
    cupom: float = 0.0
    observacoes: str = ""
    validade: str = ""
    confianca: str = "confirmada"


class OfertaUpdate(OfertaCreate):
    pass


class ResultadoCalculoOut(BaseModel):
    valor_pontos_pix: float
    cashback_valor_pix: float
    preco_efetivo_pix: float
    rendimento_parcelamento: float
    valor_pontos_cartao: float
    cashback_valor_cartao: float
    preco_efetivo_cartao: float
    melhor_forma_pagamento: str
    preco_efetivo: float
    economia_vs_anunciado: float


class OfertaOut(BaseModel):
    id: int
    produto_id: int
    loja: str
    tipo: str
    preco_pix: float
    preco_cartao: float
    parcelas: int
    pontos_por_real: float
    pontos_por_dolar_cartao: float
    percentual_bonus_transferencia: float
    valor_milheiro: float
    cashback_pct: float
    frete: float
    cupom: float
    observacoes: Optional[str]
    validade: Optional[str]
    confianca: str
    preco_efetivo: Optional[float]
    url_produto: Optional[str]
    logo_url: Optional[str] = None
    imagem_produto: Optional[str] = None
    origem: Optional[str] = None
    atualizada_em: Optional[str]
    criado_em: Optional[str]
    resultado: ResultadoCalculoOut


class ResultadoAutomaticoOut(BaseModel):
    loja: str
    tipo: str
    preco_pix: float
    preco_cartao: float
    parcelas: int
    pontos_por_real: float
    parceiro_encontrado: bool
    parceiro_nome: Optional[str]
    confianca_pix_cartao: bool
    url_produto: str
    logo_url: str = ""
    imagem_produto: str = ""
    origem: str = "google_shopping"
    resultado: ResultadoCalculoOut


class PesquisaAutomaticaOut(BaseModel):
    """
    , envelope da resposta da pesquisa automatica, alem do ranking de ofertas, informa se o resultado veio do cache ou de uma consulta nova, e quais fontes, quando houve alguma, falharam durante a busca, sem interromper a pesquisa
    """

    resultados: list[ResultadoAutomaticoOut]
    veio_do_cache: bool = False
    fontes_com_erro: dict[str, str] = Field(default_factory=dict)


class CalculoLivreOut(BaseModel):
    """
    , resultado da calculadora livre, a mesma logica de calculo de uma oferta, so que sem estar ligada a nenhum produto nem gravar nada no banco, util para simular qualquer compra do dia a dia
    """

    resultado: ResultadoCalculoOut


class SimulacaoParcelamentoIn(BaseModel):
    preco_pix: float
    preco_cartao: float
    rendimento_mensal: float
    max_parcelas: int = Field(default=12, le=36)


class ParcelaSimuladaOut(BaseModel):
    parcelas: int
    custo_efetivo: float


# historico

class HistoricoOut(BaseModel):
    id: int
    produto_id: int
    loja: str
    preco_anunciado: Optional[float]
    preco_efetivo: Optional[float]
    registrado_em: Optional[str]
    origem: Optional[str] = None


class ParceiroLiveloOut(BaseModel):
    nome: str
    alias: str
    pontos_padrao: float
