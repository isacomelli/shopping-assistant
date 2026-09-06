"""
orquestrador da pesquisa automatica de um produto.

este modulo junta duas fontes de dados para montar uma oferta por
loja automaticamente, sem que voce precise digitar nada na mao.

primeiro, o buscape e consultado para descobrir o preco e a lista de
lojas que vendem o produto, ver scrapers/buscape.py.

segundo, para cada loja encontrada, o modulo consulta os parceiros
livelo ja carregados no banco de dados no startup do app. quando a
loja e parceira, o resultado traz a pontuacao por real ou por dolar.
quando nao e, o resultado so marca isso, com pontos_por_real zerado e
parceiro_encontrado como False, a oferta continua aparecendo no
ranking normalmente, so sem pontos.

nao existe mais consulta live ao site da livelo durante a pesquisa de
produto, o que elimina o gargalo de abrir o playwright para cada loja.
"""

from dataclasses import dataclass
from typing import Optional

from database import db
from engine.price_engine import Oferta, ResultadoOferta, calcular_oferta

VALOR_MILHEIRO_PADRAO_PESQUISA = 15.0
BONUS_TRANSFERENCIA_PADRAO_PESQUISA = 80.0
PARCELAS_PADRAO_PESQUISA = 6


@dataclass
class ResultadoAutomatico:
    """
    resultado de uma loja encontrada automaticamente, com a oferta
    montada, o parceiro livelo encontrado na busca, quando houver, e
    o calculo ja pronto para mostrar na tela.
    """

    oferta: Oferta
    resultado: ResultadoOferta
    parceiro_encontrado: bool
    parceiro_nome: Optional[str]
    confianca_pix_cartao: bool


def buscar_parceiro_para_loja(nome_loja):
    """
    pesquisa a loja nos parceiros livelo ja carregados no banco de
    dados no startup do app. devolve o primeiro parceiro casado, ou
    none quando a loja nao for parceira.
    """
    return db.buscar_parceiro_livelo_por_nome(nome_loja)


def montar_oferta_a_partir_do_buscape(oferta_buscape, cotacao_dolar,
                                       pontos_por_dolar_cartao_padrao,
                                       valor_milheiro=VALOR_MILHEIRO_PADRAO_PESQUISA,
                                       percentual_bonus_transferencia=BONUS_TRANSFERENCIA_PADRAO_PESQUISA,
                                       parcelas=PARCELAS_PADRAO_PESQUISA):
    """
    monta uma Oferta pronta para calculo a partir de uma oferta
    encontrada no buscape, consultando os parceiros livelo em cache.
    """
    parceiro = buscar_parceiro_para_loja(oferta_buscape.loja)
    pontos_por_real = float(parceiro["pontos_padrao"]) if parceiro else 0.0

    oferta = Oferta(
        loja=oferta_buscape.loja,
        preco_pix=oferta_buscape.preco_pix,
        preco_cartao=oferta_buscape.preco_cartao,
        parcelas=parcelas,
        tipo="online",
        pontos_por_real=pontos_por_real,
        cotacao_dolar=cotacao_dolar,
        pontos_por_dolar_cartao=pontos_por_dolar_cartao_padrao,
        percentual_bonus_transferencia=percentual_bonus_transferencia,
        valor_milheiro=valor_milheiro,
    )

    return oferta, parceiro, oferta_buscape.confianca_pix_cartao


def pesquisar_produto_automaticamente(nome_produto, cdi_mensal,
                                       cotacao_dolar, pontos_por_dolar_cartao_padrao,
                                       buscador_buscape=None,
                                       valor_milheiro=VALOR_MILHEIRO_PADRAO_PESQUISA,
                                       percentual_bonus_transferencia=BONUS_TRANSFERENCIA_PADRAO_PESQUISA,
                                       parcelas=PARCELAS_PADRAO_PESQUISA):
    """
    pesquisa um produto no buscape e devolve o ranking automatico de
    ofertas, ja calculado da mais barata para a mais cara.

    para cada loja encontrada no buscape, consulta os parceiros livelo
    ja carregados no banco no startup do app.
    """
    if buscador_buscape is None:
        from scrapers.buscape import buscar_ofertas_buscape as buscador_buscape

    ofertas_buscape = buscador_buscape(nome_produto)

    resultados = []
    for oferta_buscape in ofertas_buscape:
        oferta, parceiro, distincao_confiavel = montar_oferta_a_partir_do_buscape(
            oferta_buscape, cotacao_dolar, pontos_por_dolar_cartao_padrao,
            valor_milheiro, percentual_bonus_transferencia, parcelas,
        )
        resultado = calcular_oferta(oferta, cdi_mensal)
        resultados.append(
            ResultadoAutomatico(
                oferta=oferta,
                resultado=resultado,
                parceiro_encontrado=parceiro is not None,
                parceiro_nome=parceiro["nome"] if parceiro else None,
                confianca_pix_cartao=distincao_confiavel,
            )
        )

    resultados.sort(key=lambda r: r.resultado.preco_efetivo)
    return resultados