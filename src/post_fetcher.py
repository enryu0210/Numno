"""게시글 '본문 내용' 가져오기.

리스트 크롤링(scraper.py)은 제목/글번호만 얻는다. AI가 진짜 나눔글인지
판단하려면 글 안의 '본문 텍스트'가 필요하므로, 이 모듈이 게시글 보기
페이지에서 본문만 뽑아온다.

설계 메모:
  - 알림 링크는 모바일 URL(m.dcinside.com)이지만, '본문 파싱'은 PC 보기
    페이지가 구조가 단순하고(.write_div) 안정적이라 PC URL로 직접 가져온다.
    (PC URL은 데스크톱 User-Agent로 접근하면 정상 응답한다)
  - 네트워크 오류나 파싱 실패는 빈 문자열을 반환해, 상위 로직이 죽지 않고
    '본문 없음' 상태로 AI 판단을 이어가게 한다.
"""

from bs4 import BeautifulSoup

from .config import Config
from .logger import get_logger
from .models import Post

log = get_logger()

# scraper 와 동일한 '진짜 브라우저처럼 보이는' 헤더 (디시 봇 차단 회피)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://gall.dcinside.com/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# 본문이 너무 길면 AI 입력 비용이 커지므로 적당히 자른다.
# (나눔글 판별엔 앞부분만 봐도 충분하다)
_MAX_BODY_CHARS = 2000


def _pc_view_url(config: Config, no: int) -> str:
    """글번호로 PC 보기 페이지 URL을 만든다. (본문 파싱 전용)"""
    return (
        f"https://gall.dcinside.com/mgallery/board/view/"
        f"?id={config.gallery_id}&no={no}"
    )


def fetch_body(post: Post, config: Config, session) -> str:
    """게시글 본문 텍스트를 반환한다. 실패하면 빈 문자열.

    Args:
        post: 본문을 가져올 게시글.
        config: 갤러리 id 등 설정.
        session: requests.Session (헤더/쿠키 재사용).

    Returns:
        본문 텍스트(최대 _MAX_BODY_CHARS자). 실패/본문없음 시 "".
    """
    url = _pc_view_url(config, post.no)
    try:
        resp = session.get(url, headers=_HEADERS, timeout=10)
        resp.encoding = "utf-8"
        if resp.status_code != 200:
            log.warning("본문 요청 실패: HTTP %s (글 %s)", resp.status_code, post.no)
            return ""
    except Exception as e:  # 타임아웃/연결오류 등 모두 흡수
        log.warning("본문 요청 중 예외(글 %s): %s", post.no, e)
        return ""

    return _parse_body(resp.text)


def _parse_body(html: str) -> str:
    """보기 페이지 HTML에서 본문 텍스트만 추출한다. (네트워크와 분리된 순수 함수)"""
    soup = BeautifulSoup(html, "lxml")

    # 디시 게시글 본문은 '.write_div' 안에 들어 있다.
    body_el = soup.select_one(".write_div")
    if body_el is None:
        return ""

    # 줄바꿈을 살려 텍스트만 뽑고, 길면 잘라 비용을 아낀다.
    text = body_el.get_text("\n", strip=True)
    if len(text) > _MAX_BODY_CHARS:
        text = text[:_MAX_BODY_CHARS]
    return text
