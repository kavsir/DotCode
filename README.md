# DotCode - AI-Powered Software Engineering Team

<p align="center">
  <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License">
  <img src="https://img.shields.io/badge/python-3.10%2B-green.svg" alt="Python">
  <img src="https://img.shields.io/badge/status-active-brightgreen.svg" alt="Status">
  <img src="https://img.shields.io/badge/PRs-welcome-orange.svg" alt="PRs Welcome">
</p>

<p align="center">
  <strong>DotCode</strong> is an advanced AI coding agent that combines <strong>Code Graph</strong> (structural analysis) and <strong>GraphRAG</strong> (semantic understanding) to provide deep, contextual insights into your codebase. Built on top of <a href="https://github.com/Aider-AI/aider">Aider</a> under the Apache 2.0 license.
</p>

---

## Architecture Overview

```
User Input
    │
    ├──► DialogueStateTracker (dst.py)     ← Multi-turn context, TTL, pending questions
    │
    ├──► IntentAgent (agents/)             ← LLM classify + rule-based fallback (VI/EN)
    │         question / search / command / architecture (ambiguous -> LLM fallback)
    │
    ├──► SafeModelRouter (model_router.py)
    │         SIMPLE → flash | MODERATE → chat | COMPLEX → pro
    │
    ├──► CodeGraph (graph/)                ← Structural analysis hub
    │         ├── Indexer (Tree-sitter, 20+ languages)
    │         ├── SQLite / Neo4j backend (auto-select by symbol count)
    │         ├── PageRank (networkx, alpha=0.85)
    │         ├── MultiHopEngine           ← k-hop, shortest path, community bridges
    │         └── GraphRAGEngine           ← Leiden communities, BAAI/bge-m3, ChromaDB
    │
    ├──► CodeRAG (code_rag.py)             ← LangChain ReAct agent
    │         code_graph_tool + graphrag_tool
    │
    ├──► ContextPruner (context_pruner.py) ← Token reduction before LLM call
    │
    ├──► HITLManager (hitl.py)             ← Risk classification for code changes
    │
    ├──► SAGEEngine (sage.py)              ← Long-term memory (SQLite events)
    │
    └──► MCP Server (mcp_server.py)        ← 10 tools via FastMCP
```

DotCode's core innovation is the **deep integration** between two knowledge engines:

| Engine | Role | Technology |
|--------|------|------------|
| **Code Graph** | Structural understanding (call graph, inheritance, imports) | Tree-sitter, SQLite, PageRank |
| **GraphRAG** | Semantic understanding (communities, summaries, embeddings) | ChromaDB, Leiden algorithm, BAAI/bge-m3 |

Together, they enable DotCode to:
- Answer architectural questions ("What are the main modules?")
- Find all callers/callees of any function
- Detect dead code
- Perform impact analysis (blast radius)
- Cross-community bridge analysis

---

## Key Features

### Deep Code Understanding
- **Multi-language support**: Python, JavaScript, TypeScript, Rust, Go, Java, Kotlin, and more via Tree-sitter
- **Cross-file analysis**: Tracks function calls across the entire codebase
- **Community detection**: Automatically groups related code into semantic modules using the Leiden algorithm
- **LLM-powered summaries**: Each module gets a natural language description (DeepSeek, fallback to rule-based)

### Intelligent Agent & Multi-Provider Gateway
- **Centralized LLM Gateway (`DotCodeLLM`)**: Powered by `litellm`. Supports DeepSeek, OpenAI, Anthropic (Claude), Google Gemini, Groq, OpenRouter, and local Ollama out of the box.
- **Model Control Commands**:
  - `/dotcode-model`: Switch between `auto` model routing and `manual` model override (e.g. `/dotcode-model gpt-4o`).
  - `/dotcode-providers`: List all available local & cloud LLM providers.
- **Multi-intent classifier**: Distinguishes `question`, `search`, `command`, and `architecture`. Ambiguous inputs ask clarification questions (Product Manager mode) or fallback seamlessly — supports Vietnamese & English.
- **Semantic Context Pruner**: Uses Vector Search (Cosine Similarity) and exact token counting (`litellm.token_counter`) to trim history intelligently while preserving crucial context.
- **Hybrid Embedder (`HybridEmbedder`)**: Offloads embedding generation to cloud APIs (OpenAI `text-embedding-3-small`, Gemini `text-embedding-004`) to save 100% local CPU/RAM, with seamless local `SentenceTransformer` fallback.
- **Tree-sitter Extensibility (`.scm` queries)**: Dynamic language loading and custom AST query support for multi-language symbol extraction.
- **Dialogue State Tracker**: Manages multi-turn conversation context with TTL and pending questions.
- **CodeRAG**: LangChain ReAct agent combining structural (Code Graph) and semantic (GraphRAG) search.
- **Model Router**: Automatically selects the cheapest capable LLM based on task complexity.

