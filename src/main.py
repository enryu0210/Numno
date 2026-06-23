"""진입점 + 폴링 루프.

흐름:
  1) 설정/로그/저장소 준비
  2) (첫 실행) 부트스트랩 — 지금 올라와 있는 글들은 '과거 글'이므로
     알림 없이 본 것으로만 등록한다. (켜자마자 옛날 글이 쏟아지는 것 방지)
  3) 주기적으로 리스트를 긁어, 처음 보는 나눔글이면 디스코드로 알린다.

실행:
  python -m src.main                # 상시 백그라운드 루프
  python -m src.main --once         # 1회만 폴링 후 종료 (테스트용)
  python -m src.main --dry-run      # 웹훅 대신 콘솔에만 출력
  python -m src.main --once --dry-run
"""

import argparse
import sys
import time

import requests

from .ai_classifier import build_classifier
from .config import ConfigError, load_config
from .detector import is_giveaway, is_giveaway_text
from .logger import get_logger
from .notifier import send_discord
from .post_fetcher import fetch_body
from .scraper import fetch_posts
from .storage import SeenStore

log = get_logger()


def _is_real_giveaway(post, config, session, classifier) -> bool:
    """이 글을 알릴 '진짜 나눔글'로 볼지 최종 판단한다.

    2단계 판별:
      1) 키워드 1차 필터(저렴 → 비쌈 순서):
         a. 제목에 키워드가 있으면 바로 후보. (네트워크 비용 0)
         b. 제목에 없으면 '본문'을 가져와 본문 키워드까지 검사한다.
            (제목엔 '나눔'을 안 쓰고 본문에만 쓰는 글이 많아서 추가함)
         → 제목·본문 어디에도 키워드가 없으면 여기서 탈락.
      2) AI 2차 판별(정밀): 본문을 Gemini에게 보여 진짜 나눔글인지 묻는다.
         - 1차에서 이미 받아온 본문이 있으면 그대로 재사용해 중복 요청을 막는다.
         - AI가 없거나(키 미설정) 판단 불가(오류)면 1차 키워드 결과를 그대로 쓴다
           (안전한 대체: AI가 죽어도 기존 동작 유지).

    주의(비용): 제목에 키워드가 없는 글은 본문을 받아와야 하므로, 신규 글
    대부분에 대해 디시로 추가 요청이 나간다. 차단/지연이 보이면 폴링 주기를
    늘리는 걸로 대응한다.
    """
    # 1차-a: 제목에 키워드가 있으면 본문을 안 봐도 후보 확정 (가장 쌈)
    keyword_hit = is_giveaway(post, config.keywords, config.exclude_keywords)

    # 본문은 한 번만 받아와 1차(본문 검사)와 2차(AI)에서 공유한다.
    body = None

    # 1차-b: 제목엔 없을 때만 본문을 받아와 본문 키워드까지 검사
    if not keyword_hit:
        body = fetch_body(post, config, session)
        keyword_hit = is_giveaway_text(body, config.keywords, config.exclude_keywords)

    # 제목·본문 어디에도 키워드 없음 → 탈락
    if not keyword_hit:
        return False

    # AI 미사용 → 키워드 결과로 확정
    if classifier is None:
        return True

    # 2차: 본문을 AI에게 넘겨 진짜 나눔글인지 판단 요청
    # (1차-b에서 이미 받아왔으면 재사용, 아니면 지금 받아온다)
    if body is None:
        body = fetch_body(post, config, session)
    result = classifier.classify(post.title, body)

    if result.decision is None:
        # 판단 불가 → 키워드 결과로 대체(놓침 방지)
        log.warning("AI 판단 불가, 키워드 결과 사용: [%s] %s", post.no, post.title)
        return True

    log.info(
        "AI 판별: [%s] %s → %s (%s)",
        post.no, post.title,
        "나눔" if result.decision else "제외", result.reason,
    )
    return result.decision


