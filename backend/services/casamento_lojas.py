"""
modulo de casamento entre nomes de loja.

o buscape mostra o nome comercial completo da loja, por exemplo "magazine luiza", enquanto a livelo cadastra o parceiro pelo apelido com que ele e conhecido no mercado, por exemplo "magalu". uma comparacao de igualdade direta nao resolve esse caso, ja que os dois nomes sao literalmente diferentes.

este modulo decide se dois nomes se referem a mesma loja em tres niveis, do mais especifico para o mais generico, parando no primeiro que bater.

primeiro, grupos de apelidos conhecidos, cadastrados aqui no codigo em GRUPOS_DE_APELIDOS, cobrindo os casos mais comuns do varejo brasileiro que uma comparacao de texto sozinha nao resolveria, tipo "magalu" para "magazine luiza".

segundo, prefixo ou igualdade, apos normalizar acentos, maiusculas e espacos, suficiente para casos como "fast shop" contra "fast shop oficial", quando um nome e o outro mais uma palavra extra no final. esse nivel e mais rigoroso que um substring solto de proposito, ver _bate_por_prefixo_ou_igual, porque substring sozinho tem falsos positivos frequentes demais para nomes de loja, por exemplo "gazin" e uma substring literal de "magazine", e "magalu" e uma substring literal de "consorcio magalu", um parceiro Livelo diferente, com pontuacao diferente.

terceiro, similaridade de texto, usando difflib da biblioteca padrao, para pegar pequenas variacoes de grafia que nao caem em nenhum dos dois casos acima, com um limite minimo definido em LIMITE_SIMILARIDADE, para nao casar lojas diferentes por coincidencia.

quem monta o cadastro de parceiros pode continuar preenchendo o campo alias com um apelido especifico daquele parceiro, o casamento considera esse alias como mais um nome candidato, junto do nome principal. GRUPOS_DE_APELIDOS serve para os casos mais conhecidos do mercado, que valem para qualquer usuario, sem precisar cadastrar o alias na mao toda vez.
"""

import unicodedata
from difflib import SequenceMatcher

LIMITE_SIMILARIDADE = 0.82

# grupos de nomes que se referem a mesma loja ou ao mesmo grupo varejista, ainda que o nome comercial e o apelido de mercado sejam bem diferentes um do outro. cada grupo e uma lista de nomes equivalentes, o casamento considera qualquer par de nomes dentro do mesmo grupo como a mesma loja, ver _grupo_de_apelidos. esta lista cobre os casos mais comuns do varejo online brasileiro, pode crescer conforme novos casos aparecerem nas pesquisas
GRUPOS_DE_APELIDOS = [
    ["magalu", "magazine luiza"],
    ["casas bahia", "grupo casas bahia"],
    ["ponto", "ponto frio", "pontofrio"],
    ["extra", "extra.com"],
    ["americanas", "americanas.com", "lojas americanas"],
    ["shoptime", "shop time"],
    ["submarino", "submarino.com"],
    ["kabum", "kabum!"],
    ["fast shop", "fastshop"],
    ["amazon", "amazon.com.br"],
    ["carrefour", "carrefour.com"],
    ["madeiramadeira", "madeira madeira"],
    ["leroy merlin", "leroymerlin"],
]


