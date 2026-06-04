"""
SQLiteAdapter - Triển khai GraphDBInterface cho SQLite.
Bọc GraphDatabase hiện có và chuyển đổi dict sang Pydantic models.
"""

import json
from typing import List, Optional

from ..models import BlastRadiusResult, Edge, EdgeType, Symbol, SymbolKind
from .database import GraphDatabase
from .interface import GraphDBInterface


def _row_to_symbol(row: dict) -> Symbol:
    """Chuyển đổi row dict từ database thành Symbol object, xử lý metadata."""
    data = dict(row)
    # Parse metadata từ string JSON thành dict
    if "metadata" in data and isinstance(data["metadata"], str):
        try:
            data["metadata"] = json.loads(data["metadata"])
        except (json.JSONDecodeError, TypeError):
            data["metadata"] = {}
    return Symbol(**data)


class SQLiteAdapter(GraphDBInterface):
    def __init__(self, db: GraphDatabase):
        self._db = db

    # ========== WRITE METHODS ==========
    def add_symbol(self, symbol: Symbol) -> None:
        raise NotImplementedError

    def add_edge(self, edge: Edge) -> None:
        raise NotImplementedError

    def replace_symbols(self, file_path: str, symbols: List[Symbol]) -> None:
        dict_symbols = [sym.model_dump() for sym in symbols]
        self._db.replace_symbols(file_path, dict_symbols)

    def replace_edges(self, file_path: str, edges: List[Edge]) -> None:
        dict_edges = [edge.model_dump() for edge in edges]
        self._db.replace_edges(file_path, dict_edges)

    # ========== READ METHODS ==========
    def get_symbol(self, symbol_id: str) -> Optional[Symbol]:
        row = self._db.get_symbol(symbol_id)
        return _row_to_symbol(row) if row else None

    def get_callees(self, symbol_id: str, depth: int = 1) -> List[Symbol]:
        """Lấy callees, tự động fallback tìm theo tên nếu ID đầy đủ không khớp."""
        rows = self._db.get_callees(symbol_id)
        if rows:
            return [_row_to_symbol(r) for r in rows]

        # Fallback: tìm symbol theo tên đơn giản
        matches = self.find_symbol_by_name(symbol_id)
        if matches:
            rows = self._db.get_callees(matches[0].id)
            return [_row_to_symbol(r) for r in rows]

        return []

    def get_callers(self, symbol_id: str, depth: int = 1) -> List[Symbol]:
        """Lấy callers, tự động fallback tìm theo tên nếu ID đầy đủ không khớp."""
        rows = self._db.get_callers(symbol_id)
        if rows:
            return [_row_to_symbol(r) for r in rows]

        # Fallback: tìm symbol theo tên đơn giản
        matches = self.find_symbol_by_name(symbol_id)
        if matches:
            rows = self._db.get_callers(matches[0].id)
            return [_row_to_symbol(r) for r in rows]

        return []

    def search(self, query: str, kind: str = None, limit: int = 10) -> List[Symbol]:
        sql = """SELECT * FROM symbols 
                 WHERE name LIKE ? OR signature LIKE ?
                 ORDER BY pagerank DESC
                 LIMIT ?"""
        params = (f"%{query}%", f"%{query}%", limit)
        if kind:
            sql = """SELECT * FROM symbols 
                     WHERE (name LIKE ? OR signature LIKE ?)
                     AND kind = ?
                     ORDER BY pagerank DESC
                     LIMIT ?"""
            params = (f"%{query}%", f"%{query}%", kind, limit)
        cur = self._db.conn.execute(sql, params)
        rows = cur.fetchall()
        return [_row_to_symbol(dict(r)) for r in rows]

    def get_symbols_in_file(self, file_path: str) -> List[Symbol]:
        rows = self._db.get_symbols_in_file(file_path)
        return [_row_to_symbol(r) for r in rows]

    def count_symbols(self) -> int:
        return self._db.count_symbols()

    # ========== ADVANCED QUERIES ==========
    def get_blast_radius(self, symbol_id: str, max_depth: int = 3) -> Optional[BlastRadiusResult]:
        sym = self.get_symbol(symbol_id)
        if not sym:
            return None

        result = BlastRadiusResult(
            symbol=sym,
            direct_callers=[],
            indirect_callers=[],
            callees=[],
            subclasses=[],
            total_impact=0,
        )

        result.direct_callers = self.get_callers(symbol_id)

        visited = {symbol_id}
        queue = [(c.id, 1) for c in result.direct_callers]
        while queue:
            current_id, depth = queue.pop(0)
            if current_id in visited or depth >= max_depth:
                continue
            visited.add(current_id)
            caller_sym = self.get_symbol(current_id)
            if caller_sym:
                result.indirect_callers.append({"symbol": caller_sym, "depth": depth})
                for c in self.get_callers(current_id):
                    queue.append((c.id, depth + 1))

        result.callees = self.get_callees(symbol_id)

        if sym.kind == SymbolKind.CLASS:
            cur = self._db.conn.execute(
                (
                    "SELECT s.* FROM symbols s JOIN edges e ON s.id = e.source_id "
                    "WHERE e.target_id = ? AND e.type = 'inherits'"
                ),
                (symbol_id,),
            )
            result.subclasses = [_row_to_symbol(dict(row)) for row in cur.fetchall()]

        result.total_impact = (
            len(result.direct_callers)
            + len(result.indirect_callers)
            + len(result.callees)
            + len(result.subclasses)
        )
        return result

    def get_unused_symbols(self) -> List[Symbol]:
        cur = self._db.conn.execute("""
            SELECT s.* FROM symbols s
            WHERE s.id NOT IN (
                SELECT DISTINCT e.target_id FROM edges e WHERE e.type = 'calls'
            )
            AND s.kind IN ('function', 'method')
            AND s.name NOT IN ('main', '__init__', '__main__')
            ORDER BY s.pagerank ASC
        """)
        return [_row_to_symbol(dict(row)) for row in cur.fetchall()]

    def find_symbol_by_name(self, name: str, kind: str = None) -> List[Symbol]:
        """Tìm symbol theo tên đơn giản (không cần ID đầy đủ)."""
        sql = "SELECT * FROM symbols WHERE name = ?"
        params = [name]
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        cur = self._db.conn.execute(sql, params)
        rows = cur.fetchall()
        return [_row_to_symbol(dict(r)) for r in rows]

    def close(self) -> None:
        self._db.conn.close()
