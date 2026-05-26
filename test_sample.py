import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from dotcode.graph import CodeGraph

# Trỏ đến thư mục dự án mẫu (đổi đường dẫn nếu cần)
project_root = os.path.join(os.path.dirname(__file__), "sample_project")
cg = CodeGraph(root=project_root)
cg.index()

print("=== Context cho cả hai file ===")
context = cg.get_context(
    chat_files=[os.path.join(project_root, "main.py")],
    other_files=[os.path.join(project_root, "utils.py")]
)
print(context)