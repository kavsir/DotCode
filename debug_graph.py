import os

from dotcode.graph.__init__old import CodeGraph

root = "multi_lang_sample"
cg = CodeGraph(root=root)
cg.index()

print(f"Symbols in DB: {cg.db.count_symbols()}")

files = [os.path.join(root, f) for f in os.listdir(root) if os.path.isfile(os.path.join(root, f))]
context = cg.get_context(chat_files=files, other_files=[])
print("=== CONTEXT ===")
print(context)
