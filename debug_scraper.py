"""
script auxiliar para testar os scrapers fora do streamlit, direto pelo
terminal, sem precisar abrir o app inteiro so pra ver o que cada
scraper esta trazendo.

exemplo de uso, pesquisar um produto no buscape, com o navegador
visivel na tela,

python debug_scraper.py buscape "geladeira electrolux tf39" --mostrar-navegador

exemplo de uso, consultar um parceiro no meliuz, em modo headless,

python debug_scraper.py meliuz "Fast Shop"

exemplo de uso, consultar se uma loja e parceira livelo, pelo nome da
loja encontrado no buscape,

python debug_scraper.py livelo "Fast Shop"

exemplo de uso, reprocessar um html do buscape ja salvo em disco, sem
abrir o navegador, util depois de ajustar os seletores em
scrapers/buscape.py,

python debug_scraper.py buscape "geladeira" --reparsear scrapers/ultimo_html_buscape.html

o termo da livelo agora e o nome da loja pesquisada, ja que o scraper
consulta a busca da livelo por loja, em vez de ler a lista inteira de
parceiros, ver o topo de scrapers/livelo.py.

por padrao, o resultado aparece formatado no terminal e tambem e salvo
em debug_output, como json, para dar para comparar pesquisas
diferentes depois, ou colar o retorno em algum lugar para analisar com
calma. use --sem-salvar se so quiser ver no terminal.

este script nao muda nenhuma logica dos scrapers, ele so chama as
mesmas funcoes que o app usa e imprime o retorno de um jeito mais
facil de ler.

exemplo de uso, reprocessar um html da livelo ja salvo em disco, sem
abrir o navegador, util depois de ajustar as expressoes regulares em
scrapers/livelo.py,

python debug_scraper.py livelo "Fast Shop" --reparsear scrapers/ultimo_html_livelo.html
"""

import argparse
import dataclasses
import json
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import asdict
from tabulate import tabulate

PASTA_SAIDA = Path(__file__).parent / "debug_output"


def _para_dict(objeto):
    """
    converte o retorno de um scraper, seja um dataclass unico ou uma
    lista deles, para algo que da para serializar em json.
    """
    if dataclasses.is_dataclass(objeto):
        return dataclasses.asdict(objeto)
    if isinstance(objeto, list):
        return [_para_dict(item) for item in objeto]
    return objeto


def _slug(texto, limite=40):
    letras = [c if c.isalnum() else "_" for c in texto.lower().strip()]
    slug = "".join(letras)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")[:limite] or "sem_termo"


