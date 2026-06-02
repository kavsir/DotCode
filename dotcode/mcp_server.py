"""
DotCode MCP Server - Phơi bày Code Graph và GraphRAG tools cho AI agent.
"""

import os
import sys
from typing import List, Optional
from fastmcp import FastMCP

# Thêm thư mục gốc vào path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotcode.graph import CodeGraph
from dotcode.models import Symbol, BlastRadiusResult, SymbolKind

# Khởi tạo MCP server
mcp = FastMCP("DotCode Code Graph")

# Khởi tạo CodeGraph (dùng SQLite, sẽ nâng cấp để chọn database linh hoạt sau)
code_graph = None

def get_code_graph() -> CodeGraph:
    """Lấy hoặc khởi tạo CodeGraph instance."""
    global code_graph
    if code_graph is None:
        root = os.getcwd()
        code_graph = CodeGraph.create_with_sqlite(root)
        if not code_graph.is_indexed():
            code_graph.index()
    return code_graph

# ==================== MCP TOOLS ====================

@mcp.tool()
async def get_callees(symbol_name: str) -> List[dict]:
    cg = get_code_graph()
    
    # Debug log
    print(f"[DEBUG] get_callees called with: {symbol_name}", flush=True)
    
    # Thử tìm theo ID đầy đủ trước
    symbols = cg.db.get_callees(symbol_name)
    print(f"[DEBUG] Direct lookup returned: {len(symbols)} results", flush=True)
    if symbols:
        return [sym.model_dump() for sym in symbols]
    
    # Fallback: tìm theo tên đơn giản
    matches = cg.db.find_symbol_by_name(symbol_name)
    print(f"[DEBUG] find_by_name returned: {len(matches)} matches", flush=True)
    if matches:
        symbols = cg.db.get_callees(matches[0].id)
        print(f"[DEBUG] Callees of {matches[0].id}: {len(symbols)} results", flush=True)
        return [sym.model_dump() for sym in symbols]
    
    return []



async def get_callers(symbol_name: str) -> List[dict]:
    """Lấy danh sách symbols gọi đến symbol (chấp nhận tên đơn giản hoặc ID đầy đủ)."""
    cg = get_code_graph()
    
    # Thử tìm theo ID đầy đủ trước
    symbols = cg.db.get_callers(symbol_name)
    if symbols:
        return [sym.model_dump() for sym in symbols]
    
    # Fallback: tìm theo tên đơn giản
    matches = cg.db.find_symbol_by_name(symbol_name)
    if matches:
        symbols = cg.db.get_callers(matches[0].id)
        return [sym.model_dump() for sym in symbols]
    
    return []

@mcp.tool()
async def get_blast_radius(symbol_id: str, max_depth: int = 3) -> dict:
    """
    Phân tích tác động: xác định tất cả các symbols bị ảnh hưởng khi thay đổi symbol này.
    
    Args:
        symbol_id: ID của symbol cần phân tích
        max_depth: Độ sâu tối đa khi duyệt đồ thị (mặc định: 3)
    
    Returns:
        BlastRadiusResult chứa direct_callers, indirect_callers, callees, subclasses.
    """
    cg = get_code_graph()
    result = cg.get_blast_radius(symbol_id, max_depth)
    if result:
        return result.model_dump()
    return {"error": "Symbol not found"}

@mcp.tool()
async def search_code(query: str, kind: str = None, limit: int = 10) -> List[dict]:
    """
    Tìm kiếm symbols trong codebase theo tên.
    
    Args:
        query: Từ khóa tìm kiếm (khớp với tên hoặc signature)
        kind: Lọc theo loại symbol (function, class, method, variable)
        limit: Số lượng kết quả tối đa (mặc định: 10)
    
    Returns:
        Danh sách các symbols khớp.
    """
    cg = get_code_graph()
    symbols = cg.db.search(query, kind=kind, limit=limit)
    return [sym.model_dump() for sym in symbols]

@mcp.tool()
async def get_unused_symbols() -> List[dict]:
    """
    Phát hiện dead code: trả về danh sách các symbols không được gọi bởi bất kỳ symbol nào khác.
    
    Returns:
        Danh sách các symbols có khả năng là dead code.
    """
    cg = get_code_graph()
    symbols = cg.get_unused_symbols()
    return [sym.model_dump() for sym in symbols]

@mcp.tool()
async def get_file_context(file_paths: List[str]) -> str:
    """
    Lấy context của một hoặc nhiều file trong codebase.
    
    Args:
        file_paths: Danh sách đường dẫn file cần lấy context
    
    Returns:
        Chuỗi text mô tả context của các file, bao gồm symbols và quan hệ.
    """
    cg = get_code_graph()
    context = cg.get_context(chat_files=file_paths, other_files=[])
    return context


