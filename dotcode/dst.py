"""
Dialogue State Tracker cho DotCode.
Quản lý trạng thái hội thoại để phân giải intent dựa trên ngữ cảnh.
"""

import hashlib
import json
import os
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import requests
from pydantic import BaseModel, Field


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
    options: List[str] = Field(default_factory=list)
    question_text: str = ""
    asked_at: float = Field(default_factory=time.time)
    _last_analysis: Optional[Dict[str, Any]] = None  # Cache cho LLM analysis
    last_ai_response: Optional[str] = None
    last_user_intent: Optional[str] = None

    # TTL fields
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

    def _get_or_run_analysis(self, user_input: str) -> Dict[str, Any]:
        """Cache và chạy LLM phân tích câu trả lời của user."""
        if hasattr(self.state, "_last_analysis") and self.state._last_analysis:
            if self.state._last_analysis.get("input") == user_input:
                return self.state._last_analysis.get("result")

        # Fast path cho các câu trả lời ngắn cơ bản
        clean_input = user_input.strip().lower()
        if clean_input in ["có", "yes", "ok", "y", "ừ", "okay", "đồng ý"]:
            result = {"is_shift": False, "resolution": "yes"}
        elif clean_input in ["không", "no", "n", "ko", "thôi"]:
            result = {"is_shift": False, "resolution": "no"}
        else:
            # LLM Phân tích
            api_key = os.getenv("DEEPSEEK_API_KEY")
            result = {"is_shift": len(user_input.split()) > 10, "resolution": "unknown"}
            if api_key:
                prompt = f"""AI đã hỏi: "{self.state.question_text}"\nNgười dùng trả lời: "{user_input}"\n
Nhiệm vụ:
1. is_shift (true/false): Người dùng có phớt lờ câu hỏi và chuyển sang lệnh/chủ đề khác không?
2. resolution ("yes", "no", "option", "unknown"): Nếu không shift, ý người dùng là đồng ý (yes), từ chối (no), hay không rõ (unknown).
Trả về đúng 1 JSON: {{"is_shift": bool, "resolution": str}}"""
                try:
                    response = requests.post(
                        "https://api.deepseek.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "max_tokens": 50, "temperature": 0.0},
                        timeout=10,
                    )
                    if response.status_code == 200:
                        content = response.json()["choices"][0]["message"]["content"].strip()
                        if "```json" in content: content = content.split("```json")[1].split("```")[0].strip()
                        elif "```" in content: content = content.split("```")[1].split("```")[0].strip()
                        parsed = json.loads(content)
                        result = {
                            "is_shift": parsed.get("is_shift", False),
                            "resolution": parsed.get("resolution", "unknown")
                        }
                except Exception:
                    pass

        # Lưu cache
        self.state._last_analysis = {"input": user_input, "result": result}
        return result

    def _resolve_yes_no(self, user_input: str) -> Dict[str, Any]:
        analysis = self._get_or_run_analysis(user_input)
        
        if analysis.get("resolution") == "yes":
            return {
                "resolved_intent": "contextual_yes",
                "confidence": 0.9,
                "delta": {"confirmation": "yes"},
            }
        if analysis.get("resolution") == "no":
            return {
                "resolved_intent": "contextual_no",
                "confidence": 0.9,
                "delta": {"confirmation": "no"},
            }
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
        """Kiểm tra xem user có đang chuyển chủ đề không, thông qua LLM."""
        if not self.state.has_pending_question:
            return False
        if self.state.is_expired:
            return True
            
        analysis = self._get_or_run_analysis(user_input)
        return analysis.get("is_shift", False)

    def needs_clarification(self, confidence: float) -> bool:
        return confidence < 0.6 and self.state.has_pending_question

    def update_state(self, new_state: DialogueState):
        self.state = new_state

    def clear_state(self):
        self.state = DialogueState()
