"""AI 판별기(ai_classifier) 단위 테스트.

실제 Gemini API를 부르지 않고, 'JSON 응답 파싱'과 '키 없을 때 안전 동작'만
검증한다. (네트워크/키 없이도 돌아가야 하는 부분)

실행: python -m pytest tests/test_ai_classifier.py -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_classifier import (
    _is_transient_error,
    _parse_response,
    build_classifier,
)
from src.config import Config


# --- JSON 응답 파싱 (OvR: 원두 품목만 통과) ---
def test_parse_bean_giveaway_true():
    # 나눔글 + 품목이 '원두' → 통과
    r = _parse_response(
        '{"is_giveaway": true, "item": "원두", "post_type": "나눔", "reason": "원두 무료 나눔"}'
    )
    assert r.decision is True
    assert r.item == "원두"


def test_parse_non_bean_giveaway_is_false():
    # 나눔글이어도 품목이 '원두'가 아니면(드립백) 제외 (짬뽕 나눔글 거르기)
    r = _parse_response(
        '{"is_giveaway": true, "item": "드립백", "post_type": "나눔", "reason": "드립백 나눔"}'
    )
    assert r.decision is False
    assert r.item == "드립백"


def test_parse_equipment_giveaway_is_false():
    # 장비 나눔도 원두가 아니므로 제외
    r = _parse_response(
        '{"is_giveaway": true, "item": "장비", "post_type": "나눔", "reason": "그라인더 나눔"}'
    )
    assert r.decision is False


def test_parse_review_is_false():
    # 후기글이면 품목과 무관하게 제외
    r = _parse_response(
        '{"is_giveaway": false, "item": "원두", "post_type": "후기", "reason": "받은 후기"}'
    )
    assert r.decision is False
    assert r.post_type == "후기"


def test_parse_markdown_fenced_json():
    # Gemma가 스키마를 무시하고 ```json ... ``` 코드펜스로 감싸도 안전하게 파싱해야 함
    fenced = '```json\n{"is_giveaway": true, "item": "원두", "post_type": "나눔", "reason": "원두 나눔"}\n```'
    r = _parse_response(fenced)
    assert r.decision is True
    assert r.item == "원두"


def test_parse_json_with_leading_text():
    # 앞뒤에 설명이 섞여도 JSON 본문({...})만 추려 파싱해야 함
    messy = '네, 판단 결과입니다: {"is_giveaway": false, "item": "장비", "post_type": "나눔", "reason": "그라인더 나눔"} 이상입니다.'
    r = _parse_response(messy)
    assert r.decision is False
    assert r.item == "장비"


def test_parse_broken_json_is_undecided():
    # 깨진 응답 → 판단 불가(None) → 상위에서 키워드 규칙으로 대체
    assert _parse_response("이건 JSON이 아님").decision is None


def test_parse_empty_is_undecided():
    assert _parse_response("").decision is None
    assert _parse_response(None).decision is None


# --- 일시적 오류(재시도 대상) 식별 ---
def test_transient_error_503():
    assert _is_transient_error(Exception("503 UNAVAILABLE: model is overloaded")) is True


def test_transient_error_429():
    assert _is_transient_error(Exception("429 RESOURCE_EXHAUSTED")) is True


def test_non_transient_error_is_not_retried():
    # 잘못된 키 등은 재시도해도 소용없으므로 일시적 오류가 아님
    assert _is_transient_error(Exception("400 API key not valid")) is False


# --- 키가 없으면 AI를 끄고 None 을 돌려줘야 함 (키워드 규칙만 사용) ---
def test_build_classifier_without_key():
    config = Config(discord_webhook_url="http://example.com", gemini_api_key="")
    assert build_classifier(config) is None
