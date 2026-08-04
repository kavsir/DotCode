"""
DotCode Benchmark Suite
Đo lường hiệu năng của các thành phần cốt lõi trong DotCode:
1. Indexer & Tree-sitter AST Parsing Speed
2. Database Read/Write Throughput (SQLite)
3. PageRank Graph Metrics Calculation Speed
4. Multi-Hop & Blast Radius Query Latency
5. Context Pruner Speed & Token Reduction Efficiency
6. Hybrid Embedder Latency & Embedding Throughput
"""

import time
import os
import sys
import tempfile
import numpy as np
from typing import List, Dict

# Ensure UTF-8 output encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotcode.graph import CodeGraph
from dotcode.context_pruner import ContextPruner
from dotcode.llm_client import HybridEmbedder, DotCodeLLM


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f" BENCHMARK: {title}")
    print("=" * 60)


def benchmark_indexer():
    print_header("1. Indexer & Tree-sitter AST Parsing Speed")
    
    tmpdir = tempfile.mkdtemp()
    try:
        cg = CodeGraph(root=tmpdir)
        
        # Create synthetic files for Python, JS, TS, Go, Rust
        py_code = """
class DataProcessor:
    def __init__(self, name):
        self.name = name

    def process(self, data):
        res = self.clean(data)
        return self.save(res)

    def clean(self, data):
        return [x.strip() for x in data if x]

    def save(self, data):
        print("Saving:", data)
        return True

def standalone_helper(x):
    return x * 2
"""
        js_code = """
class ServiceClient {
    constructor(url) {
        this.url = url;
    }

    async fetchData() {
        const raw = await fetch(this.url);
        return this.parseJSON(raw);
    }

    parseJSON(raw) {
        return JSON.parse(raw);
    }
}
function helper(a, b) { return a + b; }
"""
        go_code = """
package main

import "fmt"

type Server struct {
    Port int
}

func (s *Server) Start() {
    fmt.Println("Server starting on port", s.Port)
    s.handleRequests()
}

func (s *Server) handleRequests() {
    fmt.Println("Handling...")
}
"""
        files = []
        # Create 15 files of each type (45 files total)
        for i in range(15):
            py_f = os.path.join(tmpdir, f"file_{i}.py")
            js_f = os.path.join(tmpdir, f"file_{i}.js")
            go_f = os.path.join(tmpdir, f"file_{i}.go")
            
            with open(py_f, "w", encoding="utf-8") as f:
                f.write(py_code)
            with open(js_f, "w", encoding="utf-8") as f:
                f.write(js_code)
            with open(go_f, "w", encoding="utf-8") as f:
                f.write(go_code)
                
            files.extend([py_f, js_f, go_f])

        start_time = time.perf_counter()
        for fpath in files:
            cg.indexer.index_file(fpath)
        elapsed = time.perf_counter() - start_time

        symbols = cg.db._db.conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        edges = cg.db._db.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

        print(f"  Indexed Files:      {len(files)} files")
        print(f"  Parsed Symbols:     {symbols} symbols")
        print(f"  Generated Edges:    {edges} edges")
        print(f"  Total Time:         {elapsed:.4f} seconds")
        print(f"  Parsing Speed:      {len(files) / elapsed:.2f} files/sec ({symbols / elapsed:.2f} symbols/sec)")

        cg.db._db.conn.close()
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def benchmark_pagerank_and_graph_queries():
    print_header("2. PageRank & Multi-Hop Graph Query Latency")
    
    tmpdir = tempfile.mkdtemp()
    try:
        cg = CodeGraph(root=tmpdir)
        
        # Populate DB with synthetic graph nodes
        symbols = []
        edges = []
        num_nodes = 500
        
        for i in range(num_nodes):
            symbols.append({
                "id": f"src/module_{i % 10}.py::func_{i}",
                "file_path": f"src/module_{i % 10}.py",
                "name": f"func_{i}",
                "kind": "function" if i % 2 == 0 else "method",
                "signature": f"func_{i}()",
                "body_hash": "hash123",
                "start_line": i * 10,
                "end_line": i * 10 + 9
            })
            
        # Connect nodes in a ring + cross edges
        for i in range(num_nodes):
            tgt = (i + 1) % num_nodes
            edges.append({
                "source_id": symbols[i]["id"],
                "target_id": symbols[tgt]["id"],
                "type": "calls",
                "weight": 1.0
            })
            if i % 5 == 0:
                random_tgt = (i * 7) % num_nodes
                edges.append({
                    "source_id": symbols[i]["id"],
                    "target_id": symbols[random_tgt]["id"],
                    "type": "calls",
                    "weight": 2.0
                })

        cg.db._db.replace_symbols("src/module_all.py", symbols)
        cg.db._db.replace_edges("src/module_all.py", edges)

        # 1. PageRank Benchmark
        start_time = time.perf_counter()
        cg._compute_pagerank()
        pr_elapsed = time.perf_counter() - start_time
        print(f"  PageRank Computation (500 nodes, 600 edges): {pr_elapsed * 1000:.2f} ms")

        # 2. Blast Radius Benchmark
        start_time = time.perf_counter()
        for _ in range(100):
            cg.db.get_blast_radius("src/module_0.py::func_0", max_depth=3)
        br_elapsed = (time.perf_counter() - start_time) / 100
        print(f"  Blast Radius Query (depth=3, avg over 100 runs): {br_elapsed * 1000:.3f} ms/query")

        from dotcode.graph.multi_hop import MultiHopEngine
        multi_hop = MultiHopEngine(cg.db._db)
        start_time = time.perf_counter()
        for _ in range(100):
            multi_hop.get_k_hop_neighbors("src/module_0.py::func_0", k=2)
        mh_elapsed = (time.perf_counter() - start_time) / 100
        print(f"  Multi-Hop Neighbors (k=2, avg over 100 runs):   {mh_elapsed * 1000:.3f} ms/query")

        cg.db._db.conn.close()
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def benchmark_context_pruner():
    print_header("3. Semantic Context Pruner Efficiency & Speed")
    
    pruner = ContextPruner(max_input_tokens=4000, keep_last_n=3)
    
    # Generate 50 realistic chat messages
    messages = []
    topics = ["login_system", "database_migration", "ui_button_style", "payment_gateway", "docker_deployment"]
    
    for i in range(50):
        topic = topics[i % len(topics)]
        messages.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Message {i}: Discussion about {topic}. Implementing feature {i} with detailed logic and parameters."
        })

    current_query = "Cần sửa lại lỗi nút đỏ trong ui_button_style"

    start_time = time.perf_counter()
    pruned = pruner.prune_messages(messages, current_query)
    prune_elapsed = time.perf_counter() - start_time

    original_tokens = pruner.estimate_tokens(messages)
    pruned_tokens = pruner.estimate_tokens(pruned)
    reduction = ((original_tokens - pruned_tokens) / original_tokens) * 100

    print(f"  Original History:   {len(messages)} messages ({original_tokens} tokens)")
    print(f"  Pruned Context:     {len(pruned)} messages ({pruned_tokens} tokens)")
    print(f"  Token Reduction:    {reduction:.1f}% saved")
    print(f"  Pruning Execution:  {prune_elapsed * 1000:.2f} ms")


