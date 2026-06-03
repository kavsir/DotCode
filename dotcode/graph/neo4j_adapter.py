"""
Neo4jAdapter - Triển khai GraphDBInterface cho Neo4j.
Hỗ trợ các dự án lớn với hàng trăm nghìn symbols.
"""

from typing import List, Optional
from neo4j import GraphDatabase as Neo4jDriver
from .interface import GraphDBInterface
from ..models import Symbol, Edge, SymbolKind, EdgeType, BlastRadiusResult


class Neo4jAdapter(GraphDBInterface):
    def __init__(self, uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = "password"):
        self._driver = Neo4jDriver.driver(uri, auth=(user, password))
        self._create_constraints()

    def _create_constraints(self):
        """Tạo constraints và indexes trong Neo4j."""
        with self._driver.session() as session:
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Symbol) REQUIRE s.id IS UNIQUE")
            session.run("CREATE INDEX IF NOT EXISTS FOR (s:Symbol) ON (s.name)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (s:Symbol) ON (s.file_path)")

    # ========== WRITE METHODS ==========
    def add_symbol(self, symbol: Symbol) -> None:
        with self._driver.session() as session:
            session.run(
                """MERGE (s:Symbol {id: $id})
                SET s.name = $name, s.kind = $kind, s.file_path = $file_path,
                    s.start_line = $start_line, s.end_line = $end_line,
                    s.signature = $signature, s.docstring = $docstring,
                    s.body_hash = $body_hash, s.complexity = $complexity,
                    s.pagerank = $pagerank""",
                id=symbol.id, name=symbol.name, kind=symbol.kind.value, file_path=symbol.file_path,
                start_line=symbol.start_line, end_line=symbol.end_line,
                signature=symbol.signature, docstring=symbol.docstring,
                body_hash=symbol.body_hash, complexity=symbol.complexity,
                pagerank=symbol.pagerank
            )

    def add_edge(self, edge: Edge) -> None:
        with self._driver.session() as session:
            session.run(
                f"""MATCH (s:Symbol {{id: $source_id}})
                MATCH (t:Symbol {{id: $target_id}})
                MERGE (s)-[:{edge.type.value.upper()} {{weight: $weight}}]->(t)""",
                source_id=edge.source_id, target_id=edge.target_id, weight=edge.weight
            )

    def replace_symbols(self, file_path: str, symbols: List[Symbol]) -> None:
        with self._driver.session() as session:
            # Xóa symbols cũ của file
            session.run("MATCH (s:Symbol {file_path: $file_path}) DETACH DELETE s", file_path=file_path)
            # Thêm symbols mới
            for sym in symbols:
                self.add_symbol(sym)

    def replace_edges(self, file_path: str, edges: List[Edge]) -> None:
        with self._driver.session() as session:
            # Xóa edges từ symbols của file
            session.run(
                """MATCH (s:Symbol {file_path: $file_path})-[r]->()
                DELETE r""", file_path=file_path
            )
            # Thêm edges mới
            for edge in edges:
                self.add_edge(edge)

    # ========== READ METHODS ==========
    def get_symbol(self, symbol_id: str) -> Optional[Symbol]:
        with self._driver.session() as session:
            result = session.run("MATCH (s:Symbol {id: $id}) RETURN s", id=symbol_id).single()
            if result:
                return self._node_to_symbol(result["s"])
            return None

    def get_callees(self, symbol_id: str, depth: int = 1) -> List[Symbol]:
        with self._driver.session() as session:
            result = session.run(
                f"MATCH (s:Symbol {{id: $id}})-[:CALLS*1..{depth}]->(t:Symbol) RETURN DISTINCT t",
                id=symbol_id
            )
            return [self._node_to_symbol(record["t"]) for record in result]

    def get_callers(self, symbol_id: str, depth: int = 1) -> List[Symbol]:
        with self._driver.session() as session:
            result = session.run(
                f"MATCH (t:Symbol {{id: $id}})<-[:CALLS*1..{depth}]-(s:Symbol) RETURN DISTINCT s",
                id=symbol_id
            )
            return [self._node_to_symbol(record["s"]) for record in result]

    def search(self, query: str, kind: str = None, limit: int = 10) -> List[Symbol]:
        with self._driver.session() as session:
            cypher = "MATCH (s:Symbol) WHERE s.name CONTAINS $query OR s.signature CONTAINS $query"
            if kind:
                cypher += " AND s.kind = $kind"
            cypher += " RETURN s ORDER BY s.pagerank DESC LIMIT $limit"
            result = session.run(cypher, query=query, kind=kind, limit=limit)
            return [self._node_to_symbol(record["s"]) for record in result]

    def get_symbols_in_file(self, file_path: str) -> List[Symbol]:
        with self._driver.session() as session:
            result = session.run("MATCH (s:Symbol {file_path: $file_path}) RETURN s", file_path=file_path)
            return [self._node_to_symbol(record["s"]) for record in result]

    def count_symbols(self) -> int:
        with self._driver.session() as session:
            result = session.run("MATCH (s:Symbol) RETURN count(s) AS count").single()
            return result["count"] if result else 0

    # ========== ADVANCED QUERIES ==========
    def get_blast_radius(self, symbol_id: str, max_depth: int = 3) -> Optional[BlastRadiusResult]:
        sym = self.get_symbol(symbol_id)
        if not sym:
            return None

        # Direct callers
        direct_callers = self.get_callers(symbol_id, depth=1)

        # Indirect callers (dùng Cypher variable-length)
        indirect_callers = []
        with self._driver.session() as session:
            result = session.run(
                f"""MATCH path = (caller:Symbol)-[:CALLS*1..{max_depth}]->(t:Symbol {{id: $id}})
                WHERE caller.id <> t.id
                RETURN DISTINCT caller, length(path) AS depth
                ORDER BY depth""",
                id=symbol_id
            )
            for record in result:
                if record["caller"]["id"] not in [c.id for c in direct_callers]:
                    indirect_callers.append({
                        "symbol": self._node_to_symbol(record["caller"]),
                        "depth": record["depth"]
                    })

        # Callees
        callees = self.get_callees(symbol_id, depth=1)

        # Subclasses
        subclasses = []
        if sym.kind == SymbolKind.CLASS:
            with self._driver.session() as session:
                result = session.run(
                    "MATCH (s:Symbol)-[:INHERITS]->(t:Symbol {id: $id}) RETURN s",
                    id=symbol_id
                )
                subclasses = [self._node_to_symbol(record["s"]) for record in result]

        total_impact = len(direct_callers) + len(indirect_callers) + len(callees) + len(subclasses)

        return BlastRadiusResult(
            symbol=sym,
            direct_callers=direct_callers,
            indirect_callers=indirect_callers,
            callees=callees,
            subclasses=subclasses,
            total_impact=total_impact
        )

    def get_unused_symbols(self) -> List[Symbol]:
        with self._driver.session() as session:
            result = session.run(
                """MATCH (s:Symbol)
                WHERE s.kind IN ['function', 'method']
                AND NOT s.name IN ['main', '__init__', '__main__']
                AND NOT (()-[r:CALLS]->(s))
                RETURN s
                ORDER BY s.pagerank ASC"""
            )
            return [self._node_to_symbol(record["s"]) for record in result]

    def close(self) -> None:
        self._driver.close()

    # ========== HELPER ==========
    def _node_to_symbol(self, node) -> Symbol:
        """Chuyển đổi Neo4j node thành Symbol object."""
        data = dict(node)
        return Symbol(
            id=data.get("id", ""),
            name=data.get("name", ""),
            kind=data.get("kind", "function"),
            file_path=data.get("file_path", ""),
            start_line=data.get("start_line", 0),
            end_line=data.get("end_line", 0),
            signature=data.get("signature"),
            docstring=data.get("docstring"),
            body_hash=data.get("body_hash"),
            complexity=data.get("complexity", 0),
            pagerank=data.get("pagerank", 0.0)
        )