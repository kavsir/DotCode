import re
from enum import Enum

class RiskLevel(Enum):
    LOW = "auto"
    MEDIUM = "confirm"
    HIGH = "approve"

class HITLManager:
    def __init__(self):
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