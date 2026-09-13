"""
camada de acesso ao banco sqlite do assistente de compras.

todas as tabelas ja possuem a coluna user_id, mesmo que hoje so exista um unico usuario local, justamente para facilitar uma eventual migracao para um servico multiusuario na nuvem no futuro.

sobre migracao de esquema, como o banco ja existe no disco de quem ja usava o app antes, nao da pra so mudar o CREATE TABLE, ele so roda na primeira vez. por isso, colunas novas sao adicionadas com ALTER TABLE dentro de _migrar_colunas_novas, ignorando o erro quando a coluna ja existe.

sobre a tabela livelo_parceiros, o cadastro e manual, feito uma vez por parceiro, com o nome exatamente como ele costuma aparecer nos resultados do buscape, mais um alias opcional para apelidos do mesmo grupo, tipo "magalu" para "magazine luiza". a pesquisa automatica em services/pesquisa_produto.py usa buscar_parceiro_livelo_por_nome para casar cada loja encontrada com esse cadastro. o casamento em si, que reconhece tanto substring simples quanto apelidos de mercado conhecidos, tipo "magalu" para "magazine luiza", mora em services/casamento_lojas.py, ver esse modulo para os detalhes.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from services.casamento_lojas import encontrar_parceiro_equivalente

CAMINHO_BANCO = Path(__file__).parent / "shopping.db"

USER_ID_PADRAO = 1

VALOR_MILHEIRO_PADRAO = 30.0
PONTOS_DOLAR_CARTAO_PADRAO = 3.0
BONUS_TRANSFERENCIA_PADRAO = 80.0
PARCELAS_PADRAO = 6


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
    tenta adicionar uma coluna nova numa tabela ja existente, e ignora o erro caso a coluna ja tenha sido criada numa execucao anterior. e assim que o sqlite migra esquema em bancos que ja estao em uso.
    """
    try:
        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {definicao_coluna}")
    except sqlite3.OperationalError as erro:
        if "duplicate column name" not in str(erro).lower():
            raise


def _renomear_coluna_se_necessario(conn, tabela, coluna_antiga, coluna_nova):
    """
    tenta renomear uma coluna existente, e ignora o erro quando a coluna antiga ja nao existe mais, seja porque o banco e novo, seja porque a renomeacao ja rodou numa execucao anterior. usado para corrigir o nome da coluna de "cdi_mensal" para "rendimento_mensal", ja que o valor nunca foi de fato o cdi, e sim o rendimento mensal liquido informado pelo usuario.
    """
    try:
        conn.execute(f"ALTER TABLE {tabela} RENAME COLUMN {coluna_antiga} TO {coluna_nova}")
    except sqlite3.OperationalError as erro:
        mensagem = str(erro).lower()
        if "no such column" not in mensagem and "duplicate column name" not in mensagem:
            raise


def _migrar_colunas_novas(conn):
    _renomear_coluna_se_necessario(conn, "user_settings", "cdi_mensal", "rendimento_mensal")
    _adicionar_coluna_se_nao_existir(
        conn, "user_settings", f"valor_milheiro_padrao REAL NOT NULL DEFAULT {VALOR_MILHEIRO_PADRAO}",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "user_settings", f"pontos_dolar_cartao_padrao REAL NOT NULL DEFAULT {PONTOS_DOLAR_CARTAO_PADRAO}",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "user_settings",
        f"percentual_bonus_transferencia_padrao REAL NOT NULL DEFAULT {BONUS_TRANSFERENCIA_PADRAO}",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "user_settings", f"parcelas_padrao INTEGER NOT NULL DEFAULT {PARCELAS_PADRAO}",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "ofertas", "pontos_por_dolar_cartao REAL NOT NULL DEFAULT 0",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "ofertas", "logo_url TEXT",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "ofertas", "percentual_bonus_transferencia REAL NOT NULL DEFAULT 0",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "ofertas", "valor_milheiro REAL NOT NULL DEFAULT 0",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "ofertas", "preco REAL NOT NULL DEFAULT 0",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "ofertas", "url_produto TEXT",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "ofertas", "atualizada_em TEXT",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "historico_precos", "preco REAL",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "historico_precos", "preco_pix REAL",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "historico_precos", "preco_cartao REAL",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "historico_precos", "parcelas INTEGER",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "historico_precos", "oferta_id INTEGER",
    )
    _adicionar_coluna_se_nao_existir(
        conn, "livelo_parceiros", "alias TEXT NOT NULL DEFAULT ''",
    )


