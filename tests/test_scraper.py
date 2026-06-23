"""리스트 파서(scraper) 단위 테스트.

실제 디시 HTML 구조를 본떠 만든 작은 조각으로,
  - 말머리(특히 줄임말+숨김 전체이름) 파싱이 정확한지
  - 제외 말머리(예: 원두후기)가 결과에서 빠지는지
를 네트워크 없이 검증한다.

실행: python -m pytest tests/test_scraper.py -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scraper import _extract_category, _parse_list
from bs4 import BeautifulSoup

# 게시글 한 행을 만드는 헬퍼. subject_html 로 말머리 셀 내용을 바꿔 끼운다.
def _row(no: int, subject_html: str, title: str = "테스트 글") -> str:
    return f"""
    <tr class="us-post" data-no="{no}" data-type="us">
      <td class="gall_num">{no}</td>
      <td class="gall_subject">{subject_html}</td>
      <td class="gall_tit">
        <a href="/mgallery/board/view/?id=coffee&no={no}">{title}</a>
      </td>
      <td class="gall_writer" user_name="글쓴이">글쓴이</td>
      <td class="gall_date" title="2026-06-23 10:00:00">06.23</td>
    </tr>
    """


# --- 말머리 전체 이름 추출 ---
def test_extract_category_short():
    # 짧은 말머리는 셀 텍스트 그대로
    cell = BeautifulSoup("<td class='gall_subject'>잡담</td>", "lxml").td
    assert _extract_category(cell) == "잡담"


def test_extract_category_with_inner():
    # 긴 말머리: 셀엔 줄임말("원두후")만 보이고 전체("원두후기")는 숨김 <p>에 있다.
    # 셀 전체 텍스트를 그냥 읽으면 "원두후원두후기"가 되므로, 숨김 전체이름을 써야 한다.
    html = (
        "<td class='gall_subject'>원두후"
        "<p class='subject_inner'>원두후기</p></td>"
    )
    cell = BeautifulSoup(html, "lxml").td
    assert _extract_category(cell) == "원두후기"


# --- 제외 말머리 필터링 ---
def test_exclude_category_removes_post():
    # 원두후기 말머리 글은 제외되고, 잡담 글만 남아야 한다.
    html = (
        "<table>"
        + _row(100, "잡담", "원두 나눔합니다")
        + _row(101, "원두후<p class='subject_inner'>원두후기</p>", "나눔 원두 후기")
        + "</table>"
    )
    posts = _parse_list(html, "coffee", exclude_categories=["원두후기"])
    nums = [p.no for p in posts]
    assert 100 in nums
    assert 101 not in nums  # 원두후기 말머리라 제외됨


def test_no_exclude_keeps_all():
    # 제외 목록이 비면 원두후기 글도 그대로 남는다(의도적 비활성화).
    html = (
        "<table>"
        + _row(101, "원두후<p class='subject_inner'>원두후기</p>", "나눔 원두 후기")
        + "</table>"
    )
    posts = _parse_list(html, "coffee", exclude_categories=[])
    assert [p.no for p in posts] == [101]


def test_notice_still_excluded():
    # '공지' 말머리는 예전처럼 계속 제외된다.
    html = "<table>" + _row(1, "<b>공지</b>", "공지글") + "</table>"
    posts = _parse_list(html, "coffee", exclude_categories=["원두후기"])
    assert posts == []
