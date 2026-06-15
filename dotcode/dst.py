"""
Dialogue State Tracker cho DotCode.
Quản lý trạng thái hội thoại để phân giải intent dựa trên ngữ cảnh.
"""

import time
import json
import os
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import requests
from pydantic import BaseModel


class PendingQuestionType(Enum):
    YES_NO = "yes_no"
    CHOICE = "choice"
    PRIORITY = "priority"
    MULTI_STEP = "multi_step"
    SUGGESTION = "suggestion"


class DialogueState(BaseModel):
    """Trạng thái hội thoại hiện tại."""
    has_pending_question: bool = False
    question_type: Optional[PendingQuestionType] = None
    question_text: Optional[str] = None
    options: List[str] = []
    context: Optional[str] = None
    last_ai_response: Optional[str] = None
    last_user_intent: Optional[str] = None

    # TTL fields
    asked_at: Optional[float] = None
    ttl_seconds: int = 300
    turn_number: int = 0
    max_turns_valid: int = 2

    @property
    def is_expired(self) -> bool:
        if not self.asked_at:
            return False
        return (time.time() - self.asked_at) > self.ttl_seconds

    @property
    def is_stale(self) -> bool:
        return self.is_expired


class DialogueStateTracker:
    def __init__(self):
        self.state = DialogueState()
        self._cache: Dict[str, dict] = {}

    def _hash_text(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    def detect_question(self, ai_response: str) -> DialogueState:
        """Dùng LLM để phát hiện câu hỏi từ AI response (có cache)."""
        resp_hash = self._hash_text(ai_response[:200])
        if resp_hash in self._cache:
            cached_data = self._cache[resp_hash]
            cached_state = DialogueState(**cached_data)
            cached_state.asked_at = time.time()
            return cached_state

        result = self._llm_detect_question(ai_response)
        self._cache[resp_hash] = result.model_dump()
        result.asked_at = time.time()
        result.last_ai_response = ai_response
        return result

    def _llm_detect_question(self, ai_response: str) -> DialogueState:
        """Gọi LLM nhẹ để phân tích câu trả lời của AI."""
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            return DialogueState()

        prompt = f"""Phân tích câu trả lời AI sau. Nếu AI đang đặt câu hỏi chờ user trả lời,
trả về JSON:
{{
  "has_question": true/false,
  "type": "yes_no" | "choice" | "priority" | "multi_step" | null,
  "options": ["option1", "option2"]
}}

AI response: {ai_response[:500]}

Chỉ trả JSON, không giải thích."""

        try:
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                    "temperature": 0.0,
                },
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()
                # Parse JSON từ LLM response
                parsed = json.loads(content)
                question_type = None
                if parsed.get("type") and parsed["type"] in [e.value for e in PendingQuestionType]:
                    question_type = PendingQuestionType(parsed["type"])
                return DialogueState(
                    has_pending_question=parsed.get("has_question", False),
                    question_type=question_type,
                    options=parsed.get("options", []),
                    question_text=ai_response,
                )
        except Exception:
            pass
        return DialogueState()

    def resolve_intent(self, user_input: str) -> Dict[str, Any]:
        """Phân giải intent dựa trên state hiện tại."""
        # Kiểm tra hết hạn
        if self.state.has_pending_question and self.state.is_expired:
            self.state = DialogueState()
            return {"resolved_intent": "delegate_to_intent_agent", "confidence": 0.0}

        # Nếu không có câu hỏi pending, chuyển tiếp
        if not self.state.has_pending_question:
            return {"resolved_intent": "delegate_to_intent_agent", "confidence": 0.0}

        q_type = self.state.question_type

        # YES_NO
        if q_type == PendingQuestionType.YES_NO:
            return self._resolve_yes_no(user_input)

        # CHOICE
        if q_type == PendingQuestionType.CHOICE:
            return self._resolve_choice(user_input)

        # PRIORITY
        if q_type == PendingQuestionType.PRIORITY:
            return self._resolve_priority(user_input)

        # MULTI_STEP
        if q_type == PendingQuestionType.MULTI_STEP:
            return self._resolve_yes_no(user_input)

        return {"resolved_intent": "delegate_to_intent_agent", "confidence": 0.0}

    def _resolve_yes_no(self, user_input: str) -> Dict[str, Any]:
        confirm_words = ["có", "yes", "ok", "đồng ý", "okay", "y", "ừ", "ừa", "ừm", "làm đi", "bắt đầu đi", "tiếp tục"]
        deny_words = ["không", "no", "ko", "n", "đừng", "thôi", "chưa", "để sau", "khoan"]

        clean_input = user_input.strip().lower()
        if clean_input in confirm_words:
            return {"resolved_intent": "contextual_yes", "confidence": 0.9, "delta": {"confirmation": "yes"}}
        if clean_input in deny_words:
            return {"resolved_intent": "contextual_no", "confidence": 0.9, "delta": {"confirmation": "no"}}
        return {"resolved_intent": "delegate_to_intent_agent", "confidence": 0.0}

    def _resolve_choice(self, user_input: str) -> Dict[str, Any]:
        clean_input = user_input.strip().lower()
        for option in self.state.options:
            if option.lower() in clean_input:
                return {
                    "resolved_intent": "command",
                    "confidence": 0.85,
                    "delta": {"choice": option},
                    "enriched_message": f"(Lựa chọn: {option}) {user_input}",
                }
        return {"resolved_intent": "delegate_to_intent_agent", "confidence": 0.3}

    def _resolve_priority(self, user_input: str) -> Dict[str, Any]:
        clean_input = user_input.strip().lower()
        if any(kw in clean_input for kw in ["trước", "đầu tiên", "first"]):
            for option in self.state.options:
                if option.lower() in clean_input:
                    return {
                        "resolved_intent": "command",
                        "confidence": 0.85,
                        "delta": {"priority": option},
                        "enriched_message": f"(Ưu tiên: {option}) {user_input}",
                    }
        return {"resolved_intent": "delegate_to_intent_agent", "confidence": 0.0}

    def is_intent_shift(self, user_input: str) -> bool:
        """Kiểm tra xem user có đang chuyển chủ đề không."""
        if not self.state.has_pending_question:
            return False
        if self.state.is_expired:
            return True
        if len(user_input.split()) > 10:
            return True
        command_verbs = ["sửa", "viết", "tạo", "xóa", "thêm", "fix", "create", "delete"]
        if any(v in user_input.lower() for v in command_verbs):
            if self.state.question_type == PendingQuestionType.PRIORITY:
                return False
            return True
        return False

    def needs_clarification(self, confidence: float) -> bool:
        return confidence < 0.6 and self.state.has_pending_question

    def update_state(self, new_state: DialogueState):
        self.state = new_state

    def clear_state(self):
        self.state = DialogueState()