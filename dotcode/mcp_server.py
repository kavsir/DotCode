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

# ==================== MAIN ====================

def main():
    """Chạy MCP server."""
    mcp.run()

if __name__ == "__main__":
    main()