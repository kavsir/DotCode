import re

with open("aider/coders/base_coder.py", "r", encoding="utf-8") as f:
    content = f.read()

# We need to replace the entire _handle_search function.
# Let's find its start and end.
import ast
class FuncFinder(ast.NodeVisitor):
    def __init__(self):
        self.start = None
        self.end = None
    
    def visit_FunctionDef(self, node):
        if node.name == "_handle_search":
            self.start = node.lineno
            self.end = getattr(node, "end_lineno", None)
        self.generic_visit(node)

tree = ast.parse(content)
finder = FuncFinder()
finder.visit(tree)

if not finder.start or not finder.end:
    print("Could not find _handle_search")
    exit(1)

new_method = """    def _handle_search(self, message):
        \"\"\"Xử lý tìm kiếm: ưu tiên Cross-Community Bridge Analysis, sau đó là tìm kiếm thông thường.\"\"\"
        if not hasattr(self, "code_graph") or not self.code_graph:
            self.io.tool_output("🔍 Code Graph Engine is not available for this project.")
            return

        # Đảm bảo GraphRAG engine được khởi tạo
        if hasattr(self.code_graph, "_ensure_graphrag"):
            self.code_graph._ensure_graphrag()

        # ===== DotCode: Phân tích ngữ nghĩa tìm kiếm với LLM =====
        search_params = {"is_bridge": False, "entity1": None, "entity2": None, "kind_filter": None}
        import os, requests, json
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if api_key:
            prompt = f\"\"\"Phân tích yêu cầu tìm kiếm sau của lập trình viên: "{message}"
Trả về JSON chứa các key:
- "is_bridge" (bool): true nếu người dùng đang hỏi về MỐI QUAN HỆ, TƯƠNG TÁC, KẾT NỐI giữa 2 module/component/hàm khác nhau.
- "entity1" (str): Tên thành phần thứ nhất (nếu is_bridge = true).
- "entity2" (str): Tên thành phần thứ hai (nếu is_bridge = true).
- "kind_filter" (str hoặc null): Loại thành phần mà người dùng muốn tìm (chỉ chọn từ: "class", "function", "variable", "interface", "method"), nếu không có thì để null.
Chỉ trả về JSON hợp lệ.\"\"\"
            try:
                response = requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "max_tokens": 100, "temperature": 0.0},
                    timeout=10,
                )
                if response.status_code == 200:
                    c = response.json()["choices"][0]["message"]["content"].strip()
                    if "```json" in c: c = c.split("```json")[1].split("```")[0].strip()
                    elif "```" in c: c = c.split("```")[1].split("```")[0].strip()
                    search_params.update(json.loads(c))
            except Exception:
                pass

        if search_params.get("is_bridge") and search_params.get("entity1") and search_params.get("entity2"):
            if self.code_graph.graphrag and not self.code_graph.graphrag.communities:
                self.code_graph.graphrag.detect_communities()
                self.code_graph.graphrag.summarize_communities()
                
            if self.code_graph.graphrag and self.code_graph.graphrag.communities:
                name1 = search_params["entity1"]
                name2 = search_params["entity2"]
                syms1 = self.code_graph.search(name1, limit=1)
                syms2 = self.code_graph.search(name2, limit=1)
                if syms1 and syms2:
                    sym1_id = syms1[0].id if hasattr(syms1[0], "id") else syms1[0]["id"]
                    sym2_id = syms2[0].id if hasattr(syms2[0], "id") else syms2[0]["id"]
                    comm1 = self.code_graph.graphrag.node_to_community.get(sym1_id)
                    comm2 = self.code_graph.graphrag.node_to_community.get(sym2_id)
                    if comm1 is not None and comm2 is not None and comm1 != comm2:
                        from dotcode.graph.multi_hop import MultiHopEngine
                        raw_db = self.code_graph.db._db if hasattr(self.code_graph.db, "_db") else self.code_graph.db
                        temp_multi_hop = MultiHopEngine(raw_db)
                        bridges = temp_multi_hop.find_community_bridges(
                            comm1, comm2, self.code_graph.graphrag.node_to_community,
                            edge_types=["calls", "references", "contains"]
                        )
                        comm1_data = self.code_graph.graphrag.communities.get(comm1, {})
                        comm2_data = self.code_graph.graphrag.communities.get(comm2, {})
                        self.io.tool_output(f"🌉 Phân tích liên kết {name1} ↔ {name2}:")
                        self.io.tool_output(f"  Community {comm1}: {comm1_data.get('summary', 'N/A')[:100]}...")
                        self.io.tool_output(f"  Community {comm2}: {comm2_data.get('summary', 'N/A')[:100]}...")
                        self.io.tool_output(f"  Bridges found: {len(bridges)}")
                        for b in bridges[:5]:
                            self.io.tool_output(
                                f"    • {b['source'].name} ({b['source'].file_path}) →"
                                f" {b['target'].name} ({b['target'].file_path}) [{b['edge_type']}]"
                            )
                        if len(bridges) == 0:
                            self.io.tool_output("  → Hai module này không có kết nối trực tiếp.")
                        elif len(bridges) <= 2:
                            self.io.tool_output("  → Kết nối yếu, hai module hoạt động độc lập.")
                        elif len(bridges) <= 5:
                            self.io.tool_output("  → Có sự tương tác rõ ràng giữa hai module.")
                        else:
                            self.io.tool_output("  → Tương tác rất chặt chẽ, chú ý blast radius khi sửa đổi.")
                        return

        # ===== Tìm kiếm thông thường =====
        all_symbols = []
        seen_ids = set()
        import re
        tokens = re.findall(r"[\\w]+", message, re.UNICODE)
        tokens = [t for t in tokens if len(t) >= 3 and not t.isdigit()]
        for token in tokens[:5]:
            symbols = self.code_graph.search(token, limit=10)
            for sym in symbols:
                sym_id = sym.id if hasattr(sym, "id") else sym["id"]
                if sym_id not in seen_ids:
                    seen_ids.add(sym_id)
                    all_symbols.append(sym)
                    
        if hasattr(self.code_graph, "graphrag") and self.code_graph.graphrag:
            try:
                semantic_results = self.code_graph.graphrag.semantic_search(message, limit=10, boost_pagerank=True)
                for r in semantic_results:
                    detail = r.get("detail")
                    if detail:
                        detail_id = detail.id if hasattr(detail, "id") else detail["id"]
                        if detail_id not in seen_ids:
                            seen_ids.add(detail_id)
                            if isinstance(detail, dict):
                                detail["combined_score"] = r.get("combined_score", 0.0)
                            else:
                                detail.combined_score = r.get("combined_score", 0.0)
                            all_symbols.append(detail)
            except Exception as e:
                self.io.tool_output(f"🔍 Semantic search error: {e}")
                
        file_mentions = self.get_file_mentions(message)
        for rel_fname in file_mentions:
            import os
            abs_fname = self.abs_root_path(rel_fname)
            if os.path.exists(abs_fname):
                file_symbols = self.code_graph.db.get_symbols_in_file(rel_fname)
                for sym in file_symbols:
                    sym_id = sym.id if hasattr(sym, "id") else sym["id"]
                    if sym_id not in seen_ids:
                        seen_ids.add(sym_id)
                        all_symbols.append(sym)
                        
        kind_filter = search_params.get("kind_filter")
        if kind_filter and all_symbols:
            filtered = []
            for s in all_symbols:
                s_kind = (
                    s.kind.value
                    if hasattr(s, "kind") and hasattr(s.kind, "value")
                    else (s.get("kind") if isinstance(s, dict) else str(s.kind))
                )
                if kind_filter == "function" and s_kind in ("function", "method"):
                    filtered.append(s)
                elif s_kind == kind_filter:
                    filtered.append(s)
            all_symbols = filtered
            
        if all_symbols:
            def get_score(sym):
                if isinstance(sym, dict):
                    combined = sym.get("combined_score", 0.0)
                    pagerank = sym.get("pagerank", 0.0)
                else:
                    combined = getattr(sym, "combined_score", 0.0) if hasattr(sym, "combined_score") else 0.0
                    pagerank = getattr(sym, "pagerank", 0.0) if hasattr(sym, "pagerank") else 0.0
                if combined is not None and combined > 0:
                    return combined
                return pagerank if pagerank is not None else 0.0
                
            all_symbols.sort(key=get_score, reverse=True)
            self.io.tool_output(f"🔍 Found {len(all_symbols)} results:")
            for sym in all_symbols[:10]:
                if isinstance(sym, dict):
                    kind = sym.get("kind", "?")
                    name = sym.get("name", "?")
                    path = sym.get("file_path", "?")
                else:
                    kind = (
                        sym.kind.value
                        if hasattr(sym, "kind") and hasattr(sym.kind, "value")
                        else str(sym.kind)
                    )
                    name = sym.name
                    path = sym.file_path
                self.io.tool_output(f"  • [{kind}] {name} ({path})")
        else:
            self.io.tool_output("🔍 No matching symbols found.")
"""

lines = content.splitlines()
new_lines = lines[:finder.start - 1] + new_method.splitlines() + lines[finder.end:]
with open("aider/coders/base_coder.py", "w", encoding="utf-8") as f:
    f.write("\n".join(new_lines))
print("Patched _handle_search successfully.")