@mcp.tool()
async def global_search(query: str, top_k: int = 3) -> List[dict]:
    """
    Tìm kiếm toàn cục trên toàn bộ codebase.
    Trả về các cộng đồng (communities) liên quan nhất đến câu hỏi,
    kèm theo tóm tắt nội dung của từng cộng đồng.

    Args:
        query: Câu hỏi hoặc chủ đề cần tìm kiếm (hỗ trợ đa ngôn ngữ)
        top_k: Số lượng cộng đồng trả về (mặc định: 3)

    Returns:
        Danh sách các cộng đồng, mỗi cộng đồng bao gồm:
        - community_id: ID của cộng đồng
        - summary: Tóm tắt nội dung của cộng đồng
        - similarity: Điểm tương đồng với câu hỏi
        - key_symbols: Danh sách các symbols chính trong cộng đồng
    """
    cg = get_code_graph()
    
    # Đảm bảo GraphRAG engine đã được khởi tạo và có dữ liệu
    if not cg.graphrag or not cg.graphrag.communities:
        return [{"error": "GraphRAG engine is not initialized. Please index the codebase first."}]
    
    # Gọi global search từ GraphRAG engine
    results = cg.graphrag.global_search(query, top_k=top_k)
    
    # Format kết quả
    formatted_results = []
    for r in results:
        community_id = r.get("community_id")
        summary = r.get("summary", "")
        similarity = r.get("similarity", 0.0)
        symbols = r.get("symbols", [])
        
        # Chuyển đổi symbols thành dict
        key_symbols = []
        for sym in symbols[:10]:  # Giới hạn 10 symbols mỗi cộng đồng
            key_symbols.append({
                "name": sym["name"],
                "kind": sym["kind"],
                "file_path": sym["file_path"],
                "start_line": sym["start_line"]
            })
        
        formatted_results.append({
            "community_id": community_id,
            "summary": summary,
            "similarity": similarity,
            "key_symbols": key_symbols
        })
    
    return formatted_results

@mcp.tool()
async def local_search(symbol_name: str, depth: int = 2) -> dict:
    """
    Tìm kiếm cục bộ: trả về chi tiết một symbol và các láng giềng (neighbors) của nó.
    Chấp nhận tên đơn giản (vd: "lend_book") hoặc ID đầy đủ (vd: "services.py::LibraryService.lend_book").

    Args:
        symbol_name: Tên hoặc ID của symbol cần tìm kiếm.
        depth: Độ sâu duyệt đồ thị (mặc định: 2)

    Returns:
        Dictionary chứa:
        - symbol: Thông tin chi tiết của symbol (name, kind, file_path, start_line, signature)
        - community_id: ID của cộng đồng chứa symbol
        - community_summary: Tóm tắt của cộng đồng
        - neighbors: Danh sách các láng giềng, mỗi láng giềng bao gồm:
            - symbol: Thông tin symbol láng giềng
            - depth: Khoảng cách từ symbol gốc
            - direction: "callee" (được gọi bởi) hoặc "caller" (gọi đến)
    """
    cg = get_code_graph()
    
    # Đảm bảo GraphRAG engine đã được khởi tạo
    if not cg.graphrag:
        return {"error": "GraphRAG engine is not initialized. Please index the codebase first."}
    
    # Tìm symbol theo tên đơn giản hoặc ID đầy đủ
    matches = cg.db.find_symbol_by_name(symbol_name)
    if not matches:
        return {"error": f"Symbol '{symbol_name}' not found."}
    
    symbol = matches[0]
    symbol_id = symbol.id
    
    # Gọi local search từ GraphRAG engine
    local_result = cg.graphrag.local_search(symbol_id, depth=depth)
    
    # Format kết quả
    formatted_neighbors = []
    for neighbor in local_result.get("neighbors", []):
        neighbor_sym = neighbor.get("symbol", {})
        formatted_neighbors.append({
            "symbol": {
                "id": neighbor_sym.get("id", ""),
                "name": neighbor_sym.get("name", ""),
                "kind": neighbor_sym.get("kind", ""),
                "file_path": neighbor_sym.get("file_path", ""),
                "start_line": neighbor_sym.get("start_line", 0),
                "signature": neighbor_sym.get("signature", "")
            },
            "depth": neighbor.get("depth", 0),
            "direction": neighbor.get("direction", "")
        })
    
    return {
        "symbol": {
            "id": symbol.id,
            "name": symbol.name,
            "kind": symbol.kind.value if hasattr(symbol.kind, 'value') else str(symbol.kind),
            "file_path": symbol.file_path,
            "start_line": symbol.start_line,
            "signature": symbol.signature
        },
        "community_id": local_result.get("community_id"),
        "community_summary": local_result.get("community_summary", ""),
        "neighbors": formatted_neighbors
    }