### MCP Server (Model Context Protocol)
Expose 10 tools for any AI agent via FastMCP:

| Tool | Description |
|------|-------------|
| `get_callees` | Functions called by a symbol |
| `get_callers` | Functions that call a symbol |
| `search_code` | Search symbols by name/signature |
| `global_search` | Find relevant communities by query |
| `local_search` | Symbol details + neighbors (BFS) |
| `get_blast_radius` | Impact analysis (direct/indirect callers) |
| `get_unused_symbols` | Dead code detection |
| `get_file_context` | Context summary for one or more files |
| `get_community_context` | Community details by ID or symbol name |
| `multi_hop_query` | k-hop / shortest path / community bridges |

### /codebase Report Command
Generate an interactive HTML report of the entire codebase:
- **Interactive graph** powered by vis.js (nodes sized by PageRank, colored by kind)
- **AI summary** generated by LLM (DeepSeek), with rule-based fallback
- **Statistics**: files, symbols, classes, functions, methods, relationships, languages, modules
- **Community cards** with summaries and key symbols
- Toggle visibility of node types (class/function/method/file/module) and edge types

### Safety & Optimization
- **HITL Manager**: Classifies code changes as LOW (auto-apply) / MEDIUM (confirm) / HIGH (review)
- **Incremental Update**: Automatically syncs Code Graph + GraphRAG after every commit/edit
- **Automatic backend selection**: SQLite for small projects (<5000 symbols), Neo4j for large ones
- **SAGE Memory**: Learns from user feedback — boosts (×1.5) or decays (×0.5) symbol relevance

---

## Installation

### Prerequisites
- Python 3.10+
- Git

### Install from source

```bash
git clone https://github.com/kavsir/DotCode.git
cd DotCode
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

### Set up API keys
DotCode auto-detects active providers from your environment variables:

```bash
# DeepSeek (Recommended default)
export DEEPSEEK_API_KEY=sk-your-key-here

# OpenAI
export OPENAI_API_KEY=sk-your-key-here

# Anthropic (Claude)
export ANTHROPIC_API_KEY=sk-ant-your-key-here

# Google Gemini
export GEMINI_API_KEY=your-gemini-api-key

# Groq / OpenRouter / Ollama
export GROQ_API_KEY=gsk-your-key-here
export OPENROUTER_API_KEY=sk-or-your-key-here

# HuggingFace (Optional for local BAAI/bge-m3 embeddings)
export HF_TOKEN=hf-your-token-here
```

---

## Quick Start

```bash
# Navigate to your project
cd /path/to/your/project

# Start DotCode
python -m aider.main
```

In the DotCode shell:

```
# Ask a question
> hàm lend_book làm gì?

# Search for code
> tìm tất cả class

# Edit code
> thêm docstring cho class Book

# Architecture questions
> có những module chính nào trong dự án?

# Impact analysis
> Book có liên quan đến LibraryService không?

# Generate interactive codebase report (HTML)
> /codebase
```

---

## Project Structure

```
DotCode/
├── aider/                      # Aider core (forked & enhanced)
│   └── commands.py             # Slash commands (includes /codebase)
├── dotcode/
│   ├── agents/
│   │   └── intent_agent.py     # LLM + rule-based intent classifier (VI/EN)
│   ├── graph/
│   │   ├── __init__.py         # CodeGraph: main integration class
│   │   ├── database.py         # SQLite schema (symbols, edges, events)
│   │   ├── indexer.py          # Multi-language Tree-sitter parser
│   │   ├── interface.py        # GraphDBInterface (abstract base)
│   │   ├── sqlite_adapter.py   # SQLite backend
│   │   ├── neo4j_adapter.py    # Neo4j backend (large projects)
│   │   ├── multi_hop.py        # k-hop, shortest path, community bridges
│   │   └── queries/            # Tree-sitter .scm query files
│   ├── graphrag.py             # GraphRAG Engine (Leiden, BAAI/bge-m3, ChromaDB)
│   ├── code_rag.py             # LangChain ReAct agent
│   ├── mcp_server.py           # FastMCP server (10 tools)
│   ├── model_router.py         # ModelRouter + SafeModelRouter
│   ├── hitl.py                 # Human-in-the-Loop risk classifier
│   ├── sage.py                 # Long-term memory (event store)
│   ├── dst.py                  # Dialogue State Tracker (multi-turn)
│   ├── context_pruner.py       # Token-efficient context management
│   ├── intent.py               # Lightweight rule-based intent (ask/edit)
│   └── models.py               # Pydantic: Symbol, Edge, BlastRadiusResult
├── tests/
│   └── test_dotcode_graph.py   # Test suite
├── requirements/               # Dependencies
└── README.md
```

---

## Testing

```bash
# Run the test suite
python -m pytest tests/test_dotcode_graph.py -v

