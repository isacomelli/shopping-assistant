# Assistente de Compras

Aplicação pessoal para calcular o custo real de uma compra, considerando preço no Pix, preço parcelado no cartão, pontos Livelo ou Esfera, cashback e o rendimento mensal líquido.

Esta branch contém a versão migrada para uma arquitetura de API mais frontend separado. A versão original em Streamlit continua disponível na branch `streamlit_version`.

## Arquitetura

```
shopping-assistant/
├── backend/          api em FastAPI, motor de calculo, banco e scrapers
│   ├── database/     acesso ao sqlite, com migracao de esquema
│   ├── engine/       motor de calculo puro, testado isoladamente
│   ├── services/     cotacao do dolar e orquestrador da pesquisa automatica
│   ├── scrapers/     buscape, livelo e meliuz
│   ├── routers/      rotas da api, perfil, produtos, ofertas, historico
│   ├── schemas.py    modelos pydantic de entrada e saida
│   ├── calculo.py    ponte entre as linhas do banco e o motor de calculo
│   ├── main.py        ponto de entrada da api
│   └── tests/
└── frontend/         next.js 14, typescript e tailwind
    ├── app/          perfil, calculadora, wishlist, historico
    ├── components/
    └── lib/          cliente da api e tipos compartilhados
```

O motor de cálculo (`engine/price_engine.py`), o acesso ao banco (`database/db.py`), os serviços e os scrapers são exatamente os mesmos módulos da versão em Streamlit, só passaram a ser chamados por rotas HTTP em vez de por telas do Streamlit.

## Como rodar com Docker

```bash
docker compose up --build
```

A API sobe em `http://localhost:8000` (documentação interativa em `/docs`) e o site em `http://localhost:3000`.

## Como rodar sem Docker

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # no Windows, .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload --port 8000
```

Frontend, em outro terminal:

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

O site abre em `http://localhost:3000` e consulta a API em `http://localhost:8000`.

## Como rodar os testes do backend

O motor de cálculo e o orquestrador de pesquisa automática têm testes isolados que não dependem de rede nem de navegador.

```bash
cd backend
pytest tests/ -v
```

## Sobre o cálculo de milhas

O valor dos pontos de cada oferta é calculado pelo método do milheiro, a mesma lógica de uma planilha que já era usada antes deste app.

```
pontos no site parceiro = pontos por real * valor da compra
pontos no cartão = (valor da compra / cotação do dólar) * pontos por dólar do cartão
milhas do site parceiro, com bônus de transferência = pontos do site parceiro * (1 + bônus)
milhas totais = milhas do site parceiro com bônus + pontos do cartão
valor em milhas = (valor do milheiro * milhas totais) / 1000
```

No Pix não existe cartão envolvido, então só o site parceiro pontua. No cartão parcelado, os dois acúmulos contam ao mesmo tempo. Por padrão, o valor do milheiro é R$ 30 e os pontos por dólar no cartão são 3, ambos ajustáveis no perfil ou por oferta. Quando uma oferta não tiver o valor do milheiro preenchido, o cálculo cai de volta para um valor fixo por ponto.

## Sobre a pesquisa automática

A pesquisa automática consulta o Buscapé para descobrir o preço e a lista de lojas que vendem o produto (`scrapers/buscape.py`). Para cada loja encontrada, o sistema verifica se ela é parceira Livelo ou Esfera a partir de um cache carregado em `database/db.py`; quando não há parceria, a loja continua aparecendo no ranking, só sem pontuação.

O scraper da Livelo por loja (`scrapers/livelo.py`) consulta `https://www.livelo.com.br/busca?query=NOME_DA_LOJA`. Se o layout do site mudar ou o acesso automatizado for bloqueado, o scraper salva o HTML da página em `backend/scrapers/debug_livelo.html` para ajudar a diagnosticar o problema.

## Limitações atuais

O scraper de Méliuz existe mas ainda não está ligado à pesquisa automática. O scraper de Esfera ainda não existe, o plano é seguir o mesmo padrão do scraper da Livelo. A confiabilidade do scraper da Livelo por loja também é um ponto de atenção, já que não existe API pública e o Akamai bloqueia o endpoint antigo que listava todos os parceiros de uma vez.

## Próximos passos sugeridos

Scraper de Esfera e integração do Méliuz na pesquisa automática, seguindo o mesmo padrão do scraper da Livelo. Migração do SQLite para Postgres, já dockerizável junto com a API. Por fim, o recurso de bater preço entre uma oferta online e uma oportunidade de loja física, comparando lado a lado para apoiar a negociação.