# taxa de pontos por real de cada parceiro Livelo conhecido, cadastrada aqui a mao em vez de vir de um scraper ou de uma tabela no banco de dados. a pagina publica que listava todos os parceiros de uma vez, https://www.livelo.com.br/juntar-pontos/todos-os-parceiros, e bloqueada pelo akamai, ver o comentario no topo antigo de database/db.py, entao nao ha como manter essa lista atualizada automaticamente. este snapshot foi extraido de uma coleta manual anterior, atraves de scrapers/livelo.py e debug_scraper.py --reparsear, e cobre so os parceiros que pontuam em pontos por real, R$, ja que o motor de calculo em engine/price_engine.py so sabe aplicar esse formato. parceiros que pontuam em pontos por dolar, U$, tipo Decolar, Booking e Hoteis.com, precisariam de uma formula diferente e nao entram aqui de proposito. quando a taxa de algum parceiro mudar ou um parceiro novo aparecer numa pesquisa, o ajuste e simplesmente editar esta lista a mao. cada entrada usa o mesmo formato de dict aceito por encontrar_parceiro_equivalente, nome e o nome como a livelo mostra o parceiro, alias e o apelido derivado do slug da propria url da livelo, que junto com GRUPOS_DE_APELIDOS acima ja cobre a diferenca entre o nome comercial usado pela loja, tipo "magazine luiza", e o nome usado pela livelo, tipo "magalu". codigo e o codigo do parceiro na propria url da livelo, tipo MZL em .../parceiros/magalu/MZL, extraido da mesma coleta manual, e serve apenas para montar a logo do parceiro em obter_url_logo_parceiro, sem entrar no casamento de nomes em si.
PARCEIROS_LIVELO_CONHECIDOS = [
    {"nome": "ABC da Construcao", "alias": "abc da construcao", "codigo": "ABC", "pontos_padrao": 1.0},
    {"nome": "Abelha Rainha", "alias": "abelha rainha", "codigo": "BLH", "pontos_padrao": 3.0},
    {"nome": "ACER", "alias": "acer", "codigo": "ACE", "pontos_padrao": 2.0},
    {"nome": "ADCOS", "alias": "adcos", "codigo": "SPA", "pontos_padrao": 8.0},
    {"nome": "Agaxtur Cruzeiros", "alias": "cruzeiros agaxtur", "codigo": "AGX", "pontos_padrao": 2.0},
    {"nome": "Allianz", "alias": "allianz", "codigo": "ALZ", "pontos_padrao": 4.0},
    {"nome": "Alura", "alias": "alura", "codigo": "ALU", "pontos_padrao": 1.0},
    {"nome": "AMOBELEZA", "alias": "amobeleza", "codigo": "AMO", "pontos_padrao": 8.0},
    {"nome": "Angeloni", "alias": "angeloni", "codigo": "AGE", "pontos_padrao": 4.0},
    {"nome": "Aramis", "alias": "aramis", "codigo": "ARA", "pontos_padrao": 2.0},
    {"nome": "Asics", "alias": "asics", "codigo": "ACS", "pontos_padrao": 1.0},
    {"nome": "Assinatura Coffee Mais", "alias": "assinatura coffemais", "codigo": "ASS", "pontos_padrao": 6.0},
    {"nome": "Assist Card Seguro-Viagem", "alias": "assist card seguros", "codigo": "ASC", "pontos_padrao": 12.0},
    {"nome": "Avon", "alias": "avon", "codigo": "AVN", "pontos_padrao": 6.0},
    {"nome": "Bagaggio", "alias": "bagaggio", "codigo": "BAG", "pontos_padrao": 8.0},
    {"nome": "Baianão", "alias": "baianao", "codigo": "BNM", "pontos_padrao": 1.0},
    {"nome": "Bankei", "alias": "bankei", "codigo": "BAN", "pontos_padrao": 0.4},
    {"nome": "Beach Park Hospedagens", "alias": "beach park", "codigo": "BPK", "pontos_padrao": 2.0},
    {"nome": "Beach Park Ingressos", "alias": "beach park", "codigo": "BPK", "pontos_padrao": 1.0},
    {"nome": "Beep", "alias": "beep", "codigo": "BEP", "pontos_padrao": 1.0},
    {"nome": "Beleza na web", "alias": "beleza na web", "codigo": "BLZ", "pontos_padrao": 2.0},
    {"nome": "Beto Carrero World", "alias": "beto carrero", "codigo": "JBW", "pontos_padrao": 2.0},
    {"nome": "Beyoung", "alias": "beyoung", "codigo": "BYG", "pontos_padrao": 3.0},
    {"nome": "Bibi", "alias": "bibi calcados", "codigo": "BBB", "pontos_padrao": 8.0},
    {"nome": "BO.BÔ", "alias": "bobo", "codigo": "RBO", "pontos_padrao": 8.0},
    {"nome": "Bobstore", "alias": "bobstore", "codigo": "IBB", "pontos_padrao": 2.0},
    {"nome": "Bombay Herbs & Spices", "alias": "bombay herbse spices", "codigo": "BBH", "pontos_padrao": 8.0},
    {"nome": "Bradesco Capitalização", "alias": "bradesco capitalizacao", "codigo": "CLZ", "pontos_padrao": 2.0},
    {"nome": "Bradesco Consórcios", "alias": "bradesco consorcios", "codigo": "BCS", "pontos_padrao": 30.0},
    {"nome": "Buddha Spa", "alias": "buddha spa", "codigo": "BDH", "pontos_padrao": 2.0},
    {"nome": "Bulbe Energia", "alias": "bulbe", "codigo": "BLB", "pontos_padrao": 12.0},
    {"nome": "Buser", "alias": "buser", "codigo": "BSR", "pontos_padrao": 2.0},
    {"nome": "Cabana Magazine", "alias": "cabana magazine", "codigo": "GRM", "pontos_padrao": 1.0},
    {"nome": "Café Orfeu", "alias": "cafe orfeu", "codigo": "CFO", "pontos_padrao": 3.0},
    {"nome": "Camicado", "alias": "camicado", "codigo": "CMC", "pontos_padrao": 8.0},
    {"nome": "Carrefour Mercado", "alias": "carrefour", "codigo": "CRM", "pontos_padrao": 1.0},
    {"nome": "Carrefour Shopping", "alias": "carrefour shopping", "codigo": "CRF", "pontos_padrao": 10.0},
    {"nome": "Carters", "alias": "carters", "codigo": "CTS", "pontos_padrao": 3.0},
    {"nome": "Cartão de Todos", "alias": "cartao de todos", "codigo": "TOD", "pontos_padrao": 2.0},
    {"nome": "Casas Bahia", "alias": "casas bahia", "codigo": "CSB", "pontos_padrao": 1.0},
    {"nome": "CEA", "alias": "cea", "codigo": "CEA", "pontos_padrao": 2.0},
    {"nome": "Centauro", "alias": "centauro", "codigo": "CEN", "pontos_padrao": 6.0},
    {"nome": "Cestas Michelli", "alias": "cestas michelli", "codigo": "MCH", "pontos_padrao": 3.0},
    {"nome": "Ciclic Seguro Celular", "alias": "ciclic celular", "codigo": "CEL", "pontos_padrao": 5.0},
    {"nome": "Ciclic Seguro Viagem", "alias": "ciclic", "codigo": "CIC", "pontos_padrao": 14.0},
    {"nome": "Civitatis", "alias": "civitatis", "codigo": "CIV", "pontos_padrao": 2.0},
    {"nome": "Claro", "alias": "claro", "codigo": "CLA", "pontos_padrao": 6.0},
    {"nome": "ClickBus", "alias": "clickbus", "codigo": "CLK", "pontos_padrao": 1.0},
    {"nome": "Coffee Mais", "alias": "coffee mais", "codigo": "CFF", "pontos_padrao": 8.0},
    {"nome": "Colcci", "alias": "colcci", "codigo": "GAM", "pontos_padrao": 8.0},
    {"nome": "Coliseu", "alias": "coliseu", "codigo": "CLS", "pontos_padrao": 2.0},
    {"nome": "Consórcio Magalu", "alias": "consorcio magalu", "codigo": "MGC", "pontos_padrao": 10.0},
    {"nome": "Converse", "alias": "converse", "codigo": "CCL", "pontos_padrao": 2.0},
    {"nome": "Cook Eletroraro", "alias": "cook eletroraro", "codigo": "COK", "pontos_padrao": 1.0},
    {"nome": "Coris", "alias": "coris", "codigo": "CRS", "pontos_padrao": 8.0},
    {"nome": "Creditas", "alias": "creditas", "codigo": "CRD", "pontos_padrao": 1.0},
    {"nome": "Crocs", "alias": "crocs", "codigo": "CRO", "pontos_padrao": 8.0},
    {"nome": "Dafiti", "alias": "dafiti", "codigo": "DAF", "pontos_padrao": 1.0},
    {"nome": "Decathlon", "alias": "decathlon", "codigo": "DCH", "pontos_padrao": 2.0},
    {"nome": "Democrata", "alias": "democrata", "codigo": "DMC", "pontos_padrao": 2.0},
    {"nome": "Divvino", "alias": "divvino", "codigo": "AGN", "pontos_padrao": 1.0},
    {"nome": "Drogal", "alias": "drogal", "codigo": "DRO", "pontos_padrao": 1.0},
    {"nome": "Drogaria Sao Paulo", "alias": "drogaria sao paulo", "codigo": "DPS", "pontos_padrao": 1.0},
    {"nome": "Drogarias Pacheco", "alias": "drogarias pacheco", "codigo": "DPC", "pontos_padrao": 1.0},
    {"nome": "Dudalina", "alias": "dudalina", "codigo": "DDL", "pontos_padrao": 8.0},
    {"nome": "Dufrio", "alias": "dufrio", "codigo": "DUF", "pontos_padrao": 1.0},
    {"nome": "Easy Live", "alias": "easy live", "codigo": "ESL", "pontos_padrao": 1.0},
    {"nome": "EDP", "alias": "edp", "codigo": "EDP", "pontos_padrao": 6.0},
    {"nome": "elbo", "alias": "elbo", "codigo": "ELB", "pontos_padrao": 8.0},
    {"nome": "Electrolux", "alias": "electrolux", "codigo": "ELX", "pontos_padrao": 1.0},
    {"nome": "Ellus", "alias": "ellus", "codigo": "ELS", "pontos_padrao": 2.0},
    {"nome": "Estapar", "alias": "estapar", "codigo": "EST", "pontos_padrao": 1.0},
    {"nome": "Eudora", "alias": "eudora", "codigo": "EUD", "pontos_padrao": 2.0},
    {"nome": "Euro", "alias": "euro", "codigo": "EUR", "pontos_padrao": 8.0},
    {"nome": "Extra", "alias": "extra", "codigo": "EXT", "pontos_padrao": 1.0},
    {"nome": "Faber-Castell", "alias": "faber castell", "codigo": "FBC", "pontos_padrao": 2.0},
    {"nome": "Farmacias App", "alias": "farmacias app", "codigo": "NCC", "pontos_padrao": 1.0},
    {"nome": "Fast Shop", "alias": "fast shop", "codigo": "FST", "pontos_padrao": 5.0},
    {"nome": "Fila", "alias": "fila", "codigo": "FLA", "pontos_padrao": 9.0},
    {"nome": "Foco", "alias": "foco", "codigo": "FOC", "pontos_padrao": 2.0},
    {"nome": "Forever Liss", "alias": "forever liss", "codigo": "LSS", "pontos_padrao": 8.0},
    {"nome": "Frigelar", "alias": "frigelar", "codigo": "FRG", "pontos_padrao": 1.0},
    {"nome": "Fóssil", "alias": "fossil", "codigo": "SCS", "pontos_padrao": 8.0},
    {"nome": "Gazin", "alias": "gazin", "codigo": "GZN", "pontos_padrao": 2.0},
    {"nome": "Giuliana Flores", "alias": "giuliana flores", "codigo": "GFL", "pontos_padrao": 3.0},
    {"nome": "Go case", "alias": "gocase", "codigo": "GCS", "pontos_padrao": 2.0},
    {"nome": "Granado", "alias": "granado", "codigo": "CGN", "pontos_padrao": 1.0},
    {"nome": "Grupo Dreams", "alias": "grupo dreams", "codigo": "DRT", "pontos_padrao": 4.0},
    {"nome": "Guess", "alias": "guess", "codigo": "GSS", "pontos_padrao": 2.0},
    {"nome": "Guldi", "alias": "guldi", "codigo": "GUL", "pontos_padrao": 1.0},
    {"nome": "Havaianas", "alias": "havaianas", "codigo": "ALP", "pontos_padrao": 2.0},
    {"nome": "Hering", "alias": "hering", "codigo": "HRG", "pontos_padrao": 3.0},
    {"nome": "Hering Outlet", "alias": "hering outlet", "codigo": "OUT", "pontos_padrao": 1.0},
    {"nome": "Hero Seguro Celular", "alias": "hero seguro celular", "codigo": "CLE", "pontos_padrao": 1.0},
    {"nome": "HERO SEGURO VIAGEM", "alias": "hero", "codigo": "HRH", "pontos_padrao": 14.0},
    {"nome": "Home Angels", "alias": "home angels", "codigo": "ZAI", "pontos_padrao": 0.1},
    {"nome": "Hope", "alias": "hope", "codigo": "HPE", "pontos_padrao": 2.0},
    {"nome": "Hope Resort", "alias": "hope resort", "codigo": "RST", "pontos_padrao": 2.0},
    {"nome": "Horas Magicas", "alias": "horas magicas", "codigo": "HMG", "pontos_padrao": 1.0},
    {"nome": "Hot Beach", "alias": "hot beach", "codigo": "HBC", "pontos_padrao": 1.0},
    {"nome": "Hoteis com", "alias": "hoteis", "codigo": "HTC", "pontos_padrao": 8.0},
    {"nome": "Hotel Nacional", "alias": "hotel nacional", "codigo": "WHN", "pontos_padrao": 1.0},
    {"nome": "Imaginarium", "alias": "imaginarium", "codigo": "IMG", "pontos_padrao": 1.0},
    {"nome": "Individual", "alias": "individual", "codigo": "IND", "pontos_padrao": 8.0},
    {"nome": "Insider Store", "alias": "insider store", "codigo": "INS", "pontos_padrao": 8.0},
    {"nome": "John John", "alias": "john john", "codigo": "JOH", "pontos_padrao": 8.0},
    {"nome": "Kabum!", "alias": "kabum", "codigo": "KBM", "pontos_padrao": 1.0},
    {"nome": "Klabin ForYou", "alias": "klabin", "codigo": "KLB", "pontos_padrao": 1.0},
    {"nome": "Klubi Consórcio Celular", "alias": "klubi celular", "codigo": "KLU", "pontos_padrao": 40.0},
    {"nome": "Klubi Consórcio Imóvel", "alias": "klubi imovel", "codigo": "IMO", "pontos_padrao": 40.0},
    {"nome": "Klubi Consórcio Moto", "alias": "klubi moto", "codigo": "MOT", "pontos_padrao": 40.0},
    {"nome": "Klubi Consórcio Viagem", "alias": "klubi viagem", "codigo": "VIA", "pontos_padrao": 40.0},
    {"nome": "Lacoste", "alias": "lacoste", "codigo": "LCT", "pontos_padrao": 2.0},
    {"nome": "LE LIS", "alias": "lelis", "codigo": "LLB", "pontos_padrao": 8.0},
    {"nome": "LEGO", "alias": "lego", "codigo": "LEG", "pontos_padrao": 1.0},
    {"nome": "Liga Vitória - Seguro de Viagem", "alias": "liga vitoria viagem", "codigo": "LSG", "pontos_padrao": 3.0},
    {"nome": "Liga Vitória Consórcio", "alias": "liga vitoria", "codigo": "LVC", "pontos_padrao": 35.0},
    {"nome": "Liga Vitória Seguro Auto", "alias": "liga vitoria auto", "codigo": "LSA", "pontos_padrao": 1.0},
    {"nome": "Liga Vitória Seguro de Vida", "alias": "liga vitoria", "codigo": "LVC", "pontos_padrao": 3.0},
    {"nome": "Liga Vitória Seguro Moto", "alias": "liga vitoria moto", "codigo": "LSM", "pontos_padrao": 1.0},
    {"nome": "Liga Vitória Seguro Residencial", "alias": "liga vitoria residencial", "codigo": "LSR", "pontos_padrao": 3.0},
    {"nome": "LIVE!", "alias": "live oficial", "codigo": "LVE", "pontos_padrao": 8.0},
    {"nome": "Liz", "alias": "liz", "codigo": "CMR", "pontos_padrao": 1.0},
    {"nome": "Localiza", "alias": "localiza", "codigo": "LCR", "pontos_padrao": 4.0},
    {"nome": "Localiza Meoo", "alias": "localiza meoo", "codigo": "LFL", "pontos_padrao": 10.0},
    {"nome": "Loccitane", "alias": "loccitane", "codigo": "PRV", "pontos_padrao": 8.0},
    {"nome": "Loccitane au Bresil", "alias": "loccitane au bresil", "codigo": "LCC", "pontos_padrao": 8.0},
    {"nome": "Loja do Mecânico", "alias": "loja do mecanico", "codigo": "LMC", "pontos_padrao": 1.0},
    {"nome": "Lojas Torra", "alias": "lojas torra", "codigo": "TRR", "pontos_padrao": 8.0},
    {"nome": "Loungerie", "alias": "loungerie", "codigo": "LGR", "pontos_padrao": 8.0},
    {"nome": "Luxury Loyalty", "alias": "luxury loyalty", "codigo": "LLY", "pontos_padrao": 2.0},
    {"nome": "Magalu", "alias": "magalu", "codigo": "MZL", "pontos_padrao": 4.0},
    {"nome": "Maltacor", "alias": "maltacor", "codigo": "MAL", "pontos_padrao": 5.0},
    {"nome": "Malwee", "alias": "malwee", "codigo": "MLW", "pontos_padrao": 8.0},
    {"nome": "MAPFRE Seguro Auto", "alias": "mapfre", "codigo": "MPF", "pontos_padrao": 1.0},
    {"nome": "Max Titanium", "alias": "max titanium", "codigo": "SUP", "pontos_padrao": 6.0},
    {"nome": "MaxRacer", "alias": "max racer", "codigo": "BCI", "pontos_padrao": 1.0},
    {"nome": "MedSênior", "alias": "medsenior", "codigo": "MED", "pontos_padrao": 7.0},
    {"nome": "Meia Sola", "alias": "meia sola", "codigo": "MSA", "pontos_padrao": 2.0},
    {"nome": "Mercado Livre", "alias": "mercado livre", "codigo": "MCL", "pontos_padrao": 2.0},
    {"nome": "Midea", "alias": "midea", "codigo": "MDI", "pontos_padrao": 8.0},
    {"nome": "Mistral", "alias": "mistral", "codigo": "MIS", "pontos_padrao": 8.0},
    {"nome": "Mizuno", "alias": "mizuno", "codigo": "VMZ", "pontos_padrao": 1.0},
    {"nome": "Mobifácil", "alias": "mobifacil", "codigo": "MOB", "pontos_padrao": 1.0},
    {"nome": "Mobills", "alias": "mobills", "codigo": "MBS", "pontos_padrao": 10.0},
    {"nome": "Mondaine", "alias": "mondaine", "codigo": "MDN", "pontos_padrao": 8.0},
    {"nome": "Monte Carlo", "alias": "montecarlo", "codigo": "MCV", "pontos_padrao": 2.0},
    {"nome": "Morana", "alias": "morana", "codigo": "MRN", "pontos_padrao": 8.0},
    {"nome": "Movida", "alias": "movida", "codigo": "MOV", "pontos_padrao": 9.0},
    {"nome": "Mycon Consórcio Digital", "alias": "mycon", "codigo": "MYC", "pontos_padrao": 32.0},
    {"nome": "Nars", "alias": "nars", "codigo": "NRS", "pontos_padrao": 3.0},
    {"nome": "Natura", "alias": "natura", "codigo": "NTR", "pontos_padrao": 4.0},
    {"nome": "Nespresso", "alias": "nespresso", "codigo": "NES", "pontos_padrao": 5.0},
    {"nome": "Netshoes", "alias": "netshoes", "codigo": "NTS", "pontos_padrao": 2.0},
    {"nome": "New Balance", "alias": "new balance", "codigo": "NWB", "pontos_padrao": 2.0},
    {"nome": "Next Seguro Viagem", "alias": "next", "codigo": "NXE", "pontos_padrao": 3.0},
    {"nome": "Nike", "alias": "nike", "codigo": "NIK", "pontos_padrao": 4.0},
    {"nome": "O Boticario", "alias": "o boticario", "codigo": "BOT", "pontos_padrao": 8.0},
    {"nome": "O.U.i Paris", "alias": "o.u.i paris", "codigo": "OUI", "pontos_padrao": 8.0},
    {"nome": "Oceane", "alias": "oceane", "codigo": "OCN", "pontos_padrao": 2.0},
    {"nome": "Oficina", "alias": "oficina", "codigo": "RZZ", "pontos_padrao": 1.0},
    {"nome": "OLX", "alias": "OLX", "codigo": "OLX", "pontos_padrao": 1.0},
    {"nome": "Olympikus", "alias": "olympikus", "codigo": "OVC", "pontos_padrao": 1.0},
    {"nome": "Osklen", "alias": "osklen", "codigo": "OSK", "pontos_padrao": 2.0},
    {"nome": "Oxford", "alias": "oxford", "codigo": "OXF", "pontos_padrao": 2.0},
    {"nome": "Pado", "alias": "pado", "codigo": "PDO", "pontos_padrao": 2.0},
    {"nome": "PerfectDraft (Ambev)", "alias": "perfec tdraft", "codigo": "ABV", "pontos_padrao": 1.0},
    {"nome": "Petlove", "alias": "pet love", "codigo": "PLV", "pontos_padrao": 2.0},
    {"nome": "Petlove Saúde", "alias": "pet love saude", "codigo": "PVS", "pontos_padrao": 8.0},
    {"nome": "Petz", "alias": "petz", "codigo": "PTZ", "pontos_padrao": 2.0},
    {"nome": "Piatan Natural", "alias": "piatan natural", "codigo": "PAT", "pontos_padrao": 3.0},
    {"nome": "PneuStore", "alias": "pneu store", "codigo": "CPX", "pontos_padrao": 1.0},
    {"nome": "Pontofrio", "alias": "pontofrio", "codigo": "PTF", "pontos_padrao": 1.0},
    {"nome": "Portal das Malas", "alias": "portal das malas", "codigo": "PDM", "pontos_padrao": 1.0},
    {"nome": "Portallar", "alias": "portallar", "codigo": "PLL", "pontos_padrao": 2.0},
    {"nome": "Porto Seguro", "alias": "portoseguro", "codigo": "POT", "pontos_padrao": 20.0},
    {"nome": "Porto Serviço", "alias": "porto servico", "codigo": "PTO", "pontos_padrao": 8.0},
    {"nome": "Posthaus", "alias": "posthaus", "codigo": "PTH", "pontos_padrao": 8.0},
    {"nome": "Probiótica", "alias": "probiotica", "codigo": "PBT", "pontos_padrao": 6.0},
    {"nome": "Puket", "alias": "puket", "codigo": "PKT", "pontos_padrao": 2.0},
    {"nome": "Qcompra", "alias": "qcompra", "codigo": "QCP", "pontos_padrao": 3.0},
    {"nome": "Quem Disse, Berenice?", "alias": "quem disse berenice", "codigo": "QDB", "pontos_padrao": 3.0},
    {"nome": "Quero Passagem", "alias": "quero passagem", "codigo": "QPV", "pontos_padrao": 1.0},
    {"nome": "Quero-Quero", "alias": "quero quero", "codigo": "LQQ", "pontos_padrao": 1.0},
    {"nome": "Quintess", "alias": "quintess", "codigo": "LHS", "pontos_padrao": 8.0},
    {"nome": "Renner", "alias": "renner", "codigo": "RNN", "pontos_padrao": 10.0},
    {"nome": "Reserva", "alias": "reserva", "codigo": "RES", "pontos_padrao": 2.0},
    {"nome": "Reservecar", "alias": "reserve car", "codigo": "RSC", "pontos_padrao": 2.0},
    {"nome": "Riachuelo", "alias": "riachuelo", "codigo": "RCH", "pontos_padrao": 3.0},
    {"nome": "Richards", "alias": "richards", "codigo": "IRC", "pontos_padrao": 2.0},
    {"nome": "Salinas", "alias": "salinas", "codigo": "SLN", "pontos_padrao": 2.0},
    {"nome": "Sam's Club", "alias": "sams club", "codigo": "WMB", "pontos_padrao": 84.0},
    {"nome": "Sam's Club - E-commerce", "alias": "sams club e commerce", "codigo": "ECO", "pontos_padrao": 1.0},
    {"nome": "Samsonite", "alias": "samsonite", "codigo": "SMS", "pontos_padrao": 2.0},
    {"nome": "Scudoo Seguro Celular", "alias": "scudoo", "codigo": "SIO", "pontos_padrao": 4.0},
    {"nome": "Seculus", "alias": "seculus", "codigo": "SCL", "pontos_padrao": 8.0},
    {"nome": "Seguro Residencial MAPFRE", "alias": "mapfre residencial", "codigo": "MSR", "pontos_padrao": 1.0},
    {"nome": "Seguro Viagem Bradesco", "alias": "seguro viagem bradesco", "codigo": "BVP", "pontos_padrao": 10.0},
    {"nome": "Sephora", "alias": "sephora", "codigo": "SPR", "pontos_padrao": 1.0},
    {"nome": "Seus Ingressos", "alias": "seus ingressos", "codigo": "SIN", "pontos_padrao": 3.0},
    {"nome": "Shiseido", "alias": "shiseido", "codigo": "SHS", "pontos_padrao": 3.0},
    {"nome": "Shoestock", "alias": "shoestock", "codigo": "NSC", "pontos_padrao": 2.0},
    {"nome": "Shopee", "alias": "shopee", "codigo": "PEE", "pontos_padrao": 2.0},
    {"nome": "Sixt", "alias": "sixt", "codigo": "SXT", "pontos_padrao": 1.0},
    {"nome": "Speedo", "alias": "speedo", "codigo": "SPD", "pontos_padrao": 2.0},
    {"nome": "Spicy", "alias": "spicy", "codigo": "MCB", "pontos_padrao": 1.0},
    {"nome": "Studio Z", "alias": "studioz", "codigo": "STZ", "pontos_padrao": 2.0},
    {"nome": "Suhai Seguradora", "alias": "suhai", "codigo": "SUH", "pontos_padrao": 2.0},
    {"nome": "SulAmérica Plano Odonto", "alias": "sulamerica seguro odonto", "codigo": "SUO", "pontos_padrao": 6.0},
    {"nome": "SulAmérica Seguro Viagem", "alias": "sulamerica seguro viagem", "codigo": "SUL", "pontos_padrao": 12.0},
    {"nome": "Summerville", "alias": "summerville", "codigo": "PPH", "pontos_padrao": 2.0},
    {"nome": "Supernosso", "alias": "supernosso", "codigo": "SPN", "pontos_padrao": 0.3333},
    {"nome": "Technos", "alias": "technos", "codigo": "TEC", "pontos_padrao": 8.0},
    {"nome": "Telhanorte", "alias": "telhanorte", "codigo": "TLN", "pontos_padrao": 1.0},
    {"nome": "Thule", "alias": "thule", "codigo": "THL", "pontos_padrao": 1.0},
    {"nome": "Tia Sônia", "alias": "tia sonia", "codigo": "AMT", "pontos_padrao": 3.0},
    {"nome": "TIM", "alias": "tim", "codigo": "TIM", "pontos_padrao": 6.0},
    {"nome": "Tokio Marine Seguros", "alias": "tokio marine", "codigo": "TOM", "pontos_padrao": 10.0},
    {"nome": "Top Móveis", "alias": "top moveis", "codigo": "TMS", "pontos_padrao": 1.0},
    {"nome": "TripChip", "alias": "tripchip", "codigo": "SKA", "pontos_padrao": 5.0},
    {"nome": "Trocafy", "alias": "trocafy", "codigo": "ALD", "pontos_padrao": 1.0},
    {"nome": "Truss", "alias": "truss", "codigo": "TUS", "pontos_padrao": 8.0},
    {"nome": "Umbro", "alias": "umbro", "codigo": "FIL", "pontos_padrao": 2.0},
    {"nome": "Under Armour", "alias": "under armour", "codigo": "VCA", "pontos_padrao": 1.0},
    {"nome": "Unidas", "alias": "unidas", "codigo": "UND", "pontos_padrao": 10.0},
    {"nome": "Universal Assistance – Seguro Viagem", "alias": "universal assistance", "codigo": "AST", "pontos_padrao": 6.0},
    {"nome": "Viajar", "alias": "viajar", "codigo": "VJR", "pontos_padrao": 2.0},
    {"nome": "Vivara", "alias": "vivara", "codigo": "VVR", "pontos_padrao": 1.0},
    {"nome": "VR Collezioni", "alias": "vr collezioni", "codigo": "VRC", "pontos_padrao": 2.0},
    {"nome": "Vult", "alias": "vult", "codigo": "VUL", "pontos_padrao": 8.0},
    {"nome": "Wise UP", "alias": "wise up", "codigo": "WSP", "pontos_padrao": 2.0},
    {"nome": "Yvy", "alias": "yvy", "codigo": "YVY", "pontos_padrao": 3.0},
    {"nome": "Zattini", "alias": "zattini", "codigo": "ZTN", "pontos_padrao": 2.0},
    {"nome": "Zee.Dog", "alias": "zeedog", "codigo": "ZDG", "pontos_padrao": 2.0},
    {"nome": "Zee.Now", "alias": "zee.now", "codigo": "ZNW", "pontos_padrao": 1.0},
    {"nome": "Zissou", "alias": "zissou", "codigo": "ZSS", "pontos_padrao": 3.0},
    {"nome": "Época Cosméticos", "alias": "epoca cosmeticos", "codigo": "EPC", "pontos_padrao": 2.0},
]


