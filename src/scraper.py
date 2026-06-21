"""디시 갤러리 리스트 크롤링 + 파싱.

마이너 갤러리 리스트 페이지 HTML을 가져와 Post 목록으로 변환한다.
디시 HTML 구조가 바뀌면 '여기 한 곳'만 고치면 되도록 파싱 로직을 격리했다.
"""

from bs4 import BeautifulSoup

from .config import Config
from .logger import get_logger
from .models import Post

log = get_logger()

_BASE = "https://gall.dcinside.com"

# 디시는 봇을 차단하므로 실제 브라우저처럼 보이는 헤더가 필수다.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://gall.dcinside.com/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def fetch_posts(config: Config, session) -> list[Post]:
    """갤러리 리스트를 가져와 일반 게시글 Post 목록을 반환한다.

    공지/AD/설문 등 비-게시글 행은 제외한다.
    네트워크 오류나 차단(403 등)이 나면 빈 리스트를 반환하여,
    상위 폴링 루프가 죽지 않고 다음 주기에 다시 시도하게 한다.

    Args:
        config: 설정(리스트 URL 포함).
        session: requests.Session (헤더/쿠키 재사용).

    Returns:
        파싱된 Post 리스트. 실패 시 빈 리스트.
    """
    try:
        resp = session.get(config.list_url, headers=_HEADERS, timeout=10)
        resp.encoding = "utf-8"  # 디시 페이지는 UTF-8
        if resp.status_code != 200:
            log.warning("리스트 요청 실패: HTTP %s", resp.status_code)
            return []
    except Exception as e:  # 타임아웃/연결오류 등 모두 흡수
        log.warning("리스트 요청 중 예외: %s", e)
        return []

    return _parse_list(resp.text, config.gallery_id)


def _parse_list(html: str, gallery_id: str) -> list[Post]:
    """리스트 HTML 문자열을 Post 목록으로 파싱한다. (네트워크와 분리된 순수 함수)"""
    soup = BeautifulSoup(html, "lxml")
    posts: list[Post] = []

    # 실제 게시글 행은 'us-post' 클래스 + data-no 속성을 가진다.
    for row in soup.select("tr.us-post[data-no]"):
        try:
            post = _parse_row(row, gallery_id)
        except Exception as e:
            # 한 행 파싱 실패가 전체를 멈추지 않도록 행 단위로 방어
            log.debug("행 파싱 실패(무시): %s", e)
            continue
        if post is not None:
            posts.append(post)

    return posts


def _parse_row(row, gallery_id: str) -> Post | None:
    """게시글 한 행(<tr>)을 Post 로 변환한다. 게시글이 아니면 None."""
    # 공지/AD 행 제외 (data-type 에 notice/ad 가 들어감)
    data_type = row.get("data-type", "")
    if "notice" in data_type or "ad" in data_type:
        return None

    # 글번호: gall_num 이 숫자가 아니면(설문/AD/'-') 제외
    num_cell = row.select_one("td.gall_num")
    num_text = num_cell.get_text(strip=True) if num_cell else ""
    if not num_text.isdigit():
        return None

    # 말머리(없을 수 있음). '공지'면 제외.
    subject_cell = row.select_one("td.gall_subject")
    category = subject_cell.get_text(strip=True) if subject_cell else ""
    if category == "공지":
        return None

    # 제목 + 링크: gall_tit 안의 글 보기 링크(a)를 찾는다.
    tit_cell = row.select_one("td.gall_tit")
    link = None
    if tit_cell:
        for a in tit_cell.select("a"):
            href = a.get("href", "")
            if "board/view" in href:  # 제목 링크 (댓글수 링크와 구분)
                link = a
                break
    if link is None:
        return None

    title = link.get_text(strip=True)
    href = link.get("href", "")
    url = href if href.startswith("http") else _BASE + href

    # 글쓴이
    writer_cell = row.select_one("td.gall_writer")
    author = writer_cell.get("user_name") if writer_cell else None
    if not author and writer_cell:
        author = writer_cell.get_text(strip=True)
    author = author or "(알수없음)"

    # 작성 시각: title 속성에 전체 일시가 있으면 그걸, 없으면 표시 텍스트
    date_cell = row.select_one("td.gall_date")
    date = ""
    if date_cell:
        date = date_cell.get("title") or date_cell.get_text(strip=True)

    return Post(
        no=int(num_text),
        title=title,
        category=category,
        author=author,
        url=url,
        date=date,
    )
