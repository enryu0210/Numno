"""나눔글 최종 판별 흐름(main._is_real_giveaway) 단위 테스트.

핵심 검증:
  - [AI 켜짐] 'AI 전수검사': 제목·본문에 '나눔' 단어가 없어도(슬랭 나눔글)
    본문을 AI에게 보내 판단한다 → AI가 원두 나눔이라 하면 통과.
  - [AI 판단 불가] 받아둔 본문으로 키워드 규칙으로 안전하게 대체한다.
  - [AI 꺼짐] 키워드 규칙만으로 동작한다.

실행: python -m pytest tests/test_main.py -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.main as main
from src.ai_classifier import ClassifyResult
from src.config import Config
from src.models import Post


def _config() -> Config:
    return Config(
        discord_webhook_url="http://example.com",
        keywords=["나눔"],
        exclude_keywords=["후기", "나눔받", "나눔 받", "나눔완료"],
    )


def _post(title: str) -> Post:
    return Post(no=1, title=title, category="", author="t", url="", date="")


class _FakeClassifier:
    """classify() 가 미리 정한 결과를 돌려주는 가짜 AI 분류기."""

    def __init__(self, result: ClassifyResult):
        self._result = result

    def classify(self, title, body):
        return self._result


def _patch_body(monkeypatch, body: str):
    """fetch_body 를 네트워크 없이 고정 본문으로 대체한다."""
    monkeypatch.setattr(main, "fetch_body", lambda post, config, session: body)


# --- AI 켜짐: '나눔' 단어가 없는 슬랭 나눔글도 AI가 잡아낸다 ---
def test_ai_catches_slang_giveaway_without_keyword(monkeypatch):
    # 실제 케이스(627563)처럼 '나눔' 단어 없이 룰렛/줄 슬랭으로만 쓴 원두 나눔글
    body = "콜롬비아 게이샤 원두 15g. 줄 남겨주세요. 19시에 룰렛 돌립니다."
    _patch_body(monkeypatch, body)
    clf = _FakeClassifier(
        ClassifyResult(decision=True, item="원두", post_type="나눔", reason="원두 룰렛 나눔")
    )
    # 제목·본문 어디에도 '나눔'이 없지만, AI 전수검사라 통과해야 한다.
    assert main._is_real_giveaway(_post("점심 심심해서 룰렛"), _config(), None, clf) is True


def test_ai_rejects_non_giveaway(monkeypatch):
    _patch_body(monkeypatch, "오늘 내린 라떼 맛있네요.")
    clf = _FakeClassifier(
        ClassifyResult(decision=False, item="없음", post_type="기타", reason="잡담")
    )
    assert main._is_real_giveaway(_post("라떼 후기"), _config(), None, clf) is False


# --- AI 판단 불가: 받아둔 본문으로 키워드 규칙 대체 ---
def test_ai_undecided_falls_back_to_keyword(monkeypatch):
    _patch_body(monkeypatch, "원두 나눔합니다. 줄 남겨주세요.")
    clf = _FakeClassifier(
        ClassifyResult(decision=None, item="없음", post_type="기타", reason="AI 오류")
    )
    # AI 실패 → 본문에 '나눔' 있으니 키워드 규칙으로 통과
    assert main._is_real_giveaway(_post("제목엔 키워드 없음"), _config(), None, clf) is True


# --- AI 꺼짐(classifier=None): 키워드 규칙만 사용 ---
def test_no_ai_uses_keyword_title(monkeypatch):
    # 제목에 키워드가 있으면 본문을 받지 않아야 한다(fetch_body 호출 시 실패시킴)
    def _boom(*a, **k):
        raise AssertionError("제목 키워드만으로 끝나야 하는데 본문을 받으려 함")

    monkeypatch.setattr(main, "fetch_body", _boom)
    assert main._is_real_giveaway(_post("원두 나눔합니다"), _config(), None, None) is True


def test_no_ai_uses_keyword_body(monkeypatch):
    _patch_body(monkeypatch, "원두 나눔합니다. 줄 남겨주세요.")
    assert main._is_real_giveaway(_post("제목엔 키워드 없음"), _config(), None, None) is True


def test_no_ai_rejects_when_no_keyword(monkeypatch):
    _patch_body(monkeypatch, "오늘 내린 라떼 맛있네요.")
    assert main._is_real_giveaway(_post("라떼 자랑"), _config(), None, None) is False
