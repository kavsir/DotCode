"""
CodeRAG Chain - Tích hợp Code Graph và GraphRAG cho DotCode sử dụng LangChain.
Hỗ trợ cả OpenAI và DeepSeek (nếu có DEEPSEEK_API_KEY).
"""

import os
import sqlite3

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent


class CodeRAG:
    def __init__(self, code_graph, graphrag):
        self.code_graph = code_graph
        self.graphrag = graphrag
        self.llm = self._create_llm()
        self.agent = self._create_agent()

    def _create_llm(self):
        """Tạo LLM phù hợp dựa trên API key có sẵn."""
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        if deepseek_key:
            # Dùng DeepSeek qua ChatOpenAI với base_url
            return ChatOpenAI(
                model="deepseek-v4-flash",
                temperature=0,
                api_key=deepseek_key,
                base_url="https://api.deepseek.com/v1",
            )
        elif openai_key:
            # Dùng OpenAI
            return ChatOpenAI(model="gpt-4o-mini", temperature=0)
        else:
            # Fallback: thử dùng model local qua Ollama
            try:
                from langchain_ollama import ChatOllama

                return ChatOllama(model="llama3.1:8b", temperature=0)
            except ImportError:
                raise ValueError(
                    "No API key found. Set DEEPSEEK_API_KEY, OPENAI_API_KEY, or install Ollama."
                )

    def _get_fresh_connection(self):
        """Tạo kết nối SQLite mới cho thread hiện tại."""
        if hasattr(self.code_graph.db, '_db'):
            raw_db = self.code_graph.db._db
            conn = sqlite3.connect(raw_db.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        else:
            conn = sqlite3.connect(self.code_graph.db_path)
            conn.row_factory = sqlite3.Row
            return conn

    def _query_code_graph_impl(self, query: str) -> str:
        """Tìm kiếm trên Code Graph và trả về kết quả dạng text, bao gồm HTTP metadata."""
        conn = self._get_fresh_connection()
        try:
            cur = conn.execute(
                """SELECT * FROM symbols 
                WHERE name LIKE ? OR signature LIKE ?
                ORDER BY COALESCE(pagerank, 0.0) DESC
                LIMIT 5""",
                (f"%{query}%", f"%{query}%"),
            )
            symbols = [dict(row) for row in cur.fetchall()]

            if not symbols:
                return "No results found."

            results = []
            for sym in symbols:
                # Lấy callees
                cur2 = conn.execute(
                    "SELECT s.name FROM symbols s JOIN edges e ON s.id = e.target_id WHERE e.source_id = ? AND e.type = 'calls'",
                    (sym["id"],),
                )
                callees = [row[0] for row in cur2.fetchall()]
                callee_str = ", ".join(callees[:3]) if callees else "none"

                # Lấy callers
                cur3 = conn.execute(
                    "SELECT s.name FROM symbols s JOIN edges e ON s.id = e.source_id WHERE e.target_id = ? AND e.type = 'calls'",
                    (sym["id"],),
                )
                callers = [row[0] for row in cur3.fetchall()]
                caller_str = ", ".join(callers[:3]) if callers else "none"

                # DotCode: Parse metadata để hiển thị HTTP path
                meta_str = sym.get("metadata", "{}")
                http_info = ""
                try:
                    import json
                    meta = json.loads(meta_str) if meta_str else {}
                    if meta.get("method") and meta.get("path"):
                        http_info = f" [{meta['method']} {meta['path']}]"
                except Exception:
                    pass

                results.append(
                    f"{sym['kind']} {sym['name']}{http_info} in {sym['file_path']} (line {sym['start_line']})"
                    f" -> calls: [{callee_str}], called by: [{caller_str}]"
                )
            return "\n".join(results)
        finally:
            conn.close()

    def _query_graphrag_impl(self, query: str) -> str:
        """Tìm kiếm ngữ nghĩa với GraphRAG."""
        results = self.graphrag.semantic_search(query, limit=5)
        if not results:
            return "No results found."
        lines = []
        for r in results:
            name = r.get('name', 'unknown')
            kind = r.get('kind', 'unknown')
            file_path = r.get('file_path', '')
            relevance = r.get('relevance', 0.0)
            
            # DotCode: Thêm HTTP metadata nếu có
            detail = r.get('detail', {})
            http_info = ""
            if detail:
                meta_str = detail.get('metadata', '{}')
                try:
                    import json
                    meta = json.loads(meta_str) if isinstance(meta_str, str) else meta_str
                    if meta.get("method") and meta.get("path"):
                        http_info = f" [{meta['method']} {meta['path']}]"
                except Exception:
                    pass
            
            lines.append(f"{name}{http_info} ({kind}) in {file_path} - relevance: {relevance:.2f}")
        return "\n".join(lines)

    def _create_agent(self):
        """Tạo LangChain Agent với các tool là Code Graph và GraphRAG."""

        @tool
        def code_graph_tool(query: str) -> str:
            """Useful for finding functions, classes, their callers, and callees. Input: a function or class name."""
            return self._query_code_graph_impl(query)

        @tool
        def graphrag_tool(query: str) -> str:
            """Useful for finding code related to a specific concept or natural language description. Input: a concept or description."""
            return self._query_graphrag_impl(query)

        tools = [code_graph_tool, graphrag_tool]
        return create_react_agent(self.llm, tools)

    def query(self, question: str) -> str:
        """Xử lý câu hỏi của người dùng qua LangChain Agent."""
        try:
            # Gọi agent với input là câu hỏi
            result = self.agent.invoke({"messages": [("user", question)]})
            # Lấy message cuối cùng (câu trả lời)
            for msg in reversed(result["messages"]):
                if msg.type == "ai":
                    return msg.content
            return "Sorry, I couldn't generate an answer."
        except Exception as e:
            return f"Sorry, I couldn't process your question: {e}"
