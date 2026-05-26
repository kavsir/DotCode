# dotcode/graph/indexer.py
import os
import hashlib
from pathlib import Path
import tree_sitter_languages
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Parser
import tree_sitter_rust as tsrust
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
    'python': PY_LANGUAGE,
    'javascript': JS_LANGUAGE,
    'typescript': TS_LANGUAGE,
    'tsx': TSX_LANGUAGE,
    'rust': RUST_LANGUAGE,
}
class Indexer:
    def __init__(self, db, root: str):
        self.db = db
        self.root = root
        self.parsers = {}       # Cache parser theo ngôn ngữ
        self.queries = {}       # Cache query string theo ngôn ngữ
        self.query_dir = os.path.join(os.path.dirname(__file__), "queries")

    # ========== LANGUAGE DETECTION ==========
    def detect_language(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        lang_map = {
            # Python
            '.py': 'python', '.pyw': 'python', '.pyx': 'python', '.pxd': 'python', '.pxi': 'python',
            # JavaScript & TypeScript
            '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
            '.ts': 'typescript', '.tsx': 'tsx', '.mts': 'typescript', '.cts': 'typescript',
            # Web
            '.html': 'html', '.htm': 'html', '.css': 'css', '.scss': 'scss', '.less': 'less',
            '.vue': 'vue', '.svelte': 'svelte',
            # Rust & Go
            '.rs': 'rust', '.go': 'go',
            # Java & Kotlin
            '.java': 'java', '.kt': 'kotlin', '.kts': 'kotlin',
            # C / C++
            '.c': 'c', '.h': 'c', '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp', '.hh': 'cpp',
            # Ruby
            '.rb': 'ruby', '.rake': 'ruby',
            # PHP
            '.php': 'php',
            # Swift
            '.swift': 'swift',
            # Scala
            '.scala': 'scala',
            # C#
            '.cs': 'c_sharp',
            # SQL
            '.sql': 'sql',
            # Shell
            '.sh': 'bash', '.bash': 'bash', '.zsh': 'bash',
            # Markdown & Text
            '.md': 'markdown', '.mdx': 'markdown', '.txt': 'text',
            # Config / Data
            '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml', '.toml': 'toml',
            '.xml': 'xml', '.csv': 'csv',
            # Lua
            '.lua': 'lua',
            # R
            '.r': 'r', '.R': 'r',
            # Dart
            '.dart': 'dart',
            # Elixir
            '.ex': 'elixir', '.exs': 'elixir',
            # Erlang
            '.erl': 'erlang', '.hrl': 'erlang',
            # Haskell
            '.hs': 'haskell',
            # Clojure
            '.clj': 'clojure', '.cljs': 'clojure', '.cljc': 'clojure', '.edn': 'clojure',
            # OCaml
            '.ml': 'ocaml', '.mli': 'ocaml',
            # Zig
            '.zig': 'zig',
            # Nim
            '.nim': 'nim',
            # Groovy
            '.groovy': 'groovy',
            # Perl
            '.pl': 'perl', '.pm': 'perl',
            # Julia
            '.jl': 'julia',
            # Terraform
            '.tf': 'terraform',
            # Makefile
            'makefile': 'make', 'Makefile': 'make',
            # Dockerfile
            'dockerfile': 'dockerfile', 'Dockerfile': 'dockerfile',
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
            'python': PY_PARSER,
            'javascript': JS_PARSER,
            'typescript': TS_PARSER,
            'tsx': TSX_PARSER,
            'rust': RUST_PARSER,
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

        code = Path(file_path).read_text(encoding='utf-8', errors='ignore')
        tree = parser.parse(bytes(code, 'utf-8'))

        # Debug: in các node types ở cấp cao nhất cho TypeScript
        if language == 'typescript':
            print(f"Root children for {file_path}:")
            for child in tree.root_node.children:
                print(f"  {child.type}")

        # Tạm thời bỏ query cho tất cả ngôn ngữ để test _traverse_generic
        query_str = None
        symbols = []

        print(f"\n--- Traversing {file_path} ({language}) ---")
        self._traverse_generic(tree.root_node, file_path, symbols)
        print(f"Symbols found: {len(symbols)}")

        edges = self._extract_edges(tree.root_node, file_path, symbols)

        rel_path = os.path.relpath(file_path, self.root)
        self.db.replace_symbols(rel_path, symbols)
        self.db.replace_edges(rel_path, edges)

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
    # ========== GENERIC TRAVERSAL (FALLBACK) ==========
    def _traverse_generic(self, node, file_path, symbols=None, parent_class=None):
        if symbols is None:
            symbols = []

        is_function = node.type in (
            'function_definition', 'function_declaration', 'method_definition',
            'function_item',
        )
        is_class = node.type in (
            'class_definition', 'class_declaration',
            'struct_item', 'impl_item',
        )

        def get_name(n):
            name_node = self._get_child(n, 'name')
            if name_node:
                return name_node.text.decode('utf-8')
            for child in n.children:
                if child.type in ('identifier', 'type_identifier', 'property_identifier', 'simple_identifier'):
                    return child.text.decode('utf-8')
            return None

        # Xử lý function/class
        if is_function or is_class:
            name = get_name(node)
            if not name:
                for child in node.children:
                    self._traverse_generic(child, file_path, symbols, parent_class)
                return

            if is_function:
                kind = 'method' if parent_class else 'function'
                sym_id = f"{file_path}::{parent_class + '.' if parent_class else ''}{name}"
                body_node = self._get_child(node, 'body')
                body_text = body_node.text.decode('utf-8') if body_node else ''
                body_hash = hashlib.md5(body_text.encode()).hexdigest()
                symbols.append({
                    'id': sym_id, 'name': name, 'kind': kind,
                    'start_line': node.start_point[0] + 1,
                    'end_line': node.end_point[0] + 1,
                    'signature': name,
                    'body_hash': body_hash,
                    'complexity': 0,
                    'metadata': '{}'
                })
            elif is_class:
                sym_id = f"{file_path}::{name}"
                body_node = self._get_child(node, 'body')
                body_text = body_node.text.decode('utf-8') if body_node else ''
                body_hash = hashlib.md5(body_text.encode()).hexdigest()
                symbols.append({
                    'id': sym_id, 'name': name, 'kind': 'class',
                    'start_line': node.start_point[0] + 1,
                    'end_line': node.end_point[0] + 1,
                    'signature': f"class {name}",
                    'body_hash': body_hash,
                    'complexity': 0,
                    'metadata': '{}'
                })
                if body_node:
                    for child in body_node.children:
                        self._traverse_generic(child, file_path, symbols, name)
                return
            # Sau khi xử lý function, return để không duyệt lại children
            return

        # Xử lý các node bao bọc (expression_statement, program, module, script)
        if node.type in ('expression_statement', 'program', 'module', 'script'):
            for child in node.children:
                self._traverse_generic(child, file_path, symbols, parent_class)
            return

        # Duyệt tất cả children cho các node còn lại
        for child in node.children:
            self._traverse_generic(child, file_path, symbols, parent_class)

    # ========== SYMBOL FACTORIES ==========
    def _make_function_symbol(self, node, file_path):
        name_node = self._get_child(node, 'name')
        if not name_node:
            return None
        name = name_node.text.decode('utf-8')
        sym_id = f"{file_path}::{name}"
        body_node = self._get_child(node, 'body')
        body_text = body_node.text.decode('utf-8') if body_node else ''
        body_hash = hashlib.md5(body_text.encode()).hexdigest()
        return {
            'id': sym_id,
            'name': name,
            'kind': 'function',
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
            'signature': name,
            'body_hash': body_hash,
            'complexity': 0,
            'metadata': '{}'
        }

    def _make_class_symbol(self, node, file_path):
        name_node = self._get_child(node, 'name')
        if not name_node:
            return None
        name = name_node.text.decode('utf-8')
        sym_id = f"{file_path}::{name}"
        body_node = self._get_child(node, 'body')
        body_text = body_node.text.decode('utf-8') if body_node else ''
        body_hash = hashlib.md5(body_text.encode()).hexdigest()
        return {
            'id': sym_id,
            'name': name,
            'kind': 'class',
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
            'signature': f"class {name}",
            'body_hash': body_hash,
            'complexity': 0,
            'metadata': '{}'
        }

    def _make_method_symbol(self, node, file_path):
        # Có thể bổ sung logic lấy parent class sau
        return self._make_function_symbol(node, file_path)

    # ========== EDGE EXTRACTION ==========
    def _extract_edges(self, root_node, file_path, symbols):
        edges = []
        symbol_map = {s['name']: s['id'] for s in symbols}
        self._traverse_for_calls(root_node, file_path, symbols, symbol_map, edges)
        self._traverse_for_imports(root_node, file_path, edges)
        return edges

    def _traverse_for_calls(self, node, file_path, symbols, symbol_map, edges):
        if node.type == 'call':
            func_node = self._get_child(node, 'function')
            if func_node and func_node.type == 'identifier':
                target_name = func_node.text.decode('utf-8')
                enclosing = self._find_enclosing_function(node)
                if enclosing:
                    source_name = enclosing.text.decode('utf-8')
                    source_id = symbol_map.get(source_name)
                    if not source_id:
                        return
                    target_id = symbol_map.get(target_name)
                    if not target_id and self.db:
                        cur = self.db.conn.execute(
                            "SELECT id FROM symbols WHERE name = ? LIMIT 1",
                            (target_name,)
                        )
                        row = cur.fetchone()
                        if row:
                            target_id = row[0]
                    if target_id and source_id != target_id:
                        edges.append({
                            'source_id': source_id,
                            'target_id': target_id,
                            'type': 'calls'
                        })
        for child in node.children:
            self._traverse_for_calls(child, file_path, symbols, symbol_map, edges)

    def _traverse_for_imports(self, root_node, file_path, edges):
        self._find_imports_recursive(root_node, file_path, edges)

    def _find_imports_recursive(self, node, file_path, edges):
        if node.type == 'import_statement':
            for child in node.children:
                if child.type == 'dotted_name':
                    module_name = child.text.decode('utf-8')
                    file_id = f"file:{os.path.relpath(file_path, self.root)}"
                    edges.append({
                        'source_id': file_id,
                        'target_id': f"module:{module_name}",
                        'type': 'imports'
                    })
        elif node.type == 'import_from_statement':
            module_name = None
            for child in node.children:
                if child.type == 'dotted_name':
                    if module_name is None:
                        module_name = child.text.decode('utf-8')
            if module_name:
                file_id = f"file:{os.path.relpath(file_path, self.root)}"
                edges.append({
                    'source_id': file_id,
                    'target_id': f"module:{module_name}",
                    'type': 'imports'
                })
        for child in node.children:
            self._find_imports_recursive(child, file_path, edges)

    # ========== HELPERS ==========
    def _get_child(self, node, field_name):
        return node.child_by_field_name(field_name)

    def _find_enclosing_function(self, node):
        current = node.parent
        while current:
            if current.type in ('function_definition', 'class_definition',
                                'function_declaration', 'class_declaration',
                                'method_definition'):
                return self._get_child(current, 'name')
            current = current.parent
        return None