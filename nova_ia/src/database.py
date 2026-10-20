import os
import sys
import sqlite3

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.path.join(BASE_DIR, "nova.db")

def conectar():
    return sqlite3.connect(DB_FILE)

def inicializar():
    with conectar() as con:

        # conversas
        con.execute("""
            CREATE TABLE IF NOT EXISTS conversas (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                sessao_id INTEGER NOT NULL DEFAULT 1,
                role      TEXT NOT NULL,
                conteudo  TEXT NOT NULL,
                data      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # sessões de conversa
        con.execute("""
            CREATE TABLE IF NOT EXISTS sessoes (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo    TEXT NOT NULL DEFAULT 'Nova conversa',
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # projetos
        con.execute("""
            CREATE TABLE IF NOT EXISTS projetos (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                nome      TEXT NOT NULL,
                cor       TEXT NOT NULL DEFAULT '#7c6fff',
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # tarefas
        con.execute("""
            CREATE TABLE IF NOT EXISTS tarefas (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                projeto_id  INTEGER REFERENCES projetos(id) ON DELETE SET NULL,
                titulo      TEXT NOT NULL,
                descricao   TEXT,
                prioridade  TEXT NOT NULL DEFAULT 'media',
                status      TEXT NOT NULL DEFAULT 'pendente',
                prazo       TIMESTAMP,
                criado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                concluido_em TIMESTAMP
            )
        """)

        # lembretes
        con.execute("""
            CREATE TABLE IF NOT EXISTS lembretes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo      TEXT NOT NULL,
                descricao   TEXT,
                data_hora   TIMESTAMP NOT NULL,
                repetir     TEXT NOT NULL DEFAULT 'nunca',
                ativo       INTEGER NOT NULL DEFAULT 1,
                disparado   INTEGER NOT NULL DEFAULT 0,
                criado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # sessões de foco
        con.execute("""
            CREATE TABLE IF NOT EXISTS sessoes_foco (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                duracao_min INTEGER NOT NULL DEFAULT 25,
                pausa_min   INTEGER NOT NULL DEFAULT 5,
                concluido   INTEGER NOT NULL DEFAULT 0,
                data        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # hábitos
        con.execute("""
            CREATE TABLE IF NOT EXISTS habitos (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                nome      TEXT NOT NULL,
                icone     TEXT NOT NULL DEFAULT '',
                cor       TEXT NOT NULL DEFAULT '#7c6fff',
                ativo     INTEGER NOT NULL DEFAULT 1,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # registros de hábitos
        con.execute("""
            CREATE TABLE IF NOT EXISTS registros_habitos (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                habito_id INTEGER NOT NULL REFERENCES habitos(id) ON DELETE CASCADE,
                data      DATE NOT NULL,
                UNIQUE(habito_id, data)
            )
        """)


# conversas


def criar_sessao(titulo: str = "Nova conversa") -> int:
    with conectar() as con:
        cur = con.execute("INSERT INTO sessoes (titulo) VALUES (?)", (titulo,))
        return cur.lastrowid

def listar_sessoes() -> list:
    with conectar() as con:
        rows = con.execute("""
            SELECT s.id, s.titulo, s.criado_em,
                   COUNT(c.id) as total
            FROM sessoes s
            LEFT JOIN conversas c ON c.sessao_id = s.id
            GROUP BY s.id
            ORDER BY s.criado_em DESC
        """).fetchall()
    return [{"id": r[0], "titulo": r[1], "criado_em": r[2], "total": r[3]} for r in rows]

def renomear_sessao(sessao_id: int, titulo: str):
    with conectar() as con:
        con.execute("UPDATE sessoes SET titulo = ? WHERE id = ?", (titulo, sessao_id))

def deletar_sessao(sessao_id: int):
    with conectar() as con:
        con.execute("DELETE FROM conversas WHERE sessao_id = ?", (sessao_id,))
        con.execute("DELETE FROM sessoes WHERE id = ?", (sessao_id,))

def salvar_mensagem(sessao_id: int, role: str, conteudo: str):
    with conectar() as con:
        con.execute(
            "INSERT INTO conversas (sessao_id, role, conteudo) VALUES (?, ?, ?)",
            (sessao_id, role, conteudo)
        )

def carregar_historico(sessao_id: int, limite: int = 30) -> list:
    with conectar() as con:
        rows = con.execute("""
            SELECT role, conteudo FROM conversas
            WHERE sessao_id = ?
            ORDER BY id DESC LIMIT ?
        """, (sessao_id, limite)).fetchall()
    return [{"role": r, "content": c} for r, c in reversed(rows)]

def limpar_historico(sessao_id: int):
    with conectar() as con:
        con.execute("DELETE FROM conversas WHERE sessao_id = ?", (sessao_id,))


# projetos


def criar_projeto(nome: str, cor: str = "#7c6fff") -> int:
    with conectar() as con:
        cur = con.execute("INSERT INTO projetos (nome, cor) VALUES (?, ?)", (nome, cor))
        return cur.lastrowid

def listar_projetos() -> list:
    with conectar() as con:
        rows = con.execute("""
            SELECT p.id, p.nome, p.cor,
                   COUNT(t.id) as total,
                   SUM(CASE WHEN t.status = 'concluida' THEN 1 ELSE 0 END) as concluidas
            FROM projetos p
            LEFT JOIN tarefas t ON t.projeto_id = p.id
            GROUP BY p.id
            ORDER BY p.criado_em DESC
        """).fetchall()
    return [{"id": r[0], "nome": r[1], "cor": r[2], "total": r[3], "concluidas": r[4]} for r in rows]

def deletar_projeto(projeto_id: int):
    with conectar() as con:
        con.execute("DELETE FROM projetos WHERE id = ?", (projeto_id,))


# tarefas


def criar_tarefa(titulo: str, descricao: str = "", projeto_id: int = None,
                 prioridade: str = "media", prazo: str = None) -> int:
    with conectar() as con:
        cur = con.execute("""
            INSERT INTO tarefas (titulo, descricao, projeto_id, prioridade, prazo)
            VALUES (?, ?, ?, ?, ?)
        """, (titulo, descricao, projeto_id, prioridade, prazo))
        return cur.lastrowid

def listar_tarefas(projeto_id: int = None, status: str = None) -> list:
    query = """
        SELECT t.id, t.titulo, t.descricao, t.prioridade, t.status,
               t.prazo, t.criado_em, t.concluido_em,
               p.nome as projeto, p.cor
        FROM tarefas t
        LEFT JOIN projetos p ON p.id = t.projeto_id
        WHERE 1=1
    """
    params = []
    if projeto_id:
        query += " AND t.projeto_id = ?"
        params.append(projeto_id)
    if status:
        query += " AND t.status = ?"
        params.append(status)
    query += " ORDER BY t.criado_em DESC"

    with conectar() as con:
        rows = con.execute(query, params).fetchall()
    return [{
        "id": r[0], "titulo": r[1], "descricao": r[2], "prioridade": r[3],
        "status": r[4], "prazo": r[5], "criado_em": r[6], "concluido_em": r[7],
        "projeto": r[8], "cor_projeto": r[9]
    } for r in rows]

def concluir_tarefa(tarefa_id: int):
    with conectar() as con:
        con.execute("""
            UPDATE tarefas SET status = 'concluida',
            concluido_em = CURRENT_TIMESTAMP WHERE id = ?
        """, (tarefa_id,))

def deletar_tarefa(tarefa_id: int):
    with conectar() as con:
        con.execute("DELETE FROM tarefas WHERE id = ?", (tarefa_id,))


# lembretes


def criar_lembrete(titulo: str, data_hora: str, descricao: str = "",
                   repetir: str = "nunca") -> int:
    with conectar() as con:
        cur = con.execute("""
            INSERT INTO lembretes (titulo, descricao, data_hora, repetir)
            VALUES (?, ?, ?, ?)
        """, (titulo, descricao, data_hora, repetir))
        return cur.lastrowid

def listar_lembretes(apenas_ativos: bool = True) -> list:
    query = "SELECT id, titulo, descricao, data_hora, repetir, ativo, disparado FROM lembretes"
    if apenas_ativos:
        query += " WHERE ativo = 1"
    query += " ORDER BY data_hora ASC"
    with conectar() as con:
        rows = con.execute(query).fetchall()
    return [{
        "id": r[0], "titulo": r[1], "descricao": r[2],
        "data_hora": r[3], "repetir": r[4], "ativo": r[5], "disparado": r[6]
    } for r in rows]

def marcar_lembrete_disparado(lembrete_id: int):
    with conectar() as con:
        con.execute("UPDATE lembretes SET disparado = 1 WHERE id = ?", (lembrete_id,))

def deletar_lembrete(lembrete_id: int):
    with conectar() as con:
        con.execute("DELETE FROM lembretes WHERE id = ?", (lembrete_id,))


# sessões de foco


def salvar_sessao_foco(duracao_min: int, pausa_min: int, concluido: bool):
    with conectar() as con:
        con.execute("""
            INSERT INTO sessoes_foco (duracao_min, pausa_min, concluido)
            VALUES (?, ?, ?)
        """, (duracao_min, pausa_min, int(concluido)))

def stats_foco_hoje() -> dict:
    with conectar() as con:
        row = con.execute("""
            SELECT COUNT(*), SUM(duracao_min)
            FROM sessoes_foco
            WHERE DATE(data) = DATE('now') AND concluido = 1
        """).fetchone()
    return {"sessoes": row[0] or 0, "minutos": row[1] or 0}


# hábitos


def criar_habito(nome: str, icone: str = "", cor: str = "#7c6fff") -> int:
    with conectar() as con:
        cur = con.execute(
            "INSERT INTO habitos (nome, icone, cor) VALUES (?, ?, ?)",
            (nome, icone, cor)
        )
        return cur.lastrowid

def listar_habitos() -> list:
    with conectar() as con:
        rows = con.execute("""
            SELECT h.id, h.nome, h.icone, h.cor,
                   EXISTS(
                       SELECT 1 FROM registros_habitos r
                       WHERE r.habito_id = h.id AND r.data = DATE('now')
                   ) as feito_hoje,
                   COUNT(r.id) as streak
            FROM habitos h
            LEFT JOIN registros_habitos r ON r.habito_id = h.id
            WHERE h.ativo = 1
            GROUP BY h.id
            ORDER BY h.criado_em ASC
        """).fetchall()
    return [{
        "id": r[0], "nome": r[1], "icone": r[2], "cor": r[3],
        "feito_hoje": bool(r[4]), "streak": r[5]
    } for r in rows]

def registrar_habito(habito_id: int):
    with conectar() as con:
        try:
            con.execute(
                "INSERT INTO registros_habitos (habito_id, data) VALUES (?, DATE('now'))",
                (habito_id,)
            )
            return True
        except sqlite3.IntegrityError:
            con.execute(
                "DELETE FROM registros_habitos WHERE habito_id = ? AND data = DATE('now')",
                (habito_id,)
            )
            return False

def deletar_habito(habito_id: int):
    with conectar() as con:
        con.execute("DELETE FROM habitos WHERE id = ?", (habito_id,))


# resumo matinal


def resumo_matinal() -> dict:
    with conectar() as con:
        tarefas_pendentes = con.execute("""
            SELECT COUNT(*) FROM tarefas WHERE status = 'pendente'
        """).fetchone()[0]

        tarefas_hoje = con.execute("""
            SELECT COUNT(*) FROM tarefas
            WHERE status = 'pendente' AND DATE(prazo) = DATE('now')
        """).fetchone()[0]

        lembretes_hoje = con.execute("""
            SELECT COUNT(*) FROM lembretes
            WHERE DATE(data_hora) = DATE('now') AND ativo = 1
        """).fetchone()[0]

        habitos_feitos = con.execute("""
            SELECT COUNT(*) FROM registros_habitos WHERE data = DATE('now')
        """).fetchone()[0]

        total_habitos = con.execute("""
            SELECT COUNT(*) FROM habitos WHERE ativo = 1
        """).fetchone()[0]

    return {
        "tarefas_pendentes": tarefas_pendentes,
        "tarefas_hoje": tarefas_hoje,
        "lembretes_hoje": lembretes_hoje,
        "habitos_feitos": habitos_feitos,
        "total_habitos": total_habitos
    }