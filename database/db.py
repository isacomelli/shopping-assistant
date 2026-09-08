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
import json
import re
from datetime import datetime

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
    _adicionar_coluna_se_nao_existir(
        conn, "ofertas", "url_produto TEXT",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "ofertas", "preco REAL NOT NULL DEFAULT 0",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "ofertas", "atualizada_em TEXT",
    )
    _adicionar_coluna_se_nao_existir(conn, "historico_precos", "preco REAL")
    _adicionar_coluna_se_nao_existir(conn, "historico_precos", "preco_pix REAL")
    _adicionar_coluna_se_nao_existir(conn, "historico_precos", "preco_cartao REAL")
    _adicionar_coluna_se_nao_existir(conn, "historico_precos", "parcelas INTEGER")
    conn.execute(
        "UPDATE ofertas SET atualizada_em = COALESCE(criado_em, CURRENT_TIMESTAMP) "
        "WHERE atualizada_em IS NULL"
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
                url_produto TEXT,
                atualizada_em TEXT DEFAULT CURRENT_TIMESTAMP,
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
        _consolidar_ofertas(conn)
        _preencher_historico_das_ofertas(conn)
        _consolidar_historico(conn)

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


def atualizar_produto(produto_id, nome, categoria, orcamento, preco_alvo):
    with conexao() as conn:
        conn.execute(
            """
            UPDATE produtos
            SET nome = ?, categoria = ?, orcamento = ?, preco_alvo = ?
            WHERE id = ? AND user_id = ?
            """,
            (nome, categoria, orcamento, preco_alvo, produto_id, USER_ID_PADRAO),
        )


def excluir_produto(produto_id):
    with conexao() as conn:
        conn.execute(
            "DELETE FROM historico_precos WHERE produto_id = ?", (produto_id,)
        )
        conn.execute("DELETE FROM ofertas WHERE produto_id = ?", (produto_id,))
        conn.execute(
            "DELETE FROM produtos WHERE id = ? AND user_id = ?",
            (produto_id, USER_ID_PADRAO),
        )


# ofertas

def _chave_oferta_automatica(linha):
    preco = linha["preco"] or linha["preco_pix"] or linha["preco_cartao"] or 0
    return (
        re.sub(r"\s+", " ", (linha["loja"] or "").strip().lower()),
        round(float(preco), 2),
        round(float(linha["preco_pix"] or 0), 2),
        round(float(linha["preco_cartao"] or 0), 2),
        int(linha["parcelas"] or 1),
    )


def _consolidar_ofertas(conn):
    linhas = conn.execute(
        """
        SELECT * FROM ofertas
        WHERE user_id = ?
        ORDER BY produto_id, criado_em, id
        """,
        (USER_ID_PADRAO,),
    ).fetchall()
    mantidas = {}
    for linha in linhas:
        chave = (linha["produto_id"], _chave_oferta_automatica(linha))
        anterior = mantidas.get(chave)
        if anterior is None:
            mantidas[chave] = linha
            continue
        conn.execute(
            "UPDATE ofertas SET atualizada_em = COALESCE(?, atualizada_em) WHERE id = ?",
            (linha["atualizada_em"] or linha["criado_em"], anterior["id"]),
        )
        conn.execute("DELETE FROM ofertas WHERE id = ?", (linha["id"],))


def registrar_oferta_pesquisa(produto_id, loja, tipo, preco_pix, preco_cartao, parcelas,
                              pontos_por_real, pontos_por_dolar_cartao,
                              percentual_bonus_transferencia, valor_milheiro, cashback_pct,
                              frete, cupom, observacoes, validade, confianca, preco_efetivo,
                              preco=0,
                              url_produto=""):
    chave_oferta = (
        re.sub(r"\s+", " ", loja.strip().lower()),
        round(float(preco or preco_pix or preco_cartao or 0), 2),
        round(float(preco_pix or 0), 2),
        round(float(preco_cartao or 0), 2),
        int(parcelas or 1),
    )
    with conexao() as conn:
        linhas = conn.execute(
            """
            SELECT * FROM ofertas
            WHERE produto_id = ? AND user_id = ?
            ORDER BY id
            """,
            (produto_id, USER_ID_PADRAO),
        ).fetchall()
        correspondentes = [
            item for item in linhas if _chave_oferta_automatica(item) == chave_oferta
        ]
        linha = correspondentes[0] if correspondentes else None
        for duplicata in correspondentes[1:]:
            conn.execute("DELETE FROM ofertas WHERE id = ?", (duplicata["id"],))
        chave_url = (url_produto or "").strip()

        valores = (
            loja, tipo, preco_pix, preco_cartao, parcelas, pontos_por_real,
            pontos_por_dolar_cartao, percentual_bonus_transferencia, valor_milheiro,
            cashback_pct, frete, cupom, observacoes, validade, confianca, preco_efetivo,
            chave_url or None,
        )
        if linha:
            conn.execute(
                """
                UPDATE ofertas
                SET loja = ?, tipo = ?, preco_pix = ?, preco_cartao = ?, parcelas = ?,
                    pontos_por_real = ?, pontos_por_dolar_cartao = ?,
                    percentual_bonus_transferencia = ?, valor_milheiro = ?,
                    cashback_pct = ?, frete = ?, cupom = ?, observacoes = ?,
                    validade = ?, confianca = ?, preco_efetivo = ?, url_produto = ?,
                    preco = ?, atualizada_em = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
                """,
                valores + (preco or preco_pix or preco_cartao or 0, linha["id"], USER_ID_PADRAO),
            )
            return linha["id"], False

        cursor = conn.execute(
            """
            INSERT INTO ofertas (
                produto_id, user_id, loja, tipo, preco_pix, preco_cartao, parcelas,
                pontos_por_real, pontos_por_dolar_cartao, percentual_bonus_transferencia,
                valor_milheiro, cashback_pct, frete, cupom, observacoes, validade,
                confianca, preco_efetivo, url_produto, atualizada_em
                , preco
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """,
            (produto_id, USER_ID_PADRAO) + valores + (preco or preco_pix or preco_cartao or 0,),
        )
        return cursor.lastrowid, True


def excluir_oferta(oferta_id, produto_id):
    with conexao() as conn:
        oferta = conn.execute(
            "SELECT * FROM ofertas WHERE id = ? AND produto_id = ? AND user_id = ?",
            (oferta_id, produto_id, USER_ID_PADRAO),
        ).fetchone()
        if not oferta:
            return False

        chave = _chave_oferta_automatica(oferta)
        chave_exibicao = (
            re.sub(r"\s+", " ", (oferta["loja"] or "").strip().lower()),
            round(float(oferta["preco_cartao"] or 0), 2),
            round(float(oferta["preco_efetivo"] or 0), 2),
        )
        historicos = conn.execute(
            "SELECT * FROM historico_precos WHERE produto_id = ?",
            (produto_id,),
        ).fetchall()
        for historico in historicos:
            chave_historico_exibicao = _chave_historico_exibicao(historico)
            if (
                _chave_historico(historico) == chave
                or chave_historico_exibicao == chave_exibicao
            ):
                conn.execute("DELETE FROM historico_precos WHERE id = ?", (historico["id"],))

        conn.execute(
            "DELETE FROM ofertas WHERE id = ? AND produto_id = ? AND user_id = ?",
            (oferta_id, produto_id, USER_ID_PADRAO),
        )
        return True

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
                observacoes, validade, confianca, preco_efetivo, atualizada_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                produto_id, USER_ID_PADRAO, loja, tipo, preco_pix, preco_cartao, parcelas,
                pontos_por_real, pontos_por_dolar_cartao, percentual_bonus_transferencia,
                valor_milheiro, cashback_pct, frete, cupom,
                observacoes, validade, confianca, preco_efetivo,
            ),
        )


