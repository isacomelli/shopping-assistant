"""
orquestrador da pesquisa automatica de um produto.

este modulo junta duas fontes de dados para montar uma oferta por
loja automaticamente, sem que voce precise digitar nada na mao na
maioria dos casos.

primeiro, o buscape e consultado para descobrir o preco e a lista de
lojas que vendem o produto, ver scrapers/buscape.py.

segundo, para cada loja encontrada, o modulo tenta casar o nome da
loja com um parceiro Livelo conhecido, atraves de
casamento_lojas.encontrar_parceiro_equivalente contra a lista fixa
PARCEIROS_LIVELO_CONHECIDOS, cadastrada a mao em
services/casamento_lojas.py. nao ha scraper, tabela no banco nem
endpoint envolvido nesse casamento, so essa lista fixa, ja que a
pagina publica de parceiros da livelo e bloqueada pelo akamai e nao
da pra manter uma lista dinamica atualizada.

quando uma loja encontrada no buscape nao bate com nenhum parceiro
conhecido, o resultado marca isso claramente, com pontos_por_real
zerado e parceiro_encontrado como False, para voce saber que precisa
adicionar esse parceiro em PARCEIROS_LIVELO_CONHECIDOS ou editar a
oferta manualmente depois.

quando o parceiro casa, a logo exibida na tela tambem vem daqui, montada por casamento_lojas.obter_url_logo_parceiro a partir do codigo do proprio parceiro, em vez de qualquer logo do buscape.

sobre o numero de parcelas, terceiro, o buscape ja informa quantas parcelas a loja anuncia, tipo "10x de R$ 165,70", em oferta_buscape.parcelas, e esse numero real e sempre priorizado quando confianca_pix_cartao vier True. o parametro parcelas_quando_nao_confirmado so entra quando o buscape nao reconheceu nenhum parcelamento, e vem do perfil financeiro, cadastrado em user_settings.parcelas_padrao, em vez de um numero fixo no codigo. o mesmo vale para valor_milheiro e percentual_bonus_transferencia, ambos lidos do perfil pelo chamador desta funcao e repassados aqui, nunca fixos no codigo.
"""

from dataclasses import dataclass
from typing import Optional

from services.casamento_lojas import (
    PARCEIROS_LIVELO_CONHECIDOS,
    encontrar_parceiro_equivalente,
    obter_url_logo_parceiro,
)
from engine.price_engine import Oferta, ResultadoOferta, calcular_oferta

# valores usados apenas quando esta funcao e chamada diretamente sem informar o perfil, tipo nos testes. em producao, routers/ofertas.py sempre repassa os valores cadastrados em user_settings.
VALOR_MILHEIRO_PADRAO_PESQUISA = 30.0
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
    logo_url: str = ""


def buscar_parceiro_para_loja(nome_loja):
    """
    tenta encontrar, entre os parceiros conhecidos em
    PARCEIROS_LIVELO_CONHECIDOS, aquele cujo nome ou apelido mais se
    aproxima do nome da loja encontrada no buscape.

    a comparacao em si e feita por
    casamento_lojas.encontrar_parceiro_equivalente. nomes bem
    diferentes do mesmo grupo, tipo "magazine luiza" contra o apelido
    "magalu", casam mesmo sem alias exatamente igual, atraves dos
    grupos de apelidos conhecidos desse modulo, ver GRUPOS_DE_APELIDOS
    em services/casamento_lojas.py.
    """
    return encontrar_parceiro_equivalente(nome_loja, PARCEIROS_LIVELO_CONHECIDOS)


def _escolher_parcelas(oferta_buscape, parcelas_quando_nao_confirmado):
    """
    decide quantas parcelas usar no calculo desta oferta. quando o buscape confirmou um parcelamento de verdade no cartao de resultado, confianca_pix_cartao True, o numero real de parcelas anunciado pela loja, oferta_buscape.parcelas, e sempre priorizado, ja que ele tambem foi usado para compor o proprio preco_cartao, ver scrapers/buscape.py. so cai para parcelas_quando_nao_confirmado, vindo do perfil financeiro, quando o buscape nao reconheceu nenhum parcelamento.
    """
    if oferta_buscape.confianca_pix_cartao and oferta_buscape.parcelas > 1:
        return oferta_buscape.parcelas
    return parcelas_quando_nao_confirmado


def montar_oferta_a_partir_do_buscape(oferta_buscape, cotacao_dolar,
                                       pontos_por_dolar_cartao_padrao,
                                       valor_milheiro=VALOR_MILHEIRO_PADRAO_PESQUISA,
                                       percentual_bonus_transferencia=BONUS_TRANSFERENCIA_PADRAO_PESQUISA,
                                       parcelas_quando_nao_confirmado=PARCELAS_PADRAO_PESQUISA):
    """
    monta uma Oferta pronta para calculo a partir de uma oferta
    encontrada no buscape, ja tentando casar com um parceiro
    cadastrado. devolve a oferta, o parceiro casado, ou none quando
    nao encontrado, e se a distincao entre pix e cartao veio confiavel
    do buscape.
    """
    parceiro = buscar_parceiro_para_loja(oferta_buscape.loja)
    pontos_por_real = float(parceiro["pontos_padrao"]) if parceiro else 0.0
    logo_url = obter_url_logo_parceiro(parceiro) if parceiro else ""

    oferta = Oferta(
        loja=oferta_buscape.loja,
        preco=oferta_buscape.preco,
        preco_pix=oferta_buscape.preco_pix,
        preco_cartao=oferta_buscape.preco_cartao,
        parcelas=_escolher_parcelas(oferta_buscape, parcelas_quando_nao_confirmado),
        tipo="online",
        pontos_por_real=pontos_por_real,
        cotacao_dolar=cotacao_dolar,
        pontos_por_dolar_cartao=pontos_por_dolar_cartao_padrao,
        percentual_bonus_transferencia=percentual_bonus_transferencia,
        valor_milheiro=valor_milheiro,
        url_produto=getattr(oferta_buscape, "url_produto", ""),
        logo_url=logo_url,
    )

    return oferta, parceiro, oferta_buscape.confianca_pix_cartao


def pesquisar_produto_automaticamente(nome_produto, rendimento_mensal,
                                       cotacao_dolar, pontos_por_dolar_cartao_padrao,
                                       buscar_ofertas_buscape=None,
                                       valor_milheiro=VALOR_MILHEIRO_PADRAO_PESQUISA,
                                       percentual_bonus_transferencia=BONUS_TRANSFERENCIA_PADRAO_PESQUISA,
                                       parcelas_quando_nao_confirmado=PARCELAS_PADRAO_PESQUISA):
    """
    pesquisa um produto no buscape e devolve o ranking automatico de
    ofertas, ja calculado da mais barata para a mais cara.

    valor_milheiro, percentual_bonus_transferencia e
    parcelas_quando_nao_confirmado devem vir do perfil financeiro
    cadastrado pelo usuario, quem chama esta funcao e responsavel por
    ler user_settings e repassar aqui, os valores padrao deste modulo
    servem so para chamadas diretas, tipo em teste.

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
            valor_milheiro, percentual_bonus_transferencia, parcelas_quando_nao_confirmado,
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
                logo_url=oferta.logo_url,
            )
        )

    resultados.sort(key=lambda r: r.resultado.preco_efetivo)
    return resultados