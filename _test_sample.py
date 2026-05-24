# Thay thế phần @"..."@ | Out-File bằng đoạn này:
with open("_test_sample.py", "w", encoding="utf-8") as f:
    f.write("""def helper():
    return 42

# main() calls helper() and print()
def main():
    result = helper()
    print(result)

class Calculator:
    def add(self, a, b):
        return a + b
    
    def compute(self):
        return self.add(1, 2)
""")
