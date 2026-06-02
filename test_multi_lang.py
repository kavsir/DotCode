'Set-Content -Path test_multi_lang.py -Value @'
from dotcode.graph.__init__old import CodeGraph

# Khởi tạo CodeGraph trỏ vào thư mục mẫu đa ngôn ngữ
cg = CodeGraph(root='multi_lang_sample')

# Index toàn bộ dự án mẫu
cg.index()

# Lấy context cho tất cả file mẫu
context = cg.get_context(
    chat_files=[
        'multi_lang_sample/main.py',
        'multi_lang_sample/app.ts',
        'multi_lang_sample/helper.rs'
    ],
    other_files=[]
)

print("=== CONTEXT OUTPUT ===")
print(context)
'@ -Encoding utf8'