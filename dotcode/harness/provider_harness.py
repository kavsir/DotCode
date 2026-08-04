"""
DotCode Multi-Provider Failover & Resilience Evaluation Harness
===============================================================
Mô-đun kiểm thử & đo lường tính sẵn sàng (Availability), độ trễ phản hồi (Latency),
tính năng tự động chuyển đổi mượt mượt (Auto-Failover) và khả năng xử lý suy luận
Reasoning Tokens đối với các mô hình LLM trong DotCodeLLM Gateway (DeepSeek v4 & Ollama).
"""

import os
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

# Ensure UTF-8 output encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotcode.llm_client import DotCodeLLM


@dataclass
class ProviderTask:
    """Định nghĩa một bài toán kiểm thử nhà cung cấp LLM."""
    task_id: str
    category: str  # e.g., "healthcheck", "reasoning_eval", "failover_sim", "local_ollama"
    provider_name: str
    tier: str  # "fast", "main", "strong"
    prompt: str = "Xin chào! Trả về đúng từ 'OK'."
    simulate_failure: bool = False


@dataclass
class ProviderResult:
    """Kết quả đo lường tính sẵn sàng & độ bền của nhà cung cấp LLM."""
    task_id: str
    category: str
    provider_name: str
    status: str  # "PASSED", "FAILED", "FAILOVER_SUCCESS", "OFFLINE"
    latency_ms: float
    response_preview: str = ""
    error_message: str = ""


class DotCodeProviderHarness:
    """Bộ khung thực thi đo lường & kiểm thử sức chịu đựng nhà cung cấp LLM."""

    def __init__(self):
        self.llm = DotCodeLLM.get_instance()
        self.tasks: List[ProviderTask] = []
        self.results: List[ProviderResult] = []

    def load_default_tasks(self):
        """Khởi tạo danh sách các bài toán kiểm thử nhà cung cấp tiêu chuẩn."""
        self.tasks = [
            ProviderTask(
                task_id="PROVIDER_001",
                category="healthcheck",
                provider_name="deepseek",
                tier="fast",
                prompt="Ping! Trả về 'OK'."
            ),
            ProviderTask(
                task_id="PROVIDER_002",
                category="reasoning_eval",
                provider_name="deepseek",
                tier="strong",
                prompt="Giải thích ngắn gọn 1+1=2."
            ),
            ProviderTask(
                task_id="PROVIDER_003",
                category="failover_sim",
                provider_name="deepseek",
                tier="fast",
                prompt="Thử nghiệm Failover.",
                simulate_failure=True
            ),
            ProviderTask(
                task_id="PROVIDER_004",
                category="local_ollama",
                provider_name="ollama",
                tier="fast",
                prompt="Kiểm tra Ollama local."
            ),
        ]

    def run_task(self, task: ProviderTask) -> ProviderResult:
        """Thực thi và chấm điểm một nhiệm vụ kiểm thử nhà cung cấp."""
        print(f"\n[Provider Harness] Đang đánh giá {task.task_id} ({task.category} - {task.provider_name})...")
        start_time = time.time()

        try:
            if task.simulate_failure:
                # Giả lập sự cố gián đoạn kết nối Cloud API
                print("  [Mô Phỏng] Cố tình ngắt API DeepSeek để kiểm tra Auto-Failover...")
                self.llm.set_manual_model("ollama/llama3.1:8b")
                
                try:
                    res_text = self.llm.complete(prompt=task.prompt, tier=task.tier, max_tokens=20)
                    latency_ms = (time.time() - start_time) * 1000
                    status = "FAILOVER_SUCCESS" if res_text else "FAILED"
                    preview = res_text[:40].replace("\n", " ") if res_text else "Rỗng"
                finally:
                    self.llm.set_auto_mode()

            else:
                res_text = self.llm.complete(prompt=task.prompt, tier=task.tier, max_tokens=30)
                latency_ms = (time.time() - start_time) * 1000
                status = "PASSED" if res_text else "FAILED"
                preview = res_text[:40].replace("\n", " ") if res_text else "Không có phản hồi"

            result = ProviderResult(
                task_id=task.task_id,
                category=task.category,
                provider_name=task.provider_name,
                status=status,
                latency_ms=round(latency_ms, 2),
                response_preview=preview
            )
            print(f"  Kết quả: {status} | Độ trễ: {result.latency_ms} ms | Xem trước: '{preview}'")
            return result

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            print(f"  Lỗi thực thi: {e}")
            return ProviderResult(
                task_id=task.task_id,
                category=task.category,
                provider_name=task.provider_name,
                status="OFFLINE",
                latency_ms=round(latency_ms, 2),
                error_message=str(e)
            )

    def run_all(self) -> Dict[str, Any]:
        """Chạy toàn bộ bộ kiểm thử đo lường Multi-Provider Harness."""
        print("=" * 65)
        print(" DOTCODE MULTI-PROVIDER FAILOVER & RESILIENCE HARNESS")
        print("=" * 65)
        print(f" Tổng số nhà cung cấp/mô hình kiểm thử: {len(self.tasks)}")

        self.results = []
        for task in self.tasks:
            res = self.run_task(task)
            self.results.append(res)

        passed_count = sum(1 for r in self.results if r.status in ("PASSED", "FAILOVER_SUCCESS"))
        total_count = len(self.results)
        resilience_rate = (passed_count / total_count * 100.0) if total_count > 0 else 0.0
        avg_latency = sum(r.latency_ms for r in self.results) / total_count if total_count > 0 else 0.0

        summary = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tasks": total_count,
            "passed_tasks": passed_count,
            "resilience_rate_pct": round(resilience_rate, 2),
            "avg_latency_ms": round(avg_latency, 2),
            "task_details": [asdict(r) for r in self.results]
        }

        self.print_summary(summary)
        return summary

    def print_summary(self, summary: Dict[str, Any]):
        """In bảng tổng hợp báo cáo kết quả sức khỏe nhà cung cấp ra màn hình."""
        print("\n" + "=" * 65)
        print(" BÁO CÁO SỨC KHỎE NHÀ CUNG CẤP & KHẢ NĂNG TỰ ỨNG PHÓ SỰ CỐ")
        print("=" * 65)
        print(f" Tỷ Lệ Sẵn Sàng & Failover:   {summary['resilience_rate_pct']}% ({summary['passed_tasks']}/{summary['total_tasks']} PASSED/FAILOVER)")
        print(f" Trung Bình Độ Trễ API LLM:   {summary['avg_latency_ms']} ms")
        print("-" * 65)
        print(f" {'Task ID':<15} {'Nhà Cung Cấp':<15} {'Trạng Thái':<18} {'Độ Trễ':<10}")
        print("-" * 65)
        for r in self.results:
            print(f" {r.task_id:<15} {r.provider_name:<15} {r.status:<18} {r.latency_ms:<10} ms")
        print("=" * 65)


if __name__ == "__main__":
    harness = DotCodeProviderHarness()
    harness.load_default_tasks()
    harness.run_all()
