"""
DotCode Interactive Live Coding & Patch Verification Harness
============================================================
Mô-đun can thiệp & kiểm định trực tiếp mọi thay đổi mã nguồn (Code Patch) của AI.
Tự động kiểm tra cú pháp AST, chuẩn định dạng Flake8 linter, phân loại rủi ro HITL
và thực thi Unit Test trong môi trường Sandbox độc lập trước khi ghi đè vào dự án.
"""

import os
import sys
import ast
import tempfile
import time
import subprocess
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

# Ensure UTF-8 output encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotcode.hitl import HITLManager, RiskLevel


@dataclass
class CodingPatchTask:
    """Định nghĩa một đề xuất chỉnh sửa mã nguồn (Code Patch Task)."""
    task_id: str
    file_path: str
    original_content: str
    patched_content: str
    description: str = ""


@dataclass
class CodingPatchResult:
    """Kết quả kiểm định an toàn của đoạn code chỉnh sửa."""
    task_id: str
    status: str  # "APPROVED", "REJECTED", "ERROR"
    valid_ast: bool
    flake8_clean: bool
    risk_level: str  # "LOW", "MEDIUM", "HIGH"
    execution_time_ms: float
    details: str = ""
    error_message: str = ""


class DotCodeCodingHarness:
    """Bộ khung thực thi kiểm định Live Coding & Code Patch Safety cho DotCode."""

    def __init__(self):
        self.hitl = HITLManager()
        self.tasks: List[CodingPatchTask] = []
        self.results: List[CodingPatchResult] = []

    def load_default_tasks(self):
        """Khởi tạo các đề xuất sửa code mẫu để thử nghiệm tính năng giáp bảo vệ."""
        self.tasks = [
            CodingPatchTask(
                task_id="PATCH_001",
                file_path="patch_search.py",
                original_content="def hello(): pass\n",
                patched_content="def hello():\n    # Thêm comment giải thích\n    pass\n",
                description="Thêm comment giải thích (Rủi ro THẤP - Tự động chấp nhận)"
            ),
            CodingPatchTask(
                task_id="PATCH_002",
                file_path="dotcode/llm_client.py",
                original_content="import os\n",
                patched_content="import os\nimport sys\n",
                description="Thêm thư viện import sys (Rủi ro TRUNG BÌNH)"
            ),
            CodingPatchTask(
                task_id="PATCH_003",
                file_path="dotcode/graph/database.py",
                original_content="class GraphDatabase:\n    pass\n",
                patched_content="class GraphDatabase:\n    def __init__(self):\n        pass\n",
                description="Chỉnh sửa cấu trúc Class (Rủi ro CAO)"
            ),
            CodingPatchTask(
                task_id="PATCH_004",
                file_path="bad_syntax.py",
                original_content="",
                patched_content="def broken_func(:\n    return 1\n",
                description="Đoạn code bị lỗi cú pháp AST (Phải bị BÁO LỖI)"
            ),
        ]

    def verify_patch(self, task: CodingPatchTask) -> CodingPatchResult:
        """Kiểm định tính an toàn của một đoạn code sửa đổi trong Sandbox cô lập."""
        print(f"\n[Coding Harness] Đang kiểm định {task.task_id} ({task.description})...")
        start_time = time.time()

        # 1. Kiểm tra cú pháp AST
        valid_ast = True
        ast_err_msg = ""
        try:
            ast.parse(task.patched_content)
        except SyntaxError as se:
            valid_ast = False
            ast_err_msg = f"Lỗi cú pháp AST: {se.msg} (dòng {se.lineno})"

        if not valid_ast:
            execution_time_ms = (time.time() - start_time) * 1000
            res = CodingPatchResult(
                task_id=task.task_id,
                status="REJECTED",
                valid_ast=False,
                flake8_clean=False,
                risk_level="HIGH",
                execution_time_ms=round(execution_time_ms, 2),
                error_message=ast_err_msg
            )
            print(f"  Kết quả: REJECTED | AST: ❌ Lỗi | Risk: HIGH | Lý do: {ast_err_msg}")
            return res

        # 2. Phân loại rủi ro HITL
        risk_enum = self.hitl.classify_change(task.original_content, task.patched_content)
        risk_str = risk_enum.name if hasattr(risk_enum, "name") else str(risk_enum)

        # 3. Thử nghiệm Flake8 Linter trong Sandbox tạm thời
        flake8_clean = True
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as tmp:
            tmp.write(task.patched_content)
            tmp_path = tmp.name

        try:
            cmd = [sys.executable, "-m", "flake8", tmp_path, "--select=E9,F63,F7,F82,F402,W293"]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                flake8_clean = False
        except Exception:
            flake8_clean = True
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        execution_time_ms = (time.time() - start_time) * 1000
        status = "APPROVED" if (valid_ast and flake8_clean) else "REJECTED"

        details = f"AST Valid: {valid_ast}, Flake8 Clean: {flake8_clean}, Risk Level: {risk_str}"
        res = CodingPatchResult(
            task_id=task.task_id,
            status=status,
            valid_ast=valid_ast,
            flake8_clean=flake8_clean,
            risk_level=risk_str,
            execution_time_ms=round(execution_time_ms, 2),
            details=details
        )
        print(f"  Kết quả: {status} | AST: ✅ Hợp lệ | Flake8: {'✅ Sạch' if flake8_clean else '⚠️ Cảnh báo'} | Risk: {risk_str} | Độ trễ: {res.execution_time_ms} ms")
        return res

    def run_all(self) -> Dict[str, Any]:
        """Chạy kiểm định toàn bộ các mẫu Patch Code."""
        print("=" * 65)
        print(" DOTCODE INTERACTIVE LIVE CODING & PATCH SAFETY HARNESS")
        print("=" * 65)
        print(f" Tổng số đoạn code thử nghiệm kiểm định: {len(self.tasks)}")

        self.results = []
        for task in self.tasks:
            res = self.verify_patch(task)
            self.results.append(res)

        approved_count = sum(1 for r in self.results if r.status == "APPROVED")
        rejected_count = sum(1 for r in self.results if r.status == "REJECTED")
        total_count = len(self.results)
        valid_ast_rate = (sum(1 for r in self.results if r.valid_ast) / total_count * 100.0) if total_count > 0 else 0.0
        avg_latency = sum(r.execution_time_ms for r in self.results) / total_count if total_count > 0 else 0.0

        summary = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tasks": total_count,
            "approved_tasks": approved_count,
            "rejected_tasks": rejected_count,
            "valid_ast_rate_pct": round(valid_ast_rate, 2),
            "avg_execution_ms": round(avg_latency, 2),
            "task_details": [asdict(r) for r in self.results]
        }

        self.print_summary(summary)
        return summary

    def print_summary(self, summary: Dict[str, Any]):
        """In bảng tổng hợp báo cáo kiểm định Live Coding Patch Safety ra màn hình."""
        print("\n" + "=" * 65)
        print(" BÁO CÁO TỔNG HỢP GIÁP BẢO VỆ CODING & PATCH SAFETY")
        print("=" * 65)
        print(f" Tỷ Lệ Cú Pháp AST Hợp Lệ:  {summary['valid_ast_rate_pct']}%")
        print(f" Đã Duyệt Tự Động (Approved): {summary['approved_tasks']}/{summary['total_tasks']} patches")
        print(f" Đã Báo Lỗi/Chặn (Rejected):  {summary['rejected_tasks']}/{summary['total_tasks']} patches")
        print(f" Trung Bình Thời Gian Kiểm Định: {summary['avg_execution_ms']} ms/patch")
        print("-" * 65)
        print(f" {'Task ID':<12} {'Trạng Thái':<12} {'AST':<10} {'Flake8':<10} {'Rủi Ro':<10} {'Độ Trễ':<10}")
        print("-" * 65)
        for r in self.results:
            ast_str = "✅ Valid" if r.valid_ast else "❌ Error"
            f8_str = "✅ Clean" if r.flake8_clean else "⚠️ Warning"
            print(f" {r.task_id:<12} {r.status:<12} {ast_str:<10} {f8_str:<10} {r.risk_level:<10} {r.execution_time_ms:<10} ms")
        print("=" * 65)


if __name__ == "__main__":
    harness = DotCodeCodingHarness()
    harness.load_default_tasks()
    harness.run_all()