def atualizar_oferta(oferta_id, produto_id, loja, tipo, preco_pix, preco_cartao, parcelas,
                     pontos_por_real, pontos_por_dolar_cartao, percentual_bonus_transferencia,
                     valor_milheiro, cashback_pct, frete, cupom, observacoes, validade,
                     confianca, preco_efetivo, preco=0):
    with conexao() as conn:
        anterior = conn.execute(
            "SELECT * FROM ofertas WHERE id = ? AND produto_id = ? AND user_id = ?",
            (oferta_id, produto_id, USER_ID_PADRAO),
        ).fetchone()
        if not anterior:
            return False

        nova_chave = {
            "loja": loja,
            "preco": preco or preco_pix or preco_cartao,
            "preco_pix": preco_pix,
            "preco_cartao": preco_cartao,
            "parcelas": parcelas,
        }
        conn.execute(
            """
            UPDATE ofertas
            SET loja = ?, tipo = ?, preco_pix = ?, preco_cartao = ?, parcelas = ?,
                pontos_por_real = ?, pontos_por_dolar_cartao = ?,
                percentual_bonus_transferencia = ?, valor_milheiro = ?,
                cashback_pct = ?, frete = ?, cupom = ?, observacoes = ?,
                validade = ?, confianca = ?, preco_efetivo = ?, preco = ?,
                atualizada_em = CURRENT_TIMESTAMP
            WHERE id = ? AND produto_id = ? AND user_id = ?
            """,
            (
                loja, tipo, preco_pix, preco_cartao, parcelas,
                pontos_por_real, pontos_por_dolar_cartao, percentual_bonus_transferencia,
                valor_milheiro, cashback_pct, frete, cupom, observacoes,
                validade, confianca, preco_efetivo, preco or preco_pix or preco_cartao,
                oferta_id, produto_id, USER_ID_PADRAO,
            ),
        )

        historicos = conn.execute(
            "SELECT * FROM historico_precos WHERE produto_id = ?",
            (produto_id,),
        ).fetchall()
        chave_anterior = _chave_oferta_automatica(anterior)
        exibicao_anterior = (
            re.sub(r"\s+", " ", (anterior["loja"] or "").strip().lower()),
            round(float(anterior["preco_cartao"] or 0), 2),
            round(float(anterior["preco_efetivo"] or 0), 2),
        )
        for historico in historicos:
            chave_historico = _chave_historico(historico)
            exibicao_historico = _chave_historico_exibicao(historico)
            if chave_historico != chave_anterior and exibicao_historico != exibicao_anterior:
                continue
            conn.execute(
                """
                UPDATE historico_precos
                SET loja = ?, preco_anunciado = ?, preco_efetivo = ?,
                    preco = ?, preco_pix = ?, preco_cartao = ?, parcelas = ?
                WHERE id = ? AND produto_id = ?
                """,
                (
                    loja, preco_cartao, preco_efetivo,
                    preco or preco_pix or preco_cartao, preco_pix, preco_cartao,
                    parcelas or 1, historico["id"], produto_id,
                ),
            )
        return True


