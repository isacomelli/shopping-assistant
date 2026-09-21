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
    {"nome": "ABC da Construcao", "alias": "abc da construcao", "codigo": "ABC", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/abc/image.jpeg"},
    {"nome": "Abelha Rainha", "alias": "abelha rainha", "codigo": "BLH", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_BLH_20230606-123124.png"},
    {"nome": "ACER", "alias": "acer", "codigo": "ACE", "pontos_padrao": 2.0, "logo_url": "https://partners-profile.livelo.com.br/ace/image.png"},
    {"nome": "ADCOS", "alias": "adcos", "codigo": "SPA", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_SPA.png"},
    {"nome": "Agaxtur Cruzeiros", "alias": "cruzeiros agaxtur", "codigo": "AGX", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_AGX_20250611-162406.png"},
    {"nome": "Allianz", "alias": "allianz", "codigo": "ALZ", "pontos_padrao": 4.0, "logo_url": "https://www.livelo.com.br/file/general/config_ALZ_new_logo_travel.png"},
    {"nome": "Alura", "alias": "alura", "codigo": "ALU", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/alu/image.webp"},
    {"nome": "AMOBELEZA", "alias": "amobeleza", "codigo": "AMO", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/amo/image.jpeg"},
    {"nome": "Angeloni", "alias": "angeloni", "codigo": "AGE", "pontos_padrao": 4.0, "logo_url": "https://www.livelo.com.br/file/general/config_AGE.png"},
    {"nome": "Aramis", "alias": "aramis", "codigo": "ARA", "pontos_padrao": 2.0, "logo_url": "https://partners-profile.livelo.com.br/ara/image.webp"},
    {"nome": "Asics", "alias": "asics", "codigo": "ACS", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_ACS_asics_192x120.jpg"},
    {"nome": "Assinatura Coffee Mais", "alias": "assinatura coffemais", "codigo": "ASS", "pontos_padrao": 6.0, "logo_url": "https://partners-profile.livelo.com.br/ass/image.webp"},
    {"nome": "Assist Card Seguro-Viagem", "alias": "assist card seguros", "codigo": "ASC", "pontos_padrao": 12.0, "logo_url": "https://www.livelo.com.br/file/general/config_ASC_asc-logo.png"},
    {"nome": "Avon", "alias": "avon", "codigo": "AVN", "pontos_padrao": 6.0, "logo_url": "https://partners-profile.livelo.com.br/avn/image.webp"},
    {"nome": "Bagaggio", "alias": "bagaggio", "codigo": "BAG", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_BAG.png"},
    {"nome": "Baianão", "alias": "baianao", "codigo": "BNM", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_BNM_20230613-133931.png"},
    {"nome": "Bankei", "alias": "bankei", "codigo": "BAN", "pontos_padrao": 0.4, "logo_url": "https://www.livelo.com.br/file/general/config_BAN_20250630-163602.png"},
    {"nome": "Beach Park Hospedagens", "alias": "beach park", "codigo": "BPK", "pontos_padrao": 2.0, "logo_url": "https://partners-profile.livelo.com.br/bpk/image.webp"},
    {"nome": "Beach Park Ingressos", "alias": "beach park", "codigo": "BPK", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/bpk/image.webp"},
    {"nome": "Beep", "alias": "beep", "codigo": "BEP", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_BEP_20220913-161656.png"},
    {"nome": "Beleza na web", "alias": "beleza na web", "codigo": "BLZ", "pontos_padrao": 2.0, "logo_url": "https://partners-profile.livelo.com.br/blz/image.jpeg"},
    {"nome": "Beto Carrero World", "alias": "beto carrero", "codigo": "JBW", "pontos_padrao": 2.0, "logo_url": "https://partners-profile.livelo.com.br/jbw/image.png"},
    {"nome": "Beyoung", "alias": "beyoung", "codigo": "BYG", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_BYG_20221103-124341.png"},
    {"nome": "Bibi", "alias": "bibi calcados", "codigo": "BBB", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/bbb/image.webp"},
    {"nome": "BO.BÔ", "alias": "bobo", "codigo": "RBO", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_RBO_20231221-210657.png"},
    {"nome": "Bobstore", "alias": "bobstore", "codigo": "IBB", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_IBB_20230601-151840.png"},
    {"nome": "Bombay Herbs & Spices", "alias": "bombay herbse spices", "codigo": "BBH", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_BBH.png"},
    {"nome": "Bradesco Capitalização", "alias": "bradesco capitalizacao", "codigo": "CLZ", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_CLZ_20230821-174405.png"},
    {"nome": "Bradesco Consórcios", "alias": "bradesco consorcios", "codigo": "BCS", "pontos_padrao": 30.0, "logo_url": "https://partners-profile.livelo.com.br/bcs/image.webp"},
    {"nome": "Buddha Spa", "alias": "buddha spa", "codigo": "BDH", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_BDH_192x120-logo-bdh.png"},
    {"nome": "Bulbe Energia", "alias": "bulbe", "codigo": "BLB", "pontos_padrao": 12.0, "logo_url": "https://www.livelo.com.br/file/general/config_BLB.png"},
    {"nome": "Buser", "alias": "buser", "codigo": "BSR", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_BSR_20221025-150747.png"},
    {"nome": "Cabana Magazine", "alias": "cabana magazine", "codigo": "GRM", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_GRM_cabana_192x120.jpg"},
    {"nome": "Café Orfeu", "alias": "cafe orfeu", "codigo": "CFO", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_CFO.png"},
    {"nome": "Camicado", "alias": "camicado", "codigo": "CMC", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_CMC_Camicado192x120.png"},
    {"nome": "Carrefour Mercado", "alias": "carrefour", "codigo": "CRM", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/crm/image.png"},
    {"nome": "Carrefour Shopping", "alias": "carrefour shopping", "codigo": "CRF", "pontos_padrao": 10.0, "logo_url": "https://partners-profile.livelo.com.br/crf/image.webp"},
    {"nome": "Carters", "alias": "carters", "codigo": "CTS", "pontos_padrao": 3.0, "logo_url": "https://partners-profile.livelo.com.br/cts/image.webp"},
    {"nome": "Cartão de Todos", "alias": "cartao de todos", "codigo": "TOD", "pontos_padrao": 2.0, "logo_url": "https://partners-profile.livelo.com.br/tod/image.webp"},
    {"nome": "Casas Bahia", "alias": "casas bahia", "codigo": "CSB", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/csb/image.jpeg"},
    {"nome": "CEA", "alias": "cea", "codigo": "CEA", "pontos_padrao": 2.0, "logo_url": "https://partners-profile.livelo.com.br/cea/image.jpeg"},
    {"nome": "Centauro", "alias": "centauro", "codigo": "CEN", "pontos_padrao": 6.0, "logo_url": "https://www.livelo.com.br/file/general/config_CEN_20241101-183633.png"},
    {"nome": "Cestas Michelli", "alias": "cestas michelli", "codigo": "MCH", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_MCH_new_logo_cestas-michelli.png"},
    {"nome": "Ciclic Seguro Celular", "alias": "ciclic celular", "codigo": "CEL", "pontos_padrao": 5.0, "logo_url": "https://www.livelo.com.br/file/general/config_CEL_20240724-205330.png"},
    {"nome": "Ciclic Seguro Viagem", "alias": "ciclic", "codigo": "CIC", "pontos_padrao": 14.0, "logo_url": "https://www.livelo.com.br/file/general/config_CIC_20240724-205301.png"},
    {"nome": "Civitatis", "alias": "civitatis", "codigo": "CIV", "pontos_padrao": 2.0, "logo_url": "https://partners-profile.livelo.com.br/civ/image.webp"},
    {"nome": "Claro", "alias": "claro", "codigo": "CLA", "pontos_padrao": 6.0, "logo_url": "https://www.livelo.com.br/file/general/config_CLA.png"},
    {"nome": "ClickBus", "alias": "clickbus", "codigo": "CLK", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_CLK_20230914-205558.png"},
    {"nome": "Coffee Mais", "alias": "coffee mais", "codigo": "CFF", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/cff/image.jpeg"},
    {"nome": "Colcci", "alias": "colcci", "codigo": "GAM", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/gam/image.jpeg"},
    {"nome": "Coliseu", "alias": "coliseu", "codigo": "CLS", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_CLS_logo-coliseu2.png"},
    {"nome": "Consórcio Magalu", "alias": "consorcio magalu", "codigo": "MGC", "pontos_padrao": 10.0, "logo_url": "https://www.livelo.com.br/file/general/config_MGC_20240515-194132.png"},
    {"nome": "Converse", "alias": "converse", "codigo": "CCL", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_CCL_20250718-163054.png"},
    {"nome": "Cook Eletroraro", "alias": "cook eletroraro", "codigo": "COK", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_COK.png"},
    {"nome": "Coris", "alias": "coris", "codigo": "CRS", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/crs/image.png"},
    {"nome": "Creditas", "alias": "creditas", "codigo": "CRD", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_CRD_crd-logo.png"},
    {"nome": "Crocs", "alias": "crocs", "codigo": "CRO", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/cro/image.webp"},
    {"nome": "Dafiti", "alias": "dafiti", "codigo": "DAF", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_DAF_20231213-191312.png"},
    {"nome": "Decathlon", "alias": "decathlon", "codigo": "DCH", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_DCH_20240313-123029.png"},
    {"nome": "Democrata", "alias": "democrata", "codigo": "DMC", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_DMC.png"},
    {"nome": "Divvino", "alias": "divvino", "codigo": "AGN", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_AGN.png"},
    {"nome": "Drogal", "alias": "drogal", "codigo": "DRO", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/dro/image.jpeg"},
    {"nome": "Drogaria Sao Paulo", "alias": "drogaria sao paulo", "codigo": "DPS", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_DPS_drogaria-sao-paulo-192x120.png"},
    {"nome": "Drogarias Pacheco", "alias": "drogarias pacheco", "codigo": "DPC", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_DPC_192x120-logo-drogarias-pacheco.png"},
    {"nome": "Dudalina", "alias": "dudalina", "codigo": "DDL", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/ddl/image.webp"},
    {"nome": "Dufrio", "alias": "dufrio", "codigo": "DUF", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_DUF_20250618-201917.png"},
    {"nome": "Easy Live", "alias": "easy live", "codigo": "ESL", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/esl/image.webp"},
    {"nome": "EDP", "alias": "edp", "codigo": "EDP", "pontos_padrao": 6.0, "logo_url": "https://www.livelo.com.br/file/general/config_EDP_20240522-161742.png"},
    {"nome": "elbo", "alias": "elbo", "codigo": "ELB", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_ELB.png"},
    {"nome": "Electrolux", "alias": "electrolux", "codigo": "ELX", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/elx/image.jpeg"},
    {"nome": "Ellus", "alias": "ellus", "codigo": "ELS", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_ELS.png"},
    {"nome": "Estapar", "alias": "estapar", "codigo": "EST", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/est/image.png"},
    {"nome": "Eudora", "alias": "eudora", "codigo": "EUD", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_EUD_eudora_192x120.jpg"},
    {"nome": "Euro", "alias": "euro", "codigo": "EUR", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_EUR.png"},
    {"nome": "Extra", "alias": "extra", "codigo": "EXT", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/ext/image.jpeg"},
    {"nome": "Faber-Castell", "alias": "faber castell", "codigo": "FBC", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_FBC.png"},
    {"nome": "Farmacias App", "alias": "farmacias app", "codigo": "NCC", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_NCC.png"},
    {"nome": "Fast Shop", "alias": "fast shop", "codigo": "FST", "pontos_padrao": 5.0, "logo_url": "https://partners-profile.livelo.com.br/fst/image.webp"},
    {"nome": "Fila", "alias": "fila", "codigo": "FLA", "pontos_padrao": 9.0, "logo_url": "https://www.livelo.com.br/file/general/config_FLA_20220908-222200.png"},
    {"nome": "Foco", "alias": "foco", "codigo": "FOC", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_FOC_foco_192x120.jpg"},
    {"nome": "Forever Liss", "alias": "forever liss", "codigo": "LSS", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_LSS.png"},
    {"nome": "Frigelar", "alias": "frigelar", "codigo": "FRG", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_FRG_frg_logo.jpg"},
    {"nome": "Fóssil", "alias": "fossil", "codigo": "SCS", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/scs/image.webp"},
    {"nome": "Gazin", "alias": "gazin", "codigo": "GZN", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_GZN_20230612-132902.png"},
    {"nome": "Giuliana Flores", "alias": "giuliana flores", "codigo": "GFL", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_GFL_192x120-giulianaflores_com-margem.png"},
    {"nome": "Go case", "alias": "gocase", "codigo": "GCS", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_GCS.png"},
    {"nome": "Granado", "alias": "granado", "codigo": "CGN", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_CGN.png"},
    {"nome": "Grupo Dreams", "alias": "grupo dreams", "codigo": "DRT", "pontos_padrao": 4.0, "logo_url": "https://www.livelo.com.br/file/general/config_DRT_20231101-141230.png"},
    {"nome": "Guess", "alias": "guess", "codigo": "GSS", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_GSS.png"},
    {"nome": "Guldi", "alias": "guldi", "codigo": "GUL", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_GUL.png"},
    {"nome": "Havaianas", "alias": "havaianas", "codigo": "ALP", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_ALP_20240805-182947.png"},
    {"nome": "Hering", "alias": "hering", "codigo": "HRG", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_HRG_192x120-hering.png"},
    {"nome": "Hering Outlet", "alias": "hering outlet", "codigo": "OUT", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/out/image.jpeg"},
    {"nome": "Hero Seguro Celular", "alias": "hero seguro celular", "codigo": "CLE", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_CLE.png"},
    {"nome": "HERO SEGURO VIAGEM", "alias": "hero", "codigo": "HRH", "pontos_padrao": 14.0, "logo_url": "https://partners-profile.livelo.com.br/hrh/image.webp"},
    {"nome": "Home Angels", "alias": "home angels", "codigo": "ZAI", "pontos_padrao": 0.1, "logo_url": "https://www.livelo.com.br/file/general/config_ZAI_new_logo_home.png"},
    {"nome": "Hope", "alias": "hope", "codigo": "HPE", "pontos_padrao": 2.0, "logo_url": "https://partners-profile.livelo.com.br/hpe/image.jpeg"},
    {"nome": "Hope Resort", "alias": "hope resort", "codigo": "RST", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_RST_192x129-logo-hope-resorts.png"},
    {"nome": "Horas Magicas", "alias": "horas magicas", "codigo": "HMG", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_HMG_192x120_horasmagicas_v2.png"},
    {"nome": "Hot Beach", "alias": "hot beach", "codigo": "HBC", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_HBC_20241016-141526.png"},
    {"nome": "Hoteis com", "alias": "hoteis", "codigo": "HTC", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/htc/image.png"},
    {"nome": "Hotel Nacional", "alias": "hotel nacional", "codigo": "WHN", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_WHN_20221123-193130.png"},
    {"nome": "Imaginarium", "alias": "imaginarium", "codigo": "IMG", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_IMG.png"},
    {"nome": "Individual", "alias": "individual", "codigo": "IND", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_IND_20240201-104950.png"},
    {"nome": "Insider Store", "alias": "insider store", "codigo": "INS", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_INS_20240417-164559.png"},
    {"nome": "John John", "alias": "john john", "codigo": "JOH", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/joh/image.webp"},
    {"nome": "Kabum!", "alias": "kabum", "codigo": "KBM", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/kbm/image.webp"},
    {"nome": "Klabin ForYou", "alias": "klabin", "codigo": "KLB", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_KLB_20230418-141817.png"},
    {"nome": "Klubi Consórcio Celular", "alias": "klubi celular", "codigo": "KLU", "pontos_padrao": 40.0, "logo_url": "https://partners-profile.livelo.com.br/klu/image.webp"},
    {"nome": "Klubi Consórcio Imóvel", "alias": "klubi imovel", "codigo": "IMO", "pontos_padrao": 40.0, "logo_url": "https://partners-profile.livelo.com.br/imo/image.webp"},
    {"nome": "Klubi Consórcio Moto", "alias": "klubi moto", "codigo": "MOT", "pontos_padrao": 40.0, "logo_url": "https://partners-profile.livelo.com.br/mot/image.webp"},
    {"nome": "Klubi Consórcio Viagem", "alias": "klubi viagem", "codigo": "VIA", "pontos_padrao": 40.0, "logo_url": "https://partners-profile.livelo.com.br/via/image.webp"},
    {"nome": "Lacoste", "alias": "lacoste", "codigo": "LCT", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_LCT.png"},
    {"nome": "LE LIS", "alias": "lelis", "codigo": "LLB", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/llb/image.jpeg"},
    {"nome": "LEGO", "alias": "lego", "codigo": "LEG", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_LEG.png"},
    {"nome": "Liga Vitória - Seguro de Viagem", "alias": "liga vitoria viagem", "codigo": "LSG", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_LSG.png"},
    {"nome": "Liga Vitória Consórcio", "alias": "liga vitoria", "codigo": "LVC", "pontos_padrao": 35.0, "logo_url": "https://www.livelo.com.br/file/general/config_LVC_20240809-203335.png"},
    {"nome": "Liga Vitória Seguro Auto", "alias": "liga vitoria auto", "codigo": "LSA", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_LSA.png"},
    {"nome": "Liga Vitória Seguro de Vida", "alias": "liga vitoria", "codigo": "LVC", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_LVC_20240809-203335.png"},
    {"nome": "Liga Vitória Seguro Moto", "alias": "liga vitoria moto", "codigo": "LSM", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_LSM.png"},
    {"nome": "Liga Vitória Seguro Residencial", "alias": "liga vitoria residencial", "codigo": "LSR", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_LSR.png"},
    {"nome": "LIVE!", "alias": "live oficial", "codigo": "LVE", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/lve/image.webp"},
    {"nome": "Liz", "alias": "liz", "codigo": "CMR", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_CMR_liz_192x120.jpg"},
    {"nome": "Localiza", "alias": "localiza", "codigo": "LCR", "pontos_padrao": 4.0, "logo_url": "https://www.livelo.com.br/file/general/config_LCR_20240115-183010.png"},
    {"nome": "Localiza Meoo", "alias": "localiza meoo", "codigo": "LFL", "pontos_padrao": 10.0, "logo_url": "https://www.livelo.com.br/file/general/config_LFL_20240614-205718.png"},
    {"nome": "Loccitane", "alias": "loccitane", "codigo": "PRV", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_PRV_loccitane_192x120.jpg"},
    {"nome": "Loccitane au Bresil", "alias": "loccitane au bresil", "codigo": "LCC", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_LCC_Loccitane.png"},
    {"nome": "Loja do Mecânico", "alias": "loja do mecanico", "codigo": "LMC", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/lmc/image.webp"},
    {"nome": "Lojas Torra", "alias": "lojas torra", "codigo": "TRR", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/trr/image.webp"},
    {"nome": "Loungerie", "alias": "loungerie", "codigo": "LGR", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_LGR_192x120-logo-loungerie2.png"},
    {"nome": "Luxury Loyalty", "alias": "luxury loyalty", "codigo": "LLY", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_LLY_new_logo_luxury.png"},
    {"nome": "Magalu", "alias": "magalu", "codigo": "MZL", "pontos_padrao": 4.0, "logo_url": "https://partners-profile.livelo.com.br/mzl/image.jpeg"},
    {"nome": "Maltacor", "alias": "maltacor", "codigo": "MAL", "pontos_padrao": 5.0, "logo_url": "https://www.livelo.com.br/file/general/config_MAL_20250812-135633.png"},
    {"nome": "Malwee", "alias": "malwee", "codigo": "MLW", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/mlw/image.webp"},
    {"nome": "MAPFRE Seguro Auto", "alias": "mapfre", "codigo": "MPF", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/mpf/image.webp"},
    {"nome": "Max Titanium", "alias": "max titanium", "codigo": "SUP", "pontos_padrao": 6.0, "logo_url": "https://www.livelo.com.br/file/general/config_SUP.png"},
    {"nome": "MaxRacer", "alias": "max racer", "codigo": "BCI", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_BCI_192x120-logo-MaxRacer.png"},
    {"nome": "MedSênior", "alias": "medsenior", "codigo": "MED", "pontos_padrao": 7.0, "logo_url": "https://www.livelo.com.br/file/general/config_MED.png"},
    {"nome": "Meia Sola", "alias": "meia sola", "codigo": "MSA", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_MSA.png"},
    {"nome": "Mercado Livre", "alias": "mercado livre", "codigo": "MCL", "pontos_padrao": 2.0, "logo_url": "https://partners-profile.livelo.com.br/mcl/image.png"},
    {"nome": "Midea", "alias": "midea", "codigo": "MDI", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/mdi/image.jpeg"},
    {"nome": "Mistral", "alias": "mistral", "codigo": "MIS", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/mis/image.jpeg"},
    {"nome": "Mizuno", "alias": "mizuno", "codigo": "VMZ", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_VMZ_192x120-mizuno230622.png"},
    {"nome": "Mobifácil", "alias": "mobifacil", "codigo": "MOB", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/mob/image.png"},
    {"nome": "Mobills", "alias": "mobills", "codigo": "MBS", "pontos_padrao": 10.0, "logo_url": "https://www.livelo.com.br/file/general/config_MBS.png"},
    {"nome": "Mondaine", "alias": "mondaine", "codigo": "MDN", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_MDN.png"},
    {"nome": "Monte Carlo", "alias": "montecarlo", "codigo": "MCV", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_MCV_20241205-164600.png"},
    {"nome": "Morana", "alias": "morana", "codigo": "MRN", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_MRN.png"},
    {"nome": "Movida", "alias": "movida", "codigo": "MOV", "pontos_padrao": 9.0, "logo_url": "https://www.livelo.com.br/file/general/config_MOV_logomovida0112.png"},
    {"nome": "Mycon Consórcio Digital", "alias": "mycon", "codigo": "MYC", "pontos_padrao": 32.0, "logo_url": "https://www.livelo.com.br/file/general/config_MYC_20240614-141501.png"},
    {"nome": "Nars", "alias": "nars", "codigo": "NRS", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_NRS_20230605-134535.png"},
    {"nome": "Natura", "alias": "natura", "codigo": "NTR", "pontos_padrao": 4.0, "logo_url": "https://partners-profile.livelo.com.br/ntr/image.jpeg"},
    {"nome": "Nespresso", "alias": "nespresso", "codigo": "NES", "pontos_padrao": 5.0, "logo_url": "https://partners-profile.livelo.com.br/nes/image.png"},
    {"nome": "Netshoes", "alias": "netshoes", "codigo": "NTS", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_NTS_20240701-230509.png"},
    {"nome": "New Balance", "alias": "new balance", "codigo": "NWB", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_NWB.png"},
    {"nome": "Next Seguro Viagem", "alias": "next", "codigo": "NXE", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_NXE_20230605-134503.png"},
    {"nome": "Nike", "alias": "nike", "codigo": "NIK", "pontos_padrao": 4.0, "logo_url": "https://www.livelo.com.br/file/general/config_NIK.png"},
    {"nome": "O Boticario", "alias": "o boticario", "codigo": "BOT", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/bot/image.webp"},
    {"nome": "O.U.i Paris", "alias": "o.u.i paris", "codigo": "OUI", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_OUI.png"},
    {"nome": "Oceane", "alias": "oceane", "codigo": "OCN", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_OCN_20220830-184933.png"},
    {"nome": "Oficina", "alias": "oficina", "codigo": "RZZ", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/rzz/image.webp"},
    {"nome": "OLX", "alias": "OLX", "codigo": "OLX", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/olx/image.png"},
    {"nome": "Olympikus", "alias": "olympikus", "codigo": "OVC", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_OVC_192x120-olympikus.png"},
    {"nome": "Osklen", "alias": "osklen", "codigo": "OSK", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_OSK_osklen-cp.png"},
    {"nome": "Oxford", "alias": "oxford", "codigo": "OXF", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_OXF.png"},
    {"nome": "Pado", "alias": "pado", "codigo": "PDO", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_PDO.png"},
    {"nome": "PerfectDraft (Ambev)", "alias": "perfec tdraft", "codigo": "ABV", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_ABV.png"},
    {"nome": "Petlove", "alias": "pet love", "codigo": "PLV", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_PLV_190x120-petlove-b.png"},
    {"nome": "Petlove Saúde", "alias": "pet love saude", "codigo": "PVS", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/pvs/image.png"},
    {"nome": "Petz", "alias": "petz", "codigo": "PTZ", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_PTZ_20250131-202704.png"},
    {"nome": "Piatan Natural", "alias": "piatan natural", "codigo": "PAT", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_PAT_192x190-piatan.png"},
    {"nome": "PneuStore", "alias": "pneu store", "codigo": "CPX", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_CPX.png"},
    {"nome": "Pontofrio", "alias": "pontofrio", "codigo": "PTF", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/ptf/image.jpeg"},
    {"nome": "Portal das Malas", "alias": "portal das malas", "codigo": "PDM", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_PDM_portaldasmalas_192x120.jpg"},
    {"nome": "Portallar", "alias": "portallar", "codigo": "PLL", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_PLL_20221128-112816.png"},
    {"nome": "Porto Seguro", "alias": "portoseguro", "codigo": "POT", "pontos_padrao": 20.0, "logo_url": "https://partners-profile.livelo.com.br/pot/image.webp"},
    {"nome": "Porto Serviço", "alias": "porto servico", "codigo": "PTO", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/pto/image.webp"},
    {"nome": "Posthaus", "alias": "posthaus", "codigo": "PTH", "pontos_padrao": 8.0, "logo_url": "https://partners-profile.livelo.com.br/pth/image.webp"},
    {"nome": "Probiótica", "alias": "probiotica", "codigo": "PBT", "pontos_padrao": 6.0, "logo_url": "https://partners-profile.livelo.com.br/pbt/image.webp"},
    {"nome": "Puket", "alias": "puket", "codigo": "PKT", "pontos_padrao": 2.0, "logo_url": "https://partners-profile.livelo.com.br/pkt/image.webp"},
    {"nome": "Qcompra", "alias": "qcompra", "codigo": "QCP", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_QCP.png"},
    {"nome": "Quem Disse, Berenice?", "alias": "quem disse berenice", "codigo": "QDB", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_QDB.png"},
    {"nome": "Quero Passagem", "alias": "quero passagem", "codigo": "QPV", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_QPV_queropassagem_192x120.jpg"},
    {"nome": "Quero-Quero", "alias": "quero quero", "codigo": "LQQ", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_LQQ_20240502-165025.png"},
    {"nome": "Quintess", "alias": "quintess", "codigo": "LHS", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_LHS.png"},
    {"nome": "Renner", "alias": "renner", "codigo": "RNN", "pontos_padrao": 10.0, "logo_url": "https://partners-profile.livelo.com.br/rnn/image.webp"},
    {"nome": "Reserva", "alias": "reserva", "codigo": "RES", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_RES_config_RES_reserva_192x120.jpg"},
    {"nome": "Reservecar", "alias": "reserve car", "codigo": "RSC", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_RSC_new_logo_reservecar.png"},
    {"nome": "Riachuelo", "alias": "riachuelo", "codigo": "RCH", "pontos_padrao": 3.0, "logo_url": "https://partners-profile.livelo.com.br/rch/image.webp"},
    {"nome": "Richards", "alias": "richards", "codigo": "IRC", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_IRC.png"},
    {"nome": "Salinas", "alias": "salinas", "codigo": "SLN", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_SLN.png"},
    {"nome": "Sam's Club", "alias": "sams club", "codigo": "WMB", "pontos_padrao": 84.0, "logo_url": "https://partners-profile.livelo.com.br/wmb/image.jpeg"},
    {"nome": "Sam's Club - E-commerce", "alias": "sams club e commerce", "codigo": "ECO", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_ECO.png"},
    {"nome": "Samsonite", "alias": "samsonite", "codigo": "SMS", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_SMS.png"},
    {"nome": "Scudoo Seguro Celular", "alias": "scudoo", "codigo": "SIO", "pontos_padrao": 4.0, "logo_url": "https://partners-profile.livelo.com.br/sio/image.png"},
    {"nome": "Seculus", "alias": "seculus", "codigo": "SCL", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_SCL.png"},
    {"nome": "Seguro Residencial MAPFRE", "alias": "mapfre residencial", "codigo": "MSR", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/msr/image.webp"},
    {"nome": "Seguro Viagem Bradesco", "alias": "seguro viagem bradesco", "codigo": "BVP", "pontos_padrao": 10.0, "logo_url": "https://www.livelo.com.br/file/general/config_BVP_20250403-142057.png"},
    {"nome": "Sephora", "alias": "sephora", "codigo": "SPR", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/spr/image.webp"},
    {"nome": "Seus Ingressos", "alias": "seus ingressos", "codigo": "SIN", "pontos_padrao": 3.0, "logo_url": "https://partners-profile.livelo.com.br/sin/image.webp"},
    {"nome": "Shiseido", "alias": "shiseido", "codigo": "SHS", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_SHS.png"},
    {"nome": "Shoestock", "alias": "shoestock", "codigo": "NSC", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_NSC_shoestock.png"},
    {"nome": "Shopee", "alias": "shopee", "codigo": "PEE", "pontos_padrao": 2.0, "logo_url": "https://partners-profile.livelo.com.br/pee/image.jpeg"},
    {"nome": "Sixt", "alias": "sixt", "codigo": "SXT", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_SXT.png"},
    {"nome": "Speedo", "alias": "speedo", "codigo": "SPD", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_SPD.png"},
    {"nome": "Spicy", "alias": "spicy", "codigo": "MCB", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_MCB.png"},
    {"nome": "Studio Z", "alias": "studioz", "codigo": "STZ", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_STZ_20230922-171808.png"},
    {"nome": "Suhai Seguradora", "alias": "suhai", "codigo": "SUH", "pontos_padrao": 2.0, "logo_url": "https://partners-profile.livelo.com.br/suh/image.webp"},
    {"nome": "SulAmérica Plano Odonto", "alias": "sulamerica seguro odonto", "codigo": "SUO", "pontos_padrao": 6.0, "logo_url": "https://www.livelo.com.br/file/general/config_SUO_20250429-191952.png"},
    {"nome": "SulAmérica Seguro Viagem", "alias": "sulamerica seguro viagem", "codigo": "SUL", "pontos_padrao": 12.0, "logo_url": "https://www.livelo.com.br/file/general/config_SUL_20250429-192024.png"},
    {"nome": "Summerville", "alias": "summerville", "codigo": "PPH", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_PPH_logo-192x120-summerville2.png"},
    {"nome": "Supernosso", "alias": "supernosso", "codigo": "SPN", "pontos_padrao": 0.3333, "logo_url": "https://www.livelo.com.br/file/general/config_SPN_192x120-super-nosso.png"},
    {"nome": "Technos", "alias": "technos", "codigo": "TEC", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_TEC.png"},
    {"nome": "Telhanorte", "alias": "telhanorte", "codigo": "TLN", "pontos_padrao": 1.0, "logo_url": "https://partners-profile.livelo.com.br/tln/image.png"},
    {"nome": "Thule", "alias": "thule", "codigo": "THL", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_THL_20230727-184159.png"},
    {"nome": "Tia Sônia", "alias": "tia sonia", "codigo": "AMT", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_AMT.png"},
    {"nome": "TIM", "alias": "tim", "codigo": "TIM", "pontos_padrao": 6.0, "logo_url": "https://www.livelo.com.br/file/general/config_TIM_20240520-105353.png"},
    {"nome": "Tokio Marine Seguros", "alias": "tokio marine", "codigo": "TOM", "pontos_padrao": 10.0, "logo_url": "https://www.livelo.com.br/file/general/config_TOM.png"},
    {"nome": "Top Móveis", "alias": "top moveis", "codigo": "TMS", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_TMS_20231204-051544.png"},
    {"nome": "TripChip", "alias": "tripchip", "codigo": "SKA", "pontos_padrao": 5.0, "logo_url": "https://www.livelo.com.br/file/general/config_SKA.png"},
    {"nome": "Trocafy", "alias": "trocafy", "codigo": "ALD", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_ALD.png"},
    {"nome": "Truss", "alias": "truss", "codigo": "TUS", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_TUS.png"},
    {"nome": "Umbro", "alias": "umbro", "codigo": "FIL", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_FIL_192x120-umbro-logo.png"},
    {"nome": "Under Armour", "alias": "under armour", "codigo": "VCA", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_VCA_192x120-under-armour.png"},
    {"nome": "Unidas", "alias": "unidas", "codigo": "UND", "pontos_padrao": 10.0, "logo_url": "https://www.livelo.com.br/file/general/config_UND_192x120-unidas-270522.png"},
    {"nome": "Universal Assistance – Seguro Viagem", "alias": "universal assistance", "codigo": "AST", "pontos_padrao": 6.0, "logo_url": "https://www.livelo.com.br/file/general/config_AST_20240626-162810.png"},
    {"nome": "Viajar", "alias": "viajar", "codigo": "VJR", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_VJR.png"},
    {"nome": "Vivara", "alias": "vivara", "codigo": "VVR", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_VVR_vivara_192x120.jpg"},
    {"nome": "VR Collezioni", "alias": "vr collezioni", "codigo": "VRC", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_VRC.png"},
    {"nome": "Vult", "alias": "vult", "codigo": "VUL", "pontos_padrao": 8.0, "logo_url": "https://www.livelo.com.br/file/general/config_VUL.png"},
    {"nome": "Wise UP", "alias": "wise up", "codigo": "WSP", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_WSP_wiseup3.png"},
    {"nome": "Yvy", "alias": "yvy", "codigo": "YVY", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_YVY_yvy_192x120.jpg"},
    {"nome": "Zattini", "alias": "zattini", "codigo": "ZTN", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_ZTN_new_logo_zattini.png"},
    {"nome": "Zee.Dog", "alias": "zeedog", "codigo": "ZDG", "pontos_padrao": 2.0, "logo_url": "https://www.livelo.com.br/file/general/config_ZDG.png"},
    {"nome": "Zee.Now", "alias": "zee.now", "codigo": "ZNW", "pontos_padrao": 1.0, "logo_url": "https://www.livelo.com.br/file/general/config_ZNW.png"},
    {"nome": "Zissou", "alias": "zissou", "codigo": "ZSS", "pontos_padrao": 3.0, "logo_url": "https://www.livelo.com.br/file/general/config_ZSS_20230505-122615.png"},
    {"nome": "Época Cosméticos", "alias": "epoca cosmeticos", "codigo": "EPC", "pontos_padrao": 2.0, "logo_url": "https://partners-profile.livelo.com.br/epc/image.webp"},
]


# padrao de url das fotos de perfil dos parceiros da livelo mais recentes, tipo https://partners-profile.livelo.com.br/mzl/image.jpeg para o codigo MZL, usado so como ultimo recurso quando o parceiro nao tiver uma logo_url ja coletada. esse padrao NAO e confiavel sozinho, cada parceiro pode usar uma extensao de arquivo diferente, .jpeg, .png, .webp, e parceiros mais antigos ficam num dominio totalmente diferente, tipo www.livelo.com.br/file/general/config_XXX.png, ver o atributo src real de cada logo em scrapers/ultimo_html_livelo.html. por isso scrapers/livelo.py agora le a logo_url de verdade direto do html, em vez de so guardar o codigo e adivinhar essa url, e PARCEIROS_LIVELO_CONHECIDOS abaixo ja vem com logo_url preenchida para todo parceiro que tinha uma logo na coleta manual mais recente.
URL_BASE_LOGO_PARCEIRO_LIVELO = "https://partners-profile.livelo.com.br"


def obter_url_logo_parceiro(parceiro):
    """
    devolve a url da logo de um parceiro Livelo, priorizando a logo_url real ja coletada, seja de um parceiro atualizado no banco por scrapers/livelo.py, seja de uma entrada de PARCEIROS_LIVELO_CONHECIDOS que ja venha com essa url preenchida.

    so cai para o padrao adivinhado a partir do codigo, em URL_BASE_LOGO_PARCEIRO_LIVELO, quando nenhuma logo_url estiver disponivel, o que pode nao bater com a extensao ou o dominio reais de todo parceiro, ver o comentario acima. aceita tanto um dict, com as chaves logo_url e codigo, quanto o proprio codigo como string. devolve uma string vazia quando o parceiro nao tiver nem logo_url nem codigo cadastrado, para quem exibe a oferta cair de volta para outra fonte de logo.
    """
    if isinstance(parceiro, dict):
        logo_url = (parceiro.get("logo_url") or "").strip()
        if logo_url:
            return logo_url
        codigo = parceiro.get("codigo")
    else:
        codigo = parceiro

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