# padrao de url das fotos de perfil dos parceiros da livelo, descoberto na mesma coleta manual da lista acima, ver o atributo src da logo em scrapers/ultimo_html_livelo.html, tipo https://partners-profile.livelo.com.br/mzl/image.jpeg para o codigo MZL. como e um padrao previsivel a partir do codigo do parceiro, nao precisa de coleta separada por logo, so o codigo ja cadastrado em PARCEIROS_LIVELO_CONHECIDOS.
URL_BASE_LOGO_PARCEIRO_LIVELO = "https://partners-profile.livelo.com.br"


def obter_url_logo_parceiro(parceiro):
    """
    monta a url da logo de um parceiro Livelo a partir do seu codigo, seguindo o padrao descrito em URL_BASE_LOGO_PARCEIRO_LIVELO. aceita tanto um dict de PARCEIROS_LIVELO_CONHECIDOS quanto o proprio codigo como string. devolve uma string vazia quando o parceiro nao tiver codigo cadastrado, para quem exibe a oferta cair de volta para outra fonte de logo.
    """
    codigo = parceiro.get("codigo") if isinstance(parceiro, dict) else parceiro
    if not codigo:
        return ""
    return f"{URL_BASE_LOGO_PARCEIRO_LIVELO}/{codigo.lower()}/image.jpeg"


