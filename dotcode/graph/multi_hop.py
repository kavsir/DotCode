"""
Multi-Hop Query Engine cho DotCode.
Hỗ trợ truy vấn đồ thị phức tạp với nhiều bước nhảy.
"""

import json
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

from dotcode.graph.sqlite_adapter import _row_to_symbol

from ..models import Symbol, SymbolKind


class MultiHopEngine:
    def __init__(self, db):
        self.db = db

    def _row_to_symbol(row: dict) -> Symbol:
        """Chuyển đổi row dict từ database thành Symbol object, xử lý metadata."""
        data = dict(row)
        if "metadata" in data and isinstance(data["metadata"], str):
            try:
                data["metadata"] = json.loads(data["metadata"])
            except (json.JSONDecodeError, TypeError):
                data["metadata"] = {}
        return Symbol(**data)

    def get_k_hop_neighbors(
        self, symbol_id: str, k: int = 2, edge_types: List[str] = None, direction: str = "both"
    ) -> List[Dict]:
        """
        Tìm tất cả symbols trong phạm vi k bước từ symbol gốc.

        Args:
            symbol_id: ID của symbol gốc
            k: Số bước nhảy tối đa
            edge_types: Danh sách loại edge cần theo dõi (mặc định: ['calls'])
            direction: 'out' (chỉ đi ra), 'in' (chỉ đi vào), 'both' (cả hai)

        Returns:
            Danh sách các dict với keys: symbol, depth, path (chuỗi các symbol từ gốc)
        """
        if edge_types is None:
            edge_types = ["calls"]

        edge_types_str = "', '".join(edge_types)

        # Tạo SQL cho việc tìm neighbors
        if direction == "out":
            query_template = """
                SELECT DISTINCT t.id as target_id, 1 as depth
                FROM edges e
                JOIN symbols t ON e.target_id = t.id
                WHERE e.source_id = ? AND e.type IN ('{edge_types}')
            """
        elif direction == "in":
            query_template = """
                SELECT DISTINCT s.id as source_id, 1 as depth
                FROM edges e
                JOIN symbols s ON e.source_id = s.id
                WHERE e.target_id = ? AND e.type IN ('{edge_types}')
            """
        else:  # both
            query_template = """
                SELECT DISTINCT 
                    CASE WHEN e.source_id = ? THEN e.target_id ELSE e.source_id END as neighbor_id,
                    1 as depth
                FROM edges e
                WHERE (e.source_id = ? OR e.target_id = ?) 
                AND e.type IN ('{edge_types}')
            """

        query_template = query_template.format(edge_types=edge_types_str)

        # BFS tìm neighbors
        visited = {symbol_id}
        results = []
        queue = deque([(symbol_id, 0, [symbol_id])])

        while queue:
            current_id, depth, path = queue.popleft()

            if depth >= k:
                continue

            if direction == "both":
                params = (current_id, current_id, current_id)
            else:
                params = (current_id,)

            rows = self.db.conn.execute(query_template, params).fetchall()

            for row in rows:
                neighbor_id = row[0]
                if neighbor_id not in visited and neighbor_id != symbol_id:
                    visited.add(neighbor_id)
                    new_path = path + [neighbor_id]
                    neighbor_sym = self.db.get_symbol(neighbor_id)
                    if neighbor_sym:
                        results.append(
                            {
                                "symbol": _row_to_symbol(neighbor_sym),
                                "depth": depth + 1,
                                "path": new_path,
                            }
                        )
                        queue.append((neighbor_id, depth + 1, new_path))

        return results

    def find_shortest_path(
        self, source_id: str, target_id: str, max_depth: int = 5, edge_types: List[str] = None
    ) -> Optional[List[Dict]]:
        """
        Tìm đường đi ngắn nhất giữa hai symbols.

        Args:
            source_id: ID của symbol nguồn
            target_id: ID của symbol đích
            max_depth: Độ sâu tìm kiếm tối đa
            edge_types: Danh sách loại edge (mặc định: ['calls'])

        Returns:
            Danh sách các dict mô tả đường đi, hoặc None nếu không tìm thấy
        """
        if edge_types is None:
            edge_types = ["calls"]

        edge_types_str = "', '".join(edge_types)

        # BFS hai phía (bidirectional) để tăng tốc
        forward_visited = {source_id: [source_id]}
        backward_visited = {target_id: [target_id]}
        forward_queue = deque([source_id])
        backward_queue = deque([target_id])

        for depth in range(max_depth):
            # Mở rộng phía forward
            for _ in range(len(forward_queue)):
                current = forward_queue.popleft()
                current_path = forward_visited[current]

                rows = self.db.conn.execute(
                    f"""SELECT DISTINCT t.id FROM edges e
                    JOIN symbols t ON e.target_id = t.id
                    WHERE e.source_id = ? AND e.type IN ('{edge_types_str}')""",
                    (current,),
                ).fetchall()

                for row in rows:
                    neighbor = row[0]
                    if neighbor in backward_visited:
                        # Tìm thấy đường đi
                        backward_path = backward_visited[neighbor]
                        full_path = current_path + backward_path[::-1][1:]
                        return self._build_path_result(full_path)

                    if neighbor not in forward_visited:
                        forward_visited[neighbor] = current_path + [neighbor]
                        forward_queue.append(neighbor)

            # Mở rộng phía backward
            for _ in range(len(backward_queue)):
                current = backward_queue.popleft()
                current_path = backward_visited[current]

                rows = self.db.conn.execute(
                    f"""SELECT DISTINCT s.id FROM edges e
                    JOIN symbols s ON e.source_id = s.id
                    WHERE e.target_id = ? AND e.type IN ('{edge_types_str}')""",
                    (current,),
                ).fetchall()

                for row in rows:
                    neighbor = row[0]
                    if neighbor in forward_visited:
                        forward_path = forward_visited[neighbor]
                        full_path = forward_path + current_path[::-1][1:]
                        return self._build_path_result(full_path)

                    if neighbor not in backward_visited:
                        backward_visited[neighbor] = current_path + [neighbor]
                        backward_queue.append(neighbor)

        return None

    def _build_path_result(self, path: List[str]) -> List[Dict]:
        """Xây dựng kết quả đường đi từ danh sách ID."""
        result = []
        for i, sym_id in enumerate(path):
            sym = self.db.get_symbol(sym_id)
            if sym:
                step = {"symbol": _row_to_symbol(sym), "step": i}
                if i > 0:
                    # Tìm edge type giữa step i-1 và i
                    prev_id = path[i - 1]
                    edge_row = self.db.conn.execute(
                        """SELECT type FROM edges 
                        WHERE source_id = ? AND target_id = ? 
                        UNION 
                        SELECT type FROM edges 
                        WHERE source_id = ? AND target_id = ? 
                        LIMIT 1""",
                        (prev_id, sym_id, sym_id, prev_id),
                    ).fetchone()
                    step["edge_type"] = edge_row[0] if edge_row else "unknown"
                result.append(step)
        return result

    def find_community_bridges(
        self,
        community_id_1: int,
        community_id_2: int,
        node_to_community: Dict[str, int],
        edge_types: List[str] = None,
    ) -> List[Dict]:
        """
        Tìm các symbols kết nối giữa hai communities.

        Args:
            community_id_1: ID của community thứ nhất
            community_id_2: ID của community thứ hai
            node_to_community: Dict ánh xạ symbol_id -> community_id
            edge_types: Danh sách loại edge

        Returns:
            Danh sách các cặp symbols kết nối hai communities
        """
        if edge_types is None:
            edge_types = ["calls", "references"]

        edge_types_str = "', '".join(edge_types)

        # Lấy tất cả symbols trong mỗi community
        comm1_symbols = {sid for sid, cid in node_to_community.items() if cid == community_id_1}
        comm2_symbols = {sid for sid, cid in node_to_community.items() if cid == community_id_2}

        bridges = []

        # Tìm edges nối giữa hai communities
        for sym1 in comm1_symbols:
            rows = self.db.conn.execute(
                f"""SELECT DISTINCT e.target_id, e.type FROM edges e
                WHERE e.source_id = ? AND e.type IN ('{edge_types_str}')
                AND e.target_id IN ({','.join(['?'] * len(comm2_symbols))})""",
                (sym1, *comm2_symbols),
            ).fetchall()

            for row in rows:
                sym2 = row[0]
                edge_type = row[1]
                sym1_data = self.db.get_symbol(sym1)
                sym2_data = self.db.get_symbol(sym2)
                if sym1_data and sym2_data:
                    bridges.append(
                        {
                            "source": _row_to_symbol(sym1_data),
                            "target": _row_to_symbol(sym2_data),
                            "edge_type": edge_type,
                            "source_community": community_id_1,
                            "target_community": community_id_2,
                        }
                    )

        return bridges

    def multi_hop_query(
        self, query_text: str, graphrag_communities: Dict = None, max_depth: int = 3
    ) -> str:
        """
        Thực hiện truy vấn multi-hop kết hợp cấu trúc và ngữ nghĩa.

        Args:
            query_text: Câu truy vấn dạng tự nhiên (ví dụ: "find all functions that call functions called by lend_book")
            graphrag_communities: Dict communities từ GraphRAG (tùy chọn)
            max_depth: Độ sâu tối đa

        Returns:
            Chuỗi text mô tả kết quả
        """
        # Phân tích query đơn giản
        import re

        # Pattern: "calls functions called by X" -> 2-hop
        match = re.search(
            r"(?:calls?|gọi)\s+(?:functions?|hàm)\s+(?:called by|được gọi bởi)\s+(\w+)",
            query_text,
            re.IGNORECASE,
        )
        if match:
            target_name = match.group(1)
            # Tìm symbol
            syms = self.db.get_symbol_by_name(target_name)
            if syms:
                # Bước 1: Tìm callees của target
                callees = self.db.get_callees(syms[0]["id"])
                results = []
                # Bước 2: Tìm callers của từng callee
                for callee in callees:
                    callers = self.db.get_callers(callee["id"])
                    for caller in callers:
                        results.append(
                            f"- {caller['name']} (calls {callee['name']} which is called by"
                            f" {target_name})"
                        )
                if results:
                    return "Multi-hop results:\n" + "\n".join(results[:10])

        # Pattern: "is X connected to Y" -> path finding
        match = re.search(
            r"(?:is|are|có phải)\s+(\w+)\s+(?:connected to|related to|liên quan đến)\s+(\w+)",
            query_text,
            re.IGNORECASE,
        )
        if match:
            source_name = match.group(1)
            target_name = match.group(2)
            source_syms = self.db.get_symbol_by_name(source_name)
            target_syms = self.db.get_symbol_by_name(target_name)
            if source_syms and target_syms:
                path = self.find_shortest_path(
                    source_syms[0]["id"], target_syms[0]["id"], max_depth
                )
                if path:
                    steps = " → ".join(
                        [f"{s['symbol'].name}({s.get('edge_type', '')})" for s in path]
                    )
                    return f"Path from {source_name} to {target_name}: {steps}"
                else:
                    return (
                        f"No path found between {source_name} and {target_name} within"
                        f" {max_depth} steps."
                    )

        return "Unable to parse query. Try: 'calls functions called by X' or 'is X connected to Y'"
