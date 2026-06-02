import os
import subprocess
from typing import List, Dict, Optional

from .interface import GraphDBInterface
from .sqlite_adapter import SQLiteAdapter
from .database import GraphDatabase
from .indexer import Indexer
from ..sage import SAGEEngine
from ..graphrag import GraphRAGEngine
from ..models import Symbol, SymbolKind, BlastRadiusResult


class CodeGraph:
    def __init__(self, root: str = None, db: GraphDBInterface = None, io=None):
        self.root = root or os.getcwd()
        self.io = io

        # Nếu không truyền db, tự tạo SQLiteAdapter (giữ tương thích ngược)
        if db is not None:
            self.db = db
            # Khi db được truyền từ ngoài, cần tự thiết lập các thành phần khác
            self.db_dir = os.path.join(self.root, '.dotcode')
            self.project_name = self._get_project_name()
            self.db_path = getattr(db, '_db', None)
            if hasattr(self.db, '_db'):
                self.db_path = self.db._db.db_path
            else:
                self.db_path = os.path.join(self.db_dir, f"{self.project_name}.db")
            self.indexer = Indexer(self.db, self.root) if hasattr(self.db, '_db') else None
            self.sage = SAGEEngine(self.db._db) if hasattr(self.db, '_db') else None
            self.graphrag = None
        else:
            # Tự tạo database và adapter
            self.db_dir = os.path.join(self.root, '.dotcode')
            self.project_name = self._get_project_name()
            self.db_path = os.path.join(self.db_dir, f"{self.project_name}.db")
            self.db = None  # Sẽ được khởi tạo lười
            self.indexer = None
            self.sage = None
            self.graphrag = None

    @classmethod
    def create_with_sqlite(cls, root: str, io=None) -> 'CodeGraph':
        """Factory method tạo CodeGraph với SQLite backend."""
        instance = cls(root=root, io=io)
        instance._ensure_db()  # Khởi tạo database và adapter
        return instance

    def _get_project_name(self) -> str:
        """Lấy tên dự án từ git remote hoặc tên thư mục gốc."""
        try:
            result = subprocess.run(
                ['git', '-C', self.root, 'remote', 'get-url', 'origin'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                name = url.rstrip('/').split('/')[-1]
                if name.endswith('.git'):
                    name = name[:-4]
                if name:
                    return name
        except Exception:
            pass

        abs_root = os.path.abspath(self.root)
        name = os.path.basename(abs_root.rstrip(os.sep))
        if not name or name == '.':
            parent = os.path.dirname(abs_root)
            name = os.path.basename(parent) if parent else 'project'
        if not name:
            name = 'project'
        return name

    def _ensure_db(self):
        """Tạo database và SQLiteAdapter nếu chưa có."""
        if self.db is None:
            os.makedirs(self.db_dir, exist_ok=True)
            raw_db = GraphDatabase(self.db_path)
            self.db = SQLiteAdapter(raw_db)
            self.indexer = Indexer(raw_db, self.root)  # Indexer vẫn cần GraphDatabase gốc
            self.sage = SAGEEngine(raw_db)

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
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            for f in filenames:
                full_path = os.path.join(dirpath, f)
                if temp_indexer.detect_language(full_path):
                    code_files.append(full_path)
        return code_files

    def get_context(self, chat_files: List[str], other_files: List[str], format: str = "text", max_tokens: int = 1024) -> str:
        if not self.is_indexed():
            return ""

        lines = []
        all_files = list(chat_files) + list(other_files)
        all_symbol_ids = []

        for fname in all_files:
            if not os.path.exists(fname):
                continue

            rel_path = os.path.relpath(fname, self.root)
            symbols = self.db.get_symbols_in_file(rel_path)  # Giờ trả về List[Symbol]

            if not symbols:
                continue

            lines.append(f"File: {rel_path}")
            for sym in symbols[:15]:
                # sym là Symbol object, truy cập thuộc tính thay vì dict key
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

                line = f"  {sym.kind.value} {sym.name}() (line {sym.start_line}){callee_str}{caller_str}"
                lines.append(line)
                all_symbol_ids.append(sym.id)

        context = "\n".join(lines)

        if all_symbol_ids and self.sage:
            sage_context = self.sage.get_context_for_prompt(all_symbol_ids[:10])
            if sage_context:
                context += "\n\n" + sage_context

        return context[:max_tokens * 4]

    def search(self, query: str, limit: int = 10) -> List[Symbol]:
        """Tìm kiếm symbols theo tên (fuzzy)."""
        if not self.is_indexed():
            return []
        return self.db.search(query, limit=limit)

    def _compute_pagerank(self):
        """Tính PageRank cho tất cả symbols. Logic này vẫn cần truy cập trực tiếp SQLite."""
        import networkx as nx
        # Tạm thời vẫn dùng conn trực tiếp vì đây là logic nội bộ của SQLite
        if hasattr(self.db, '_db'):
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
            pagerank = nx.pagerank(G, alpha=0.85, weight='weight')
            for sym_id, rank in pagerank.items():
                raw_db.conn.execute("UPDATE symbols SET pagerank = ? WHERE id = ?", (rank, sym_id))
            raw_db.conn.commit()

    def update_file(self, file_path: str):
        """Cập nhật index cho một file cụ thể."""
        if not self.db:
            self._ensure_db()
        self.indexer.index_file(file_path)
        self._compute_pagerank()
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
                    text = self.graphrag._get_symbol_text(sym.dict() if hasattr(sym, 'dict') else sym)
                    texts.append(text)
                    metadatas.append({
                        "symbol_id": sym.id,
                        "name": sym.name,
                        "kind": sym.kind.value,
                        "file_path": rel_path,
                        "start_line": sym.start_line,
                        "pagerank": sym.pagerank,
                    })
                    ids.append(sym.id)
                if texts:
                    embeddings = self.graphrag.model.encode(texts).tolist()
                    self.graphrag.collection.add(
                        embeddings=embeddings,
                        documents=texts,
                        metadatas=metadatas,
                        ids=ids
                    )
            self.graphrag.detect_communities()
            self.graphrag.summarize_communities()

    def get_blast_radius(self, symbol_id: str, max_depth: int = 3) -> Optional[BlastRadiusResult]:
        """Tính toán blast radius."""
        if not self.db:
            return None
        return self.db.get_blast_radius(symbol_id, max_depth)

    def get_unused_symbols(self) -> List[Symbol]:
        """Phát hiện dead code."""
        if not self.db:
            return []
        return self.db.get_unused_symbols()

    def _ensure_graphrag(self):
        if self.graphrag is None and self.db is not None:
            try:
                from ..graphrag import GraphRAGEngine
                # GraphRAGEngine cần GraphDatabase gốc, không phải adapter
                raw_db = self.db._db if hasattr(self.db, '_db') else self.db
                self.graphrag = GraphRAGEngine(raw_db, self.root)
            except Exception as e:
                if self.io:
                    self.io.tool_warning(f"GraphRAG init failed: {e}")

    def semantic_search(self, query: str, limit: int = 10) -> list:
        """Tìm kiếm ngữ nghĩa qua GraphRAG."""
        self._ensure_graphrag()
        if not self.graphrag:
            return []
        return self.graphrag.semantic_search(query, limit)