import re
from enum import Enum


class RiskLevel(Enum):
    LOW = "auto"
    MEDIUM = "confirm"
    HIGH = "approve"


class HITLManager:
    def __init__(self):
        # Lưu lại rules làm fallback cho các đoạn code quá rời rạc (fragments) không thể parse AST
        self.rules = {
            RiskLevel.LOW: [
                r"^\s*#.*$",
                r"^\s*import\s",
                r"^\s*from\s.*\simport\s",
                r"^\s*pass\s*$",
            ],
            RiskLevel.HIGH: [
                r"^\s*def\s+__init__\s*\(",
                r"^\s*class\s+\w+",
                r"^\s*@\w+",
                r"^\s*raise\s",
            ],
        }

    def classify_change(self, search_block: str, replace_block: str) -> RiskLevel:
        # Nếu chỉ là khoảng trắng hoặc comments
        clean_replace = "\n".join([line for line in replace_block.splitlines() if line.strip() and not line.strip().startswith("#")])
        if not clean_replace:
            return RiskLevel.LOW

        import ast
        import textwrap
        
        # Xử lý lề và vá lỗi thiếu block (ví dụ: đang khai báo class/function dang dở)
        code_to_parse = textwrap.dedent(clean_replace)
        if code_to_parse.strip().endswith(":"):
            code_to_parse += "\n    pass"

        try:
            tree = ast.parse(code_to_parse)
            risk = RiskLevel.LOW
            has_code = False
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    return RiskLevel.HIGH
                if isinstance(node, ast.FunctionDef):
                    if node.name == "__init__" or node.decorator_list:
                        return RiskLevel.HIGH
                    if risk == RiskLevel.LOW:
                        risk = RiskLevel.MEDIUM
                if isinstance(node, ast.Raise):
                    return RiskLevel.HIGH
                
                # Bất kỳ câu lệnh logic nào khác (Loop, Assign, Return, Call...) -> chuyển thành MEDIUM
                if not isinstance(node, (ast.Module, ast.Import, ast.ImportFrom, ast.Pass, ast.Constant, ast.Expr)):
                    if risk == RiskLevel.LOW:
                        risk = RiskLevel.MEDIUM
                    has_code = True
            
            # Nếu AST nhận diện là LOW nhưng block thay thế rất lớn -> MEDIUM
            if risk == RiskLevel.LOW and len(search_block.strip()) > 50 and has_code:
                return RiskLevel.MEDIUM
                
            return risk
        except SyntaxError:
            pass

        # === Fallback Regex (Chỉ kích hoạt nếu AST không thể Parse) ===
        for pattern in self.rules[RiskLevel.HIGH]:
            if re.search(pattern, replace_block, re.MULTILINE):
                return RiskLevel.HIGH
        for pattern in self.rules[RiskLevel.LOW]:
            if re.search(pattern, replace_block, re.MULTILINE):
                if len(search_block.strip()) > 50:
                    return RiskLevel.MEDIUM
                return RiskLevel.LOW
                
        return RiskLevel.MEDIUM

    def should_auto_apply(self, search_block: str, replace_block: str) -> bool:
        return self.classify_change(search_block, replace_block) == RiskLevel.LOW

    def get_confirm_message(self, risk_level: RiskLevel, file_path: str) -> str:
        messages = {
            RiskLevel.LOW: f"🔧 Auto-applied safe change in {file_path}",
            RiskLevel.MEDIUM: f"⚠️ Confirm change in {file_path}?",
            RiskLevel.HIGH: f"🚨 Important change in {file_path} - Please review carefully:",
        }
        return messages[risk_level]