def inicializar_banco():
    with conexao() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                rendimento_mensal REAL NOT NULL DEFAULT 1.1,
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

            CREATE TABLE IF NOT EXISTS livelo_parceiros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
                nome TEXT NOT NULL,
                alias TEXT NOT NULL DEFAULT '',
                pontos_padrao REAL NOT NULL DEFAULT 0,
                atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, nome)
            );
            """
        )

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


def salvar_configuracoes(rendimento_mensal, cotacao_dolar, valor_milheiro_padrao,
                          percentual_bonus_transferencia_padrao, parcelas_padrao):
    """
    salva o perfil financeiro. o campo de pontos por dolar padrao do cartao nao entra mais aqui, porque cada cartao cadastrado ja tem sua propria taxa de pontos por dolar, um padrao global so duplicava essa informacao sem servir pra nada. percentual_bonus_transferencia_padrao e parcelas_padrao sao os valores usados pela pesquisa automatica quando o buscape nao confirma um parcelamento proprio da loja, ver services/pesquisa_produto.py.
    """
    with conexao() as conn:
        conn.execute(
            """
            UPDATE user_settings
            SET rendimento_mensal = ?, cotacao_dolar = ?, valor_milheiro_padrao = ?,
                percentual_bonus_transferencia_padrao = ?, parcelas_padrao = ?,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (
                rendimento_mensal, cotacao_dolar, valor_milheiro_padrao,
                percentual_bonus_transferencia_padrao, parcelas_padrao, USER_ID_PADRAO,
            ),
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


def atualizar_produto(produto_id, nome, categoria, orcamento, preco_alvo):
    with conexao() as conn:
        cursor = conn.execute(
            """
            UPDATE produtos SET nome = ?, categoria = ?, orcamento = ?, preco_alvo = ?
            WHERE id = ? AND user_id = ?
            """,
            (nome, categoria, orcamento, preco_alvo, produto_id, USER_ID_PADRAO),
        )
        return cursor.rowcount > 0


def atualizar_status_produto(produto_id, status):
    with conexao() as conn:
        conn.execute(
            "UPDATE produtos SET status = ? WHERE id = ? AND user_id = ?",
            (status, produto_id, USER_ID_PADRAO),
        )


def excluir_produto(produto_id):
    """
    remove o produto e tudo que depende dele, as ofertas cadastradas e o historico de precos, para nao deixar linha orfa no banco.
    """
    with conexao() as conn:
        produto = conn.execute(
            "SELECT id FROM produtos WHERE id = ? AND user_id = ?", (produto_id, USER_ID_PADRAO),
        ).fetchone()
        if not produto:
            return False
        conn.execute("DELETE FROM historico_precos WHERE produto_id = ?", (produto_id,))
        conn.execute("DELETE FROM ofertas WHERE produto_id = ?", (produto_id,))
        conn.execute("DELETE FROM produtos WHERE id = ? AND user_id = ?", (produto_id, USER_ID_PADRAO))
        return True


# ofertas

def listar_ofertas_por_produto(produto_id):
    with conexao() as conn:
        linhas = conn.execute(
            "SELECT * FROM ofertas WHERE produto_id = ? ORDER BY criado_em DESC", (produto_id,)
        ).fetchall()
        return [dict(linha) for linha in linhas]


