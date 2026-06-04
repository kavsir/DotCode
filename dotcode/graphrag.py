import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import chromadb
import igraph as ig
import leidenalg
import numpy as np
from chromadb.config import Settings
from huggingface_hub import login
from sentence_transformers import SentenceTransformer
from sympy import symbols


class GraphRAGEngine:
    def __init__(self, db, root: str):
        self.db = db
        self.root = root
        hf_token = os.getenv("HF_TOKEN")

        # Đăng nhập Hugging Face trước khi tạo model
        if hf_token:
            try:
                login(token=hf_token, add_to_git_credential=False)
            except Exception:
                pass

        # Embedding model
        self.model_name = "BAAI/bge-m3"
        self._model = SentenceTransformer(self.model_name, token=hf_token, trust_remote_code=True)

        # ChromaDB cho vector search
        chroma_dir = os.path.join(root, ".dotcode", "chroma")
        os.makedirs(chroma_dir, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=chroma_dir)
        self.collection = self.chroma_client.get_or_create_collection("code_symbols")

        # Community data (in-memory)
        self.communities: Dict[int, Dict] = {}
        self.node_to_community: Dict[str, int] = {}

    @property
    def model(self):
        if self._model is None:
            self._model = SentenceTransformer(self.model_name, trust_remote_code=True)
        return self._model

    # ==================== COMMUNITY DETECTION ====================

    def detect_communities(self) -> int:
        if not self.db:
            return 0

        symbols = self.db.conn.execute("SELECT id FROM symbols").fetchall()
        edges = self.db.conn.execute(
            "SELECT source_id, target_id, weight FROM edges WHERE type IN ('calls', 'contains',"
            " 'inherits', 'references')"
        ).fetchall()

        if not symbols or not edges:
            return 0

        symbol_ids = [s[0] for s in symbols]
        id_to_idx = {sid: i for i, sid in enumerate(symbol_ids)}

        edge_list = []
        edge_weights = []
        for src, tgt, w in edges:
            if src in id_to_idx and tgt in id_to_idx:
                edge_list.append((id_to_idx[src], id_to_idx[tgt]))
                edge_weights.append(w)

        if not edge_list:
            return 0

        g = ig.Graph(n=len(symbol_ids), edges=edge_list, directed=False)
        g.es["weight"] = edge_weights

        partition = leidenalg.find_partition(
            g, leidenalg.ModularityVertexPartition, weights="weight", n_iterations=10
        )

        self.communities = {}
        self.node_to_community = {}

        for i, comm_id in enumerate(partition.membership):
            symbol_id = symbol_ids[i]
            self.node_to_community[symbol_id] = comm_id
            if comm_id not in self.communities:
                self.communities[comm_id] = {"id": comm_id, "nodes": [], "summary": ""}
            self.communities[comm_id]["nodes"].append(symbol_id)

        return len(self.communities)

    # ==================== SUMMARIZATION ====================

    def summarize_communities(self, use_llm: bool = True) -> None:
        """Tạo tóm tắt cho mỗi community. Nếu use_llm=True, dùng LLM để tạo mô tả có ý nghĩa."""
        for comm_id, comm_data in self.communities.items():
            nodes = comm_data["nodes"][:15]  # Top 15 nodes để tránh quá dài

            # Lấy thông tin chi tiết
            node_info = []
            for node_id in nodes:
                sym = self.db.get_symbol(node_id)
                if sym:
                    node_info.append(
                        f"- {sym['kind']} {sym['name']} in {sym['file_path']} (line"
                        f" {sym['start_line']})"
                    )

            if use_llm:
                summary = self._llm_summarize_community(node_info)
            else:
                summary = self._rule_summarize(node_info)

            self.communities[comm_id]["summary"] = summary

    def _llm_summarize_community(self, node_info: list) -> str:
        """Dùng LLM để tạo tóm tắt có ý nghĩa cho community."""
        import os

        import requests

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            return self._rule_summarize_community_fallback(node_info)

        symbols_text = "\n".join(node_info[:10])

        prompt = f"""You are analyzing a codebase. Below is a list of related functions, classes, and methods that form a "community" (a group of tightly connected code).

    Your task: Write a brief summary (2-3 sentences) describing:
    1. What this community does (its main purpose)
    2. How the key symbols work together
    3. What role this community plays in the larger codebase

    Symbols in this community:
    {symbols_text}

    Summary:"""

        try:
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.3,
                },
                timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                return self._rule_summarize_community_fallback(node_info)
        except Exception:
            return self._rule_summarize_community_fallback(node_info)

    def _rule_summarize_community_fallback(self, node_info: list) -> str:
        """Fallback: tạo tóm tắt rule-based nếu LLM không khả dụng."""
        if not node_info:
            return "Empty community"

        # Đếm loại
        kinds = {}
        for info in node_info[:10]:
            # Trích xuất kind từ chuỗi "- method xxx in file.py"
            parts = info.split()
            if len(parts) >= 2:
                kind = parts[1]
                kinds[kind] = kinds.get(kind, 0) + 1

        kind_str = ", ".join([f"{v} {k}s" for k, v in kinds.items()])
        names = []
        for info in node_info[:5]:
            parts = info.split()
            if len(parts) >= 3:
                names.append(parts[2].rstrip(","))

        return f"Community with {kind_str}. Key symbols: {', '.join(names)}"

    def _rule_summarize(self, names: List[str], kinds: List[str]) -> str:
        if not names:
            return "Empty community"

        kind_counts = {}
        for k in kinds:
            kind_counts[k] = kind_counts.get(k, 0) + 1

        kind_str = ", ".join([f"{v} {k}s" for k, v in kind_counts.items()])
        top_names = names[:5]

        return f"Community with {kind_str}. Key symbols: {', '.join(top_names)}"

    def _llm_summarize(self, names: List[str], kinds: List[str]) -> str:
        return self._rule_summarize(names, kinds)

    # ==================== GLOBAL SEARCH ====================

    def global_search(self, query: str, top_k: int = 3) -> List[Dict]:
        if not self.communities:
            return []

        query_emb = self.model.encode([query], normalize_embeddings=True)[0]

        summaries = []
        comm_ids = []
        for comm_id, comm_data in self.communities.items():
            if comm_data["summary"]:
                summaries.append(comm_data["summary"])
                comm_ids.append(comm_id)

        if not summaries:
            return []

        summary_embs = self.model.encode(summaries, normalize_embeddings=True)
        similarities = np.dot(summary_embs, query_emb)

        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            comm_id = comm_ids[idx]
            comm_data = self.communities[comm_id]

            symbols = []
            for node_id in comm_data["nodes"][:10]:
                sym = self.db.get_symbol(node_id)
                if sym:
                    symbols.append(sym)

            results.append(
                {
                    "community_id": comm_id,
                    "summary": comm_data["summary"],
                    "similarity": float(similarities[idx]),
                    "symbols": symbols,
                }
            )

        return results

    # ==================== LOCAL SEARCH ====================

    def local_search(self, symbol_id: str, depth: int = 2) -> Dict:
        if not self.db:
            return {"symbol": None, "neighbors": []}

        sym = self.db.get_symbol(symbol_id)
        if not sym:
            return {"symbol": None, "neighbors": []}

        neighbors = []
        visited = {symbol_id}
        queue = [(symbol_id, 0)]

        while queue:
            current_id, current_depth = queue.pop(0)
            if current_depth >= depth:
                continue

            callees = self.db.get_callees(current_id)
            for c in callees:
                if c["id"] not in visited:
                    visited.add(c["id"])
                    neighbors.append(
                        {"symbol": c, "depth": current_depth + 1, "direction": "callee"}
                    )
                    queue.append((c["id"], current_depth + 1))

            callers = self.db.get_callers(current_id)
            for c in callers:
                if c["id"] not in visited:
                    visited.add(c["id"])
                    neighbors.append(
                        {"symbol": c, "depth": current_depth + 1, "direction": "caller"}
                    )
                    queue.append((c["id"], current_depth + 1))

        community_id = self.node_to_community.get(symbol_id)
        community_summary = ""
        if community_id is not None and community_id in self.communities:
            community_summary = self.communities[community_id].get("summary", "")

        return {
            "symbol": sym,
            "neighbors": neighbors,
            "community_id": community_id,
            "community_summary": community_summary,
        }

    # ==================== VECTOR INDEX ====================

    def _get_symbol_text(self, symbol: dict) -> str:
        parts = [
            f"{symbol['kind']} {symbol['name']}",
            f"in {symbol['file_path']}",
        ]
        if symbol.get("signature"):
            parts.append(f"signature: {symbol['signature']}")
        return " ".join(parts)

    def index_symbols(self) -> int:
        if not self.db:
            return 0

        symbols = self.db.conn.execute("SELECT * FROM symbols").fetchall()
        symbols = [dict(s) for s in symbols]

        if not symbols:
            return 0

        try:
            self.chroma_client.delete_collection("code_symbols")
        except Exception:
            pass
        self.collection = self.chroma_client.get_or_create_collection("code_symbols")

        texts = []
        metadatas = []
        ids = []

        for sym in symbols:
            text = self._get_symbol_text(sym)
            texts.append(text)
            metadatas.append(
                {
                    "symbol_id": sym["id"],
                    "name": sym["name"],
                    "kind": sym["kind"],
                    "file_path": sym["file_path"],
                    "start_line": sym["start_line"],
                    "pagerank": sym.get("pagerank", 0.0),
                }
            )
            ids.append(sym["id"])

        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_metadatas = metadatas[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]
            embeddings = self.model.encode(batch_texts).tolist()
            self.collection.add(
                embeddings=embeddings,
                documents=batch_texts,
                metadatas=batch_metadatas,
                ids=batch_ids,
            )

        self.detect_communities()
        self.summarize_communities()
        self.auto_weight = self._compute_auto_weight()
        return len(symbols)

    def semantic_search(
        self, query: str, limit: int = 10, boost_pagerank: bool = True
    ) -> List[Dict]:
        """
        Tìm kiếm ngữ nghĩa với PageRank boosting.
        Code Graph (cấu trúc) + GraphRAG (ngữ nghĩa) = kết quả toàn diện.
        """
        if not self.collection or self.collection.count() == 0:
            return []

        query_embedding = self.model.encode([query]).tolist()
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=limit * 2,  # Lấy gấp đôi để lọc
            include=["metadatas", "distances", "documents"],
        )

        symbols = []
        if results["ids"] and results["ids"][0]:
            for i, symbol_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 1.0
                semantic_score = 1.0 - (distance / 2.0)

                sym = self.db.get_symbol(symbol_id) if self.db else None

                # DotCode: Kết hợp PageRank từ Code Graph
                pagerank = sym.get("pagerank", 0.0) if sym else 0.0

                # Công thức kết hợp: semantic_score * (1 + pagerank)
                # PageRank cao sẽ boost điểm số
                if boost_pagerank and pagerank > 0:
                    weight = getattr(self, "auto_weight", 3.0)
                    combined_score = semantic_score * (1.0 + pagerank * weight)
                else:
                    combined_score = semantic_score
                symbols.append(
                    {
                        "symbol_id": symbol_id,
                        "name": metadata.get("name", "unknown"),
                        "kind": metadata.get("kind", "unknown"),
                        "file_path": metadata.get("file_path", ""),
                        "semantic_score": round(semantic_score, 3),
                        "pagerank": round(pagerank, 4),
                        "combined_score": round(combined_score, 3),
                        "detail": sym,
                    }
                )

        # Sắp xếp lại theo combined_score
        symbols.sort(key=lambda x: x["combined_score"], reverse=True)

        # Trả về top limit kết quả
        return symbols[:limit]

    def get_context_for_prompt(self, query: str, max_symbols: int = 10) -> str:
        lines = []

        global_results = self.global_search(query, top_k=2)
        if global_results:
            lines.append("# Related Communities:")
            for gr in global_results:
                lines.append(f"## Community (relevance: {gr['similarity']:.2f})")
                lines.append(f"Summary: {gr['summary']}")
                lines.append("Key symbols:")
                for sym in gr["symbols"][:5]:
                    lines.append(f"  - {sym['kind']} {sym['name']} in {sym['file_path']}")
                lines.append("")

        semantic_results = self.semantic_search(query, limit=max_symbols)
        if semantic_results:
            lines.append("# Semantically Related Symbols:")
            for r in semantic_results[:max_symbols]:
                name = r.get("name", "unknown")
                kind = r.get("kind", "unknown")
                file_path = r.get("file_path", "")
                relevance = r.get("relevance", 0.0)
                lines.append(f"  - {kind} {name} in {file_path} (relevance: {relevance:.2f})")

        return "\n".join(lines)

    def _compute_auto_weight(self) -> float:
        """Tự động tính pagerank_weight dựa trên đặc điểm đồ thị."""
        if not self.db:
            return 3.0

        total_nodes = self.db.count_symbols()
        if total_nodes == 0:
            return 3.0

        edge_count = self.db.conn.execute(
            "SELECT COUNT(*) FROM edges WHERE type IN ('calls', 'references', 'contains')"
        ).fetchone()[0]
        if edge_count == 0:
            return 3.0

        edge_density = edge_count / total_nodes

        pagerank_stats = self.db.conn.execute(
            "SELECT AVG(pagerank), AVG(pagerank * pagerank) FROM symbols WHERE pagerank > 0"
        ).fetchone()

        if pagerank_stats and pagerank_stats[0] and pagerank_stats[1]:
            mean_pr = pagerank_stats[0]
            variance = pagerank_stats[1] - mean_pr * mean_pr
            std_pr = variance**0.5 if variance > 0 else 0.001
            cv = std_pr / mean_pr if mean_pr > 0 else 1.0
        else:
            cv = 1.0

        base_weight = 3.0
        scale_by_nodes = max(1.0, total_nodes / 1000.0)
        scale_by_density = 1.0 / max(edge_density, 0.1)
        scale_by_cv = cv

        auto_weight = base_weight * scale_by_nodes * scale_by_density * scale_by_cv
        auto_weight = max(1.0, min(10.0, auto_weight))

        return round(auto_weight, 2)
