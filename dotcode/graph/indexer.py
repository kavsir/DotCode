# dotcode/graph/indexer.py
import hashlib
import os
from pathlib import Path
from platform import node

import json
import tree_sitter_javascript as tsjavascript
import tree_sitter_languages
import tree_sitter_python as tspython
import tree_sitter_rust as tsrust
import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Parser

PY_LANGUAGE = Language(tspython.language())
PY_PARSER = Parser(PY_LANGUAGE)

JS_LANGUAGE = Language(tsjavascript.language())
JS_PARSER = Parser(JS_LANGUAGE)

TS_LANGUAGE = Language(tstypescript.language_typescript())
TS_PARSER = Parser(TS_LANGUAGE)

TSX_LANGUAGE = Language(tstypescript.language_tsx())
TSX_PARSER = Parser(TSX_LANGUAGE)

RUST_LANGUAGE = Language(tsrust.language())
RUST_PARSER = Parser(RUST_LANGUAGE)

HARD_LANGUAGES = {
    "python": PY_LANGUAGE,
    "javascript": JS_LANGUAGE,
    "typescript": TS_LANGUAGE,
    "tsx": TSX_LANGUAGE,
    "rust": RUST_LANGUAGE,
}


class Indexer:
    def __init__(self, db, root: str):
        self.db = db
        self.root = root
        self.parsers = {}  # Cache parser theo ngôn ngữ
        self.queries = {}  # Cache query string theo ngôn ngữ
        self.query_dir = os.path.join(os.path.dirname(__file__), "queries")

    # ========== LANGUAGE DETECTION ==========
    def detect_language(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        lang_map = {
            # Python
            ".py": "python",
            ".pyw": "python",
            ".pyx": "python",
            ".pxd": "python",
            ".pxi": "python",
            # JavaScript & TypeScript
            ".js": "javascript",
            ".jsx": "javascript",
            ".mjs": "javascript",
            ".cjs": "javascript",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".mts": "typescript",
            ".cts": "typescript",
            # Web
            ".html": "html",
            ".htm": "html",
            ".css": "css",
            ".scss": "scss",
            ".less": "less",
            ".vue": "vue",
            ".svelte": "svelte",
            # Rust & Go
            ".rs": "rust",
            ".go": "go",
            # Java & Kotlin
            ".java": "java",
            ".kt": "kotlin",
            ".kts": "kotlin",
            # C / C++
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".hpp": "cpp",
            ".hh": "cpp",
            # Ruby
            ".rb": "ruby",
            ".rake": "ruby",
            # PHP
            ".php": "php",
            # Swift
            ".swift": "swift",
            # Scala
            ".scala": "scala",
            # C#
            ".cs": "c_sharp",
            # SQL
            ".sql": "sql",
            # Shell
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "bash",
            # Markdown & Text
            ".md": "markdown",
            ".mdx": "markdown",
            ".txt": "text",
            # Config / Data
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".xml": "xml",
            ".csv": "csv",
            # Lua
            ".lua": "lua",
            # R
            ".r": "r",
            ".R": "r",
            # Dart
            ".dart": "dart",
            # Elixir
            ".ex": "elixir",
            ".exs": "elixir",
            # Erlang
            ".erl": "erlang",
            ".hrl": "erlang",
            # Haskell
            ".hs": "haskell",
            # Clojure
            ".clj": "clojure",
            ".cljs": "clojure",
            ".cljc": "clojure",
            ".end": "clojure",
            # OCaml
            ".ml": "ocaml",
            ".mli": "ocaml",
            # Zig
            ".zig": "zig",
            # Nim
            ".nim": "nim",
            # Groovy
            ".groovy": "groovy",
            # Perl
            ".pl": "perl",
            ".pm": "perl",
            # Julia
            ".jl": "julia",
            # Terraform
            ".tf": "terraform",
            # Makefile
            "makefile": "make",
            "Makefile": "make",
            # Dockerfile
            "dockerfile": "dockerfile",
            "Dockerfile": "dockerfile",
        }
        # Xử lý đặc biệt cho file không có extension (Makefile, Dockerfile, ...)
        basename = os.path.basename(file_path).lower()
        if basename in lang_map:
            return lang_map[basename]
        return lang_map.get(ext)

    # ========== PARSER MANAGEMENT ==========
    def _get_parser(self, language: str):
        if language in self.parsers:
            return self.parsers[language]

        # Ưu tiên parser cứng đã import (hoạt động ổn định)
        hardcoded = {
            "python": PY_PARSER,
            "javascript": JS_PARSER,
            "typescript": TS_PARSER,
            "tsx": TSX_PARSER,
            "rust": RUST_PARSER,
        }
        parser = hardcoded.get(language)
        if parser:
            self.parsers[language] = parser
            return parser

        # Fallback sang tree-sitter-languages (có thể lỗi với phiên bản tree-sitter mới)
        try:
            parser = tree_sitter_languages.get_parser(language)
            self.parsers[language] = parser
            return parser
        except Exception:
            return None

    # ========== QUERY MANAGEMENT ==========
    def _get_query(self, language: str) -> str:
        if language in self.queries:
            return self.queries[language]
        query_path = os.path.join(self.query_dir, f"{language}.scm")
        if os.path.exists(query_path):
            with open(query_path, "r", encoding="utf-8") as f:
                query_str = f.read()
            self.queries[language] = query_str
            return query_str
        # Nếu không có file query, trả về None để fallback sang duyệt thủ công
        return None

    # ========== MAIN INDEXING ==========
    def index_file(self, file_path: str):
        language = self.detect_language(file_path)
        if not language:
            return

        parser = self._get_parser(language)
        if not parser:
            return

        code = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        tree = parser.parse(bytes(code, "utf-8"))

        rel_path = os.path.relpath(file_path, self.root).replace('\\', '/')

        symbols = self._extract_symbols(tree.root_node, rel_path, language)  # Truyền language
        edges = self._extract_edges(tree.root_node, rel_path, symbols)

        self._add_contains_edges(symbols, edges)

        self.db.replace_symbols(rel_path, symbols)
        self.db.replace_edges(rel_path, edges)

    def _add_contains_edges(self, symbols, edges):
        """Tạo edges 'contains' giữa class và methods của nó."""
        for sym in symbols:
            if sym["kind"] == "class":
                class_name = sym["name"]
                for other in symbols:
                    if other["kind"] == "method" and other.get("parent_class") == class_name:
                        edges.append(
                            {
                                "source_id": sym["id"],
                                "target_id": other["id"],
                                "type": "contains",
                                "weight": 5.0,
                            }
                        )

    # ========== QUERY-BASED SYMBOL EXTRACTION ==========
    def _extract_symbols_with_query(self, root_node, file_path, query_str, language):
        symbols = []
        lang = HARD_LANGUAGES.get(language)
        if not lang:
            self._traverse_generic(root_node, file_path, symbols)
            return symbols

        try:
            query = lang.query(query_str)
            captures = query.captures(root_node)
            for node, tag in captures:
                if tag == "function":
                    sym = self._make_function_symbol(node, file_path)
                    if sym:
                        symbols.append(sym)
                elif tag == "class":
                    sym = self._make_class_symbol(node, file_path)
                    if sym:
                        symbols.append(sym)
                elif tag == "method":
                    sym = self._make_method_symbol(node, file_path)
                    if sym:
                        symbols.append(sym)
        except Exception:
            self._traverse_generic(root_node, file_path, symbols)
        return symbols

    def _extract_symbols(self, root_node, file_path: str, language: str = "python"):
        symbols = []
        print(f"DEBUG _extract_symbols: language={language}, file_path={file_path[:50]}")
        if language == "python":
            print("  -> Using _traverse_for_symbols")
            self._traverse_for_symbols(root_node, file_path, symbols, parent_class=None)
        else:
            print("  -> Using _traverse_generic")
            self._traverse_generic(root_node, file_path, symbols, parent_class=None)
        print(f"  -> Symbols found: {len(symbols)}")
        return symbols
    # ========== GENERIC TRAVERSAL (FALLBACK) ==========
    def _traverse_generic(self, node, file_path, symbols=None, parent_class=None):
        if symbols is None:
            symbols = []

        is_function = node.type in (
            "function_definition", "function_declaration", "method_definition",
            "function_item", "arrow_function",
        )
        is_class = node.type in (
            "class_definition", "class_declaration",
            "struct_item", "impl_item",
        )

        def get_name(n):
            name_node = self._get_child(n, "name")
            if name_node:
                return name_node.text.decode("utf-8")
            for child in n.children:
                if child.type in ("identifier", "type_identifier", "property_identifier", "simple_identifier"):
                    return child.text.decode("utf-8")
            return None

        if is_function or is_class:
            name = get_name(node)
            # Đặc biệt cho arrow_function: lấy tên từ parent pair hoặc variable_declarator
            if not name and node.type == "arrow_function":
                parent = node.parent
                if parent and parent.type == "pair":
                    key_node = self._get_child(parent, "key")
                    if key_node:
                        name = key_node.text.decode("utf-8")
                elif parent and parent.type == "variable_declarator":
                    name_node = self._get_child(parent, "name")
                    if name_node:
                        name = name_node.text.decode("utf-8")

            if not name:
                for child in node.children:
                    self._traverse_generic(child, file_path, symbols, parent_class)
                return

            if is_function:
                kind = "method" if parent_class else "function"
                sym_id = f"{file_path}::{parent_class + '.' if parent_class else ''}{name}"
                body_node = self._get_child(node, "body")
                body_text = body_node.text.decode("utf-8") if body_node else ""
                body_hash = hashlib.md5(body_text.encode()).hexdigest()
                symbols.append({
                    "id": sym_id, "name": name, "kind": kind,
                    "start_line": node.start_point[0] + 1, "end_line": node.end_point[0] + 1,
                    "signature": name, "body_hash": body_hash, "complexity": 0, "metadata": json.dumps(self._extract_http_metadata(node)),
                })
            elif is_class:
                sym_id = f"{file_path}::{name}"
                body_node = self._get_child(node, "body")
                body_text = body_node.text.decode("utf-8") if body_node else ""
                body_hash = hashlib.md5(body_text.encode()).hexdigest()
                symbols.append({
                    "id": sym_id, "name": name, "kind": "class",
                    "start_line": node.start_point[0] + 1, "end_line": node.end_point[0] + 1,
                    "signature": f"class {name}", "body_hash": body_hash, "complexity": 0, "metadata": json.dumps(self._extract_http_metadata(node)),
                })
                if body_node:
                    for child in body_node.children:
                        self._traverse_generic(child, file_path, symbols, name)
                return
            return

        # Node bao bọc: duyệt vào bên trong
        if node.type in (
            "expression_statement", "program", "module", "script",
            "export_statement", "lexical_declaration", "variable_declaration",
            "object", "pair", "statement_block",
        ):
            for child in node.children:
                self._traverse_generic(child, file_path, symbols, parent_class)
            return

        for child in node.children:
            self._traverse_generic(child, file_path, symbols, parent_class)


    # ========== SYMBOL FACTORIES ==========
    def _make_function_symbol(self, node, file_path):
        name_node = self._get_child(node, "name")
        if not name_node:
            return None
        name = name_node.text.decode("utf-8")
        sym_id = f"{file_path}::{name}"
        body_node = self._get_child(node, "body")
        body_text = body_node.text.decode("utf-8") if body_node else ""
        body_hash = hashlib.md5(body_text.encode()).hexdigest()
        return {
            "id": sym_id,
            "name": name,
            "kind": "function",
            "start_line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
            "signature": name,
            "body_hash": body_hash,
            "complexity": 0,
            "metadata": "{}",
        }

    def _make_class_symbol(self, node, file_path):
        name_node = self._get_child(node, "name")
        if not name_node:
            return None
        name = name_node.text.decode("utf-8")
        sym_id = f"{file_path}::{name}"
        body_node = self._get_child(node, "body")
        body_text = body_node.text.decode("utf-8") if body_node else ""
        body_hash = hashlib.md5(body_text.encode()).hexdigest()
        return {
            "id": sym_id,
            "name": name,
            "kind": "class",
            "start_line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
            "signature": f"class {name}",
            "body_hash": body_hash,
            "complexity": 0,
            "metadata": "{}",
        }

    def _make_method_symbol(self, node, file_path):
        # Có thể bổ sung logic lấy parent class sau
        return self._make_function_symbol(node, file_path)

    # ========== EDGE EXTRACTION ==========
    def _extract_edges(self, root_node, file_path, symbols):
        edges = []
        symbol_map = {s["name"]: s["id"] for s in symbols}
        self._traverse_for_calls(root_node, file_path, symbols, symbol_map, edges)
        self._traverse_for_imports(root_node, file_path, edges)
        self._add_import_references(file_path, symbols, edges)
        return edges

    def _traverse_for_calls(self, node, file_path, symbols, symbol_map, edges):
        if node.type == "call":
            func_node = self._get_child(node, "function")
            if func_node:
                target_name = None
                if func_node.type == "identifier":
                    target_name = func_node.text.decode("utf-8")
                elif func_node.type == "attribute":
                    # self.method() hoặc object.method()
                    attr_node = self._get_child(func_node, "attribute")
                    if attr_node:
                        target_name = attr_node.text.decode("utf-8")
                    # Nếu là self.method, ta chỉ lấy method name
                    if not target_name:
                        # Thử lấy từ object
                        obj_node = self._get_child(func_node, "object")
                        if obj_node and obj_node.type == "identifier":
                            target_name = obj_node.text.decode("utf-8")

                if target_name:
                    enclosing = self._find_enclosing_function(node)
                    if enclosing:
                        source_name = enclosing.text.decode("utf-8")
                        source_id = symbol_map.get(source_name)
                        if not source_id:
                            return

                        # Tìm target trong cùng file trước
                        target_id = symbol_map.get(target_name)
                        # Nếu không có, tìm trong các module được import
                        if not target_id and self.db:
                            # Lấy danh sách imports của file hiện tại
                            imports = self._get_imports_for_file(file_path)
                            # Tìm target trong các module được import
                            for imp_module in imports:
                                cur = self.db.conn.execute(
                                    (
                                        "SELECT id FROM symbols WHERE name = ? AND file_path LIKE ?"
                                        " LIMIT 1"
                                    ),
                                    (target_name, f"%{imp_module}.py"),
                                )
                                row = cur.fetchone()
                                if row:
                                    target_id = row[0]
                                    break
                            # Nếu vẫn không tìm thấy, tìm trong toàn bộ database
                            if not target_id:
                                cur = self.db.conn.execute(
                                    "SELECT id FROM symbols WHERE name = ? LIMIT 1", (target_name,)
                                )
                                row = cur.fetchone()
                                if row:
                                    target_id = row[0]

                        if target_id and source_id != target_id:
                            edges.append(
                                {
                                    "source_id": source_id,
                                    "target_id": target_id,
                                    "type": "calls",
                                    "weight": 5.0,
                                }
                            )
        for child in node.children:
            self._traverse_for_calls(child, file_path, symbols, symbol_map, edges)

    def _get_imports_for_file(self, file_path):
        """Lấy danh sách các module được import trong file."""
        imports = set()
        # Parse imports từ AST
        code = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        tree = PY_PARSER.parse(bytes(code, "utf-8"))
        self._collect_imports(tree.root_node, imports)
        return imports

    def _collect_imports(self, node, imports):
        """Đệ quy thu thập tên module từ import statements."""
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    module_name = child.text.decode("utf-8")
                    imports.add(module_name)
        elif node.type == "import_from_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    module_name = child.text.decode("utf-8")
                    imports.add(module_name)
                    break  # Chỉ lấy module chính
        for child in node.children:
            self._collect_imports(child, imports)

    def _traverse_for_imports(self, root_node, file_path, edges):
        self._find_imports_recursive(root_node, file_path, edges)

    def _find_imports_recursive(self, node, file_path, edges):
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    module_name = child.text.decode("utf-8")
                    file_id = f"file:{os.path.relpath(file_path, self.root)}"
                    edges.append(
                        {
                            "source_id": file_id,
                            "target_id": f"module:{module_name}",
                            "type": "imports",
                        }
                    )
        elif node.type == "import_from_statement":
            module_name = None
            for child in node.children:
                if child.type == "dotted_name":
                    if module_name is None:
                        module_name = child.text.decode("utf-8")
            if module_name:
                file_id = f"file:{os.path.relpath(file_path, self.root)}"
                edges.append(
                    {"source_id": file_id, "target_id": f"module:{module_name}", "type": "imports"}
                )
        for child in node.children:
            self._find_imports_recursive(child, file_path, edges)

    # ========== HELPERS ==========
    def _get_child(self, node, field_name):
        return node.child_by_field_name(field_name)

    def _find_enclosing_function(self, node):
        current = node.parent
        while current:
            if current.type in (
                "function_definition",
                "class_definition",
                "function_declaration",
                "class_declaration",
                "method_definition",
            ):
                return self._get_child(current, "name")
            current = current.parent
        return None

    def _add_import_references(self, file_path, symbols, edges):
        """Tạo edges references từ class-level symbols đến class-level symbols của module được import."""
        imports = [e for e in edges if e["type"] == "imports"]
        if not imports:
            return

        used_names = self._get_used_names(file_path)

        # Lọc symbols cấp class (class và function standalone)
        class_symbols = [s for s in symbols if s["kind"] in ("class", "function")]
        if not class_symbols:
            class_symbols = symbols[:1]  # fallback

        for imp in imports:
            module_name = imp["target_id"].replace("module:", "")
            cur = self.db.conn.execute(
                (
                    "SELECT id, name, kind FROM symbols WHERE file_path LIKE ? AND kind IN"
                    " ('class', 'function')"
                ),
                (f"%{module_name}.py",),
            )
            imported_symbols = {row[1]: row[0] for row in cur.fetchall()}

            for used_name in used_names:
                if used_name in imported_symbols:
                    for sym in class_symbols:
                        edges.append(
                            {
                                "source_id": sym["id"],
                                "target_id": imported_symbols[used_name],
                                "type": "references",
                                "weight": 5.0,
                            }
                        )
                        # Thêm chiều ngược lại
                        edges.append(
                            {
                                "source_id": imported_symbols[used_name],
                                "target_id": sym["id"],
                                "type": "references",
                                "weight": 5.0,
                            }
                        )

    def _traverse_for_symbols(self, node, file_path: str, symbols: list, parent_class=None):
        """Đệ quy tìm function_definition và class_definition (Python)."""
        if not hasattr(self, '_debug_printed'):
            self._debug_printed = True
            print(f"DEBUG root children: {[c.type for c in node.children[:20]]}")
        if node.type == "function_definition":
            name_node = self._get_child(node, "name")
            if name_node:
                name = name_node.text.decode("utf-8")
                kind = "method" if parent_class else "function"
                sym_id = f"{file_path}::{parent_class + '.' if parent_class else ''}{name}"
                body_node = self._get_child(node, "body")
                body_text = body_node.text.decode("utf-8") if body_node else ""
                body_hash = hashlib.md5(body_text.encode()).hexdigest()
                meta = self._extract_http_metadata(node)
                print(f"DEBUG metadata for function {name}: {meta}")
                symbols.append(
                    {
                        "id": sym_id,
                        "name": name,
                        "kind": kind,
                        "start_line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                        "signature": (
                            name_node.parent.text.decode("utf-8").split(":")[0].strip()
                            if name_node.parent
                            else name
                        ),
                        "body_hash": body_hash,
                        "complexity": 0,
                        "metadata": json.dumps(meta),
                        "parent_class": parent_class,       
                    }
                )
        elif node.type == "class_definition":
            name_node = self._get_child(node, "name")
            if name_node:
                class_name = name_node.text.decode("utf-8")
                sym_id = f"{file_path}::{class_name}"
                body_node = self._get_child(node, "body")
                body_text = body_node.text.decode("utf-8") if body_node else ""
                body_hash = hashlib.md5(body_text.encode()).hexdigest()
                meta = self._extract_http_metadata(node)
                print(f"DEBUG metadata for class {class_name}: {meta}")
                symbols.append(
                    {
                        "id": sym_id,
                        "name": class_name,
                        "kind": "class",
                        "start_line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                        "signature": f"class {class_name}",
                        "body_hash": body_hash,
                        "complexity": 0,
                        "metadata": json.dumps(meta),
                        "parent_class": None,
                    }
                )
                if body_node:
                    for child in body_node.children:
                        self._traverse_for_symbols(
                            child, file_path, symbols, parent_class=class_name
                        )
                return  # Không duyệt tiếp vào class body ở vòng ngoài
            
        elif node.type == "decorated_definition":
            print(f"  -> Traversing decorated definition, children: {[c.type for c in node.children]}")
            for child in node.children:
                self._traverse_for_symbols(child, file_path, symbols, parent_class)
            return
        else:
            # Duyệt tất cả children cho các node khác
            for child in node.children:
                self._traverse_for_symbols(child, file_path, symbols, parent_class)

    def _get_used_names(self, file_path):
        """Lấy tất cả các tên (identifier, attribute) được sử dụng trong file."""
        code = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        tree = PY_PARSER.parse(bytes(code, "utf-8"))
        names = set()
        self._collect_names(tree.root_node, names)
        return names

    def _collect_names(self, node, names):
        """Đệ quy thu thập tên identifier và attribute."""
        if node.type == "identifier":
            names.add(node.text.decode("utf-8"))
        elif node.type == "attribute":
            attr_node = self._get_child(node, "attribute")
            if attr_node:
                names.add(attr_node.text.decode("utf-8"))
        for child in node.children:
            self._collect_names(child, names)


    def _extract_http_metadata(self, node):
        """Trích xuất HTTP method và path từ decorator của FastAPI/Flask."""
        http_info = {}
        import re
        
        parent = node.parent
        
        # Trường hợp function nằm trong decorated_definition (có decorator)
        if parent and parent.type == 'decorated_definition':
            for child in parent.children:
                if child.type == 'decorator':
                    decorator_text = child.text.decode('utf-8')
                    http_info = self._parse_decorator(decorator_text, http_info)
                    if http_info:
                        break
            if http_info and 'path' in http_info:
                router_prefix = self._get_router_prefix(node)
                if router_prefix:
                    http_info['path'] = router_prefix + http_info['path']
            return http_info
        
        # Trường hợp function nằm trực tiếp trong block/module
        if parent and parent.type in ('block', 'module'):
            func_idx = None
            for i, child in enumerate(parent.children):
                if child == node:
                    func_idx = i
                    break
            
            if func_idx is not None and func_idx > 0:
                prev = parent.children[func_idx - 1]
                if prev.type == 'decorator':
                    decorator_text = prev.text.decode('utf-8')
                    http_info = self._parse_decorator(decorator_text, http_info)
        
        if http_info and 'path' in http_info:
            router_prefix = self._get_router_prefix(node)
            if router_prefix:
                http_info['path'] = router_prefix + http_info['path']
        
        return http_info

    def _parse_decorator(self, decorator_text, http_info):
        """Parse một decorator để lấy method và path."""
        import re
        print(f"DEBUG _parse_decorator: {decorator_text[:100]}")  # Thêm dòng này

        # FastAPI: @router.post("/books/borrow") hoặc @app.get("/books/search")
        fastapi_match = re.search(
            r'@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
            decorator_text
        )
        if fastapi_match:
            http_info['method'] = fastapi_match.group(1).upper()
            http_info['path'] = fastapi_match.group(2)
            http_info['framework'] = 'FastAPI'
            print(f"  -> Parsed: {http_info}")  # Thêm dòng này

        return http_info

    def _get_router_prefix(self, node):
        """Tìm router prefix từ file (ví dụ: @router = APIRouter(prefix="/api"))."""
        import re
        try:
            root = node
            while root.parent:
                root = root.parent
            code = root.text.decode('utf-8')
            match = re.search(r'APIRouter\s*\(\s*prefix\s*=\s*["\']([^"\']+)["\']', code)
            if match:
                return match.group(1)
        except Exception:
            pass
        return ""