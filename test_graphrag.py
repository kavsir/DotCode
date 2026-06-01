import sys
sys.path.insert(0, "D:/DotCode")
from dotcode.graph import CodeGraph

cg = CodeGraph(root=".")
cg.index()
print("Total symbols in DB:", cg.db.count_symbols())
print("GraphRAG collection count:", cg.graphrag.collection.count() if cg.graphrag else 0)
results = cg.semantic_search("muon sach", limit=5)
print("Semantic search results:")
for r in results:
    name = r.get("name", "unknown")
    kind = r.get("kind", "unknown")
    file_path = r.get("file_path", "")
    relevance = r.get("relevance", 0.0)
    print(f"  {name} ({kind}) in {file_path} - relevance: {relevance:.2f}")