import os
import subprocess
from typing import Dict, List, Optional

from dotcode.graph.multi_hop import MultiHopEngine

from ..graphrag import GraphRAGEngine
from ..models import BlastRadiusResult, Symbol, SymbolKind
from ..sage import SAGEEngine
from .database import GraphDatabase
from .indexer import Indexer
from .interface import GraphDBInterface
from .neo4j_adapter import Neo4jAdapter
from .sqlite_adapter import SQLiteAdapter


class CodeGraph:
    multi_hop = None

    def __init__(self, root: str = None, db: GraphDBInterface = None, io=None):
        self.root = root or os.getcwd()
        self.io = io
        self.multi_hop = None
        self.graphrag = None

        if db is not None:
            # Backend được truyền từ ngoài (giữ nguyên)
            self.db = db
            self.db_dir = os.path.join(self.root, ".dotcode")
            self.project_name = self._get_project_name()
            if hasattr(db, "_db") and hasattr(db._db, "db_path"):
                self.db_path = db._db.db_path
            else:
                self.db_path = os.path.join(self.db_dir, f"{self.project_name}.db")
            self.indexer = Indexer(self.db._db, self.root) if hasattr(self.db, "_db") else None
            self.sage = SAGEEngine(self.db._db) if hasattr(self.db, "_db") else None
            self.graphrag = None
        else:
            # Tự động chọn backend
            self._init_backend()

    def _init_backend(self):
        """Tự động chọn backend dựa trên biến môi trường và quy mô dự án."""
        backend = os.getenv("DOTCODE_BACKEND", "auto")
        self.db_dir = os.path.join(self.root, ".dotcode")
        self.project_name = self._get_project_name()
        self.db_path = os.path.join(self.db_dir, f"{self.project_name}.db")

        if backend == "neo4j":
            self._init_neo4j()
        elif backend == "sqlite":
            self._init_sqlite()
        else:  # auto
            # Nếu đã có database SQLite, kiểm tra quy mô
            if os.path.exists(self.db_path):
                raw_db = GraphDatabase(self.db_path)
                try:
                    count = raw_db.count_symbols()
                except Exception:
                    count = 0
                if count > 5000:
                    # Dự án lớn, chuyển sang Neo4j nếu có cấu hình
                    if os.getenv("NEO4J_URI"):
                        self._init_neo4j()
                    else:
                        self._init_sqlite()
                        if self.io:
                            self.io.tool_warning(
                                "Dự án có hơn 5000 symbols, cân nhắc dùng Neo4j để tăng hiệu năng. "
                                "Đặt biến môi trường NEO4J_URI để kích hoạt."
                            )
                else:
                    self._init_sqlite()
            else:
                self._init_sqlite()

    def _init_sqlite(self):
        """Khởi tạo backend SQLite."""
        self.db_path = os.path.join(self.db_dir, f"{self.project_name}.db")
        os.makedirs(self.db_dir, exist_ok=True)
        raw_db = GraphDatabase(self.db_path)
        self.db = SQLiteAdapter(raw_db)
        self.indexer = Indexer(raw_db, self.root)
        self.sage = SAGEEngine(raw_db)
        self.graphrag = None
        self.multi_hop = None
        if self.io:
            self.io.tool_output(f"📁 Code Graph database: {self.db_path}")

    def _init_neo4j(self):
        """Khởi tạo backend Neo4j."""
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        self.db = Neo4jAdapter(uri=uri, user=user, password=password)
        self.indexer = None
        self.sage = None
        self.graphrag = None
        self.db_path = uri
        if self.io:
            self.io.tool_output(f"📁 Code Graph database: {uri} (Neo4j)")

    @classmethod
    def create_auto(cls, root: str, io=None) -> "CodeGraph":
        """Factory method tự động chọn backend."""
        return cls(root=root, io=io)

    @classmethod
    def create_with_sqlite(cls, root: str, io=None) -> "CodeGraph":
        """Factory method tạo CodeGraph với SQLite backend."""
        os.environ["DOTCODE_BACKEND"] = "sqlite"
        instance = cls(root=root, io=io)
        return instance

    @classmethod
    def create_with_neo4j(cls, root: str, io=None) -> "CodeGraph":
        """Factory method tạo CodeGraph với Neo4j backend."""
        os.environ["DOTCODE_BACKEND"] = "neo4j"
        return cls(root=root, io=io)

    def _get_project_name(self) -> str:
        """Lấy tên dự án từ git remote hoặc tên thư mục gốc."""
        try:
            result = subprocess.run(
                ["git", "-C", self.root, "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                name = url.rstrip("/").split("/")[-1]
                if name.endswith(".git"):
                    name = name[:-4]
                if name:
                    return name
        except Exception:
            pass

        abs_root = os.path.abspath(self.root)
        name = os.path.basename(abs_root.rstrip(os.sep))
        if not name or name == ".":
            parent = os.path.dirname(abs_root)
            name = os.path.basename(parent) if parent else "project"
        if not name:
            name = "project"
        return name

    def _ensure_db(self):
        """Tạo database và SQLiteAdapter nếu chưa có."""
        if self.db is None:
            os.makedirs(self.db_dir, exist_ok=True)
            raw_db = GraphDatabase(self.db_path)
            self.db = SQLiteAdapter(raw_db)
            self.indexer = Indexer(raw_db, self.root)
            self.sage = SAGEEngine(raw_db)
            self.graphrag = None
            self.multi_hop = None

    def is_indexed(self) -> bool:
        if self.db is None:
            if os.path.exists(self.db_path):
                self._ensure_db()
            else:
                return False
        try:
            return self.db.count_symbols() > 0
        except Exception:
            return False

    def index(self, files: list = None):
        if files is None:
            files = self._collect_code_files()
        if not files:
            return
        self._ensure_db()
        # Chỉ index nếu dùng SQLite (Neo4j cần migration riêng)
        if hasattr(self.db, "_db") and self.indexer:
            for f in files:
                self.indexer.index_file(f)
            self._compute_pagerank()
            self._ensure_graphrag()
            if self.graphrag:
                self.graphrag.index_symbols()

    def _collect_code_files(self):
        code_files = []
        from .indexer import Indexer

        temp_indexer = Indexer(None, self.root)
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for f in filenames:
                full_path = os.path.join(dirpath, f)
                if temp_indexer.detect_language(full_path):
                    code_files.append(full_path)
        return code_files

    def get_context(
        self,
        chat_files: List[str],
        other_files: List[str],
        format: str = "text",
        max_tokens: int = 1024,
    ) -> str:
        if not self.is_indexed():
            return ""

        lines = []
        all_files = list(chat_files) + list(other_files)
        all_symbol_ids = []
        seen_communities = set()

        # === Phần 1: Mô tả từng file (giữ nguyên) ===
        for fname in all_files:
            if not os.path.exists(fname):
                continue

            rel_path = os.path.relpath(fname, self.root)
            symbols = self.db.get_symbols_in_file(rel_path)

            if not symbols:
                continue

            lines.append(f"File: {rel_path}")
            for sym in symbols[:15]:
                callees = self.db.get_callees(sym.id)
                callee_str = ""
                if callees:
                    callee_names = [c.name for c in callees[:5]]
                    callee_str = f" → calls: {', '.join(callee_names)}"

                callers = self.db.get_callers(sym.id)
                caller_str = ""
                if callers:
                    caller_names = [c.name for c in callers[:3]]
                    caller_str = f" ← called by: {', '.join(caller_names)}"

                kind_str = sym.kind.value if hasattr(sym.kind, "value") else sym.kind
                line = f"  {kind_str} {sym.name}() (line {sym.start_line}){callee_str}{caller_str}"
                lines.append(line)
                all_symbol_ids.append(sym.id)

                # Thu thập community của symbol này
                if self.graphrag and hasattr(self.graphrag, "node_to_community"):
                    comm_id = self.graphrag.node_to_community.get(sym.id)
                    if comm_id is not None and comm_id not in seen_communities:
                        seen_communities.add(comm_id)

        # === Phần 2: Semantic Context (MỚI) ===
        if seen_communities and self.graphrag and hasattr(self.graphrag, "communities"):
            lines.append("")
            lines.append("# 🏗️ Architecture Overview (Semantic Context):")
            lines.append("")

            for comm_id in sorted(seen_communities)[:5]:  # Giới hạn 5 communities
                comm_data = self.graphrag.communities.get(comm_id)
                if not comm_data:
                    continue

                summary = comm_data.get("summary", "")
                if not summary:
                    continue

                # Cắt ngắn summary nếu quá dài
                if len(summary) > 200:
                    summary = summary[:200] + "..."

                lines.append(f"## Community {comm_id}: {summary}")

                # Liệt kê các symbols chính trong community này
                node_ids = comm_data.get("nodes", [])[:5]
                key_symbols = []
                for node_id in node_ids:
                    sym = self.db.get_symbol(node_id)
                    if sym:
                        key_symbols.append(
                            f"{sym.kind.value if hasattr(sym.kind, 'value') else sym.kind} {sym.name}"
                        )

                if key_symbols:
                    lines.append(f"   Key symbols: {', '.join(key_symbols)}")

                # Tìm cross-community bridges
                if len(seen_communities) > 1:
                    for other_comm_id in seen_communities:
                        if other_comm_id <= comm_id:
                            continue
                        if self.multi_hop:
                            bridges = self.multi_hop.find_community_bridges(
                                comm_id,
                                other_comm_id,
                                self.graphrag.node_to_community,
                                edge_types=["calls", "references"],
                            )
                            if bridges:
                                lines.append(
                                    f"   → Connected to Community {other_comm_id} via:"
                                    f" {bridges[0]['source'].name} →"
                                    f" {bridges[0]['target'].name} ({bridges[0]['edge_type']})"
                                )

                lines.append("")

        # === Phần 3: SAGE memory context (giữ nguyên) ===
        if all_symbol_ids and self.sage:
            sage_context = self.sage.get_context_for_prompt(all_symbol_ids[:10])
            if sage_context:
                lines.append("")
                lines.append(sage_context)

        context = "\n".join(lines)
        return context[: max_tokens * 4]

    def search(self, query: str, limit: int = 10) -> List[Symbol]:
        if not self.is_indexed():
            return []
        return self.db.search(query, limit=limit)

    def _compute_pagerank(self):
        """Tính PageRank cho tất cả symbols. Chỉ hỗ trợ SQLite."""
        if not hasattr(self.db, "_db"):
            return
        import networkx as nx

        raw_db = self.db._db
        rows = raw_db.conn.execute(
            "SELECT source_id, target_id, weight FROM edges WHERE type IN ('calls', 'references')"
        ).fetchall()
        if not rows:
            return
        G = nx.DiGraph()
        for src, tgt, w in rows:
            G.add_edge(src, tgt, weight=w)
        all_symbols = raw_db.conn.execute("SELECT id FROM symbols").fetchall()
        for (sym_id,) in all_symbols:
            if sym_id not in G:
                G.add_node(sym_id)
        pagerank = nx.pagerank(G, alpha=0.85, weight="weight")
        for sym_id, rank in pagerank.items():
            raw_db.conn.execute("UPDATE symbols SET pagerank = ? WHERE id = ?", (rank, sym_id))
        raw_db.conn.commit()

    def update_file(self, file_path: str):
        """Cập nhật index cho một file cụ thể. Chỉ hỗ trợ SQLite."""
        if not hasattr(self.db, "_db") or not self.indexer:
            return
        if not self.db:
            self._ensure_db()
        self.indexer.index_file(file_path)
        self._compute_pagerank()

        # DotCode: Unified Feedback Loop - đảm bảo GraphRAG luôn được đồng bộ
        self._ensure_graphrag()
        if self.graphrag:
            rel_path = os.path.relpath(file_path, self.root)
            symbols = self.db.get_symbols_in_file(rel_path)
            if symbols:
                for sym in symbols:
                    try:
                        self.graphrag.collection.delete(ids=[sym.id])
                    except Exception:
                        pass
                texts = []
                metadatas = []
                ids = []
                for sym in symbols:
                    text = self.graphrag._get_symbol_text(
                        sym.model_dump() if hasattr(sym, "model_dump") else sym.__dict__
                    )
                    texts.append(text)
                    metadatas.append(
                        {
                            "symbol_id": sym.id,
                            "name": sym.name,
                            "kind": sym.kind.value if hasattr(sym.kind, "value") else sym.kind,
                            "file_path": rel_path,
                            "start_line": sym.start_line,
                            "pagerank": sym.pagerank,
                        }
                    )
                    ids.append(sym.id)
                if texts:
                    embeddings = self.graphrag.model.encode(texts).tolist()
                    self.graphrag.collection.add(
                        embeddings=embeddings, documents=texts, metadatas=metadatas, ids=ids
                    )
            # Unified Feedback Loop: luôn cập nhật communities sau khi code thay đổi
        self.graphrag.detect_communities()
        self.graphrag.summarize_communities()

    def get_blast_radius(self, symbol_id: str, max_depth: int = 3) -> Optional[BlastRadiusResult]:
        if not self.db:
            return None
        return self.db.get_blast_radius(symbol_id, max_depth)

    def get_unused_symbols(self) -> List[Symbol]:
        if not self.db:
            return []
        return self.db.get_unused_symbols()

    def _ensure_multi_hop(self):
        if self.multi_hop is None and self.db is not None:
            raw_db = self.db._db if hasattr(self.db, "_db") else self.db
            self.multi_hop = MultiHopEngine(raw_db)

    def _ensure_graphrag(self):
        if self.graphrag is None and hasattr(self.db, "_db"):
            try:
                raw_db = self.db._db
                self.graphrag = GraphRAGEngine(raw_db, self.root)
            except Exception as e:
                if self.io:
                    self.io.tool_warning(f"GraphRAG init failed: {e}")

    def semantic_search(self, query: str, limit: int = 10) -> list:
        self._ensure_graphrag()
        if not self.graphrag:
            return []
        return self.graphrag.semantic_search(query, limit)
