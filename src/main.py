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
from .detector import has_any_keyword, is_giveaway, is_giveaway_text
from .logger import get_logger
from .notifier import send_discord
from .post_fetcher import fetch_body
from .scraper import fetch_posts
from .storage import SeenStore

log = get_logger()


def _keyword_giveaway(post, body, config) -> bool:
    """키워드 규칙만으로 나눔글 후보인지 판단한다. (AI 미사용/오류 시의 대체 수단)

    제목 또는 본문 중 한 곳이라도 포함 키워드가 있고 제외어가 없으면 후보.
    body 가 None 이면 본문은 검사하지 않는다(아직 안 받아온 경우).
    """
    if is_giveaway(post, config.keywords, config.exclude_keywords):
        return True
    if body is not None:
        return is_giveaway_text(body, config.keywords, config.exclude_keywords)
    return False


def _is_real_giveaway(post, config, session, classifier) -> bool:
    """이 글을 알릴 '진짜 원두 나눔글'로 볼지 최종 판단한다.

    판별 전략은 'AI가 켜져 있는지'에 따라 둘로 나뉜다.

    [AI 켜짐] 'AI 전수검사(+ 느슨한 사전 필터)' — 새 글의 본문을 가져온 뒤,
        제목/본문에 나눔 '신호'(나눔/룰렛/추첨/택비/고닉 등)가 하나라도 있는
        글만 AI에게 보낸다. 이유: 커피갤 나눔글은 '나눔'이라는 단어 없이
        "룰렛/추첨/줄서기" 같은 슬랭으로만 쓰는 경우가 많아 키워드로 '정밀'
        필터링하면 진짜 나눔글을 놓치지만(미탐), 잡담/질문처럼 나눔 신호가
        '전혀' 없는 글까지 AI에 보내면 무료 호출 한도(RPD)를 금방 소진한다.
        그래서 넓은 신호로 명백한 무관글만 싸게 걸러 AI 호출을 아낀다.
        (신호 목록이 비어 있으면[config] 사전 필터를 끄고 모든 글을 AI에 보냄)
        - AI가 판단 불가(일시적 오류·한도 초과 등)면, 이미 받아온 본문으로
          키워드 규칙을 돌려 안전하게 대체(fallback)한다. (놓침 방지)

    [AI 꺼짐] 키워드 규칙만 사용 — 제목에 키워드가 있으면 바로 후보, 없으면
        본문을 받아와 본문 키워드까지 검사한다. (AI가 없는 환경의 기존 동작)

    주의(비용): AI 켜짐 모드는 사전 필터를 통과한 '신규 글마다' AI 1회를
    호출한다. 같은 글은 seen 기록 덕분에 다시 호출하지 않는다. 무료 등급의
    일일 한도(RPD)에 걸리면 모델을 한도가 큰 것(flash-lite)으로 바꾸거나
    사전 필터 신호를 좁혀 호출량을 더 줄인다.
    """
    # --- AI 꺼짐: 기존 키워드 규칙(제목 → 본문)만으로 판단 ---
    if classifier is None:
        if _keyword_giveaway(post, None, config):  # 제목만으로 후보면 본문 생략
            return True
        body = fetch_body(post, config, session)  # 제목에 없으면 본문까지 확인
        return _keyword_giveaway(post, body, config)

    # --- AI 켜짐: 본문을 받아온다 (본문 받기는 무료 — AI 호출만 한도를 쓴다) ---
    body = fetch_body(post, config, session)

    # 느슨한 사전 필터: 제목/본문에 나눔 신호가 '하나도' 없으면 AI 호출을 생략한다.
    # (신호 목록이 비어 있으면 필터를 끄고 통과 — 순수 전수검사)
    signals = config.ai_prefilter_keywords
    if signals and not has_any_keyword(f"{post.title}\n{body}", signals):
        log.info("사전 필터: 나눔 신호 없어 AI 생략: [%s] %s", post.no, post.title)
        return False

    # AI 전수검사: 본문을 AI에게 넘겨 '원두 나눔'인지 판단
    result = classifier.classify(post.title, body)

    if result.decision is None:
        # AI 판단 불가(재시도까지 실패) → 받아둔 본문으로 키워드 규칙 대체
        keyword_hit = _keyword_giveaway(post, body, config)
        log.warning(
            "AI 판단 불가, 키워드 결과로 대체: [%s] %s → %s",
            post.no, post.title, "나눔후보" if keyword_hit else "제외",
        )
        return keyword_hit

    log.info(
        "AI 판별: [%s] %s → %s (품목=%s, %s)",
        post.no, post.title,
        "원두나눔" if result.decision else "제외", result.item, result.reason,
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
