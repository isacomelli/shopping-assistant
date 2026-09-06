"""
camada de acesso ao banco sqlite do assistente de compras.

todas as tabelas ja possuem a coluna user_id, mesmo que hoje so exista
um unico usuario local, justamente para facilitar uma eventual
migracao para um servico multiusuario na nuvem no futuro.

sobre migracao de esquema, como o banco ja existe no disco de quem ja
usava o app antes, nao da pra so mudar o CREATE TABLE, ele so roda na
primeira vez. por isso, colunas novas sao adicionadas com ALTER TABLE
dentro de _migrar_colunas_novas, ignorando o erro quando a coluna ja
existe.

sobre a livelo, a pesquisa automatica em
services/pesquisa_produto.py consulta a busca da livelo direto por
loja, em scrapers/livelo.py, nao existe mais tabela nem cadastro
manual de parceiro aqui.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

CAMINHO_BANCO = Path(__file__).parent / "shopping.db"

USER_ID_PADRAO = 1

VALOR_MILHEIRO_PADRAO = 15.0
PONTOS_DOLAR_CARTAO_PADRAO = 3.0


@contextmanager
def conexao():
    conn = sqlite3.connect(CAMINHO_BANCO)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _adicionar_coluna_se_nao_existir(conn, tabela, definicao_coluna):
    """
    tenta adicionar uma coluna nova numa tabela ja existente, e
    ignora o erro caso a coluna ja tenha sido criada numa execucao
    anterior. e assim que o sqlite migra esquema em bancos que ja
    estao em uso.
    """
    nome_coluna = definicao_coluna.split()[0]
    try:
        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {definicao_coluna}")
    except sqlite3.OperationalError as erro:
        if "duplicate column name" not in str(erro).lower():
            raise


def _migrar_colunas_novas(conn):
    _adicionar_coluna_se_nao_existir(
        conn, "user_settings", f"valor_milheiro_padrao REAL NOT NULL DEFAULT {VALOR_MILHEIRO_PADRAO}",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "user_settings", f"pontos_dolar_cartao_padrao REAL NOT NULL DEFAULT {PONTOS_DOLAR_CARTAO_PADRAO}",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "ofertas", "pontos_por_dolar_cartao REAL NOT NULL DEFAULT 0",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "ofertas", "percentual_bonus_transferencia REAL NOT NULL DEFAULT 0",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "ofertas", "valor_milheiro REAL NOT NULL DEFAULT 0",
    )


def inicializar_banco():
    with conexao() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                cdi_mensal REAL NOT NULL DEFAULT 1.1,
                cotacao_dolar REAL NOT NULL DEFAULT 5.4,
                atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            );

            CREATE TABLE IF NOT EXISTS cartoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                nome TEXT NOT NULL,
                pontos_por_dolar REAL NOT NULL DEFAULT 0,
                cashback_pct REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                nome TEXT NOT NULL,
                categoria TEXT,
                orcamento REAL,
                preco_alvo REAL,
                status TEXT NOT NULL DEFAULT 'esperar',
                criado_em TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ofertas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL DEFAULT 1,
                loja TEXT NOT NULL,
                tipo TEXT NOT NULL DEFAULT 'online',
                preco_pix REAL NOT NULL,
                preco_cartao REAL NOT NULL,
                parcelas INTEGER NOT NULL DEFAULT 1,
                pontos_por_real REAL NOT NULL DEFAULT 0,
                valor_ponto REAL NOT NULL DEFAULT 0,
                cashback_pct REAL NOT NULL DEFAULT 0,
                frete REAL NOT NULL DEFAULT 0,
                cupom REAL NOT NULL DEFAULT 0,
                observacoes TEXT,
                validade TEXT,
                confianca TEXT NOT NULL DEFAULT 'confirmada',
                preco_efetivo REAL,
                criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (produto_id) REFERENCES produtos(id)
            );

            CREATE TABLE IF NOT EXISTS historico_precos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER NOT NULL,
                loja TEXT NOT NULL,
                preco_anunciado REAL,
                preco_efetivo REAL,
                registrado_em TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (produto_id) REFERENCES produtos(id)
            );
            """
        )

        # a tabela livelo_parceiros existia para o cadastro manual de
        # parceiros, feature removida, a pesquisa automatica agora
        # consulta a livelo direto por loja, ver
        # services/pesquisa_produto.py e scrapers/livelo.py. este drop
        # limpa a tabela em bancos que ja existiam antes dessa
        # mudanca, sem afetar nenhuma outra tabela
        conn.execute("DROP TABLE IF EXISTS livelo_parceiros")

        _migrar_colunas_novas(conn)

        conn.execute(
            "INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)",
            (USER_ID_PADRAO,),
        )