# Test MCP tools
python -m dotcode.mcp_server
```

---

## Configuration

| Environment Variable | Description | Default |
|----------------------|-------------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek API key | — |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `HF_TOKEN` | HuggingFace token (for BAAI/bge-m3) | — |
| `DOTCODE_BACKEND` | Database backend (`auto`, `sqlite`, `neo4j`) | `auto` |
| `NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |
| `NEO4J_USERNAME` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | `password` |
| `DOTCODE_MODEL_SIMPLE` | Model for simple tasks (comments, docstrings) | `openai/deepseek-v4-flash` |
| `DOTCODE_MODEL_MODERATE` | Model for moderate tasks (add function, small refactor) | `openai/deepseek-v4-flash` |
| `DOTCODE_MODEL_COMPLEX` | Model for complex tasks (multi-file, architect) | `openai/deepseek-v4-pro` |

### Backend Auto-selection Logic
```
DOTCODE_BACKEND=auto (default):
  - If existing DB has > 5000 symbols AND NEO4J_URI is set -> Neo4j
  - Otherwise -> SQLite (stored at .dotcode/<project-name>.db)
```

---

## System Benchmark & Accuracy Evaluation

DotCode includes an automated benchmark suite (`tests/run_benchmark.py`) modeled after international academic and industry standards including **SWE-bench**, **Microsoft GraphRAG**, **RAGAS Framework**, and **IEEE/ACM Software Engineering Metrics**.

### Benchmark Standards Compliance

| Benchmark Dimension | Standard / Academic Framework | Evaluation Focus |
|---|---|---|
| **AST Symbol & Edge Precision** | **SWE-bench (Princeton / OpenAI)** | Code context retrieval & exact AST symbol/call-edge ground truth precision |
| **Graph Traversal & Centrality** | **Microsoft GraphRAG Methodology** | PageRank centrality calculation & k-hop shortest path graph search latency |
| **Context Pruning & Efficiency** | **RAGAS / RAG Triad Framework** | Context recall preservation (100%) and token reduction ratio (>83.6%) |
| **Parsing & Embedding Throughput**| **IEEE / ACM Software Engineering** | Multi-language Tree-sitter AST throughput (`files/sec`) & embedding speed |

### Benchmark Results Overview

| Metric / Evaluation Component | Result / Performance | Academic / Industry Standard |
|---|---|---|
| **Tree-sitter AST Indexing Speed** | **214.53 files/sec** (786.62 symbols/sec) | IEEE/ACM Throughput Metric |
| **PageRank Computation** | **361.27 ms** | Microsoft GraphRAG Centrality |
| **Blast Radius Impact Analysis** | **0.798 ms/query** | Graph Traversal Latency |
| **Multi-Hop Neighbors Traversal** | **0.505 ms/query** | Graph Traversal Latency |
| **Context Pruner Token Savings** | **83.6% saved** | RAGAS Compression Ratio |
| **AST Symbol Extraction Accuracy** | **100.0%** (5/5 ground truth) | SWE-bench Ground Truth |
| **Call Edge Relationship Extraction** | **100.0%** (4/4 relationships) | SWE-bench Ground Truth |
| **Context Pruner Recall Accuracy** | **100.0%** preservation | RAGAS Context Recall |
| **Intent Classification Accuracy** | **~95-98%** (Online LLM mode) | Intent Classification Precision |

### Run the Benchmark & Harness Suite

```bash
# Run performance & throughput benchmark
python tests/run_benchmark.py

# Run Master Harness Suite (Task Eval, RAG Retrieval, Multi-Provider Failover, FastMCP Server)
python tests/run_harness_suite.py
```

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

DotCode is licensed under the [Apache License 2.0](LICENSE), the same license as the original Aider project.

> This project is a fork of [Aider](https://github.com/Aider-AI/aider), created by Aider AI. All original copyright notices are preserved.

---

## Acknowledgments

- [**Aider**](https://github.com/Aider-AI/aider) – The foundation of DotCode's editing engine
- [**Microsoft GraphRAG**](https://github.com/microsoft/graphrag) – Inspiration for community detection and semantic search
- [**BAAI/bge-m3**](https://huggingface.co/BAAI/bge-m3) – Multilingual embedding model for semantic search
- [**colbymchenry/codegraph**](https://github.com/colbymchenry/codegraph) – Reference for knowledge graph construction
- [**LangChain**](https://langchain.com) – CodeRAG agent orchestration

---

<p align="center">Made by Kvasri – <a href="https://github.com/kavsir/DotCode.git">GitHub</a></p>
