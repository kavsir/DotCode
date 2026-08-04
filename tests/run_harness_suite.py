"""
DotCode Master Harness Suite Runner
===================================
Bộ nhà điều phối trung tâm (Master Orchestrator) tự động kích hoạt
và tổng hợp báo cáo của toàn bộ 4 bộ khung Harness trong dự án DotCode:
1. Task Evaluation Harness (Pass@1 Resolution Rate)
2. Context & RAG Retrieval Harness (Context Recall & Compression Ratio)
3. Multi-Provider Failover & Resilience Harness (API Health & Failover Rate)
4. FastMCP Server & Tool Integration Harness (Schema Validation Rate)
"""

import sys
import time
from typing import Dict, Any

# Ensure UTF-8 output encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from tests.harness.eval_harness import DotCodeEvalHarness
from dotcode.harness import (
    DotCodeRetrievalHarness,
    DotCodeProviderHarness,
    DotCodeMCPHarness,
)


def run_master_harness_suite() -> Dict[str, Any]:
    """Chạy toàn bộ 4 bộ Harness và tổng hợp báo cáo Master Scorecard."""
    start_time = time.time()

    print("=" * 70)
    print(" 👑 DOTCODE MASTER HARNESS SUITE - EXECUTIVE DASHBOARD")
    print("=" * 70)

    # 1. Run Task Evaluation Harness
    eval_harness = DotCodeEvalHarness()
    eval_harness.load_default_suite()
    eval_summary = eval_harness.run_all()

    # 2. Run Context & RAG Retrieval Harness
    retrieval_harness = DotCodeRetrievalHarness()
    retrieval_harness.load_default_tasks()
    retrieval_summary = retrieval_harness.run_all()

    # 3. Run Multi-Provider Harness
    provider_harness = DotCodeProviderHarness()
    provider_harness.load_default_tasks()
    provider_summary = provider_harness.run_all()

    # 4. Run FastMCP Server Harness
    mcp_harness = DotCodeMCPHarness()
    mcp_harness.load_default_tasks()
    mcp_summary = mcp_harness.run_all()

    total_duration_s = time.time() - start_time

    # 5. Build Master Scorecard Summary
    master_summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_duration_s": round(total_duration_s, 2),
        "task_eval_pass_at_1": eval_summary["pass_at_1_rate"],
        "retrieval_context_recall": retrieval_summary["avg_recall_pct"],
        "retrieval_token_compression": retrieval_summary["avg_compression_pct"],
        "provider_resilience_rate": provider_summary["resilience_rate_pct"],
        "mcp_schema_valid_rate": mcp_summary["schema_valid_rate_pct"],
    }

    print_master_scorecard(master_summary)
    return master_summary


def print_master_scorecard(summary: Dict[str, Any]):
    """In bảng tổng hợp Master Scorecard Dashboard ra màn hình."""
    print("\n" + "=" * 70)
    print(" 🏆 BÁO CÁO ĐÁNH GIÁ CHẤT LƯỢNG TỔNG THỂ (MASTER SCORECARD)")
    print("=" * 70)
    print(f" Thời Gian Hoàn Thành Toàn Bộ Suite: {summary['total_duration_s']} giây")
    print("-" * 70)
    print(f" 1. Task Evaluation (SWE-bench Lite):    {summary['task_eval_pass_at_1']}% Pass@1 Rate")
    print(f" 2. Context & RAG Retrieval:             {summary['retrieval_context_recall']}% Context Recall")
    print(f" 3. Context Pruner Compression:          {summary['retrieval_token_compression']}% Token Saved")
    print(f" 4. Multi-Provider API Resilience:       {summary['provider_resilience_rate']}% Available & Failover")
    print(f" 5. FastMCP Server & Tools Validation:   {summary['mcp_schema_valid_rate']}% Schema Passed")
    print("-" * 70)
    
    # Calculate Overall Master Score
    overall_score = (
        summary["task_eval_pass_at_1"]
        + summary["retrieval_context_recall"]
        + summary["provider_resilience_rate"]
        + summary["mcp_schema_valid_rate"]
    ) / 4.0

    print(f" 🌟 ĐIỂM CHẤT LƯỢNG TỔNG THỂ (MASTER GRADE): {round(overall_score, 2)} / 100.0%")
    print("=" * 70)


if __name__ == "__main__":
    run_master_harness_suite()
