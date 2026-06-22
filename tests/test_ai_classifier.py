"""AI 판별기(ai_classifier) 단위 테스트.

실제 Gemini API를 부르지 않고, 'JSON 응답 파싱'과 '키 없을 때 안전 동작'만
검증한다. (네트워크/키 없이도 돌아가야 하는 부분)

실행: python -m pytest tests/test_ai_classifier.py -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_classifier import _parse_response, build_classifier
from src.config import Config


# --- JSON 응답 파싱 ---
def test_parse_giveaway_true():
    r = _parse_response('{"is_giveaway": true, "post_type": "나눔", "reason": "원두 무료 나눔"}')
    assert r.decision is True
    assert r.post_type == "나눔"


def test_parse_giveaway_false():
    r = _parse_response('{"is_giveaway": false, "post_type": "후기", "reason": "받은 후기"}')
    assert r.decision is False
    assert r.post_type == "후기"


def test_parse_broken_json_is_undecided():
    # 깨진 응답 → 판단 불가(None) → 상위에서 키워드 규칙으로 대체
    assert _parse_response("이건 JSON이 아님").decision is None


def test_parse_empty_is_undecided():
    assert _parse_response("").decision is None
    assert _parse_response(None).decision is None


# --- 키가 없으면 AI를 끄고 None 을 돌려줘야 함 (키워드 규칙만 사용) ---
def test_build_classifier_without_key():
    config = Config(discord_webhook_url="http://example.com", gemini_api_key="")
    assert build_classifier(config) is None
