"""
orquestrador da pesquisa automatica de um produto.

este modulo junta duas fontes de dados para montar uma oferta por
loja automaticamente, sem que voce precise digitar nada na mao.

primeiro, o buscape e consultado para descobrir o preco e a lista de
lojas que vendem o produto, ver scrapers/buscape.py.

segundo, para cada loja encontrada, o modulo consulta diretamente a
livelo, atraves da busca por loja em scrapers/livelo.py,
buscar_parceiro_livelo, que pesquisa livelo.com.br/busca?query= pelo
nome da loja. quando a loja e parceira, o resultado traz a
pontuacao por real ou por dolar. quando nao e, o resultado so marca
isso, com pontos_por_real zerado e parceiro_encontrado como False, a
oferta continua aparecendo no ranking normalmente, so sem pontos.

nao existe mais cadastro manual de parceiro, nem tabela auxiliar no
banco, a consulta e sempre em tempo real, uma loja por vez.
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
    montada, o parceiro livelo encontrado na busca, quando houver, e
    o calculo ja pronto para mostrar na tela.
    """

    oferta: Oferta
    resultado: ResultadoOferta
    parceiro_encontrado: bool
    parceiro_nome: Optional[str]
    confianca_pix_cartao: bool


def buscar_parceiro_para_loja(nome_loja, buscador_livelo):
    """
    pesquisa a loja na busca da livelo e devolve o primeiro parceiro
    reconhecido, ou none quando a loja nao for parceira.

    buscador_livelo e injetavel para facilitar teste sem depender de
    rede real ou do playwright, veja
    scrapers.livelo.buscar_parceiro_livelo para a implementacao de
    verdade. qualquer falha na consulta, por exemplo
    ErroScraperLivelo por bloqueio de bot, e tratada aqui mesmo como
    loja nao encontrada, para uma loja com problema nao travar a
    pesquisa do produto inteiro.
    """
    try:
        encontrados = buscador_livelo(nome_loja)
    except Exception:
        encontrados = []

    return encontrados[0] if encontrados else None


def montar_oferta_a_partir_do_buscape(oferta_buscape, cotacao_dolar,
                                       pontos_por_dolar_cartao_padrao,
                                       buscador_livelo,
                                       valor_milheiro=VALOR_MILHEIRO_PADRAO_PESQUISA,
                                       percentual_bonus_transferencia=BONUS_TRANSFERENCIA_PADRAO_PESQUISA,
                                       parcelas=PARCELAS_PADRAO_PESQUISA):
    """
    monta uma Oferta pronta para calculo a partir de uma oferta
    encontrada no buscape, consultando a livelo pelo nome da loja.
    devolve a oferta, o parceiro encontrado, ou none quando a loja
    nao for parceira, e se a distincao entre pix e cartao veio
    confiavel do buscape.
    """
    parceiro = buscar_parceiro_para_loja(oferta_buscape.loja, buscador_livelo)
    pontos_por_real = float(parceiro.pontos_padrao) if parceiro else 0.0

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
                                       buscador_livelo=None,
                                       valor_milheiro=VALOR_MILHEIRO_PADRAO_PESQUISA,
                                       percentual_bonus_transferencia=BONUS_TRANSFERENCIA_PADRAO_PESQUISA,
                                       parcelas=PARCELAS_PADRAO_PESQUISA):
    """
    pesquisa um produto no buscape e devolve o ranking automatico de
    ofertas, ja calculado da mais barata para a mais cara.

    para cada loja encontrada no buscape, consulta a livelo por
    loja, atraves de buscador_livelo, ver
    buscar_parceiro_para_loja.

    buscador_buscape e buscador_livelo sao injetaveis para facilitar
    teste sem depender de rede real ou do playwright, por padrao
    usam scrapers.buscape.buscar_ofertas_buscape e
    scrapers.livelo.buscar_parceiro_livelo. deixa propagar
    ErroScraperBuscape quando a busca do buscape falhar, o chamador
    decide como mostrar isso na tela. falha na consulta da livelo,
    por loja, nao interrompe a pesquisa, ver
    buscar_parceiro_para_loja.
    """
    if buscador_buscape is None:
        from scrapers.buscape import buscar_ofertas_buscape as buscador_buscape

    if buscador_livelo is None:
        from scrapers.livelo import buscar_parceiro_livelo as buscador_livelo

    ofertas_buscape = buscador_buscape(nome_produto)

    resultados = []
    for oferta_buscape in ofertas_buscape:
        oferta, parceiro, distincao_confiavel = montar_oferta_a_partir_do_buscape(
            oferta_buscape, cotacao_dolar, pontos_por_dolar_cartao_padrao,
            buscador_livelo, valor_milheiro, percentual_bonus_transferencia, parcelas,
        )
        resultado = calcular_oferta(oferta, cdi_mensal)
        resultados.append(
            ResultadoAutomatico(
                oferta=oferta,
                resultado=resultado,
                parceiro_encontrado=parceiro is not None,
                parceiro_nome=parceiro.nome if parceiro else None,
                confianca_pix_cartao=distincao_confiavel,
            )
        )

    resultados.sort(key=lambda r: r.resultado.preco_efetivo)
    return resultados