def _inserir_oferta(conn, produto_id, loja, tipo, preco_pix, preco_cartao, parcelas, pontos_por_real, pontos_por_dolar_cartao, percentual_bonus_transferencia, valor_milheiro, cashback_pct, frete, cupom, observacoes, validade, confianca, preco_efetivo, preco, url_produto, logo_url=""):
    cursor = conn.execute(
        """
        INSERT INTO ofertas (
            produto_id, user_id, loja, tipo, preco_pix, preco_cartao, parcelas,
            pontos_por_real, pontos_por_dolar_cartao, percentual_bonus_transferencia,
            valor_milheiro, cashback_pct, frete, cupom,
            observacoes, validade, confianca, preco_efetivo, preco, url_produto, logo_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            produto_id, USER_ID_PADRAO, loja, tipo, preco_pix, preco_cartao, parcelas,
            pontos_por_real, pontos_por_dolar_cartao, percentual_bonus_transferencia,
            valor_milheiro, cashback_pct, frete, cupom,
            observacoes, validade, confianca, preco_efetivo, preco, url_produto, logo_url,
        ),
    )
    return cursor.lastrowid


def adicionar_oferta(produto_id, loja, tipo, preco_pix, preco_cartao, parcelas, pontos_por_real, pontos_por_dolar_cartao, percentual_bonus_transferencia, valor_milheiro, cashback_pct, frete, cupom, observacoes, validade, confianca, preco_efetivo, preco=0.0, url_produto="", logo_url=""):
    """
    cadastra uma oferta a mao, tipicamente vinda do formulario manual da calculadora. devolve o id da linha criada, para o chamador poder linkar essa oferta a um registro de historico. logo_url fica vazia por padrao, ja que o formulario manual nao pesquisa nenhum parceiro Livelo, so a pesquisa automatica preenche esse campo.
    """
    with conexao() as conn:
        return _inserir_oferta(
            conn, produto_id, loja, tipo, preco_pix, preco_cartao, parcelas,
            pontos_por_real, pontos_por_dolar_cartao, percentual_bonus_transferencia,
            valor_milheiro, cashback_pct, frete, cupom, observacoes, validade,
            confianca, preco_efetivo, preco, url_produto, logo_url,
        )


def registrar_oferta_pesquisa(produto_id, loja, tipo, preco_pix, preco_cartao, preco, parcelas, pontos_por_real, pontos_por_dolar_cartao, percentual_bonus_transferencia, valor_milheiro, cashback_pct, frete, cupom, observacoes, validade, confianca, preco_efetivo, url_produto, logo_url=""):
    """
    cadastra uma oferta encontrada pela pesquisa automatica no buscape, mesma tabela da oferta manual, so que sempre com preco e url_produto preenchidos. devolve o id da linha criada. logo_url vem do parceiro Livelo casado pela propria pesquisa, ver services/pesquisa_produto.py, e fica vazia quando nenhum parceiro casar.
    """
    with conexao() as conn:
        return _inserir_oferta(
            conn, produto_id, loja, tipo, preco_pix, preco_cartao, parcelas,
            pontos_por_real, pontos_por_dolar_cartao, percentual_bonus_transferencia,
            valor_milheiro, cashback_pct, frete, cupom, observacoes, validade,
            confianca, preco_efetivo, preco, url_produto, logo_url,
        )


def atualizar_oferta(oferta_id, produto_id, loja, tipo, preco_pix, preco_cartao, parcelas, pontos_por_real, pontos_por_dolar_cartao, percentual_bonus_transferencia, valor_milheiro, cashback_pct, frete, cupom, observacoes, validade, confianca, preco_efetivo, preco=0.0):
    """
    atualiza uma oferta existente com os dados do formulario manual de edicao. logo_url nao entra nesta atualizacao de proposito, o formulario manual nao pesquisa parceiro nenhum, entao uma logo ja gravada por uma pesquisa automatica anterior continua valendo depois da edicao.
    """
    with conexao() as conn:
        cursor = conn.execute(
            """
            UPDATE ofertas
            SET loja = ?, tipo = ?, preco_pix = ?, preco_cartao = ?, parcelas = ?,
                pontos_por_real = ?, pontos_por_dolar_cartao = ?,
                percentual_bonus_transferencia = ?, valor_milheiro = ?,
                cashback_pct = ?, frete = ?, cupom = ?, observacoes = ?,
                validade = ?, confianca = ?, preco_efetivo = ?, preco = ?,
                atualizada_em = CURRENT_TIMESTAMP
            WHERE id = ? AND produto_id = ?
            """,
            (
                loja, tipo, preco_pix, preco_cartao, parcelas, pontos_por_real,
                pontos_por_dolar_cartao, percentual_bonus_transferencia, valor_milheiro,
                cashback_pct, frete, cupom, observacoes, validade, confianca,
                preco_efetivo, preco, oferta_id, produto_id,
            ),
        )
        return cursor.rowcount > 0


def excluir_oferta(oferta_id, produto_id):
    with conexao() as conn:
        cursor = conn.execute(
            "DELETE FROM ofertas WHERE id = ? AND produto_id = ?", (oferta_id, produto_id),
        )
        return cursor.rowcount > 0


# historico de precos

def registrar_historico(produto_id, loja, preco_anunciado, preco_efetivo, preco=None, preco_pix=None, preco_cartao=None, parcelas=None, oferta_id=None):
    with conexao() as conn:
        cursor = conn.execute(
            """
            INSERT INTO historico_precos (
                produto_id, loja, preco_anunciado, preco_efetivo,
                preco, preco_pix, preco_cartao, parcelas, oferta_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (produto_id, loja, preco_anunciado, preco_efetivo, preco, preco_pix, preco_cartao, parcelas, oferta_id),
        )
        return cursor.lastrowid


def listar_historico(produto_id):
    with conexao() as conn:
        linhas = conn.execute(
            "SELECT * FROM historico_precos WHERE produto_id = ? ORDER BY registrado_em",
            (produto_id,),
        ).fetchall()
        return [dict(linha) for linha in linhas]


def excluir_historico(registro_id, produto_id):
    with conexao() as conn:
        cursor = conn.execute(
            "DELETE FROM historico_precos WHERE id = ? AND produto_id = ?",
            (registro_id, produto_id),
        )
        return cursor.rowcount > 0


def encontrar_oferta_do_historico(registro_id, produto_id):
    """
    devolve a oferta ligada a um registro de historico, para o front poder abrir direto a edicao daquela oferta na calculadora.

    quando o registro tem oferta_id preenchido, o vinculo e direto. registros mais antigos, criados antes dessa coluna existir, caem de volta para um casamento por loja, escolhendo entre as ofertas daquela loja a que tiver o preco efetivo mais proximo do que foi salvo no historico.
    """
    with conexao() as conn:
        historico = conn.execute(
            "SELECT * FROM historico_precos WHERE id = ? AND produto_id = ?",
            (registro_id, produto_id),
        ).fetchone()
        if not historico:
            return None
        historico = dict(historico)

        if historico.get("oferta_id"):
            linha = conn.execute(
                "SELECT * FROM ofertas WHERE id = ? AND produto_id = ?",
                (historico["oferta_id"], produto_id),
            ).fetchone()
            if linha:
                return dict(linha)

        candidatas = conn.execute(
            "SELECT * FROM ofertas WHERE produto_id = ? AND loja = ? ORDER BY criado_em DESC",
            (produto_id, historico["loja"]),
        ).fetchall()
        candidatas = [dict(linha) for linha in candidatas]
        if not candidatas:
            return None

        preco_efetivo_historico = historico.get("preco_efetivo")
        if preco_efetivo_historico is not None:
            candidatas.sort(
                key=lambda linha: abs((linha["preco_efetivo"] or 0) - preco_efetivo_historico)
            )
        return candidatas[0]


# parceiros livelo ou esfera, cadastro manual
# cadastrado uma vez por parceiro, com o nome exatamente como ele aparece nos resultados do buscape. o alias e opcional, util para apelidos do mesmo grupo que a pesquisa automatica tambem deve reconhecer, tipo "magalu" para "magazine luiza".

def listar_parceiros_livelo():
    with conexao() as conn:
        linhas = conn.execute(
            "SELECT * FROM livelo_parceiros WHERE user_id = ? ORDER BY nome", (USER_ID_PADRAO,)
        ).fetchall()
        return [dict(linha) for linha in linhas]


def adicionar_parceiro_livelo_manual(nome, pontos_padrao, alias=""):
    """
    cadastra ou atualiza, pelo nome, um parceiro Livelo ou Esfera com a taxa de pontos por real informada a mao.
    """
    with conexao() as conn:
        conn.execute(
            """
            INSERT INTO livelo_parceiros (user_id, nome, alias, pontos_padrao, atualizado_em)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, nome) DO UPDATE SET
                alias = excluded.alias,
                pontos_padrao = excluded.pontos_padrao,
                atualizado_em = CURRENT_TIMESTAMP
            """,
            (USER_ID_PADRAO, nome.strip(), alias.strip(), pontos_padrao),
        )


def salvar_parceiros_livelo(parceiros):
    """
    cadastra ou atualiza varios parceiros de uma vez, aceitando tanto dicts quanto objetos com atributos nome, alias e pontos_padrao.
    """
    for parceiro in parceiros:
        if isinstance(parceiro, dict):
            nome = parceiro["nome"]
            alias = parceiro.get("alias", "")
            pontos_padrao = parceiro["pontos_padrao"]
        else:
            nome = parceiro.nome
            alias = getattr(parceiro, "alias", "")
            pontos_padrao = parceiro.pontos_padrao
        adicionar_parceiro_livelo_manual(nome, pontos_padrao, alias)


def remover_parceiro_livelo(parceiro_id):
    with conexao() as conn:
        conn.execute(
            "DELETE FROM livelo_parceiros WHERE id = ? AND user_id = ?",
            (parceiro_id, USER_ID_PADRAO),
        )


def buscar_parceiro_livelo_por_nome(termo):
    """
    procura, entre os parceiros cadastrados, aquele cujo nome ou alias mais se aproxima do termo informado, tipicamente o nome de uma loja encontrado na pesquisa automatica do buscape.

    o casamento em si acontece em services.casamento_lojas.encontrar_parceiro_equivalente, que reconhece tanto substring simples, o suficiente para nomes como "fast shop" e "fast shop oficial", quanto grupos de apelidos de mercado conhecidos, tipo "magalu" para "magazine luiza", mesmo sem um alias cadastrado a mao para esse parceiro especifico. devolve o primeiro parceiro que bater, ou none quando nenhum casar.
    """
    if not termo or not termo.strip():
        return None

    return encontrar_parceiro_equivalente(termo, listar_parceiros_livelo())