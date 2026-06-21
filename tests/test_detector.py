"""나눔글 판별(detector) 단위 테스트.

실행: python -m pytest tests/test_detector.py -v
"""

import os
import sys

# tests/ 에서 실행해도 src 패키지를 import 할 수 있게 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.detector import is_giveaway
from src.models import Post

KEYWORDS = ["나눔"]
EXCLUDE = ["나눔후기", "나눔받", "나눔 받", "마감", "나눔완료"]


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


def test_exclude_received():
    assert is_giveaway(_post("나눔 받아가신 분 후기요"), KEYWORDS, EXCLUDE) is False


def test_exclude_closed():
    assert is_giveaway(_post("원두 나눔 마감되었습니다"), KEYWORDS, EXCLUDE) is False


# --- 미탐: 나눔과 무관하면 False ---
def test_unrelated():
    assert is_giveaway(_post("라떼 아트 후기입니다"), KEYWORDS, EXCLUDE) is False


def test_empty_title():
    assert is_giveaway(_post(""), KEYWORDS, EXCLUDE) is False
