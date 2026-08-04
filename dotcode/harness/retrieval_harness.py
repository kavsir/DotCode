"""
DotCode Context & RAG Retrieval Evaluation Harness
==================================================
Mô-đun đánh giá & đo lường chất lượng truy xuất ngữ cảnh (Context Recall, Precision),
hiệu quả nén tiết kiệm token (>80%) và độ trễ của bộ tìm kiếm RAG kép (Code Graph + GraphRAG).
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
from dotcode.context_pruner import ContextPruner


@dataclass
class RetrievalTask:
    """Định nghĩa một bài toán đánh giá truy xuất ngữ cảnh."""
    task_id: str
    category: str  # e.g., "symbol_search", "semantic_rag", "context_pruning", "multi_hop"
    query: str
    ground_truth_symbols: List[str] = field(default_factory=list)
    ground_truth_files: List[str] = field(default_factory=list)


@dataclass
class RetrievalResult:
    """Kết quả đo lường của một bài toán truy xuất."""
    task_id: str
    category: str
    status: str  # "PASSED", "FAILED", "ERROR"
    recall_pct: float
    precision_pct: float
    compression_ratio_pct: float
    latency_ms: float
    retrieved_count: int
    ground_truth_count: int
    error_message: str = ""


class DotCodeRetrievalHarness:
    """Bộ khung thực thi đo lường RAG Retrieval & Context Pruning cho DotCode."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = os.path.abspath(workspace_root)
        self.code_graph = CodeGraph(self.workspace_root)
        self.context_pruner = ContextPruner()
        self.tasks: List[RetrievalTask] = []
        self.results: List[RetrievalResult] = []

    def load_default_tasks(self):
        """Khởi tạo danh sách các bài toán truy xuất tiêu chuẩn."""
        self.tasks = [
            RetrievalTask(
                task_id="RETRIEVAL_001",
                category="symbol_search",
                query="CodeGraph",
                ground_truth_symbols=["CodeGraph"],
                ground_truth_files=["dotcode/graph/__init__.py"]
            ),
            RetrievalTask(
                task_id="RETRIEVAL_002",
                category="semantic_rag",
                query="ContextPruner",
                ground_truth_symbols=["ContextPruner"],
                ground_truth_files=["dotcode/context_pruner.py"]
            ),
            RetrievalTask(
                task_id="RETRIEVAL_003",
                category="context_pruning",
                query="prune_messages",
                ground_truth_symbols=["prune_messages"],
                ground_truth_files=["dotcode/context_pruner.py"]
            ),
            RetrievalTask(
                task_id="RETRIEVAL_004",
                category="multi_hop",
                query="MultiHopEngine",
                ground_truth_symbols=["MultiHopEngine"],
                ground_truth_files=["dotcode/graph/multi_hop.py"]
            ),
        ]

    def run_task(self, task: RetrievalTask) -> RetrievalResult:
        """Thực thi và chấm điểm một nhiệm vụ truy xuất ngữ cảnh."""
        print(f"\n[Retrieval Harness] Đang đánh giá {task.task_id} ({task.category})...")
        start_time = time.time()

        try:
            # 1. Tìm kiếm symbol từ Code Graph
            retrieved_symbols = self.code_graph.search(task.query, limit=10)
            retrieved_names = [
                s.name if hasattr(s, "name") else s.get("name", "")
                for s in retrieved_symbols
            ]

            latency_ms = (time.time() - start_time) * 1000

            # 2. Tính chỉ số Context Recall
            found_count = 0
            for gt in task.ground_truth_symbols:
                if any(gt.lower() in r.lower() for r in retrieved_names):
                    found_count += 1

            total_gt = len(task.ground_truth_symbols)
            recall_pct = (found_count / total_gt * 100.0) if total_gt > 0 else 100.0

            # 3. Tính chỉ số Context Precision
            total_retrieved = len(retrieved_symbols)
            precision_pct = (found_count / total_retrieved * 100.0) if total_retrieved > 0 else 100.0

            # 4. Kiểm thử tỷ lệ nén ContextPruner
            fake_history = [
                {"role": "user" if i % 2 == 0 else "assistant", "content": f"Nội dung tin nhắn thử nghiệm số {i} liên quan tới {task.query}"}
                for i in range(40)
            ]
            pruned_msgs = self.context_pruner.prune_messages(fake_history, task.query)
            compression_pct = ((len(fake_history) - len(pruned_msgs)) / len(fake_history) * 100.0) if len(fake_history) > 0 else 0.0

            status = "PASSED" if recall_pct >= 80.0 else "FAILED"

            res = RetrievalResult(
                task_id=task.task_id,
                category=task.category,
                status=status,
                recall_pct=round(recall_pct, 2),
                precision_pct=round(precision_pct, 2),
                compression_ratio_pct=round(compression_pct, 2),
                latency_ms=round(latency_ms, 2),
                retrieved_count=total_retrieved,
                ground_truth_count=total_gt
            )
            print(f"  Kết quả: {status} | Recall: {res.recall_pct}% | Precision: {res.precision_pct}% | Tỷ lệ nén: {res.compression_ratio_pct}% | Độ trễ: {res.latency_ms} ms")
            return res

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            print(f"  Lỗi thực thi: {e}")
            return RetrievalResult(
                task_id=task.task_id,
                category=task.category,
                status="ERROR",
                recall_pct=0.0,
                precision_pct=0.0,
                compression_ratio_pct=0.0,
                latency_ms=round(latency_ms, 2),
                retrieved_count=0,
                ground_truth_count=len(task.ground_truth_symbols),
                error_message=str(e)
            )

    def run_all(self) -> Dict[str, Any]:
        """Chạy toàn bộ bộ kiểm thử đo lường RAG Retrieval Harness."""
        print("=" * 65)
        print(" DOTCODE CONTEXT & RAG RETRIEVAL EVALUATION HARNESS")
        print("=" * 65)
        print(f" Tổng số bài toán kiểm thử: {len(self.tasks)}")

        self.results = []
        for task in self.tasks:
            res = self.run_task(task)
            self.results.append(res)

        passed_count = sum(1 for r in self.results if r.status == "PASSED")
        total_count = len(self.results)
        avg_recall = sum(r.recall_pct for r in self.results) / total_count if total_count > 0 else 0.0
        avg_precision = sum(r.precision_pct for r in self.results) / total_count if total_count > 0 else 0.0
        avg_compression = sum(r.compression_ratio_pct for r in self.results) / total_count if total_count > 0 else 0.0
        avg_latency = sum(r.latency_ms for r in self.results) / total_count if total_count > 0 else 0.0

        summary = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tasks": total_count,
            "passed_tasks": passed_count,
            "avg_recall_pct": round(avg_recall, 2),
            "avg_precision_pct": round(avg_precision, 2),
            "avg_compression_pct": round(avg_compression, 2),
            "avg_latency_ms": round(avg_latency, 2),
            "task_details": [asdict(r) for r in self.results]
        }

        self.print_summary(summary)
        return summary

    def print_summary(self, summary: Dict[str, Any]):
        """In bảng tổng hợp báo cáo kết quả ra màn hình."""
        print("\n" + "=" * 65)
        print(" BÁO CÁO TỔNG HỢP KẾT QUẢ RETRIEVAL HARNESS")
        print("=" * 65)
        print(f" Trung bình Context Recall:    {summary['avg_recall_pct']}%")
        print(f" Trung bình Context Precision: {summary['avg_precision_pct']}%")
        print(f" Trung bình Tỷ lệ Nén Token:   {summary['avg_compression_pct']}%")
        print(f" Trung bình Độ Trễ Truy Xuất:  {summary['avg_latency_ms']} ms")
        print("-" * 65)
        print(f" {'Task ID':<15} {'Category':<18} {'Trạng Thái':<12} {'Recall %':<10} {'Latency':<10}")
        print("-" * 65)
        for r in self.results:
            print(f" {r.task_id:<15} {r.category:<18} {r.status:<12} {r.recall_pct:<10}% {r.latency_ms:<10} ms")
        print("=" * 65)


if __name__ == "__main__":
    harness = DotCodeRetrievalHarness()
    harness.load_default_tasks()
    harness.run_all()