# historico de precos

def _chave_historico(linha):
    preco = linha["preco"] or linha["preco_pix"] or linha["preco_cartao"] or linha["preco_anunciado"] or 0
    return (
        re.sub(r"\s+", " ", (linha["loja"] or "").strip().lower()),
        round(float(preco), 2),
        round(float(linha["preco_pix"] or linha["preco_anunciado"] or 0), 2),
        round(float(linha["preco_cartao"] or linha["preco_anunciado"] or 0), 2),
        int(linha["parcelas"] or 1),
    )


def _chave_historico_exibicao(linha):
    return (
        re.sub(r"\s+", " ", (linha["loja"] or "").strip().lower()),
        round(float(linha["preco_anunciado"] or 0), 2),
        round(float(linha["preco_pix"] or linha["preco_anunciado"] or 0), 2),
        round(float(linha["preco_efetivo"] or 0), 2),
    )


def _consolidar_historico(conn):
    linhas = conn.execute(
        "SELECT * FROM historico_precos ORDER BY registrado_em, id"
    ).fetchall()
    mantidas = {}
    for linha in linhas:
        chave = (linha["produto_id"], _chave_historico_exibicao(linha))
        anterior = mantidas.get(chave)
        if anterior is None:
            mantidas[chave] = linha
            continue
        conn.execute(
            """
            UPDATE historico_precos
            SET registrado_em = COALESCE(?, registrado_em)
            WHERE id = ?
            """,
            (linha["registrado_em"], anterior["id"]),
        )
        conn.execute("DELETE FROM historico_precos WHERE id = ?", (linha["id"],))


