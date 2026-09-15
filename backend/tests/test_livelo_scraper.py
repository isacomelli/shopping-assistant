import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers.livelo import parsear_html_livelo


HTML_CARTAO_PARCEIRO = """
<html><body>
<a href="/juntar-pontos/parceiros/magalu/MZL">
    <img alt="Logo Magalu" src="https://partners-profile.livelo.com.br/mzl/image.jpeg">
    <span>4 pontos por R$ 1</span>
</a>
<a href="/juntar-pontos/parceiros/decolar/DCR">
    <img alt="Logo Decolar" src="https://www.livelo.com.br/file/general/config_DCR_x.png">
    <span>2 pontos por U$ 1</span>
</a>
</body></html>
"""


def test_parsear_html_livelo_le_logo_url_direto_do_src():
    """
    a logo_url de cada parceiro precisa vir do atributo src de verdade, em vez de um
    padrao adivinhado a partir do codigo, ja que parceiros diferentes usam extensoes e
    ate dominios diferentes para a propria logo, ver o comentario em
    services/casamento_lojas.py sobre esse erro antigo.
    """
    parceiros = parsear_html_livelo(HTML_CARTAO_PARCEIRO)
    por_codigo = {parceiro.codigo: parceiro for parceiro in parceiros}

    assert por_codigo["MZL"].logo_url == "https://partners-profile.livelo.com.br/mzl/image.jpeg"
    # a decolar fica num dominio totalmente diferente do padrao partners-profile,
    # exatamente o caso que o padrao adivinhado por codigo nao cobre
    assert por_codigo["DCR"].logo_url == "https://www.livelo.com.br/file/general/config_DCR_x.png"


def test_parsear_html_livelo_sem_img_devolve_logo_vazia():
    html = """
    <html><body>
    <a href="/juntar-pontos/parceiros/sem-logo/SLG">
        <span>1 ponto por R$ 1</span>
    </a>
    </body></html>
    """
    parceiros = parsear_html_livelo(html)
    assert parceiros[0].logo_url == ""