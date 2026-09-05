"""
orquestrador da pesquisa automatica de um produto.

este modulo junta duas fontes de dados para montar uma oferta por
loja automaticamente, sem que voce precise digitar nada na mao na
maioria dos casos.

primeiro, o buscape e consultado para descobrir o preco e a lista de
lojas que vendem o produto, ver scrapers/buscape.py.

segundo, para cada loja encontrada, o modulo tenta casar o nome da
loja com um parceiro ja cadastrado na tabela livelo_parceiros, pelo
nome. essa tabela nao e mais alimentada por um scraper automatico da
livelo, porque o site bloqueia qualquer acesso automatizado a nivel
de dominio, atraves do akamai, o bloqueio acontece antes mesmo do
conteudo da pagina carregar, entao nao importa qual pagina do site e
consultada, o resultado e sempre access denied, ver o html salvo em
scrapers/debug_livelo.html. por isso a tabela e mantida por cadastro
manual, feito uma vez por parceiro em app.py e reaproveitado em todas
as pesquisas seguintes.

quando uma loja encontrada no buscape nao bate com nenhum parceiro
cadastrado, o resultado marca isso claramente, com pontos_por_real
zerado e parceiro_encontrado como False, para voce saber que precisa
cadastrar esse parceiro ou editar a oferta manualmente com o botao
editar variaveis.
"""

from dataclasses import dataclass
from typing import Optional

from engine.price_engine import Oferta, ResultadoOferta, calcular_oferta

VALOR_MILHEIRO_PADRAO_PESQUISA = 15.0
BONUS_TRANSFERENCIA_PADRAO_PESQUISA = 80.0
PARCELAS_PADRAO_PESQUISA = 6


@dataclass
class ResultadoAutomatico:
    """
    resultado de uma loja encontrada automaticamente, com a oferta
    montada, o parceiro livelo casado, quando houver, e o calculo
    ja pronto para mostrar na tela.
    """

    oferta: Oferta
    resultado: ResultadoOferta
    parceiro_encontrado: bool
    parceiro_nome: Optional[str]
    confianca_pix_cartao: bool


def _normalizar_nome_loja(nome):
    return " ".join(nome.strip().lower().split())


def casar_parceiro_livelo(nome_loja, parceiros_cadastrados):
    """
    tenta encontrar, entre os parceiros ja cadastrados manualmente,
    aquele cujo nome mais se aproxima do nome da loja encontrada no
    buscape.

    usa comparacao simples de substring nos dois sentidos, o
    suficiente para nomes como "fast shop" e "fast shop oficial", mas
    nomes bem diferentes do mesmo grupo, tipo "magazine luiza" contra
    o apelido "magalu", ainda vao exigir que voce cadastre o parceiro
    usando o mesmo nome que aparece nos resultados do buscape, ou um
    apelido reconhecivel.
    """
    nome_normalizado = _normalizar_nome_loja(nome_loja)
    for parceiro in parceiros_cadastrados:
        nome_parceiro_normalizado = _normalizar_nome_loja(parceiro["nome"])
        if nome_normalizado in nome_parceiro_normalizado or nome_parceiro_normalizado in nome_normalizado:
            return parceiro
    return None


def montar_oferta_a_partir_do_buscape(oferta_buscape, parceiros_cadastrados, cotacao_dolar,
                                       pontos_por_dolar_cartao_padrao,
                                       valor_milheiro=VALOR_MILHEIRO_PADRAO_PESQUISA,
                                       percentual_bonus_transferencia=BONUS_TRANSFERENCIA_PADRAO_PESQUISA,
                                       parcelas=PARCELAS_PADRAO_PESQUISA):
    """
    monta uma Oferta pronta para calculo a partir de uma oferta
    encontrada no buscape, ja tentando casar com um parceiro livelo
    cadastrado manualmente. devolve a oferta, o parceiro casado, ou
    none quando nao encontrado, e se a distincao entre pix e cartao
    veio confiavel do buscape.
    """
    parceiro = casar_parceiro_livelo(oferta_buscape.loja, parceiros_cadastrados)
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


def pesquisar_produto_automaticamente(nome_produto, parceiros_cadastrados, cdi_mensal,
                                       cotacao_dolar, pontos_por_dolar_cartao_padrao,
                                       buscador_buscape=None,
                                       valor_milheiro=VALOR_MILHEIRO_PADRAO_PESQUISA,
                                       percentual_bonus_transferencia=BONUS_TRANSFERENCIA_PADRAO_PESQUISA,
                                       parcelas=PARCELAS_PADRAO_PESQUISA):
    """
    pesquisa um produto no buscape e devolve o ranking automatico de
    ofertas, ja calculado da mais barata para a mais cara.

    buscador_buscape e injetavel para facilitar teste sem depender de
    rede real ou do playwright, por padrao usa
    scrapers.buscape.buscar_ofertas_buscape. deixa propagar
    ErroScraperBuscape quando a busca falhar, o chamador decide como
    mostrar isso na tela.
    """
    if buscador_buscape is None:
        from scrapers.buscape import buscar_ofertas_buscape as buscador_buscape

    ofertas_buscape = buscador_buscape(nome_produto)

    resultados = []
    for oferta_buscape in ofertas_buscape:
        oferta, parceiro, distincao_confiavel = montar_oferta_a_partir_do_buscape(
            oferta_buscape, parceiros_cadastrados, cotacao_dolar, pontos_por_dolar_cartao_padrao,
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
