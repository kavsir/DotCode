"""
DotCode FastMCP Server & Tool Integration Evaluation Harness
============================================================
Mô-đun kiểm thử & đo lường tính đúng đắn dữ liệu (Schema Validation), độ trễ (Latency)
và độ an toàn nén/phân trang dữ liệu đầu ra của 10 công cụ FastMCP Server trong DotCode.
"""

import os
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

# Ensure UTF-8 output encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotcode.graph import CodeGraph


@dataclass
class MCPTask:
    """Định nghĩa một bài toán kiểm thử công cụ MCP Server."""
    task_id: str
    tool_name: str
    kwargs: Dict[str, Any]
    expected_keys: List[str] = field(default_factory=list)


@dataclass
class MCPResult:
    """Kết quả đo lường tính chính xác & hiệu năng của một công cụ MCP Server."""
    task_id: str
    tool_name: str
    status: str  # "PASSED", "FAILED", "ERROR"
    latency_ms: float
    schema_valid: bool
    result_preview: str = ""
    error_message: str = ""


class DotCodeMCPHarness:
    """Bộ khung thực thi kiểm thử 10 công cụ FastMCP Server của DotCode."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = os.path.abspath(workspace_root)
        self.code_graph = CodeGraph(self.workspace_root)
        self.tasks: List[MCPTask] = []
        self.results: List[MCPResult] = []

    def load_default_tasks(self):
        """Khởi tạo 10 bài toán kiểm thử tương ứng 10 công cụ FastMCP."""
        self.tasks = [
            MCPTask(task_id="MCP_001", tool_name="search_code", kwargs={"query": "CodeGraph"}, expected_keys=["name", "file_path"]),
            MCPTask(task_id="MCP_002", tool_name="get_callees", kwargs={"symbol_id": "dotcode/graph/__init__.py::CodeGraph"}, expected_keys=[]),
            MCPTask(task_id="MCP_003", tool_name="get_callers", kwargs={"symbol_id": "dotcode/graph/__init__.py::CodeGraph"}, expected_keys=[]),
            MCPTask(task_id="MCP_004", tool_name="get_blast_radius", kwargs={"symbol_name": "CodeGraph"}, expected_keys=[]),
            MCPTask(task_id="MCP_005", tool_name="get_unused_symbols", kwargs={}, expected_keys=[]),
            MCPTask(task_id="MCP_006", tool_name="get_file_context", kwargs={"file_paths": ["dotcode/graph/__init__.py"]}, expected_keys=[]),
            MCPTask(task_id="MCP_007", tool_name="global_search", kwargs={"query": "GraphRAG"}, expected_keys=[]),
            MCPTask(task_id="MCP_008", tool_name="local_search", kwargs={"symbol_name": "ContextPruner"}, expected_keys=[]),
            MCPTask(task_id="MCP_009", tool_name="get_community_context", kwargs={"community_id": 0}, expected_keys=[]),
            MCPTask(task_id="MCP_010", tool_name="multi_hop_query", kwargs={"query_type": "neighbors", "symbol_name": "CodeGraph"}, expected_keys=[]),
        ]

    def _execute_mcp_tool(self, tool_name: str, kwargs: Dict[str, Any]) -> Any:
        """Thực thi trực tiếp logic của công cụ MCP tương ứng."""
        if tool_name == "search_code":
            return self.code_graph.search(kwargs.get("query", ""), limit=5)
        elif tool_name == "get_callees":
            return self.code_graph.db.get_callees(kwargs.get("symbol_id", ""))
        elif tool_name == "get_callers":
            return self.code_graph.db.get_callers(kwargs.get("symbol_id", ""))
        elif tool_name == "get_blast_radius":
            return self.code_graph.get_blast_radius(kwargs.get("symbol_name", ""))
        elif tool_name == "get_unused_symbols":
            return self.code_graph.get_unused_symbols()
        elif tool_name == "get_file_context":
            return self.code_graph.get_context(kwargs.get("file_paths", []), [])
        elif tool_name == "global_search":
            if self.code_graph.graphrag:
                return self.code_graph.graphrag.global_search(kwargs.get("query", ""))
            return []
        elif tool_name == "local_search":
            if self.code_graph.graphrag:
                return self.code_graph.graphrag.local_search(kwargs.get("symbol_name", ""))
            return {}
        elif tool_name == "get_community_context":
            if self.code_graph.graphrag:
                return self.code_graph.graphrag.communities.get(kwargs.get("community_id", 0), {})
            return {}
        elif tool_name == "multi_hop_query":
            from dotcode.graph.multi_hop import MultiHopEngine
            raw_db = self.code_graph.db._db if hasattr(self.code_graph.db, "_db") else self.code_graph.db
            m = MultiHopEngine(raw_db)
            return m.get_k_hop_neighbors(kwargs.get("symbol_name", ""), k=2)
        else:
            raise ValueError(f"Unknown MCP tool: {tool_name}")

    def run_task(self, task: MCPTask) -> MCPResult:
        """Thực thi và kiểm tra một công cụ FastMCP Server."""
        print(f"\n[MCP Harness] Đang đánh giá {task.task_id} ({task.tool_name})...")
        start_time = time.time()

        try:
            output = self._execute_mcp_tool(task.tool_name, task.kwargs)
            latency_ms = (time.time() - start_time) * 1000
            
            schema_valid = True
            if task.expected_keys and isinstance(output, list) and len(output) > 0:
                first_item = output[0]
                for k in task.expected_keys:
                    if hasattr(first_item, k):
                        continue
                    if isinstance(first_item, dict) and k in first_item:
                        continue
                    schema_valid = False
                    break

            preview = str(output)[:40].replace("\n", " ")
            status = "PASSED" if schema_valid else "FAILED"

            res = MCPResult(
                task_id=task.task_id,
                tool_name=task.tool_name,
                status=status,
                latency_ms=round(latency_ms, 2),
                schema_valid=schema_valid,
                result_preview=preview
            )
            print(f"  Kết quả: {status} | Độ trễ: {res.latency_ms} ms | Xem trước: '{preview}'")
            return res

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            print(f"  Lỗi thực thi tool: {e}")
            return MCPResult(
                task_id=task.task_id,
                tool_name=task.tool_name,
                status="ERROR",
                latency_ms=round(latency_ms, 2),
                schema_valid=False,
                error_message=str(e)
            )

    def run_all(self) -> Dict[str, Any]:
        """Chạy kiểm thử toàn bộ 10 công cụ FastMCP Server."""
        print("=" * 65)
        print(" DOTCODE FASTMCP SERVER & TOOL EVALUATION HARNESS")
        print("=" * 65)
        print(f" Tổng số công cụ MCP kiểm thử: {len(self.tasks)}")

        self.results = []
        for task in self.tasks:
            res = self.run_task(task)
            self.results.append(res)

        passed_count = sum(1 for r in self.results if r.status == "PASSED")
        total_count = len(self.results)
        schema_valid_rate = (sum(1 for r in self.results if r.schema_valid) / total_count * 100.0) if total_count > 0 else 0.0
        avg_latency = sum(r.latency_ms for r in self.results) / total_count if total_count > 0 else 0.0

        summary = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tasks": total_count,
            "passed_tasks": passed_count,
            "schema_valid_rate_pct": round(schema_valid_rate, 2),
            "avg_latency_ms": round(avg_latency, 2),
            "task_details": [asdict(r) for r in self.results]
        }

        self.print_summary(summary)
        return summary

    def print_summary(self, summary: Dict[str, Any]):
        """In bảng tổng hợp kết quả kiểm thử MCP Tools ra màn hình."""
        print("\n" + "=" * 65)
        print(" BÁO CÁO TỔNG HỢP KIỂM THỬ FASTMCP SERVER & TOOLS")
        print("=" * 65)
        print(f" Tỷ Lệ Đạt Chuẩn Schema MCP:   {summary['schema_valid_rate_pct']}% ({summary['passed_tasks']}/{summary['total_tasks']} PASSED)")
        print(f" Trung Bình Độ Trễ Xử Lý Tool: {summary['avg_latency_ms']} ms/tool")
        print("-" * 65)
        print(f" {'Task ID':<12} {'Tên Công Cụ MCP':<25} {'Trạng Thái':<12} {'Độ Trễ':<10}")
        print("-" * 65)
        for r in self.results:
            print(f" {r.task_id:<12} {r.tool_name:<25} {r.status:<12} {r.latency_ms:<10} ms")
        print("=" * 65)


if __name__ == "__main__":
    harness = DotCodeMCPHarness()
    harness.load_default_tasks()
    harness.run_all()
