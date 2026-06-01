import os
import subprocess
from .database import GraphDatabase
from .indexer import Indexer
from . .sage import SAGEEngine
from ..graphrag import GraphRAGEngine


class CodeGraph:
    def __init__(self, root: str = None, db_path: str = None, io=None):
        self.root = root or os.getcwd()
        self.io = io

        # Thư mục chứa database
        self.db_dir = os.path.join(self.root, '.dotcode')
        # Tên dự án (lấy từ git hoặc tên thư mục)
        self.project_name = self._get_project_name()
        # Đường dẫn database dự kiến (chưa tạo file)
        self.db_path = db_path or os.path.join(self.db_dir, f"{self.project_name}.db")

        # Database và indexer sẽ được khởi tạo lười (lazy)
        self.db = None
        self.indexer = None
        self.sage = None
        self.graphrag = None
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
        
        # Fallback: tên thư mục gốc (resolve đường dẫn tuyệt đối)
        abs_root = os.path.abspath(self.root)
        name = os.path.basename(abs_root.rstrip(os.sep))
        # Nếu basename trả về rỗng hoặc '.', dùng tên ổ đĩa hoặc 'project'
        if not name or name == '.':
            # Thử lấy tên thư mục cha
            parent = os.path.dirname(abs_root)
            name = os.path.basename(parent) if parent else 'project'
        if not name:
            name = 'project'
        return name

    def _ensure_db(self):
        """Tạo database và các thành phần liên quan nếu chưa có."""
        if self.db is None:
            os.makedirs(self.db_dir, exist_ok=True)
            self.db = GraphDatabase(self.db_path)
            self.indexer = Indexer(self.db, self.root)
            self.sage = SAGEEngine(self.db)

    # ===== Lifecycle =====
    def is_indexed(self) -> bool:
        # Nếu db chưa được khởi tạo, thử mở database nếu file tồn tại
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
        """Thu thập tất cả file code dựa trên detect_language (đa ngôn ngữ)."""
        code_files = []
        # Cần một indexer tạm để dùng detect_language
        # Vì indexer chưa được tạo, ta tạo tạm không cần db
        from .indexer import Indexer
        temp_indexer = Indexer(None, self.root)  # db=None, chỉ dùng để detect
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            for f in filenames:
                full_path = os.path.join(dirpath, f)
                if temp_indexer.detect_language(full_path):
                    code_files.append(full_path)
        return code_files

    # ===== Context Retrieval =====
    def get_context(self, chat_files, other_files, format="text", max_tokens=1024):
        if self.db is None or not self.is_indexed():
            return ""

        lines = []
        all_files = list(chat_files) + list(other_files)
        all_symbol_ids = []

        for fname in all_files:
            if not os.path.exists(fname):
                continue

            rel_path = os.path.relpath(fname, self.root)
            symbols = self.db.get_symbols_in_file(rel_path)

            if not symbols:
                continue

            lines.append(f"File: {rel_path}")
            for sym in symbols[:15]:
                callees = self.db.get_callees(sym['id'])
                callee_str = ""
                if callees:
                    callee_names = [c['name'] for c in callees[:5]]
                    callee_str = f" → calls: {', '.join(callee_names)}"

                callers = self.db.get_callers(sym['id'])
                caller_str = ""
                if callers:
                    caller_names = [c['name'] for c in callers[:3]]
                    caller_str = f" ← called by: {', '.join(caller_names)}"

                line = f"  {sym['kind']} {sym['name']}() (line {sym['start_line']}){callee_str}{caller_str}"
                lines.append(line)
                all_symbol_ids.append(sym['id'])

        context = "\n".join(lines)

        # Bổ sung SAGE memory context (nếu có)
        if all_symbol_ids and self.sage:
            sage_context = self.sage.get_context_for_prompt(all_symbol_ids[:10])
            if sage_context:
                context += "\n\n" + sage_context

        return context[:max_tokens * 4]
    
    def search(self, query: str, limit: int = 10) -> list:
        """Tìm kiếm symbols theo tên (fuzzy)."""
        if not self.is_indexed():
            return []
        
        cur = self.db.conn.execute(
            """SELECT * FROM symbols 
            WHERE name LIKE ? OR signature LIKE ?
            ORDER BY pagerank DESC
            LIMIT ?""",
            (f"%{query}%", f"%{query}%", limit)
        )
        return [dict(row) for row in cur.fetchall()]
    
    def _ensure_graphrag(self):
        if self.graphrag is None and self.db is not None:
            try:
                from ..graphrag import GraphRAGEngine
                self.graphrag = GraphRAGEngine(self.db, self.root)
            except Exception as e:
                if self.io:
                    self.io.tool_warning(f"GraphRAG init failed: {e}")
    
    def semantic_search(self, query: str, limit: int = 10) -> list:
        """Tìm kiếm ngữ nghĩa qua GraphRAG."""
        self._ensure_graphrag()
        if not self.graphrag:
            return []
        return self.graphrag.semantic_search(query, limit)
    
    def _compute_pagerank(self):
        """Tính PageRank cho tất cả symbols dựa trên edges."""
        import networkx as nx
        
        rows = self.db.conn.execute(
            "SELECT source_id, target_id, weight FROM edges WHERE type IN ('calls', 'references')"
        ).fetchall()
        
        if not rows:
            return
        
        G = nx.DiGraph()
        for src, tgt, w in rows:
            G.add_edge(src, tgt, weight=w)
        
        all_symbols = self.db.conn.execute("SELECT id FROM symbols").fetchall()
        for (sym_id,) in all_symbols:
            if sym_id not in G:
                G.add_node(sym_id)
        
        pagerank = nx.pagerank(G, alpha=0.85, weight='weight')
        
        for sym_id, rank in pagerank.items():
            self.db.conn.execute(
                "UPDATE symbols SET pagerank = ? WHERE id = ?", (rank, sym_id)
            )
        self.db.conn.commit()

    def update_file(self, file_path: str):
        """Cập nhật index cho một file cụ thể (sau khi file thay đổi)."""
        if not self.db:
            self._ensure_db()
        
        # Index lại file
        self.indexer.index_file(file_path)
        
        # Tính lại PageRank
        self._compute_pagerank()
        
        # Cập nhật GraphRAG embeddings nếu có
        if self.graphrag:
            rel_path = os.path.relpath(file_path, self.root)
            symbols = self.db.get_symbols_in_file(rel_path)
            if symbols:
                # Xóa embeddings cũ
                for sym in symbols:
                    try:
                        self.graphrag.collection.delete(ids=[sym['id']])
                    except Exception:
                        pass
                
                # Tạo embeddings mới
                texts = []
                metadatas = []
                ids = []
                for sym in symbols:
                    text = self.graphrag._get_symbol_text(sym)
                    texts.append(text)
                    metadatas.append({
                        "symbol_id": sym['id'],
                        "name": sym['name'],
                        "kind": sym['kind'],
                        "file_path": rel_path,
                        "start_line": sym['start_line'],
                        "pagerank": sym.get('pagerank', 0.0),
                    })
                    ids.append(sym['id'])
                
                if texts:
                    embeddings = self.graphrag.model.encode(texts).tolist()
                    self.graphrag.collection.add(
                        embeddings=embeddings,
                        documents=texts,
                        metadatas=metadatas,
                        ids=ids
                    )
            
            # Cập nhật communities
            self.graphrag.detect_communities()
            self.graphrag.summarize_communities()