@mcp.tool()
async def get_community_context(community_id: int = None, symbol_name: str = None) -> dict:
    """
    Lấy context của một cộng đồng (community) cụ thể.
    Có thể truyền trực tiếp community_id hoặc tên symbol để tự động tìm cộng đồng chứa nó.

    Args:
        community_id: ID của cộng đồng cần xem (tùy chọn)
        symbol_name: Tên symbol để tìm cộng đồng chứa nó (tùy chọn)

    Returns:
        Dictionary chứa:
        - community_id: ID của cộng đồng
        - summary: Tóm tắt nội dung của cộng đồng
        - symbols: Danh sách các symbols trong cộng đồng
        - total_nodes: Tổng số nodes trong cộng đồng
    """
    cg = get_code_graph()
    
    if not cg.graphrag or not cg.graphrag.communities:
        return {"error": "GraphRAG engine is not initialized. Please index the codebase first."}
    
    # Xác định community_id
    target_community_id = community_id
    
    if target_community_id is None and symbol_name:
        # Tìm cộng đồng chứa symbol
        matches = cg.db.find_symbol_by_name(symbol_name)
        if not matches:
            return {"error": f"Symbol '{symbol_name}' not found."}
        symbol_id = matches[0].id
        target_community_id = cg.graphrag.node_to_community.get(symbol_id)
        if target_community_id is None:
            return {"error": f"Symbol '{symbol_name}' does not belong to any community."}
    
    if target_community_id is None:
        return {"error": "Please provide either community_id or symbol_name."}
    
    if target_community_id not in cg.graphrag.communities:
        return {"error": f"Community {target_community_id} not found."}
    
    comm_data = cg.graphrag.communities[target_community_id]
    
    # Lấy chi tiết symbols
    symbols = []
    for node_id in comm_data["nodes"]:
        sym = cg.db.get_symbol(node_id)
        if sym:
            symbols.append({
                "id": sym.id,
                "name": sym.name,
                "kind": sym.kind.value if hasattr(sym.kind, 'value') else str(sym.kind),
                "file_path": sym.file_path,
                "start_line": sym.start_line,
                "signature": sym.signature
            })
    
    return {
        "community_id": target_community_id,
        "summary": comm_data.get("summary", ""),
        "symbols": symbols,
        "total_nodes": len(comm_data["nodes"])
    }

@mcp.tool()
async def get_blast_radius(symbol_name: str, max_depth: int = 3) -> dict:
    """
    Phân tích tác động: xác định tất cả các symbols bị ảnh hưởng khi thay đổi symbol này.
    Chấp nhận tên đơn giản hoặc ID đầy đủ.

    Args:
        symbol_name: Tên hoặc ID của symbol cần phân tích
        max_depth: Độ sâu tối đa khi duyệt đồ thị (mặc định: 3)

    Returns:
        BlastRadiusResult chứa direct_callers, indirect_callers, callees, subclasses, total_impact.
    """
    cg = get_code_graph()
    
    # Tìm symbol
    matches = cg.db.find_symbol_by_name(symbol_name)
    if not matches:
        return {"error": f"Symbol '{symbol_name}' not found."}
    
    symbol_id = matches[0].id
    result = cg.get_blast_radius(symbol_id, max_depth)
    
    if result:
        return result.model_dump()
    return {"error": "Blast radius analysis failed."}

@mcp.tool()
async def get_unused_symbols() -> dict:
    """
    Phát hiện dead code: trả về danh sách các symbols không được gọi bởi bất kỳ symbol nào khác.

    Returns:
        Dictionary với key 'unused_symbols' chứa danh sách các symbols có khả năng là dead code.
    """
    cg = get_code_graph()
    symbols = cg.get_unused_symbols()
    return {
        "unused_symbols": [
            {
                "id": sym.id,
                "name": sym.name,
                "kind": sym.kind.value if hasattr(sym.kind, 'value') else str(sym.kind),
                "file_path": sym.file_path,
                "start_line": sym.start_line
            }
            for sym in symbols
        ],
        "total": len(symbols)
    }

