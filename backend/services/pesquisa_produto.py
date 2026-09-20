"""
orquestrador da pesquisa automatica de um produto.

este modulo junta tres fontes de dados para montar uma oferta por loja automaticamente, sem que voce precise digitar nada na mao na maioria dos casos.

primeiro, o google shopping e consultado como fonte principal, trazendo uma quantidade muito maior de lojas do que o buscape sozinho, incluindo lojas como leroy merlin, shopee, aliexpress, mercado livre e fast shop, que o buscape raramente lista, ver services/google_shopping.py.

segundo, quando a pesquisa pede a fonte complementar, o buscape tambem e consultado, e as ofertas das duas fontes sao unidas e deduplicadas por services/normalizacao_lojas.normalizar_e_filtrar_ofertas, cada oferta guarda de qual fonte ela veio, atraves do campo origem, o buscape nunca e usado sozinho, ele so complementa o google shopping.

terceiro, para cada loja encontrada, o modulo tenta casar o nome da loja com um parceiro livelo conhecido, atraves de casamento_lojas.encontrar_parceiro_equivalente contra a lista fixa PARCEIROS_LIVELO_CONHECIDOS, cadastrada a mao em services/casamento_lojas.py, nao ha scraper, tabela no banco nem endpoint envolvido nesse casamento, so essa lista fixa, ja que a pagina publica de parceiros da livelo e bloqueada pelo akamai e nao da pra manter uma lista dinamica atualizada.

quando uma loja encontrada nao bate com nenhum parceiro conhecido, o resultado marca isso claramente, com pontos_por_real zerado e parceiro_encontrado como False, para voce saber que precisa adicionar esse parceiro em PARCEIROS_LIVELO_CONHECIDOS ou editar a oferta manualmente depois. importante, isso nunca zera os pontos do proprio cartao de credito, os pontos do cartao existem sempre que o pagamento e feito no cartao, independentemente da loja ter parceria com a livelo, ver montar_oferta_a_partir_do_buscape abaixo, pontos_por_dolar_cartao vem sempre do perfil ou do cartao escolhido, nunca do casamento com a livelo.

sobre o numero de parcelas, o scraper de origem ja informa quantas parcelas a loja anuncia, tipo "10x de R$ 165,70", em oferta.parcelas, e esse numero real e sempre priorizado quando confianca_pix_cartao vier True. o parametro parcelas_quando_nao_confirmado so entra quando nenhuma fonte reconheceu um parcelamento, e vem do perfil financeiro, cadastrado em user_settings.parcelas_padrao, em vez de um numero fixo no codigo. o mesmo vale para valor_milheiro e percentual_bonus_transferencia, ambos lidos do perfil pelo chamador desta funcao e repassados aqui, nunca fixos no codigo.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

from services.casamento_lojas import (
    PARCEIROS_LIVELO_CONHECIDOS,
    encontrar_parceiro_equivalente,
    obter_url_logo_parceiro,
)
from services.normalizacao_lojas import normalizar_e_filtrar_ofertas
from engine.price_engine import Oferta, ResultadoOferta, calcular_oferta

# valores usados apenas quando esta funcao e chamada diretamente sem informar o perfil, tipo nos testes, em producao, routers/ofertas.py sempre repassa os valores cadastrados em user_settings
VALOR_MILHEIRO_PADRAO_PESQUISA = 30.0
BONUS_TRANSFERENCIA_PADRAO_PESQUISA = 80.0
PARCELAS_PADRAO_PESQUISA = 6


@dataclass
class ResultadoAutomatico:
    """
    resultado de uma loja encontrada automaticamente, com a oferta montada, o parceiro livelo casado, quando houver, o calculo ja pronto para mostrar na tela, e a origem da oferta, google shopping ou buscape
    """

    oferta: Oferta
    resultado: ResultadoOferta
    parceiro_encontrado: bool
    parceiro_nome: Optional[str]
    confianca_pix_cartao: bool
    url_produto: str = ""
    logo_url: str = ""
    imagem_produto: str = ""
    origem: str = "google_shopping"


def buscar_parceiro_para_loja(nome_loja, parceiros_conhecidos=None):
    """
    tenta encontrar um parceiro livelo equivalente ao nome da loja encontrada na pesquisa, quando parceiros_conhecidos e informado, tipicamente pelo chamador de producao em routers/ofertas.py, que passa os parceiros ja atualizados na tabela livelo_parceiros do banco, misturados com o fallback de PARCEIROS_LIVELO_CONHECIDOS para os que ainda nao tiverem sido atualizados, a busca usa essa lista, quando nao e informado, none por padrao, cai para PARCEIROS_LIVELO_CONHECIDOS sozinho, o que mantem esta funcao e seus testes funcionando sem precisar de banco nenhum
    """
    if parceiros_conhecidos is None:
        parceiros_conhecidos = PARCEIROS_LIVELO_CONHECIDOS
    return encontrar_parceiro_equivalente(nome_loja, parceiros_conhecidos)


def _escolher_parcelas(oferta_encontrada, parcelas_quando_nao_confirmado):
    """
    decide quantas parcelas usar no calculo desta oferta, quando a fonte confirmou um parcelamento de verdade, confianca_pix_cartao True, o numero real de parcelas anunciado, oferta_encontrada.parcelas, e sempre priorizado, so cai para parcelas_quando_nao_confirmado, vindo do perfil financeiro, quando nenhuma fonte reconheceu parcelamento
    """
    if getattr(oferta_encontrada, "confianca_pix_cartao", False) and getattr(oferta_encontrada, "parcelas", 1) > 1:
        return oferta_encontrada.parcelas
    return parcelas_quando_nao_confirmado


def montar_oferta_a_partir_do_buscape(oferta_buscape, cotacao_dolar,
                                       pontos_por_dolar_cartao_padrao,
                                       valor_milheiro=VALOR_MILHEIRO_PADRAO_PESQUISA,
                                       percentual_bonus_transferencia=BONUS_TRANSFERENCIA_PADRAO_PESQUISA,
                                       parcelas_quando_nao_confirmado=PARCELAS_PADRAO_PESQUISA,
                                       parceiros_conhecidos=None):
    """
    monta uma Oferta pronta para calculo a partir de um resultado encontrado por qualquer scraper de origem, buscape ou google shopping, ja que os dois expoem os mesmos campos, loja, preco, preco_pix, preco_cartao, parcelas, confianca_pix_cartao e url_produto, ja tentando casar com um parceiro cadastrado, devolve a oferta, o parceiro casado, ou none quando nao encontrado, e se a distincao entre pix e cartao veio confiavel da fonte.

    os pontos do cartao de credito, pontos_por_dolar_cartao_padrao, entram sempre na oferta montada, independentemente do parceiro ter sido encontrado ou nao, ja que pontuar no cartao nao depende de nenhuma parceria com a livelo, so o pontos_por_real do site parceiro fica zerado quando nenhum parceiro casar.

    parceiros_conhecidos segue a mesma regra de buscar_parceiro_para_loja, None cai para PARCEIROS_LIVELO_CONHECIDOS
    """
    parceiro = buscar_parceiro_para_loja(oferta_buscape.loja, parceiros_conhecidos)
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
        # cashback exibido pelo próprio Google Shopping no cartão de resultado, zero para as fontes que não informam
        cashback_pct=float(getattr(oferta_buscape, "cashback_pct", 0.0) or 0.0),
        url_produto=getattr(oferta_buscape, "url_produto", ""),
        logo_url=logo_url,
    )

    return oferta, parceiro, oferta_buscape.confianca_pix_cartao


def _buscar_no_google_shopping(nome_produto, buscar_ofertas_google_shopping):
    """
    chama o scraper do google shopping e devolve a lista de ofertas encontradas, ou uma lista vazia quando a fonte falhar, ja que o google shopping bloqueia trafego automatizado com mais frequencia do que o buscape, uma falha aqui nunca deve interromper a pesquisa inteira, so reduzir a quantidade de fontes disponiveis
    """
    if buscar_ofertas_google_shopping is None:
        from services.google_shopping import buscar_ofertas_google_shopping as buscar_ofertas_google_shopping

    try:
        return list(buscar_ofertas_google_shopping(nome_produto)), None
    except Exception as erro:
        return [], str(erro)


def _buscar_no_buscape_complementar(nome_produto, buscar_ofertas_buscape):
    """
    chama o scraper do buscape como fonte complementar, do mesmo jeito que _buscar_no_google_shopping trata a fonte principal, uma falha aqui tambem nunca interrompe a pesquisa, so reduz a quantidade de fontes disponiveis
    """
    if buscar_ofertas_buscape is None:
        from scrapers.buscape import buscar_ofertas_buscape as buscar_ofertas_buscape

    try:
        return list(buscar_ofertas_buscape(nome_produto)), None
    except Exception as erro:
        return [], str(erro)


def buscar_ofertas_combinadas(nome_produto, incluir_buscape_complementar=True,
                               buscar_ofertas_google_shopping=None, buscar_ofertas_buscape=None):
    """
    busca ofertas no google shopping como fonte principal e, quando incluir_buscape_complementar for True, tambem no buscape como fonte complementar, as duas fontes rodam em paralelo, cada uma com o seu proprio navegador, une as duas listas, marca a origem de cada oferta, e aplica normalizar_e_filtrar_ofertas para padronizar nomes de loja, remover resultados secundarios e deduplicar o conjunto final.

    devolve a tupla, lista de ofertas ja normalizadas e deduplicadas, dicionario com as mensagens de erro de cada fonte que falhou, para o chamador poder decidir se avisa o usuario mesmo quando pelo menos uma fonte funcionou
    """
    # as duas fontes rodam em paralelo, cada uma com o seu próprio navegador
    with ThreadPoolExecutor(max_workers=2) as executor:
        futuro_google = executor.submit(
            _buscar_no_google_shopping, nome_produto, buscar_ofertas_google_shopping,
        )
        futuro_buscape = None
        if incluir_buscape_complementar:
            futuro_buscape = executor.submit(
                _buscar_no_buscape_complementar, nome_produto, buscar_ofertas_buscape,
            )
        ofertas_google, erro_google = futuro_google.result()
        ofertas_buscape, erro_buscape = futuro_buscape.result() if futuro_buscape else ([], None)

    for oferta in ofertas_google:
        oferta.origem = "google_shopping"
    for oferta in ofertas_buscape:
        oferta.origem = "buscape"

    if not ofertas_google and not ofertas_buscape:
        from services.google_shopping import ErroScraperGoogleShopping
        raise ErroScraperGoogleShopping(
            erro_google or "nenhuma fonte de busca retornou ofertas para este produto"
        )

    ofertas_combinadas = normalizar_e_filtrar_ofertas(ofertas_google + ofertas_buscape, nome_produto)

    erros = {}
    if erro_google:
        erros["google_shopping"] = erro_google
    if erro_buscape:
        erros["buscape"] = erro_buscape

    return ofertas_combinadas, erros


def pesquisar_produto_automaticamente(nome_produto, rendimento_mensal,
                                       cotacao_dolar, pontos_por_dolar_cartao_padrao,
                                       incluir_buscape_complementar=True,
                                       buscar_ofertas_google_shopping=None,
                                       buscar_ofertas_buscape=None,
                                       valor_milheiro=VALOR_MILHEIRO_PADRAO_PESQUISA,
                                       percentual_bonus_transferencia=BONUS_TRANSFERENCIA_PADRAO_PESQUISA,
                                       parcelas_quando_nao_confirmado=PARCELAS_PADRAO_PESQUISA,
                                       parceiros_conhecidos=None,
                                       erros_por_fonte=None):
    """
    pesquisa um produto no google shopping, com o buscape como fonte complementar opcional, e devolve o ranking automatico de ofertas, ja calculado da mais barata para a mais cara.

    valor_milheiro, percentual_bonus_transferencia e parcelas_quando_nao_confirmado devem vir do perfil financeiro cadastrado pelo usuario, quem chama esta funcao e responsavel por ler user_settings e repassar aqui, os valores padrao deste modulo servem so para chamadas diretas, tipo em teste.

    parceiros_conhecidos e a lista de parceiros livelo usada para casar cada loja encontrada, tipicamente montada por routers/ofertas.py juntando os parceiros ja atualizados na tabela livelo_parceiros do banco com o fallback fixo de PARCEIROS_LIVELO_CONHECIDOS para os que ainda nao tiverem sido atualizados, quando None, so o fallback fixo e usado, o que mantem esta funcao testavel sem depender de banco nenhum.

    buscar_ofertas_google_shopping e buscar_ofertas_buscape sao injetaveis para facilitar teste sem depender de rede real ou do playwright, por padrao usam services.google_shopping.buscar_ofertas_google_shopping e scrapers.buscape.buscar_ofertas_buscape, deixa propagar ErroScraperGoogleShopping quando nenhuma fonte trouxer nenhuma oferta, o chamador decide como mostrar isso na tela

    erros_por_fonte, quando informado, deve ser um dicionario vazio que esta funcao preenche com a mensagem de erro de cada fonte que falhou, para o chamador avisar o usuario mesmo quando outra fonte trouxe resultados
    """
    ofertas_encontradas, erros_das_fontes = buscar_ofertas_combinadas(
        nome_produto,
        incluir_buscape_complementar=incluir_buscape_complementar,
        buscar_ofertas_google_shopping=buscar_ofertas_google_shopping,
        buscar_ofertas_buscape=buscar_ofertas_buscape,
    )
    if erros_por_fonte is not None:
        erros_por_fonte.update(erros_das_fontes)

    resultados = []
    for oferta_encontrada in ofertas_encontradas:
        oferta, parceiro, distincao_confiavel = montar_oferta_a_partir_do_buscape(
            oferta_encontrada, cotacao_dolar, pontos_por_dolar_cartao_padrao,
            valor_milheiro, percentual_bonus_transferencia, parcelas_quando_nao_confirmado,
            parceiros_conhecidos=parceiros_conhecidos,
        )
        resultado = calcular_oferta(oferta, rendimento_mensal)
        resultados.append(
            ResultadoAutomatico(
                oferta=oferta,
                resultado=resultado,
                parceiro_encontrado=parceiro is not None,
                parceiro_nome=parceiro["nome"] if parceiro else None,
                confianca_pix_cartao=distincao_confiavel,
                url_produto=getattr(oferta_encontrada, "url_produto", ""),
                logo_url=oferta.logo_url,
                imagem_produto=getattr(oferta_encontrada, "imagem_produto", ""),
                origem=getattr(oferta_encontrada, "origem", "google_shopping"),
            )
        )

    resultados.sort(key=lambda r: r.resultado.preco_efetivo)
    return resultados