def benchmark_embedder():
    print_header("4. Embedder Throughput & Mode")
    
    embedder = HybridEmbedder(local_model_name="all-MiniLM-L6-v2")
    active_mode = embedder.llm.get_embedding_model()
    print(f"  Active Embedder Mode: {active_mode}")

    sample_texts = [
        "def calculate_total(items): return sum(item.price for item in items)",
        "class DatabaseConnection: def connect(self): pass",
        "async function fetchUser(id) { return await api.get(`/users/${id}`); }",
        "type User struct { ID string; Name string }",
        "SELECT * FROM users WHERE active = true ORDER BY created_at DESC;"
    ] * 4  # 20 texts

    start_time = time.perf_counter()
    embeddings = embedder.encode(sample_texts)
    elapsed = time.perf_counter() - start_time

    print(f"  Batch Size:         {len(sample_texts)} code snippets")
    print(f"  Vector Dimension:   {embeddings.shape[1]}")
    print(f"  Total Time:         {elapsed * 1000:.2f} ms")
    print(f"  Embedding Speed:    {len(sample_texts) / elapsed:.2f} texts/sec")


def benchmark_accuracy():
    print_header("5. Accuracy & Precision Metrics Evaluation")
    
    # --- 1. AST Symbol & Call Edge Extraction Accuracy ---
    tmpdir = tempfile.mkdtemp()
    try:
        cg = CodeGraph(root=tmpdir)
        test_file = os.path.join(tmpdir, "app.py")
        code_content = """
class DatabaseManager:
    def connect(self):
        self.authenticate()

    def authenticate(self):
        pass

    def query(self, sql):
        self.connect()
        return []

def standalone_processor():
    db = DatabaseManager()
    db.query("SELECT 1")
"""
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(code_content)

        cg.indexer.index_file(test_file)
        
        # Ground truths
        expected_symbols = {"DatabaseManager", "connect", "authenticate", "query", "standalone_processor"}
        extracted_raw = cg.db._db.conn.execute("SELECT name FROM symbols").fetchall()
        extracted_symbols = {r[0] for r in extracted_raw}

        symbol_accuracy = (len(extracted_symbols.intersection(expected_symbols)) / len(expected_symbols)) * 100
        print(f"  [AST Symbol Extraction] Accuracy:  {symbol_accuracy:.1f}% ({len(extracted_symbols)}/{len(expected_symbols)} symbols)")

        extracted_edges = cg.db._db.conn.execute("SELECT COUNT(*) FROM edges WHERE type='calls'").fetchone()[0]
        print(f"  [Call Edge Extraction] Edges Found: {extracted_edges} call relationships")

        cg.db._db.conn.close()
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    # --- 2. Intent Agent Classification Accuracy ---
    try:
        from dotcode.agents.intent_agent import IntentAgent
        agent = IntentAgent()
        
        test_cases = [
            ("hàm connect làm gì?", "question"),
            ("tìm tất cả class có chứa Database", "search"),
            ("thêm docstring cho class DatabaseManager", "edit"),
            ("cho tôi xem cấu trúc kiến trúc dự án", "architecture"),
            ("what does DatabaseManager do?", "question"),
            ("find all functions calling query", "search"),
            ("refactor the connect function", "edit"),
            ("dự án được chia thành những module nào?", "architecture"),
        ]

        correct_intents = 0
        for query, expected_intent in test_cases:
            intent, confidence = agent.classify(query)
            if intent == expected_intent:
                correct_intents += 1

        intent_accuracy = (correct_intents / len(test_cases)) * 100
        print(f"  [Intent Classification] Accuracy:  {intent_accuracy:.1f}% ({correct_intents}/{len(test_cases)} test cases)")
    except Exception as e:
        print(f"  [Intent Classification] Error: {e}")

    # --- 3. Context Pruner Precision & Recall ---
    try:
        pruner = ContextPruner(max_input_tokens=4000, keep_last_n=2)
        test_msgs = [
            {"role": "user", "content": "Hãy cấu hình JWT authentication trong auth.py"},
            {"role": "assistant", "content": "Đã tạo xong file auth.py"},
            {"role": "user", "content": "Sửa lại màu nút đỏ ở giao diện frontend"},
            {"role": "assistant", "content": "Đã đổi CSS nút đỏ"},
            {"role": "user", "content": "JWT auth có dùng refresh token không?"}
        ]
        
        # Target: Message 0 ("JWT authentication") is relevant to current query ("JWT auth")
        pruned_msgs = pruner.prune_messages(test_msgs, "JWT auth có dùng refresh token không?")
        has_relevant = any("JWT authentication" in msg["content"] for msg in pruned_msgs)
        recall_score = 100.0 if has_relevant else 0.0

        print(f"  [Context Pruner Recall] Accuracy:  {recall_score:.1f}% (Relevant context preserved)")
    except Exception as e:
        print(f"  [Context Pruner Recall] Error: {e}")


def main():
    print("=" * 60)
    print(" DOTCODE SYSTEM BENCHMARK SUITE")
    print("=" * 60)
    
    benchmark_indexer()
    benchmark_pagerank_and_graph_queries()
    benchmark_context_pruner()
    benchmark_embedder()
    benchmark_accuracy()
    
    print("\n" + "=" * 60)
    print(" [SUCCESS] BENCHMARK COMPLETED SUCCESSFULLY!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
