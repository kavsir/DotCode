# 🤖 DotCode – AI-Powered Software Engineering Team

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

## 🧠 Architecture Overview

```
User Input → Intent Agent → Code Graph + GraphRAG → Hybrid Context → LLM → Response
                                                                          │
                                                              MCP Server (10+ tools)
```

DotCode's core innovation is the **deep integration** between two knowledge engines:

| Engine | Role | Technology |
|--------|------|------------|
| **Code Graph** | Structural understanding (call graph, inheritance, imports) | Tree-sitter, SQLite, PageRank |
| **GraphRAG** | Semantic understanding (communities, summaries, embeddings) | ChromaDB, Leiden algorithm, LLM |

Together, they enable DotCode to:
- Answer architectural questions ("What are the main modules?")
- Find all callers/callees of any function
- Detect dead code
- Perform impact analysis (blast radius)
- Cross-community bridge analysis

---

## ✨ Key Features

### 🔍 Deep Code Understanding
- **Multi-language support**: Python, JavaScript, TypeScript, Rust, and 50+ others via Tree-sitter
- **Cross-file analysis**: Tracks function calls across the entire codebase
- **Community detection**: Automatically groups related code into semantic modules
- **LLM-powered summaries**: Each module gets a natural language description

### 🧠 Intelligent Agent
- **Multi-intent classifier**: Distinguishes questions, commands, searches, and ambiguous inputs
- **Auto-context expansion**: Automatically adds relevant files to the chat
- **CodeRAG**: LangChain-based agent combining structural and semantic search
- **Model Router**: Automatically selects the cheapest capable LLM for each task

### 🌐 MCP Server (Model Context Protocol)
Expose 10+ tools for any AI agent:
- `get_callees` / `get_callers`
- `search_code` / `global_search` / `local_search`
- `get_blast_radius` / `get_unused_symbols`
- `multi_hop_query` (k-hop, shortest path, community bridges)

### 🛡️ Safety & Optimization
- **HITL Manager**: Auto-applies safe changes, asks confirmation for risky ones
- **Incremental Update**: Automatically syncs Code Graph + GraphRAG after every commit/undo
- **CLAUDE.md integration**: Behavioral guidelines for cleaner, more focused code generation
- **Automatic backend selection**: SQLite for small projects, Neo4j for large ones

---

## 📦 Installation

### Prerequisites
- Python 3.10+
- Git

### Install from source

```bash
git clone https://github.com/yourusername/DotCode.git
cd DotCode
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

### Set up API keys

```bash
# DeepSeek (recommended)
export DEEPSEEK_API_KEY=sk-your-key-here

# OpenAI (optional)
export OPENAI_API_KEY=sk-your-key-here
```

---

## 🚀 Quick Start

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
```

---

## 📁 Project Structure

```
DotCode/
├── aider/                  # Aider core (forked & enhanced)
├── dotcode/
│   ├── agents/             # IntentAgent (multi-lingual classifier)
│   ├── graph/              # Code Graph Engine
│   │   ├── database.py     # SQLite schema
│   │   ├── indexer.py      # Multi-language parser
│   │   ├── interface.py    # GraphDBInterface (abstract)
│   │   ├── sqlite_adapter.py
│   │   ├── neo4j_adapter.py
│   │   ├── multi_hop.py    # Multi-hop query engine
│   │   └── queries/        # Tree-sitter queries (.scm files)
│   ├── graphrag.py         # GraphRAG Engine (communities, embeddings)
│   ├── model_router.py     # Automatic LLM selection
│   ├── hitl.py             # Human-in-the-Loop manager
│   ├── sage.py             # Long-term memory
│   ├── code_rag.py         # LangChain CodeRAG agent
│   ├── mcp_server.py       # MCP tools for AI agents
│   └── models.py           # Pydantic data models
├── tests/                  # Test suite
├── requirements/           # Dependencies
└── README.md
```

---

## 🧪 Testing

```bash
# Run the test suite
python -m pytest tests/test_dotcode_graph.py -v

# Test MCP tools
python -m dotcode.mcp_server
```

---

## 🔧 Configuration

| Environment Variable | Description | Default |
|----------------------|-------------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek API key | — |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `DOTCODE_BACKEND` | Database backend (`auto`, `sqlite`, `neo4j`) | `auto` |
| `NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |
| `DOTCODE_MODEL_SIMPLE` | Model for simple tasks | `deepseek/deepseek-v4-flash` |
| `DOTCODE_MODEL_COMPLEX` | Model for complex tasks | `deepseek/deepseek-v4-pro` |

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

DotCode is licensed under the [Apache License 2.0](LICENSE), the same license as the original Aider project.

> This project is a fork of [Aider](https://github.com/Aider-AI/aider), created by Aider AI. All original copyright notices are preserved.

---

## 🙏 Acknowledgments

- [**Aider**](https://github.com/Aider-AI/aider) – The foundation of DotCode's editing engine
- [**Microsoft GraphRAG**](https://github.com/microsoft/graphrag) – Inspiration for community detection and semantic search
- [**colbymchenry/codegraph**](https://github.com/colbymchenry/codegraph) – Reference for knowledge graph construction
- [**LangChain**](https://langchain.com) – CodeRAG agent orchestration

---

<p align="center">Made with ❤️ by [Your Name] – <a href="https://github.com/yourusername/DotCode">GitHub</a></p>