# configuracoes

def obter_configuracoes():
    with conexao() as conn:
        linha = conn.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (USER_ID_PADRAO,)
        ).fetchone()
        return dict(linha)


def salvar_configuracoes(cdi_mensal, cotacao_dolar, valor_milheiro_padrao, pontos_dolar_cartao_padrao):
    with conexao() as conn:
        conn.execute(
            """
            UPDATE user_settings
            SET cdi_mensal = ?, cotacao_dolar = ?, valor_milheiro_padrao = ?,
                pontos_dolar_cartao_padrao = ?, atualizado_em = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (cdi_mensal, cotacao_dolar, valor_milheiro_padrao, pontos_dolar_cartao_padrao, USER_ID_PADRAO),
        )


# cartoes

def listar_cartoes():
    with conexao() as conn:
        linhas = conn.execute(
            "SELECT * FROM cartoes WHERE user_id = ? ORDER BY nome", (USER_ID_PADRAO,)
        ).fetchall()
        return [dict(linha) for linha in linhas]


def adicionar_cartao(nome, pontos_por_dolar, cashback_pct):
    with conexao() as conn:
        conn.execute(
            "INSERT INTO cartoes (user_id, nome, pontos_por_dolar, cashback_pct) VALUES (?, ?, ?, ?)",
            (USER_ID_PADRAO, nome, pontos_por_dolar, cashback_pct),
        )


def remover_cartao(cartao_id):
    with conexao() as conn:
        conn.execute("DELETE FROM cartoes WHERE id = ? AND user_id = ?", (cartao_id, USER_ID_PADRAO))


# produtos, a wishlist da reforma

def listar_produtos():
    with conexao() as conn:
        linhas = conn.execute(
            "SELECT * FROM produtos WHERE user_id = ? ORDER BY criado_em DESC", (USER_ID_PADRAO,)
        ).fetchall()
        return [dict(linha) for linha in linhas]


def obter_produto(produto_id):
    with conexao() as conn:
        linha = conn.execute(
            "SELECT * FROM produtos WHERE id = ? AND user_id = ?", (produto_id, USER_ID_PADRAO)
        ).fetchone()
        return dict(linha) if linha else None


def adicionar_produto(nome, categoria, orcamento, preco_alvo, status="esperar"):
    with conexao() as conn:
        cursor = conn.execute(
            """
            INSERT INTO produtos (user_id, nome, categoria, orcamento, preco_alvo, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (USER_ID_PADRAO, nome, categoria, orcamento, preco_alvo, status),
        )
        return cursor.lastrowid


def atualizar_status_produto(produto_id, status):
    with conexao() as conn:
        conn.execute(
            "UPDATE produtos SET status = ? WHERE id = ? AND user_id = ?",
            (status, produto_id, USER_ID_PADRAO),
        )


# ofertas

def listar_ofertas_por_produto(produto_id):
    with conexao() as conn:
        linhas = conn.execute(
            "SELECT * FROM ofertas WHERE produto_id = ? ORDER BY criado_em DESC", (produto_id,)
        ).fetchall()
        return [dict(linha) for linha in linhas]


def adicionar_oferta(produto_id, loja, tipo, preco_pix, preco_cartao, parcelas,
                      pontos_por_real, pontos_por_dolar_cartao, percentual_bonus_transferencia,
                      valor_milheiro, cashback_pct, frete, cupom, observacoes, validade,
                      confianca, preco_efetivo):
    with conexao() as conn:
        conn.execute(
            """
            INSERT INTO ofertas (
                produto_id, user_id, loja, tipo, preco_pix, preco_cartao, parcelas,
                pontos_por_real, pontos_por_dolar_cartao, percentual_bonus_transferencia,
                valor_milheiro, cashback_pct, frete, cupom,
                observacoes, validade, confianca, preco_efetivo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                produto_id, USER_ID_PADRAO, loja, tipo, preco_pix, preco_cartao, parcelas,
                pontos_por_real, pontos_por_dolar_cartao, percentual_bonus_transferencia,
                valor_milheiro, cashback_pct, frete, cupom,
                observacoes, validade, confianca, preco_efetivo,
            ),
        )


# historico de precos

def registrar_historico(produto_id, loja, preco_anunciado, preco_efetivo):
    with conexao() as conn:
        conn.execute(
            """
            INSERT INTO historico_precos (produto_id, loja, preco_anunciado, preco_efetivo)
            VALUES (?, ?, ?, ?)
            """,
            (produto_id, loja, preco_anunciado, preco_efetivo),
        )


def listar_historico(produto_id):
    with conexao() as conn:
        linhas = conn.execute(
            "SELECT * FROM historico_precos WHERE produto_id = ? ORDER BY registrado_em",
            (produto_id,),
        ).fetchall()
        return [dict(linha) for linha in linhas]


# =============================================================================
# parceiros livelo em cache, lidos do arquivo html manual
# =============================================================================


def salvar_parceiros_livelo(parceiros):
    """
    substitui a lista inteira de parceiros livelo em cache. usada no
    startup do app, quando o arquivo ultimo_html_livelo.html e
    reprocessado.
    """
    with conexao() as conn:
        conn.execute("DELETE FROM livelo_parceiros")
        for parceiro in parceiros:
            conn.execute(
                """
                INSERT INTO livelo_parceiros
                (codigo, nome, url, pontos_padrao, moeda_padrao,
                 pontos_clube, em_promocao, pontos_anteriores, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    parceiro.codigo,
                    parceiro.nome,
                    parceiro.url,
                    parceiro.pontos_padrao,
                    parceiro.moeda_padrao,
                    parceiro.pontos_clube,
                    1 if parceiro.em_promocao else 0,
                    parceiro.pontos_anteriores,
                ),
            )


def listar_parceiros_livelo():
    with conexao() as conn:
        linhas = conn.execute(
            "SELECT * FROM livelo_parceiros ORDER BY nome"
        ).fetchall()
        return [dict(linha) for linha in linhas]


def buscar_parceiro_livelo_por_nome(nome_loja):
    """
    busca um parceiro livelo pelo nome da loja, usando comparacao
    flexivel de texto. devolve o dicionario do parceiro ou none.
    """
    with conexao() as conn:
        linhas = conn.execute(
            "SELECT * FROM livelo_parceiros ORDER BY nome"
        ).fetchall()
        parceiros = [dict(linha) for linha in linhas]
        return _casar_nome_loja(nome_loja, parceiros)


def _normalizar_nome(texto):
    import unicodedata
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().strip().split())


