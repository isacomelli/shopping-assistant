# Assistente de Compras da Reforma

Aplicação pessoal e local para calcular o custo real de uma compra, considerando preço no Pix, preço parcelado no cartão, pontos Livelo ou Esfera, cashback e o rendimento de deixar o dinheiro investido no CDI.

## Como rodar

```bash
cd shopping-assistant
python -m venv .venv
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.venv\Scripts\activate.bat
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
streamlit run app.py
```

O app abre em `http://localhost:8501`. Se o computador e o celular estiverem na mesma rede Wi-Fi, também dá para abrir pelo IP local do computador.

## Como rodar os testes

O motor de cálculo, que é a parte mais importante do projeto, tem testes isolados que não dependem de banco, scraper ou interface.

```bash
pytest tests/ -v
```

## Estrutura do projeto

```
shopping-assistant/
├── app.py                    tela inicial, perfil financeiro e cartões
├── pages/
│   ├── 1_Calculadora.py      busca no BuscaPé, cadastro de ofertas e ranking de preço efetivo
│   ├── 2_Wishlist.py         lista de compras da reforma com orçamento
│   ├── 3_Parceiros_Livelo.py consulta de parceiros Livelo e Méliuz por loja, sob demanda
│   └── 4_Historico.py        evolução do preço efetivo ao longo do tempo
├── engine/
│   └── price_engine.py       cálculo puro, testado isoladamente
├── database/
│   └── db.py                 acesso ao SQLite, incluindo o cache de parceiros por loja
├── scrapers/
│   ├── buscape.py            busca de preços por produto
│   ├── livelo.py             consulta de pontos por loja, e a listagem completa como apoio manual
│   └── meliuz.py             consulta de cashback por loja
├── services/
│   └── cambio.py             cotação do dólar via API pública
└── tests/
    └── test_price_engine.py
```

## Sobre o fluxo de busca

A partir desta versão, a pesquisa de um produto começa pelo BuscaPé, que devolve um pequeno conjunto de lojas com preço. Só então o app consulta a Livelo e o Méliuz, loja a loja, em vez de baixar o catálogo inteiro de parceiros de uma vez.

Essa mudança de ordem existe por dois motivos. Primeiro, uma consulta por loja específica se parece mais com a navegação de uma pessoa real do que baixar uma listagem inteira, o que reduz a chance de bloqueio por proteção contra navegador automatizado. Segundo, a página de um parceiro específico costuma trazer regras mais detalhadas, por categoria, como "3 pontos em eletrodomésticos, 2 pontos no restante", que não aparecem na listagem geral.

Cada consulta por loja fica guardada em cache por 24 horas na tabela `cache_parceiros_loja`, para não repetir a mesma busca sempre que o produto aparecer de novo numa pesquisa.

## Sobre bloqueios e limites dos scrapers

Tanto a Livelo quanto o BuscaPé usam proteção contra navegador automatizado, e o BuscaPé atualmente não permite acesso automatizado segundo o próprio robots.txt do site. Por isso, é esperado que as buscas automáticas falhem de vez em quando, ou mesmo com frequência, dependendo de como cada site estiver se comportando no momento.

Nenhum dos scrapers deste projeto usa técnicas agressivas de disfarce de navegador, como imitar a assinatura TLS de um Chrome real ou alterar dezenas de sinais de fingerprint. Quando uma consulta falha, o caminho mais confiável continua sendo cadastrar a oferta manualmente na Calculadora, que funciona independentemente de qualquer scraper.

A Esfera não tem scraper automático neste projeto, porque a lista de parceiros só fica visível depois de login numa conta pessoal, e automatizar esse tipo de acesso está fora do escopo do projeto. Os pontos Esfera de uma oferta continuam sendo cadastrados manualmente.

## Limitações do MVP atual

Os seletores do scraper do BuscaPé são uma aproximação razoável, não foram validados contra o site ao vivo no momento em que este projeto foi escrito, já que o BuscaPé bloqueia esse tipo de acesso. Se a busca automática não encontrar nada, o html da página é salvo em `scrapers/debug_buscape.html` para ajudar a ajustar os seletores. O mesmo vale para a Livelo, em `scrapers/debug_livelo.html`, e para o Méliuz, em `scrapers/debug_meliuz.html`.

## Próximos passos sugeridos

Primeiro, ajustar os seletores do scraper do BuscaPé com base no html real salvo em `debug_buscape.html`, depois de uma tentativa de busca. Depois, avaliar se vale a pena procurar um endpoint de API interno do BuscaPé ou da Livelo, pela aba de rede do navegador, que às vezes responde com uma proteção mais fraca do que a página principal. Por fim, o recurso de bater preço entre uma oferta online e uma oportunidade de loja física, comparando lado a lado para apoiar a negociação.