def _salvar_json(nome_scraper, termo, dados):
    PASTA_SAIDA.mkdir(exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = PASTA_SAIDA / f"{nome_scraper}_{_slug(termo)}_{carimbo}.json"
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


def rodar_buscape(termo, headless):
    from scrapers.buscape import ErroScraperBuscape, buscar_ofertas_buscape

    try:
        ofertas = buscar_ofertas_buscape(termo, headless=headless)
    except ErroScraperBuscape as erro:
        print(f"erro no scraper do buscape, {erro}")
        sys.exit(1)

    print(f"{len(ofertas)} ofertas encontradas para {termo!r}\n")
    print(tabulate(
        [{k: v for k, v in asdict(o).items() if k not in ("url_produto", 'nome_produto')} for o in ofertas],
        headers="keys",
        tablefmt="github"
    ))


def rodar_buscape_de_arquivo(caminho_html):
    """
    reprocessa um html do buscape ja salvo em disco, sem abrir o
    navegador, util para ajustar os seletores em scrapers/buscape.py
    rapidamente, testando varias vezes em cima do mesmo html.
    """
    from scrapers.buscape import parsear_html_buscape

    html = Path(caminho_html).read_text(encoding="utf-8")
    cartoes, ofertas = parsear_html_buscape(html)

    print(f"{len(cartoes)} cartoes de resultado encontrados no html")
    print(f"{len(ofertas)} ofertas com preco reconhecido\n")

    print(tabulate(
            [{k: v for k, v in asdict(o).items() if k not in ("url_produto", 'nome_produto')} for o in ofertas],
            headers="keys",
            tablefmt="github"
        ))
    
    return ofertas


def rodar_livelo(termo, headless):
    from scrapers.livelo import ErroScraperLivelo, buscar_parceiro_livelo

    try:
        parceiros = buscar_parceiro_livelo(termo, headless=headless)
    except ErroScraperLivelo as erro:
        print(f"erro no scraper da livelo, {erro}")
        sys.exit(1)

    if not parceiros:
        print(f"nenhum parceiro livelo encontrado para {termo!r}, essa loja provavelmente nao e parceira")
        return parceiros

    print(f"{len(parceiros)} parceiro(s) encontrado(s) para {termo!r}\n")
    for parceiro in parceiros:
        print(
            f"- {parceiro.nome}, {parceiro.pontos_padrao} pontos por "
            f"{parceiro.moeda_padrao}, em promocao, {parceiro.em_promocao}"
        )
    return parceiros


def rodar_livelo_de_arquivo(caminho_html):
    """
    reprocessa um html da livelo ja salvo em disco, sem abrir o
    navegador, util para ajustar as expressoes regulares em
    scrapers/livelo.py rapidamente, testando varias vezes em cima do
    mesmo html, por exemplo scrapers/ultimo_html_livelo.html, salvo
    apos toda coleta, ou scrapers/debug_livelo.html, salvo so quando
    nenhum parceiro foi reconhecido.
    """
    from scrapers.livelo import parsear_html_livelo

    html = Path(caminho_html).read_text(encoding="utf-8")
    parceiros = parsear_html_livelo(html)

    print(f"{len(parceiros)} parceiros reconhecidos no html\n")
    print(tabulate(
        [asdict(p) for p in parceiros],
        headers="keys",
        tablefmt="github",
    ))

    return parceiros


def rodar_meliuz(termo, headless):
    from scrapers.meliuz import buscar_cashback_por_loja

    resultado = buscar_cashback_por_loja(termo, headless=headless)
    if resultado.encontrado:
        print(
            f"{termo}, cashback de {resultado.cashback_pct}%, "
            f"consultado em {resultado.url_consultada}"
        )
    else:
        print(f"{termo}, nenhum cashback encontrado, {resultado.mensagem}")
    return resultado


SCRAPERS = {
    "buscape": rodar_buscape,
    "livelo": rodar_livelo,
    "meliuz": rodar_meliuz,
}


def main():
    parser = argparse.ArgumentParser(
        description="testa um scraper isolado e mostra o retorno bruto no terminal",
    )
    parser.add_argument("scraper", choices=sorted(SCRAPERS.keys()), help="qual scraper rodar")
    parser.add_argument("termo", help="produto ou loja a pesquisar, entre aspas se tiver espaco")
    parser.add_argument(
        "--mostrar-navegador",
        action="store_true",
        help="abre o navegador visivel em vez de headless, util para ver o que esta travando",
    )
    parser.add_argument(
        "--sem-salvar",
        action="store_true",
        help="nao salva o resultado em debug_output, so mostra no terminal",
    )
    parser.add_argument(
        "--reparsear",
        metavar="ARQUIVO_HTML",
        help=(
            "so para o buscape, em vez de abrir o navegador, reprocessa um html "
            "ja salvo em disco, por exemplo scrapers/ultimo_html_buscape.html. "
            "util para ajustar os seletores sem gastar tempo com rede"
        ),
    )
    args = parser.parse_args()

    if args.reparsear:
        if args.scraper == "buscape":
            resultado = rodar_buscape_de_arquivo(args.reparsear)
        elif args.scraper == "livelo":
            resultado = rodar_livelo_de_arquivo(args.reparsear)
        else:
            print("--reparsear so esta implementado para buscape e livelo por enquanto")
            sys.exit(1)
    else:
        funcao = SCRAPERS[args.scraper]
        resultado = funcao(args.termo, headless=not args.mostrar_navegador)

    if not args.sem_salvar:
        caminho = _salvar_json(args.scraper, args.termo, _para_dict(resultado))
        print(f"\nresultado completo salvo em {caminho}")


if __name__ == "__main__":
    main()