def _casar_nome_loja(nome_loja, parceiros):
    """
    tenta casar o nome da loja do buscape com um parceiro livelo ja
    conhecido, usando comparacao por substrings normalizadas.
    """
    nome_norm = _normalizar_nome(nome_loja)

    # remocoes comuns para melhorar o casamento
    sufixos = [".com.br", ".com", " brasil", " online", " shop", " store"]
    nome_base = nome_norm
    for sufixo in sufixos:
        nome_base = nome_base.replace(sufixo, "")

    melhor_casamento = None
    melhor_pontuacao = 0

    for parceiro in parceiros:
        parceiro_norm = _normalizar_nome(parceiro["nome"])
        parceiro_base = parceiro_norm
        for sufixo in sufixos:
            parceiro_base = parceiro_base.replace(sufixo, "")

        # pontuacao 3: igualdade exata
        if nome_norm == parceiro_norm:
            return parceiro

        # pontuacao 2: um contem o outro (base limpo)
        if nome_base in parceiro_base or parceiro_base in nome_base:
            if len(parceiro_base) > melhor_pontuacao:
                melhor_casamento = parceiro
                melhor_pontuacao = len(parceiro_base)
            continue

        # pontuacao 1: palavras significativas em comum
        palavras_loja = {p for p in nome_base.split() if len(p) > 2}
        palavras_parceiro = {p for p in parceiro_base.split() if len(p) > 2}
        if palavras_loja and palavras_parceiro:
            intersecao = palavras_loja & palavras_parceiro
            if len(intersecao) == len(palavras_loja) or len(intersecao) == len(palavras_parceiro):
                if len(parceiro_base) > melhor_pontuacao:
                    melhor_casamento = parceiro
                    melhor_pontuacao = len(parceiro_base)

    return melhor_casamento