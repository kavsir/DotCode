import os
from .database import GraphDatabase
from .indexer import Indexer
from ..sage import SAGEEngine


class CodeGraph:
    def __init__(self, root: str = None, db_path: str = None, io=None):
        self.root = root or os.getcwd()
        self.io = io

        if db_path is None:
            db_dir = os.path.join(self.root, '.dotcode')
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, 'graph.db')

        self.db = GraphDatabase(db_path)
        self.indexer = Indexer(self.db, self.root)
        self.sage = SAGEEngine(self.db)  # <<< ĐÃ CHUYỂN XUỐNG SAU self.db

    # ===== Lifecycle =====
    def is_indexed(self) -> bool:
        try:
            return self.db.count_symbols() > 0
        except Exception:
            return False

    def index(self, files: list = None):
        if files is None:
            files = self._collect_code_files()   # Đã đổi thành đa ngôn ngữ
        for f in files:
            self.indexer.index_file(f)

    def _collect_code_files(self):
        """Thu thập tất cả file code dựa trên detect_language (đa ngôn ngữ)."""
        code_files = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            for f in filenames:
                full_path = os.path.join(dirpath, f)
                # Sử dụng indexer để kiểm tra xem file có được hỗ trợ không
                if self.indexer.detect_language(full_path):
                    code_files.append(full_path)
        return code_files

    # ===== Context Retrieval =====
    def get_context(self, chat_files, other_files, format="text", max_tokens=1024):
        if not self.is_indexed():
            return ""

        lines = []
        all_files = list(chat_files) + list(other_files)

        # Biến này để thu thập tất cả symbol ids cho SAGE
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

                # Thu thập symbol ids cho SAGE
                all_symbol_ids.append(sym['id'])

        # Ghép các dòng thành context
        context = "\n".join(lines)

        # Bổ sung SAGE memory context (nếu có)
        if all_symbol_ids and self.sage:
            sage_context = self.sage.get_context_for_prompt(all_symbol_ids[:10])
            if sage_context:
                context += "\n\n" + sage_context

        return context[:max_tokens * 4]