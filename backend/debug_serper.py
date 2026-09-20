"""
script auxiliar para inspecionar a resposta bruta da api do serper antes de qualquer filtro do app, util para entender por que uma loja como o mercado livre aparece no google e nao aparece no ranking final.

coloque este arquivo dentro da pasta backend do projeto, ao lado de main.py, e rode de la, com a variavel de ambiente SERPER_API_KEY ja definida,

    python debug_serper.py "aquecedor komeco 16 litros gas natural inox"

salva tres arquivos em debug_output, o json bruto devolvido pela serper, a lista ja convertida em ofertas antes do filtro de qualidade, e a lista final depois do filtro e da deduplicacao, para comparar os tres passo a passo e ver exatamente onde cada oferta se perde.

o arquivo .env do projeto so e lido pelo docker-compose na hora de montar o container da api, rodando este script fora do docker essa variavel nao chega sozinha no processo. por isso o script chama load_dotenv, da biblioteca python-dotenv, apontando primeiro para um .env em backend/, ao lado deste arquivo, e depois para um .env na raiz do repositorio, um nivel acima. se a biblioteca ainda nao estiver instalada,

    pip install python-dotenv
"""

import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _carregar_env_local():
    """
    chama load_dotenv apontando para o .env em backend/, ao lado deste script, e depois para um .env na raiz do repositorio, um nivel acima. load_dotenv nao sobrescreve uma variavel que ja estiver definida no ambiente, entao um export feito na mao no terminal sempre continua tendo prioridade sobre o .env.
    """
    pasta_backend = Path(__file__).resolve().parent
    load_dotenv(pasta_backend / ".env")
    load_dotenv(pasta_backend.parent / ".env")

from services.google_shopping import URL_API_SERPER, TIMEOUT_API_SEGUNDOS, _ofertas_do_serper
from services.normalizacao_lojas import (
    _chave_deduplicacao,
    padronizar_nome_loja,
    resultado_parece_produto_principal,
)

PASTA_SAIDA = Path(__file__).parent / "debug_output"


def buscar_json_bruto(termo, chave_api):
    resposta = requests.post(
        URL_API_SERPER,
        headers={"X-API-KEY": chave_api, "Content-Type": "application/json"},
        json={"q": termo, "gl": "br", "hl": "pt-br", "num": 100},
        timeout=TIMEOUT_API_SEGUNDOS,
    )
    resposta.raise_for_status()
    return resposta.json()


def separar_motivo_de_descarte(ofertas, termo):
    """
    reproduz manualmente o que normalizar_e_filtrar_ofertas faz por dentro, so que guardando o motivo de cada oferta descartada, filtro de qualidade ou duplicata, em vez de so devolver a lista final pronta.
    """
    aprovadas_no_filtro = []
    descartadas_pelo_filtro = []

    for oferta in ofertas:
        oferta.loja = padronizar_nome_loja(oferta.loja)
        nome_produto_encontrado = getattr(oferta, "nome_produto", "") or oferta.loja
        if resultado_parece_produto_principal(nome_produto_encontrado, termo):
            aprovadas_no_filtro.append(oferta)
        else:
            descartadas_pelo_filtro.append(oferta)

    vistas = {}
    finais = []
    descartadas_por_duplicata = []
    for oferta in aprovadas_no_filtro:
        chave = _chave_deduplicacao(oferta)
        if chave in vistas:
            descartadas_por_duplicata.append((oferta, vistas[chave]))
            continue
        vistas[chave] = oferta
        finais.append(oferta)

    return finais, descartadas_pelo_filtro, descartadas_por_duplicata


def salvar(nome, dados):
    PASTA_SAIDA.mkdir(exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = PASTA_SAIDA / f"{nome}_{carimbo}.json"
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"salvo em {caminho}")
    return caminho


def main():
    if len(sys.argv) < 2:
        print('uso, python debug_serper.py "termo de busca"')
        sys.exit(1)
    termo = sys.argv[1]

    _carregar_env_local()
    chave_api = os.environ.get("SERPER_API_KEY", "").strip()
    if not chave_api:
        print("SERPER_API_KEY nao foi encontrada nem no ambiente nem num .env em backend/ ou na raiz do repositorio")
        sys.exit(1)

    dados_brutos = buscar_json_bruto(termo, chave_api)
    salvar("serper_bruto", dados_brutos)

    itens_shopping = dados_brutos.get("shopping", [])
    print(f"a serper devolveu {len(itens_shopping)} itens no campo shopping")

    ofertas = _ofertas_do_serper(dados_brutos)
    print(f"{len(ofertas)} viraram OfertaGoogleShopping, com preco, loja e link reconhecidos")
    salvar("ofertas_antes_do_filtro", [asdict(o) for o in ofertas])

    finais, descartadas_pelo_filtro, descartadas_por_duplicata = separar_motivo_de_descarte(ofertas, termo)

    print(f"{len(finais)} sobreviveram ao filtro de qualidade e a deduplicacao")

    print(f"{len(descartadas_pelo_filtro)} foram descartadas pelo filtro de qualidade, sobreposicao de palavras baixa ou termo secundario no nome")
    for oferta in descartadas_pelo_filtro:
        print(f"  descartada, {oferta.loja}, {oferta.nome_produto!r}")

    print(f"{len(descartadas_por_duplicata)} foram descartadas por bater a mesma chave de deduplicacao de outra oferta")
    for oferta, oferta_mantida in descartadas_por_duplicata:
        print(f"  descartada, {oferta.loja} {oferta.preco}, considerada duplicata de {oferta_mantida.loja} {oferta_mantida.preco}")

    salvar("ofertas_finais", [asdict(o) for o in finais])


if __name__ == "__main__":
    main()