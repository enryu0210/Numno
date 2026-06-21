"""디스코드 웹훅 알림 전송.

나눔글이 감지되면 이 모듈이 디스코드 채널로 임베드 메시지를 보낸다.
전송 실패(네트워크 오류, 4xx/5xx)와 디스코드의 요청 제한(429)을 처리한다.
"""

import time

from .config import Config
from .logger import get_logger
from .models import Post

log = get_logger()

# 디스코드 임베드 색상 (커피색 느낌의 갈색)
_EMBED_COLOR = 0x6F4E37

_MAX_RETRY = 2          # 최종 실패 전 재시도 횟수
_RETRY_WAIT_SEC = 3     # 일반 실패 시 재시도 대기


def send_discord(post: Post, config: Config, session) -> bool:
    """나눔글 한 건을 디스코드 웹훅으로 보낸다.

    Args:
        post: 알릴 게시글.
        config: 웹훅 URL 등 설정.
        session: requests.Session.

    Returns:
        전송 성공 여부(True/False). 실패해도 예외를 던지지 않고 False 반환.
    """
    payload = {
        "content": "☕ **커피갤러리 나눔글이 올라왔어요!**",
        "embeds": [
            {
                "title": post.title,
                "url": post.url,
                "color": _EMBED_COLOR,
                "fields": [
                    {"name": "글쓴이", "value": post.author, "inline": True},
                    {"name": "작성", "value": post.date or "-", "inline": True},
                    {"name": "말머리", "value": post.category or "-", "inline": True},
                ],
                "footer": {"text": f"디시 커피갤러리 · 글번호 {post.no}"},
            }
        ],
    }

    # 재시도 루프: 일시적 오류(타임아웃/5xx/429)는 잠시 후 다시 시도
    for attempt in range(_MAX_RETRY + 1):
        try:
            resp = session.post(config.discord_webhook_url, json=payload, timeout=10)
        except Exception as e:
            log.warning("웹훅 전송 예외(%d/%d): %s", attempt + 1, _MAX_RETRY + 1, e)
            time.sleep(_RETRY_WAIT_SEC)
            continue

        # 성공 (204 No Content 가 정상 응답)
        if 200 <= resp.status_code < 300:
            log.info("알림 전송 성공: [%s] %s", post.no, post.title)
            return True

        # 요청 제한: 디스코드가 알려주는 대기 시간을 존중
        if resp.status_code == 429:
            retry_after = _parse_retry_after(resp)
            log.warning("디스코드 요청 제한(429). %.1f초 대기 후 재시도", retry_after)
            time.sleep(retry_after)
            continue

        # 그 외 오류
        log.warning("웹훅 전송 실패: HTTP %s %s", resp.status_code, resp.text[:200])
        time.sleep(_RETRY_WAIT_SEC)

    log.error("알림 전송 최종 실패: [%s] %s", post.no, post.title)
    return False


def _parse_retry_after(resp) -> float:
    """429 응답에서 재시도 대기 시간(초)을 안전하게 추출한다."""
    try:
        body = resp.json()
        if isinstance(body, dict) and "retry_after" in body:
            return float(body["retry_after"])
    except Exception:
        pass
    # 헤더 fallback
    header = resp.headers.get("Retry-After")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    return 5.0  # 정보가 없으면 5초 기본 대기
