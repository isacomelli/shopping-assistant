import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.google_shopping import parsear_html_google_shopping

# três variações de estrutura, cartão inteiro dentro do link, link só no título e preço separado do símbolo R$
HTML_EXEMPLO = """
<html><body>
<h2>Produtos patrocinados</h2>
<div>
  <div class="cartao-a">
    <a href="https://www.magalu.com.br/aquecedor-komeco-ko16di">
      <img src="https://exemplo.com/img1.jpg">
      <div>Aquecedor de Água A Gás Komeco 16 Litros Ko 16DI Digital Glp Inox Prat</div>
      <div><span>R$ 1.398</span></div>
      <div>Magalu</div>
      <div>Grátis</div>
      <div>Méliuz Indica</div>
      <div>Ganhe 5% de cashback</div>
      <div>Ativar cashback</div>
    </a>
  </div>
  <div class="cartao-b">
    <img src="https://exemplo.com/img2.jpg">
    <a href="/shopping/product/123"><h3>Aquecedor De Água A Gás Komeco 16 Litros KO 16DI Digital GLP</h3></a>
    <div>R$ 1.398</div>
    <div>Leroy Merlin</div>
    <div>Nota da loja: 4.2/5</div>
    <div>Méliuz Indica</div>
    <div>Ganhe 1.5% de cashback</div>
  </div>
  <div class="cartao-c">
    <a href="https://www.mercadolivre.com.br/aquecedor">
      <img src="https://exemplo.com/img3.jpg">
      <div>Aquecedor de Água Gás Komeco 16 Litros Digital Inox GLP G2 Bivolt</div>
      <div><span>R$</span><span>1.330</span></div>
      <div>Mercado Livre</div>
      <div>(31)</div>
      <div>Méliuz Indica</div>
      <div>Sem cashback no momento</div>
    </a>
  </div>
</div>
</body></html>
"""


def _por_loja():
    return {oferta.loja: oferta for oferta in parsear_html_google_shopping(HTML_EXEMPLO)}


def test_reconhece_tres_ofertas_de_estruturas_diferentes():
    assert set(_por_loja()) == {"Magalu", "Leroy Merlin", "Mercado Livre"}


def test_le_preco_sem_centavos_e_com_simbolo_separado():
    ofertas = _por_loja()
    assert ofertas["Magalu"].preco == 1398.0
    assert ofertas["Leroy Merlin"].preco == 1398.0
    assert ofertas["Mercado Livre"].preco == 1330.0


def test_le_cashback_exibido_no_cartao():
    ofertas = _por_loja()
    assert ofertas["Magalu"].cashback_pct == 5.0
    assert ofertas["Leroy Merlin"].cashback_pct == 1.5
    assert ofertas["Mercado Livre"].cashback_pct == 0.0


def test_nome_do_produto_nao_e_confundido_com_a_loja():
    ofertas = _por_loja()
    assert ofertas["Magalu"].nome_produto.startswith("Aquecedor de Água A Gás Komeco")
    assert "Leroy" not in ofertas["Leroy Merlin"].nome_produto


def test_le_url_e_imagem_do_produto():
    ofertas = _por_loja()
    assert ofertas["Magalu"].url_produto == "https://www.magalu.com.br/aquecedor-komeco-ko16di"
    assert ofertas["Leroy Merlin"].url_produto == "https://www.google.com/shopping/product/123"
    assert ofertas["Mercado Livre"].imagem_produto == "https://exemplo.com/img3.jpg"


def test_pix_e_cartao_recebem_o_preco_anunciado():
    oferta = _por_loja()["Magalu"]
    assert oferta.preco_pix == 1398.0
    assert oferta.preco_cartao == 1398.0
    assert oferta.confianca_pix_cartao is False


def test_html_sem_precos_devolve_lista_vazia():
    assert parsear_html_google_shopping("<html><body><p>nada aqui</p></body></html>") == []


def test_ofertas_do_serper_le_loja_preco_link_e_imagem():
    from services.google_shopping import _ofertas_do_serper

    dados = {
        "shopping": [
            {"title": "Aquecedor Komeco 16 Litros", "source": "Leroy Merlin", "link": "https://www.leroymerlin.com.br/x", "price": "R$ 1.398,00", "imageUrl": "https://exemplo.com/a.jpg"},
            {"title": "Aquecedor Komeco 16 Litros", "source": "Mercado Livre", "link": "https://www.mercadolivre.com.br/y", "price": "R$ 1.330"},
            {"title": "Sem preço", "source": "Loja X", "link": "https://x.com"},
        ]
    }
    ofertas = _ofertas_do_serper(dados)
    assert [o.loja for o in ofertas] == ["Leroy Merlin", "Mercado Livre"]
    assert ofertas[0].preco == 1398.0
    assert ofertas[1].preco == 1330.0
    assert ofertas[0].imagem_produto == "https://exemplo.com/a.jpg"


def test_ofertas_do_serper_com_resposta_vazia():
    from services.google_shopping import _ofertas_do_serper

    assert _ofertas_do_serper({}) == []


def test_bloqueio_so_e_detectado_pela_pagina_de_verificacao():
    from services.google_shopping import _html_indica_bloqueio

    pagina_normal = '<html><script>var x = "recaptcha";</script><body>resultados</body></html>'
    assert _html_indica_bloqueio(pagina_normal, "https://www.google.com/search?q=x") is False
    assert _html_indica_bloqueio("<html></html>", "https://www.google.com/sorry/index?continue=x") is True
    assert _html_indica_bloqueio('<form id="captcha-form"></form>', "https://www.google.com/search") is True


def test_descricao_da_pagina_mostra_titulo_e_endereco():
    from services.google_shopping import _descrever_pagina

    texto = _descrever_pagina("<html><title> Antes de continuar </title></html>", "https://consent.google.com/x")
    assert "Antes de continuar" in texto
    assert "consent.google.com" in texto
