import os
import sys

# Tắt warning model
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

from dotcode.dst import DialogueStateTracker, DialogueState, PendingQuestionType
from dotcode.agents.intent_agent import IntentAgent

print('=== 1. TEST DST (Dialogue State Tracker) ===')
dst = DialogueStateTracker()
dst.state.has_pending_question = True
dst.state.question_text = 'Bạn có muốn tôi tự động sửa lỗi import ở file dst.py không?'
dst.state.question_type = PendingQuestionType.YES_NO

test_responses = [
    'triển luôn đi bạn',
    'ok quất',
    'thôi dừng lại đã, cho tôi hỏi cái khác',
    'từ từ, hàm is_intent_shift() ở đâu?'
]

for resp in test_responses:
    print(f'\nAI hỏi: {dst.state.question_text}')
    print(f'User đáp: {resp}')
    is_shift = dst.is_intent_shift(resp)
    if is_shift:
         print('-> Kết quả: ĐÁNH TRỐNG LẢNG (Intent Shift)')
    else:
         resolution = dst.resolve_intent(resp)
         print(f'-> Kết quả: TRẢ LỜI CÂU HỎI ({resolution.get("resolved_intent")})')


print('\n=== 2. TEST INTENT AGENT ===')
agent = IntentAgent()

test_queries = [
    'lỗi',
    'sao lại thế',
    'kiến trúc con này ntn',
    'tìm xem có module nào về database không'
]

for q in test_queries:
    print(f'\nUser hỏi: {q}')
    is_ambig = agent.is_ambiguous(q)
    if is_ambig:
        print('-> Kết quả: Bị chặn vì mơ hồ')
    else:
        intent, conf = agent.classify(q)
        print(f'-> Kết quả: Không bị chặn, phân loại thành: {intent} (tự tin: {conf})')
