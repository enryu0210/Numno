"""나눔글 판별(detector) 단위 테스트.

실행: python -m pytest tests/test_detector.py -v
"""

import os
import sys

# tests/ 에서 실행해도 src 패키지를 import 할 수 있게 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.detector import has_any_keyword, is_giveaway, is_giveaway_text
from src.models import Post

KEYWORDS = ["나눔"]
# '마감'은 제외어에서 뺐다: 진행 중인 나눔글도 "마감 19:45"처럼 마감 '시각'을
# 본문에 적는 경우가 많아, '마감' 두 글자로 거르면 진짜 나눔글까지 탈락했다.
# (이미 끝난 나눔글인지 여부는 이제 AI가 본문을 읽고 판단한다)
EXCLUDE = ["후기", "나눔받", "나눔 받", "나눔완료"]


def _post(title: str) -> Post:
    """제목만 다른 더미 게시글 생성 헬퍼."""
    return Post(no=1, title=title, category="", author="tester", url="", date="")


# --- 정탐: 진짜 나눔글이면 True ---
def test_basic_giveaway():
    assert is_giveaway(_post("에티오피아 원두 나눔합니다"), KEYWORDS, EXCLUDE) is True


def test_giveaway_with_spaces():
    # 공백을 모두 제거해 비교하므로, 글자 사이를 띄운 "나 눔"도 잡아낸다.
    assert is_giveaway(_post("드립백 나 눔 합니다"), KEYWORDS, EXCLUDE) is True
    assert is_giveaway(_post("드립백 나눔 합니다"), KEYWORDS, EXCLUDE) is True


def test_giveaway_bracket():
    assert is_giveaway(_post("[나눔] 콜드브루 원액"), KEYWORDS, EXCLUDE) is True


# --- 오탐 방지: 제외어가 있으면 False ---
def test_exclude_review():
    assert is_giveaway(_post("지난번 나눔후기 올립니다"), KEYWORDS, EXCLUDE) is False


def test_exclude_review_separated():
    # 회귀 테스트: '나눔'과 '후기'가 떨어져 있어도 후기글이면 걸러야 한다.
    # (기존엔 제외어가 "나눔후기" 붙은 형태라서 이런 제목이 알림으로 새어 나갔음)
    assert is_giveaway(_post("원두 나눔 잘 받았어요 후기"), KEYWORDS, EXCLUDE) is False
    assert is_giveaway(_post("[후기] 지난 나눔 정말 좋았습니다"), KEYWORDS, EXCLUDE) is False


def test_exclude_received():
    assert is_giveaway(_post("나눔 받아가신 분 후기요"), KEYWORDS, EXCLUDE) is False


def test_exclude_closed():
    # '나눔완료'는 명백히 끝난 글이므로 키워드 단계에서 거른다.
    assert is_giveaway(_post("원두 나눔완료 했습니다"), KEYWORDS, EXCLUDE) is False


def test_deadline_time_not_excluded():
    # 회귀 테스트: 진행 중 나눔글이 마감 '시각'을 적었다고 탈락하면 안 된다.
    # (예: 본문에 "나눔 마감 19:45" — '마감'을 제외어에서 뺀 이유)
    body = "원두 나눔합니다. 줄 남겨주세요. 나눔 마감 19:45"
    assert is_giveaway_text(body, KEYWORDS, EXCLUDE) is True


# --- 미탐: 나눔과 무관하면 False ---
def test_unrelated():
    assert is_giveaway(_post("라떼 아트 후기입니다"), KEYWORDS, EXCLUDE) is False


def test_empty_title():
    assert is_giveaway(_post(""), KEYWORDS, EXCLUDE) is False


# --- 본문 키워드 검사: is_giveaway_text (제목에 없고 본문에만 쓴 글 대응) ---
def test_body_keyword_hit():
    # 제목엔 '나눔'이 없어도 본문에 있으면 후보로 잡아야 한다.
    body = "오늘 원두가 너무 많이 남아서 필요하신 분께 나눔하려고 합니다."
    assert is_giveaway_text(body, KEYWORDS, EXCLUDE) is True


def test_body_no_keyword():
    body = "오늘 내린 라떼가 정말 맛있네요. 다들 좋은 하루 보내세요."
    assert is_giveaway_text(body, KEYWORDS, EXCLUDE) is False


def test_body_exclude_wins():
    # 본문에 '나눔'이 있어도 제외어(후기)가 함께 있으면 탈락시킨다.
    body = "지난번 나눔 받은 원두 후기 남깁니다. 정말 맛있었어요."
    assert is_giveaway_text(body, KEYWORDS, EXCLUDE) is False


def test_body_empty():
    # 본문 파싱 실패로 빈 문자열이 와도 죽지 않고 False.
    assert is_giveaway_text("", KEYWORDS, EXCLUDE) is False


# --- 사전 필터: has_any_keyword (제외어 무시, '포함 신호'만 본다) ---
SIGNALS = ["나눔", "룰렛", "추첨", "택비", "고닉"]


def test_signal_present():
    # 슬랭('룰렛')만 있어도 신호로 잡아 AI로 보낸다.
    assert has_any_keyword("점심 심심해서 룰렛 돌림", SIGNALS) is True


def test_signal_absent():
    # 나눔과 무관한 잡담은 신호가 없어 AI를 건너뛴다.
    assert has_any_keyword("오늘 라떼 맛있네요 다들 화이팅", SIGNALS) is False


def test_signal_ignores_exclude():
    # 제외어(후기)가 있어도 사전 필터는 '포함 신호'만 보므로 통과시킨다.
    # (후기/마감 같은 최종 판단은 AI에게 맡긴다)
    assert has_any_keyword("원두 나눔 받은 후기입니다", SIGNALS) is True
