# Assistente de Compras da Reforma

Aplicação pessoal e local para calcular o custo real de uma compra, considerando preço no pix, preço parcelado no cartão, pontos Livelo ou Esfera, cashback e o rendimento de deixar o dinheiro investido no CDI.

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
│   ├── 1_Calculadora.py      cadastro de ofertas e ranking de preço efetivo
│   ├── 2_Wishlist.py         lista de compras da reforma com orçamento
│   ├── 3_Parceiros_Livelo.py lista de parceiros Livelo, atualizada sob demanda
│   └── 4_Historico.py        evolução do preço efetivo ao longo do tempo
├── engine/
│   └── price_engine.py       cálculo puro, testado isoladamente
├── database/
│   └── db.py                 acesso ao SQLite
├── scrapers/
│   └── livelo.py             leitura da página pública de parceiros
├── services/
│   └── cambio.py             cotação do dólar via API pública
└── tests/
    └── test_price_engine.py
```

## Sobre o scraper da Livelo

O scraper lê apenas a página pública `https://www.livelo.com.br/juntar-pontos/todos-os-parceiros`, que lista os parceiros do Compre e Pontue e a taxa de pontos de cada um. Não faz login, não acessa nenhuma conta, e não coleta nenhum dado pessoal.

Dois pontos de atenção:

Primeiro, o layout do site pode mudar a qualquer momento, já que não existe uma API oficial. Se o botão de atualizar parar de trazer resultados, o primeiro lugar para olhar são as expressões regulares em `scrapers/livelo.py`.

Segundo, é melhor não rodar o scraper com muita frequência. O app já foi pensado para atualizar sob demanda, quando você clica no botão, e guarda o resultado no banco até a próxima atualização manual.

## Limitações do MVP atual

Livelo tem o scraper pronto. Esfera e Méliuz ainda não, o plano é seguir o mesmo padrão do scraper da Livelo para os dois. A busca automática de preços via BuscaPé ou Google Shopping também ainda não existe, hoje as ofertas são cadastradas manualmente na calculadora, incluindo as de loja física e negociação presencial.

## Próximos passos sugeridos

Primeiro, scraper de Esfera e Méliuz, seguindo o mesmo padrão do de Livelo. Depois, busca automática de preços por produto via BuscaPé ou Google Shopping. Por fim, o recurso de bater preço entre uma oferta online e uma oportunidade de loja física, comparando lado a lado para apoiar a negociação.
