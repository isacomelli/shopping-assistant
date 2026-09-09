import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.casamento_lojas import encontrar_parceiro_equivalente, nomes_equivalentes


def test_casa_por_grupo_de_apelidos_conhecido():
    assert nomes_equivalentes("Magalu", "Magazine Luiza") is True


def test_casa_por_grupo_de_apelidos_mesmo_com_sufixo_extra():
    assert nomes_equivalentes("Magazine Luiza Oficial", "magalu") is True


def test_casa_por_substring_direto():
    assert nomes_equivalentes("Fast Shop", "Fast Shop Oficial") is True


def test_casa_ignorando_acento_maiuscula_e_espaco():
    assert nomes_equivalentes("  Americanas  ", "AMERICANAS") is True
    assert nomes_equivalentes("Amazon", "AMAZON.COM.BR") is True


def test_nao_casa_lojas_totalmente_diferentes():
    assert nomes_equivalentes("Magalu", "Kabum") is False


def test_nao_casa_quando_nome_vazio():
    assert nomes_equivalentes("", "Magazine Luiza") is False
    assert nomes_equivalentes("Magalu", None) is False


def test_casa_por_similaridade_de_texto_para_pequena_variacao_de_grafia():
    assert nomes_equivalentes("Shoptime", "Shop time") is True


def test_encontrar_parceiro_equivalente_usa_alias_do_cadastro():
    parceiros = [
        {"nome": "Fast Shop Oficial", "alias": "Fast Shop", "pontos_padrao": 6.0},
        {"nome": "Amazon", "alias": "", "pontos_padrao": 10.0},
    ]
    parceiro = encontrar_parceiro_equivalente("Fast Shop", parceiros)
    assert parceiro is not None
    assert parceiro["nome"] == "Fast Shop Oficial"


def test_encontrar_parceiro_equivalente_usa_grupo_de_apelidos_sem_alias_cadastrado():
    parceiros = [
        {"nome": "Magalu", "alias": "", "pontos_padrao": 4.0},
        {"nome": "Amazon", "alias": "", "pontos_padrao": 10.0},
    ]
    parceiro = encontrar_parceiro_equivalente("Magazine Luiza", parceiros)
    assert parceiro is not None
    assert parceiro["nome"] == "Magalu"


def test_encontrar_parceiro_equivalente_devolve_none_quando_nao_ha_casamento():
    parceiros = [{"nome": "Amazon", "alias": "", "pontos_padrao": 10.0}]
    assert encontrar_parceiro_equivalente("Casas Bahia", parceiros) is None
