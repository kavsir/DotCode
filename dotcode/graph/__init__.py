import os
import subprocess
from .database import GraphDatabase
from .indexer import Indexer
from . .sage import SAGEEngine


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
        # Fallback: tên thư mục gốc
        name = os.path.basename(self.root.rstrip(os.sep))
        return name if name else 'project'

    def _ensure_db(self):
        """Tạo database và các thành phần liên quan nếu chưa có."""
        if self.db is None:
            os.makedirs(self.db_dir, exist_ok=True)
            self.db = GraphDatabase(self.db_path)
            self.indexer = Indexer(self.db, self.root)
            self.sage = SAGEEngine(self.db)

    # ===== Lifecycle =====
    def is_indexed(self) -> bool:
        if self.db is None:
            return False
        try:
            return self.db.count_symbols() > 0
        except Exception:
            return False

    def index(self, files: list = None):
        """Index toàn bộ repo hoặc danh sách file. Chỉ tạo database khi có ít nhất 1 file code."""
        if files is None:
            files = self._collect_code_files()

        # Không có file code nào được hỗ trợ → không tạo database
        if not files:
            return

        # Tạo database lười (lazy) trước khi index
        self._ensure_db()

        for f in files:
            self.indexer.index_file(f)

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