def _bootstrap(posts, store: SeenStore) -> None:
    """첫 실행 시: 현재 글을 모두 '본 것'으로만 등록(알림 X)."""
    for post in posts:
        store.add(post.no)
    store.save()
    log.info("첫 실행 부트스트랩 완료: 기존 글 %d건을 알림 없이 등록", len(posts))


def _process(posts, store: SeenStore, config, session, dry_run: bool, classifier) -> int:
    """처음 보는 글들을 검사해 나눔글이면 알린다. 반환값은 알린 건수.

    핵심 규칙: 나눔글이든 아니든 '처음 본 글'은 전부 seen 에 등록한다.
    (그래야 다음 폴링 때 같은 글을 또 검사/알림하지 않는다)
    """
    notified = 0
    # 오래된 글이 먼저 알림 가도록 글번호 오름차순 처리
    for post in sorted(posts, key=lambda p: p.no):
        if store.contains(post.no):
            continue  # 이미 처리한 글

        if _is_real_giveaway(post, config, session, classifier):
            if dry_run:
                log.info("[DRY-RUN] 나눔글 감지: [%s] %s (%s)", post.no, post.title, post.url)
                store.add(post.no)
                notified += 1
            else:
                # 전송 성공해야 seen 에 넣는다 → 실패 시 다음 주기에 재시도
                if send_discord(post, config, session):
                    store.add(post.no)
                    notified += 1
                # 실패하면 seen 에 추가하지 않음 (다음 폴링 때 다시 시도)
        else:
            store.add(post.no)  # 나눔글 아님 → 재검사 방지용으로만 등록

    store.save()
    return notified


def run(once: bool = False, dry_run: bool = False) -> None:
    """서비스 메인 진입 함수."""
    # --- 준비 단계 ---
    try:
        config = load_config()
    except ConfigError as e:
        log.error("설정 오류:\n%s", e)
        sys.exit(1)

    store = SeenStore(limit=config.seen_limit)
    store.load()
    session = requests.Session()
    # AI 분류기 준비(키 없으면 None → 키워드 규칙만 사용)
    classifier = build_classifier(config)

    log.info(
        "Numno 시작 | 갤러리=%s | 주기=%d초 | 키워드=%s | AI=%s | dry_run=%s",
        config.gallery_id, config.poll_interval_sec, config.keywords,
        "켜짐" if classifier else "꺼짐", dry_run,
    )

    # --- 첫 실행 부트스트랩 ---
    # seen 파일이 없던 첫 가동이면, 기존 글을 알림 없이 등록만 한다.
    first_run = not store.exists()
    if first_run:
        posts = fetch_posts(config, session)
        if posts:
            _bootstrap(posts, store)
        else:
            log.warning("부트스트랩 중 글을 못 가져왔습니다(차단/네트워크?). 다음 주기에 재시도")
        if once:
            return

    # --- 폴링 루프 ---
    try:
        while True:
            # 루프 본문 전체를 감싸 한 번의 오류로 서비스가 죽지 않게 함
            try:
                posts = fetch_posts(config, session)
                if posts:
                    n = _process(posts, store, config, session, dry_run, classifier)
                    log.info("폴링 완료: 글 %d건 확인, 신규 알림 %d건", len(posts), n)
                else:
                    log.info("폴링 완료: 가져온 글 없음")
            except Exception as e:
                log.exception("폴링 중 예기치 못한 오류(계속 진행): %s", e)

            if once:
                break
            time.sleep(config.poll_interval_sec)
    except KeyboardInterrupt:
        log.info("사용자 종료(Ctrl+C). 안전하게 종료합니다.")
        store.save()


def main() -> None:
    parser = argparse.ArgumentParser(description="디시 커피갤러리 나눔글 알림 서비스")
    parser.add_argument("--once", action="store_true", help="1회만 폴링 후 종료")
    parser.add_argument("--dry-run", action="store_true", help="웹훅 대신 콘솔에만 출력")
    args = parser.parse_args()
    run(once=args.once, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