@mcp.tool()
async def multi_hop_query(
    query_type: str,
    symbol_id: str = None,
    target_id: str = None,
    k: int = 2,
    edge_types: str = "calls",
    max_depth: int = 5,
    community_id_1: int = None,
    community_id_2: int = None
) -> dict:
    """
    Thực hiện truy vấn đồ thị phức tạp với nhiều bước nhảy (multi-hop).
    Hỗ trợ các loại truy vấn: k_hop, shortest_path, community_bridges.

    Args:
        query_type: Loại truy vấn - 'k_hop', 'shortest_path', hoặc 'community_bridges'
        symbol_id: ID của symbol gốc (cho k_hop và shortest_path)
        target_id: ID của symbol đích (cho shortest_path)
        k: Số bước nhảy (cho k_hop, mặc định: 2)
        edge_types: Danh sách edge types phân cách bằng dấu phẩy (mặc định: 'calls')
        max_depth: Độ sâu tối đa (cho shortest_path, mặc định: 5)
        community_id_1: ID community thứ nhất (cho community_bridges)
        community_id_2: ID community thứ hai (cho community_bridges)

    Returns:
        Dictionary chứa kết quả truy vấn.
    """
    cg = get_code_graph()
    
    # Đảm bảo Multi-Hop Engine đã được khởi tạo
    if not cg.multi_hop:
        cg._ensure_multi_hop()
    
    if not cg.multi_hop:
        return {"error": "Multi-Hop Engine is not available. Please index the codebase first."}
    
    # Parse edge_types từ string thành list
    edge_type_list = [e.strip() for e in edge_types.split(",")]
    
    try:
        if query_type == "k_hop":
            if not symbol_id:
                # Fallback: tìm theo tên
                matches = cg.db.find_symbol_by_name(symbol_id) if symbol_id else []
                if not matches:
                    return {"error": "symbol_id is required for k_hop query"}
                symbol_id = matches[0].id
            
            neighbors = cg.multi_hop.get_k_hop_neighbors(
                symbol_id=symbol_id,
                k=k,
                edge_types=edge_type_list,
                direction="both"
            )
            
            return {
                "query_type": "k_hop",
                "source_symbol": symbol_id,
                "k": k,
                "edge_types": edge_type_list,
                "total_neighbors": len(neighbors),
                "neighbors": [
                    {
                        "name": n["symbol"].name,
                        "kind": n["symbol"].kind.value if hasattr(n["symbol"].kind, 'value') else str(n["symbol"].kind),
                        "file_path": n["symbol"].file_path,
                        "depth": n["depth"],
                        "path": n["path"]
                    }
                    for n in neighbors[:20]  # Giới hạn 20 kết quả
                ]
            }
        
        elif query_type == "shortest_path":
            if not symbol_id or not target_id:
                # Fallback: tìm theo tên
                if symbol_id:
                    matches = cg.db.find_symbol_by_name(symbol_id)
                    symbol_id = matches[0].id if matches else symbol_id
                if target_id:
                    matches = cg.db.find_symbol_by_name(target_id)
                    target_id = matches[0].id if matches else target_id
            
            if not symbol_id or not target_id:
                return {"error": "Both symbol_id and target_id are required for shortest_path query"}
            
            path = cg.multi_hop.find_shortest_path(
                source_id=symbol_id,
                target_id=target_id,
                max_depth=max_depth,
                edge_types=edge_type_list
            )
            
            if path:
                return {
                    "query_type": "shortest_path",
                    "source_symbol": symbol_id,
                    "target_symbol": target_id,
                    "path_length": len(path) - 1,
                    "edge_types": edge_type_list,
                    "path": [
                        {
                            "step": s["step"],
                            "name": s["symbol"].name,
                            "kind": s["symbol"].kind.value if hasattr(s["symbol"].kind, 'value') else str(s["symbol"].kind),
                            "file_path": s["symbol"].file_path,
                            "edge_type": s.get("edge_type", "")
                        }
                        for s in path
                    ]
                }
            else:
                return {
                    "query_type": "shortest_path",
                    "source_symbol": symbol_id,
                    "target_symbol": target_id,
                    "path_length": -1,
                    "message": f"No path found within {max_depth} steps"
                }
        
        elif query_type == "community_bridges":
            if community_id_1 is None or community_id_2 is None:
                return {"error": "Both community_id_1 and community_id_2 are required for community_bridges query"}
            
            if not cg.graphrag or not cg.graphrag.communities:
                return {"error": "GraphRAG engine is not initialized. Please index the codebase first."}
            
            bridges = cg.multi_hop.find_community_bridges(
                community_id_1=community_id_1,
                community_id_2=community_id_2,
                node_to_community=cg.graphrag.node_to_community,
                edge_types=edge_type_list
            )
            
            return {
                "query_type": "community_bridges",
                "community_id_1": community_id_1,
                "community_id_2": community_id_2,
                "total_bridges": len(bridges),
                "bridges": [
                    {
                        "source_name": b["source"].name,
                        "source_file": b["source"].file_path,
                        "target_name": b["target"].name,
                        "target_file": b["target"].file_path,
                        "edge_type": b["edge_type"]
                    }
                    for b in bridges[:20]  # Giới hạn 20 kết quả
                ]
            }
        
        else:
            return {"error": f"Unknown query_type: {query_type}. Supported types: k_hop, shortest_path, community_bridges"}
    
    except Exception as e:
        return {"error": f"Query failed: {str(e)}"}

# ==================== MAIN ====================

def main():
    """Chạy MCP server."""
    mcp.run()

if __name__ == "__main__":
    main()