def normalizar_nome_loja(nome):
    """
    remove acentos, deixa em minusculas e junta espacos repetidos, o mesmo tratamento aplicado tanto ao nome cadastrado quanto ao nome encontrado na pesquisa, para que a comparacao nao dependa de maiusculas, acentuacao ou espacamento.
    """
    forma_normalizada = unicodedata.normalize("NFKD", nome or "")
    sem_acento = "".join(c for c in forma_normalizada if not unicodedata.combining(c))
    return " ".join(sem_acento.strip().lower().split())


def _bate_por_prefixo_ou_igual(apelido, nome_normalizado):
    """
    comparacao usada tanto para decidir se um nome pertence a um grupo de GRUPOS_DE_APELIDOS quanto no nivel generico de nomes_equivalentes.

    um substring solto demais faz "magalu" bater com "consorcio magalu", que e um parceiro Livelo diferente, com pontuacao diferente, e faz "gazin" bater com "magazine", so por coincidencia de letras no meio da palavra. em vez disso, so considera o mesmo lugar quando os dois nomes sao exatamente iguais, ou quando um deles e o outro mais uma palavra extra no final, separada por espaco, tipo "magazine luiza" contra "magazine luiza oficial", o caso mais comum de sufixo que as lojas acrescentam no proprio nome.
    """
    if not apelido or not nome_normalizado:
        return False
    if apelido == nome_normalizado:
        return True
    return (
        nome_normalizado.startswith(apelido + " ")
        or apelido.startswith(nome_normalizado + " ")
    )


