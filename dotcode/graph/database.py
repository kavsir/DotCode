import os
import sqlite3

from git import List, Optional

from ..models import Edge, Symbol

SCHEMA = """
CREATE TABLE IF NOT EXISTS symbols (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    file_path TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    signature TEXT,
    body_hash TEXT,
    complexity INTEGER DEFAULT 0,
    pagerank REAL DEFAULT 0.0,
    metadata TEXT DEFAULT '{}',
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS edges (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('calls', 'imports', 'references', 'inherits', 'contains')),
    weight REAL DEFAULT 1.0,
    PRIMARY KEY (source_id, target_id, type)
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL CHECK(event_type IN ('user_accept', 'user_reject', 'bug_fix', 'refactor', 'question')),
    description TEXT,
    timestamp TEXT DEFAULT (datetime('now')),
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS event_symbols (
    event_id TEXT NOT NULL,
    symbol_id TEXT NOT NULL,
    relevance REAL DEFAULT 1.0,
    PRIMARY KEY (event_id, symbol_id)
);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
"""


class GraphDatabase:
    def __init__(self, db_path=":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.row_factory = sqlite3.Row  # Để truy vấn trả về dict-like

    def replace_symbols(self, file_path: str, symbols: list):
        """Xóa symbols cũ của file và chèn mới."""
        self.conn.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))
        for sym in symbols:
            self.conn.execute(
                """INSERT OR REPLACE INTO symbols 
                (id, name, kind, file_path, start_line, end_line, signature, body_hash, complexity, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sym["id"],
                    sym["name"],
                    sym["kind"],
                    file_path,
                    sym["start_line"],
                    sym["end_line"],
                    sym.get("signature"),
                    sym.get("body_hash"),
                    sym.get("complexity", 0),
                    sym.get("metadata", "{}"),
                ),
            )
        self.conn.commit()

    def replace_edges(self, file_path: str, edges: list):
        """Xóa edges cũ liên quan đến file và chèn mới."""
        self.conn.execute(
            """
            DELETE FROM edges WHERE source_id IN 
            (SELECT id FROM symbols WHERE file_path = ?)
        """,
            (file_path,),
        )
        for edge in edges:
            self.conn.execute(
                """INSERT OR REPLACE INTO edges (source_id, target_id, type, weight)
                VALUES (?, ?, ?, ?)""",
                (edge["source_id"], edge["target_id"], edge["type"], edge.get("weight", 1.0)),
            )
        self.conn.commit()

    def get_symbols_in_file(self, file_path: str):
        cur = self.conn.execute("SELECT * FROM symbols WHERE file_path = ?", (file_path,))
        return [dict(row) for row in cur.fetchall()]

    def get_symbol(self, symbol_id: str):
        cur = self.conn.execute("SELECT * FROM symbols WHERE id = ?", (symbol_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_callees(self, symbol_id: str):
        """Lấy những symbol được gọi bởi symbol_id."""
        cur = self.conn.execute(
            """
            SELECT s.* FROM symbols s
            JOIN edges e ON s.id = e.target_id
            WHERE e.source_id = ? AND e.type = 'calls'
        """,
            (symbol_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    def get_callers(self, symbol_id: str):
        cur = self.conn.execute(
            """
            SELECT s.* FROM symbols s
            JOIN edges e ON s.id = e.source_id
            WHERE e.target_id = ? AND e.type = 'calls'
        """,
            (symbol_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    def count_symbols(self):
        cur = self.conn.execute("SELECT COUNT(*) FROM symbols")
        return cur.fetchone()[0]

    def get_symbol_as_model(self, symbol_id: str) -> Optional[Symbol]:
        """Trả về Symbol object từ database row."""
        row = self.get_symbol(symbol_id)
        if row:
            return Symbol(**row)
        return None

    def get_callees_as_models(self, symbol_id: str) -> List[Symbol]:
        """Trả về danh sách Symbol objects."""
        rows = self.get_callees(symbol_id)
        return [Symbol(**r) for r in rows]

    def get_callers_as_models(self, symbol_id: str) -> List[Symbol]:
        """Trả về danh sách Symbol objects."""
        rows = self.get_callers(symbol_id)
        return [Symbol(**r) for r in rows]

    def get_edges_as_models(self, symbol_id: str = None) -> List[Edge]:
        """Trả về danh sách Edge objects, có thể lọc theo source_id."""
        if symbol_id:
            rows = self.conn.execute(
                "SELECT * FROM edges WHERE source_id = ?", (symbol_id,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM edges").fetchall()
        return [Edge(**dict(r)) for r in rows]
