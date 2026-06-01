import os
import json
import hashlib
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from sentence_transformers import SentenceTransformer
from huggingface_hub import login
import chromadb
from chromadb.config import Settings
import igraph as ig
import leidenalg


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
        self._model = SentenceTransformer(
            self.model_name,
            token=hf_token,
            trust_remote_code=True
        )
        
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
            "SELECT source_id, target_id FROM edges WHERE type IN ('calls', 'references', 'inherits')"
        ).fetchall()
        
        if not symbols or not edges:
            return 0
        
        symbol_ids = [s[0] for s in symbols]
        id_to_idx = {sid: i for i, sid in enumerate(symbol_ids)}
        
        edge_list = []
        for src, tgt in edges:
            if src in id_to_idx and tgt in id_to_idx:
                edge_list.append((id_to_idx[src], id_to_idx[tgt]))
        
        if not edge_list:
            return 0
        
        g = ig.Graph(n=len(symbol_ids), edges=edge_list, directed=True)
        
        partition = leidenalg.find_partition(
            g, leidenalg.ModularityVertexPartition,
            n_iterations=10
        )
        
        self.communities = {}
        self.node_to_community = {}
        
        for i, comm_id in enumerate(partition.membership):
            symbol_id = symbol_ids[i]
            self.node_to_community[symbol_id] = comm_id
            
            if comm_id not in self.communities:
                self.communities[comm_id] = {
                    "id": comm_id,
                    "nodes": [],
                    "summary": "",
                }
            self.communities[comm_id]["nodes"].append(symbol_id)
        
        return len(self.communities)

    # ==================== SUMMARIZATION ====================
    
    def summarize_communities(self, use_llm: bool = False) -> None:
        for comm_id, comm_data in self.communities.items():
            nodes = comm_data["nodes"][:10]
            
            node_names = []
            node_kinds = []
            for node_id in nodes:
                sym = self.db.get_symbol(node_id)
                if sym:
                    node_names.append(sym["name"])
                    node_kinds.append(sym["kind"])
            
            if use_llm:
                summary = self._llm_summarize(node_names, node_kinds)
            else:
                summary = self._rule_summarize(node_names, node_kinds)
            
            self.communities[comm_id]["summary"] = summary

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
            
            results.append({
                "community_id": comm_id,
                "summary": comm_data["summary"],
                "similarity": float(similarities[idx]),
                "symbols": symbols,
            })
        
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
                    neighbors.append({"symbol": c, "depth": current_depth + 1, "direction": "callee"})
                    queue.append((c["id"], current_depth + 1))
            
            callers = self.db.get_callers(current_id)
            for c in callers:
                if c["id"] not in visited:
                    visited.add(c["id"])
                    neighbors.append({"symbol": c, "depth": current_depth + 1, "direction": "caller"})
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
        if symbol.get('signature'):
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
            metadatas.append({
                "symbol_id": sym['id'],
                "name": sym['name'],
                "kind": sym['kind'],
                "file_path": sym['file_path'],
                "start_line": sym['start_line'],
                "pagerank": sym.get('pagerank', 0.0),
            })
            ids.append(sym['id'])
        
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            batch_metadatas = metadatas[i:i+batch_size]
            batch_ids = ids[i:i+batch_size]
            embeddings = self.model.encode(batch_texts).tolist()
            self.collection.add(
                embeddings=embeddings,
                documents=batch_texts,
                metadatas=batch_metadatas,
                ids=batch_ids
            )
        
        self.detect_communities()
        self.summarize_communities()
        
        return len(symbols)

    def semantic_search(self, query: str, limit: int = 10) -> List[Dict]:
        if not self.collection or self.collection.count() == 0:
            return []
        
        query_embedding = self.model.encode([query]).tolist()
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=limit,
            include=["metadatas", "distances", "documents"]
        )
        
        symbols = []
        if results['ids'] and results['ids'][0]:
            for i, symbol_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                distance = results['distances'][0][i] if results['distances'] else 1.0
                sym = self.db.get_symbol(symbol_id) if self.db else None
                
                symbols.append({
                    'symbol_id': symbol_id,
                    'name': metadata.get('name', 'unknown'),
                    'kind': metadata.get('kind', 'unknown'),
                    'file_path': metadata.get('file_path', ''),
                    'relevance': 1.0 - (distance / 2.0),
                    'detail': sym,
                })
        
        return symbols

    def get_context_for_prompt(self, query: str, max_symbols: int = 10) -> str:
        lines = []
        
        global_results = self.global_search(query, top_k=2)
        if global_results:
            lines.append("# Related Communities:")
            for gr in global_results:
                lines.append(f"## Community (relevance: {gr['similarity']:.2f})")
                lines.append(f"Summary: {gr['summary']}")
                lines.append("Key symbols:")
                for sym in gr['symbols'][:5]:
                    lines.append(f"  - {sym['kind']} {sym['name']} in {sym['file_path']}")
                lines.append("")
        
        semantic_results = self.semantic_search(query, limit=max_symbols)
        if semantic_results:
            lines.append("# Semantically Related Symbols:")
            for r in semantic_results[:max_symbols]:
                name = r.get('name', 'unknown')
                kind = r.get('kind', 'unknown')
                file_path = r.get('file_path', '')
                relevance = r.get('relevance', 0.0)
                lines.append(f"  - {kind} {name} in {file_path} (relevance: {relevance:.2f})")
        
        return "\n".join(lines)