def _grupo_de_apelidos(nome_normalizado):
    """
    devolve o grupo de GRUPOS_DE_APELIDOS ao qual o nome normalizado pertence, comparando cada apelido do grupo contra o nome normalizado atraves de _bate_por_prefixo_ou_igual, ja que o nome encontrado na pesquisa pode trazer um sufixo extra, tipo "magazine luiza oficial". devolve none quando o nome nao pertencer a nenhum grupo cadastrado.
    """
    for grupo in GRUPOS_DE_APELIDOS:
        for apelido in grupo:
            if _bate_por_prefixo_ou_igual(normalizar_nome_loja(apelido), nome_normalizado):
                return grupo
    return None


def nomes_equivalentes(nome_a, nome_b):
    """
    decide se dois nomes de loja se referem ao mesmo lugar, tentando, nesta ordem, grupo de apelidos conhecido, prefixo ou igualdade, e por ultimo similaridade de texto acima de LIMITE_SIMILARIDADE.

    devolve um booleano simples, sem indicar qual criterio decidiu, quem precisar diferenciar o motivo do casamento deve chamar _grupo_de_apelidos diretamente.
    """
    normalizado_a = normalizar_nome_loja(nome_a)
    normalizado_b = normalizar_nome_loja(nome_b)

    if not normalizado_a or not normalizado_b:
        return False

    if normalizado_a == normalizado_b:
        return True

    grupo_a = _grupo_de_apelidos(normalizado_a)
    if grupo_a is not None:
        for apelido in grupo_a:
            if _bate_por_prefixo_ou_igual(normalizar_nome_loja(apelido), normalizado_b):
                return True

    if _bate_por_prefixo_ou_igual(normalizado_a, normalizado_b):
        return True

    similaridade = SequenceMatcher(None, normalizado_a, normalizado_b).ratio()
    return similaridade >= LIMITE_SIMILARIDADE


def encontrar_parceiro_equivalente(nome_loja, parceiros, chave_nome="nome", chave_alias="alias"):
    """
    percorre uma lista de parceiros, tipicamente vinda de database.db.listar_parceiros_livelo, e devolve o primeiro cujo nome ou alias seja equivalente ao nome da loja informado, segundo nomes_equivalentes. devolve none quando nenhum parceiro casar.

    cada parceiro pode ser um dict ou um objeto com atributos, as chaves chave_nome e chave_alias indicam onde ler o nome e o alias de cada um.
    """
    for parceiro in parceiros:
        if isinstance(parceiro, dict):
            nome = parceiro.get(chave_nome)
            alias = parceiro.get(chave_alias)
        else:
            nome = getattr(parceiro, chave_nome, None)
            alias = getattr(parceiro, chave_alias, None)

        if nome and nomes_equivalentes(nome_loja, nome):
            return parceiro
        if alias and nomes_equivalentes(nome_loja, alias):
            return parceiro

    return None