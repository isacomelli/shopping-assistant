import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers.buscape import _determinar_precos_pix_cartao


def test_sem_parcelamento_reconhecido_usa_mesmo_valor_para_pix_e_cartao():
    """
    quando o cartao de resultado nao trouxe nenhum parcelamento reconhecivel, antes o pix e o cartao ficavam zerados, o que fazia o preco efetivo tambem zerar no ranking, ver engine/price_engine.py. agora os dois recebem o proprio preco anunciado.
    """
    preco_pix, preco_cartao, confianca = _determinar_precos_pix_cartao(
        preco=1999.0, parcelas=1, valor_parcela=0.0,
    )
    assert preco_pix == 1999.0
    assert preco_cartao == 1999.0
    assert confianca is False


def test_sem_valor_de_parcela_reconhecido_tambem_usa_mesmo_valor():
    preco_pix, preco_cartao, confianca = _determinar_precos_pix_cartao(
        preco=850.5, parcelas=3, valor_parcela=0.0,
    )
    assert preco_pix == 850.5
    assert preco_cartao == 850.5
    assert confianca is False


def test_com_parcelamento_reconhecido_mantem_a_distincao_normal():
    preco_pix, preco_cartao, confianca = _determinar_precos_pix_cartao(
        preco=1489.0, parcelas=6, valor_parcela=248.17,
    )
    assert preco_pix == 1489.0
    assert preco_cartao == 1489.02
    assert confianca is True
