import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.casamento_lojas import (
    PARCEIROS_LIVELO_CONHECIDOS,
    encontrar_parceiro_equivalente,
    nomes_equivalentes,
    obter_url_logo_parceiro,
)


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


def test_lista_real_de_parceiros_conhecidos_casa_magazine_luiza_com_magalu():
    """
    reproduz o bug em que ofertas da Magazine Luiza apareciam com "Valor dos pontos, R$ 0,00" mesmo a Magalu sendo parceira ativa da Livelo, a lista PARCEIROS_LIVELO_CONHECIDOS precisa casar o nome comercial usado pelo buscape com o parceiro cadastrado.
    """
    parceiro = encontrar_parceiro_equivalente("Magazine Luiza", PARCEIROS_LIVELO_CONHECIDOS)
    assert parceiro is not None
    assert parceiro["nome"] == "Magalu"
    assert parceiro["pontos_padrao"] == 4.0


def test_obter_url_logo_parceiro_prefere_logo_url_real_do_parceiro():
    """
    quando o parceiro ja tem uma logo_url real coletada, seja de PARCEIROS_LIVELO_CONHECIDOS, seja de um parceiro atualizado no banco por scrapers/livelo.py, essa url deve ganhar do padrao adivinhado a partir do codigo, que nao serve para parceiros fora do dominio partners-profile.livelo.com.br ou com uma extensao de arquivo diferente de .jpeg.
    """
    parceiro = {"codigo": "DCR", "logo_url": "https://www.livelo.com.br/file/general/config_DCR_x.png"}
    assert obter_url_logo_parceiro(parceiro) == "https://www.livelo.com.br/file/general/config_DCR_x.png"


def test_obter_url_logo_parceiro_cai_para_padrao_por_codigo_sem_logo_url():
    parceiro = {"codigo": "MZL"}
    assert obter_url_logo_parceiro(parceiro) == "https://partners-profile.livelo.com.br/mzl/image.jpeg"


def test_lista_real_de_parceiros_conhecidos_ja_vem_com_logo_url_preenchida():
    """
    todo parceiro do snapshot fixo foi regerado a partir da coleta manual mais recente, em scrapers/ultimo_html_livelo.html, entao nenhum deveria depender do padrao adivinhado por codigo.
    """
    sem_logo_url = [p for p in PARCEIROS_LIVELO_CONHECIDOS if not p.get("logo_url")]
    assert sem_logo_url == []
    