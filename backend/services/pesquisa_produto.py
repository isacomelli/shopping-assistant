"""
orquestrador da pesquisa automatica de um produto.

este modulo junta duas fontes de dados para montar uma oferta por
loja automaticamente, sem que voce precise digitar nada na mao na
maioria dos casos.

primeiro, o buscape e consultado para descobrir o preco e a lista de
lojas que vendem o produto, ver scrapers/buscape.py.

segundo, para cada loja encontrada, o modulo tenta casar o nome da
loja com um parceiro Livelo ou Esfera ja cadastrado, atraves de
database.db.buscar_parceiro_livelo_por_nome, que faz a comparacao
por substring nos dois sentidos, do jeito que buscar_parceiro_para_loja
espera. a busca sempre passa pelo modulo database.db, e nao por uma
lista carregada em memoria antecipadamente, para que o cadastro de
parceiros possa mudar entre uma pesquisa e outra sem precisar reiniciar
nada.

quando uma loja encontrada no buscape nao bate com nenhum parceiro
cadastrado, o resultado marca isso claramente, com pontos_por_real
zerado e parceiro_encontrado como False, para voce saber que precisa
cadastrar esse parceiro ou editar a oferta manualmente depois.
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
    montada, o parceiro Livelo casado, quando houver, e o calculo
    ja pronto para mostrar na tela.
    """

    oferta: Oferta
    resultado: ResultadoOferta
    parceiro_encontrado: bool
    parceiro_nome: Optional[str]
    confianca_pix_cartao: bool
    url_produto: str = ""


def buscar_parceiro_para_loja(nome_loja):
    """
    tenta encontrar, entre os parceiros ja cadastrados, aquele cujo
    nome ou apelido mais se aproxima do nome da loja encontrada no
    buscape.

    a comparacao em si e feita por database.db.buscar_parceiro_livelo_por_nome,
    que compara por substring nos dois sentidos contra o nome e o
    alias de cada parceiro. nomes bem diferentes do mesmo grupo, tipo
    "magazine luiza" contra o apelido "magalu", so casam se o alias
    correspondente estiver cadastrado.
    """
    return db.buscar_parceiro_livelo_por_nome(nome_loja)


def montar_oferta_a_partir_do_buscape(oferta_buscape, cotacao_dolar,
                                       pontos_por_dolar_cartao_padrao,
                                       valor_milheiro=VALOR_MILHEIRO_PADRAO_PESQUISA,
                                       percentual_bonus_transferencia=BONUS_TRANSFERENCIA_PADRAO_PESQUISA,
                                       parcelas=PARCELAS_PADRAO_PESQUISA):
    """
    monta uma Oferta pronta para calculo a partir de uma oferta
    encontrada no buscape, ja tentando casar com um parceiro
    cadastrado. devolve a oferta, o parceiro casado, ou none quando
    nao encontrado, e se a distincao entre pix e cartao veio confiavel
    do buscape.
    """
    parceiro = buscar_parceiro_para_loja(oferta_buscape.loja)
    pontos_por_real = float(parceiro["pontos_padrao"]) if parceiro else 0.0

    oferta = Oferta(
        loja=oferta_buscape.loja,
        preco=oferta_buscape.preco,
        preco_pix=oferta_buscape.preco_pix,
        preco_cartao=oferta_buscape.preco_cartao,
        parcelas=parcelas,
        tipo="online",
        pontos_por_real=pontos_por_real,
        cotacao_dolar=cotacao_dolar,
        pontos_por_dolar_cartao=pontos_por_dolar_cartao_padrao,
        percentual_bonus_transferencia=percentual_bonus_transferencia,
        valor_milheiro=valor_milheiro,
        url_produto=getattr(oferta_buscape, "url_produto", ""),
    )

    return oferta, parceiro, oferta_buscape.confianca_pix_cartao


def pesquisar_produto_automaticamente(nome_produto, rendimento_mensal,
                                       cotacao_dolar, pontos_por_dolar_cartao_padrao,
                                       buscar_ofertas_buscape=None,
                                       valor_milheiro=VALOR_MILHEIRO_PADRAO_PESQUISA,
                                       percentual_bonus_transferencia=BONUS_TRANSFERENCIA_PADRAO_PESQUISA,
                                       parcelas=PARCELAS_PADRAO_PESQUISA):
    """
    pesquisa um produto no buscape e devolve o ranking automatico de
    ofertas, ja calculado da mais barata para a mais cara.

    buscar_ofertas_buscape e injetavel para facilitar teste sem
    depender de rede real ou do playwright, por padrao usa
    scrapers.buscape.buscar_ofertas_buscape. deixa propagar
    ErroScraperBuscape quando a busca falhar, o chamador decide como
    mostrar isso na tela.
    """
    if buscar_ofertas_buscape is None:
        from scrapers.buscape import buscar_ofertas_buscape as buscar_ofertas_buscape

    ofertas_buscape = buscar_ofertas_buscape(nome_produto)

    resultados = []
    for oferta_buscape in ofertas_buscape:
        oferta, parceiro, distincao_confiavel = montar_oferta_a_partir_do_buscape(
            oferta_buscape, cotacao_dolar, pontos_por_dolar_cartao_padrao,
            valor_milheiro, percentual_bonus_transferencia, parcelas,
        )
        resultado = calcular_oferta(oferta, rendimento_mensal)
        resultados.append(
            ResultadoAutomatico(
                oferta=oferta,
                resultado=resultado,
                parceiro_encontrado=parceiro is not None,
                parceiro_nome=parceiro["nome"] if parceiro else None,
                confianca_pix_cartao=distincao_confiavel,
                url_produto=getattr(oferta_buscape, "url_produto", ""),
            )
        )

    resultados.sort(key=lambda r: r.resultado.preco_efetivo)
    return resultados