def _preencher_historico_das_ofertas(conn):
    ofertas = conn.execute(
        "SELECT * FROM ofertas WHERE user_id = ? ORDER BY criado_em, id",
        (USER_ID_PADRAO,),
    ).fetchall()
    historicos = conn.execute("SELECT * FROM historico_precos").fetchall()
    chaves_existentes = {
        (linha["produto_id"], linha["registrado_em"][:10], _chave_historico_exibicao(linha))
        for linha in historicos
    }
    for oferta in ofertas:
        preco_anunciado = oferta["preco_cartao"] or oferta["preco_pix"] or 0
        registro = {
            "loja": oferta["loja"],
            "preco_anunciado": preco_anunciado,
            "preco_pix": oferta["preco_pix"] or preco_anunciado,
            "preco_efetivo": oferta["preco_efetivo"],
        }
        chave = (
            oferta["produto_id"],
            (oferta["criado_em"] or oferta["atualizada_em"] or "")[:10],
            _chave_historico_exibicao(registro),
        )
        if chave in chaves_existentes:
            continue
        conn.execute(
            """
            INSERT INTO historico_precos (
                produto_id, loja, preco_anunciado, preco_efetivo,
                registrado_em, preco, preco_pix, preco_cartao, parcelas
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                oferta["produto_id"], oferta["loja"], preco_anunciado,
                oferta["preco_efetivo"], oferta["criado_em"] or oferta["atualizada_em"],
                oferta["preco"] or oferta["preco_pix"] or preco_anunciado,
                oferta["preco_pix"] or preco_anunciado,
                oferta["preco_cartao"] or preco_anunciado,
                oferta["parcelas"] or 1,
            ),
        )
        chaves_existentes.add(chave)


def registrar_historico(produto_id, loja, preco_anunciado, preco_efetivo,
                        preco=0, preco_pix=0, preco_cartao=0, parcelas=1):
    with conexao() as conn:
        chave = _chave_historico_exibicao({
            "loja": loja,
            "preco_anunciado": preco_anunciado,
            "preco_pix": preco_pix or preco_anunciado,
            "preco_efetivo": preco_efetivo,
        })
        existentes = conn.execute(
            "SELECT * FROM historico_precos WHERE produto_id = ?",
            (produto_id,),
        ).fetchall()
        if any(_chave_historico_exibicao(linha) == chave for linha in existentes):
            linha = next(linha for linha in existentes if _chave_historico_exibicao(linha) == chave)
            conn.execute(
                "UPDATE historico_precos SET registrado_em = CURRENT_TIMESTAMP WHERE id = ?",
                (linha["id"],),
            )
            return False
        conn.execute(
            """
            INSERT INTO historico_precos (
                produto_id, loja, preco_anunciado, preco_efetivo,
                preco, preco_pix, preco_cartao, parcelas
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (produto_id, loja, preco_anunciado, preco_efetivo,
             preco or preco_anunciado, preco_pix or preco_anunciado,
             preco_cartao or preco_anunciado, parcelas or 1),
        )
        return True


def listar_historico(produto_id):
    with conexao() as conn:
        linhas = conn.execute(
            "SELECT * FROM historico_precos WHERE produto_id = ? ORDER BY registrado_em",
            (produto_id,),
        ).fetchall()
        unicas = {}
        for linha in linhas:
            registro = dict(linha)
            chave = _chave_historico_exibicao(registro)
            unicas.setdefault(chave, registro)
        return list(unicas.values())


def encontrar_oferta_do_historico(registro_id, produto_id):
    with conexao() as conn:
        historico = conn.execute(
            "SELECT * FROM historico_precos WHERE id = ? AND produto_id = ?",
            (registro_id, produto_id),
        ).fetchone()
        if not historico:
            return None
        chave = _chave_historico(historico)
        chave_exibicao = _chave_historico_exibicao(historico)
        ofertas = conn.execute(
            "SELECT * FROM ofertas WHERE produto_id = ? AND user_id = ?",
            (produto_id, USER_ID_PADRAO),
        ).fetchall()
        for oferta in ofertas:
            exibicao = (
                re.sub(r"\s+", " ", (oferta["loja"] or "").strip().lower()),
                round(float(oferta["preco_cartao"] or 0), 2),
                round(float(oferta["preco_pix"] or oferta["preco_cartao"] or 0), 2),
                round(float(oferta["preco_efetivo"] or 0), 2),
            )
            if _chave_oferta_automatica(oferta) == chave or exibicao == chave_exibicao:
                return dict(oferta)
        return None


def excluir_historico(registro_id, produto_id):
    with conexao() as conn:
        registro = conn.execute(
            "SELECT * FROM historico_precos WHERE id = ? AND produto_id = ?",
            (registro_id, produto_id),
        ).fetchone()
        if not registro:
            return False

        chave = _chave_historico(registro)
        chave_exibicao = _chave_historico_exibicao(registro)
        ofertas = conn.execute(
            "SELECT * FROM ofertas WHERE produto_id = ? AND user_id = ?",
            (produto_id, USER_ID_PADRAO),
        ).fetchall()
        for oferta in ofertas:
            chave_oferta_exibicao = (
                re.sub(r"\s+", " ", (oferta["loja"] or "").strip().lower()),
                round(float(oferta["preco_cartao"] or 0), 2),
                round(float(oferta["preco_pix"] or oferta["preco_cartao"] or 0), 2),
                round(float(oferta["preco_efetivo"] or 0), 2),
            )
            if (
                _chave_oferta_automatica(oferta) == chave
                or chave_oferta_exibicao == chave_exibicao
            ):
                conn.execute("DELETE FROM ofertas WHERE id = ?", (oferta["id"],))

        conn.execute(
            "DELETE FROM historico_precos WHERE id = ? AND produto_id = ?",
            (registro_id, produto_id),
        )
        return True


# livelo parceiros (compatibilidade)

def listar_parceiros_livelo():
    """
    Retorna a lista de parceiros Livelo/Esfera carregada a partir de um
    arquivo ao lado do módulo (livelo_parceiros.json ou livelo_parceiros.html).

    Cada parceiro é um dict com as chaves 'nome', 'alias' e
    'pontos_padrao' (float). Se o arquivo não existir, retorna lista vazia.
    """
    base = Path(__file__).parent
    html_path = base / "livelo_parceiros.html"
    json_paths = [base / "livelo_parceiros.json"]
    debug_dir = base.parent / "debug_output"
    json_paths.extend(sorted(
        debug_dir.glob("livelo_teste_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ))

    for json_path in json_paths:
        if not json_path.exists():
            continue
        try:
            with json_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            parceiros = []
            for p in data:
                nome = str(p.get("nome", "")).strip()
                alias = str(p.get("alias", "") or nome).strip()
                try:
                    pontos = float(p.get("pontos_padrao", 0.0))
                except Exception:
                    pontos = 0.0
                if nome:
                    parceiros.append({"nome": nome, "alias": alias, "pontos_padrao": pontos})
            return parceiros
        except Exception:
            continue

    if html_path.exists():
        text = html_path.read_text(encoding="utf-8")
        parceiros = []
        # tenta extrair linhas com nome e um numero (pontos) por heurística
        for line in text.splitlines():
            clean = re.sub(r"<[^>]+>", "", line).strip()
            if not clean:
                continue
            m = re.match(r"^(?P<n>.+?)[\s–\-—:]+(?P<p>[\d.,]+)\s*$", clean)
            if m:
                nome = m.group("n").strip()
                try:
                    pontos = float(m.group("p").replace(",", "."))
                except Exception:
                    pontos = 0.0
            else:
                nome = clean
                pontos = 0.0
            if nome:
                parceiros.append({"nome": nome, "alias": nome, "pontos_padrao": pontos})
        return parceiros

    return []


def buscar_parceiro_livelo_por_nome(nome_loja):
    """
    Procura um parceiro cujo nome case com a loja informada. A comparação
    é feita em lowercase e aceita correspondências parciais.

    Retorna o dicionário do parceiro ou None se não encontrado.
    """
    if not nome_loja:
        return None
    candidatos = listar_parceiros_livelo()
    alvo = nome_loja.strip().lower()

    # primeiro tenta correspondência exata ou contida no nome ou alias
    for p in candidatos:
        nome_p = p.get("nome", "").strip().lower()
        alias_p = str(p.get("alias") or p.get("nome", "")).strip().lower()
        if not nome_p and not alias_p:
            continue
        if (
            nome_p == alvo
            or nome_p in alvo
            or alvo in nome_p
            or alvo in alias_p
            or alias_p in alvo
        ):
            return p

    # fallback: tenta tokenização simples (palavras em comum)
    alvo_tokens = set(re.findall(r"\w+", alvo))
    best = None
    best_score = 0
    for p in candidatos:
        nome_p = p.get("nome", "").strip().lower()
        alias_p = str(p.get("alias") or p.get("nome", "")).strip().lower()
        tokens = set(re.findall(r"\w+", f"{nome_p} {alias_p}"))
        score = len(alvo_tokens & tokens)
        if score > best_score:
            best_score = score
            best = p
    if best_score > 0:
        return best

    return None