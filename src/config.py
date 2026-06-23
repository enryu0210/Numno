"""설정 로드 및 검증.

설정은 두 가지 방법으로 줄 수 있다(우선순위 순):
  1) config.json 파일 (로컬 PC에서 실행할 때 편함)
  2) 환경변수            (Railway 등 클라우드 배포 시 권장)

config.json 이 있으면 그걸 쓰고, 없으면 환경변수에서 읽는다.
어느 쪽이든 필수값(웹훅 URL)이 비어 있으면 친절한 한국어 메시지로 즉시 종료시킨다.

저장 경로(data/, logs/)도 여기서 한 곳에 정의한다.
클라우드에서는 컨테이너가 재시작되면 파일이 사라지므로(휘발성),
DATA_DIR 환경변수로 영구 디스크(Railway Volume 등) 경로를 지정할 수 있게 했다.
"""

import json
import os
from dataclasses import dataclass, field

# 이 파일(src/config.py) 기준으로 프로젝트 루트 경로를 계산한다.
# 어디서 실행하든(작업 스케줄러 등) 경로가 어긋나지 않게 하기 위함.
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_SRC_DIR)
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")

# 데이터/로그 저장 경로.
# - 로컬: 프로젝트 폴더 안의 data/, logs/
# - 클라우드: DATA_DIR / LOG_DIR 환경변수로 영구 디스크 경로를 지정
#   (지정 안 하면 재배포 때마다 '본 글' 기록이 사라져 알림을 놓칠 수 있음)
DATA_DIR = os.environ.get("DATA_DIR") or os.path.join(PROJECT_ROOT, "data")
LOG_DIR = os.environ.get("LOG_DIR") or os.path.join(PROJECT_ROOT, "logs")


# 무료 등급 RPD(하루 호출 수) 한도가 가장 넉넉하면서 system_instruction·JSON
# 모드를 지원하는 모델. (최신/큰 모델일수록 무료 한도가 짜다 — 한 곳에서 관리)
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"

# 'AI 전수검사' 사전 필터 기본 신호 키워드.
# (Config 기본값과 _build_config 가 공유 — 한 곳에서만 고치면 되게 상수로 둠)
DEFAULT_PREFILTER_KEYWORDS = [
    "나눔", "룰렛", "추첨", "당첨", "응모", "선착",
    "드림", "드려", "드릴", "쏜다", "쏠게", "쏩니",
    "착불", "반택", "택비", "택배비", "무료", "고닉",
]


class ConfigError(Exception):
    """설정이 잘못되었을 때 발생하는 예외."""


@dataclass
class Config:
    """서비스 실행에 필요한 모든 설정값."""

    discord_webhook_url: str
    gallery_id: str = "coffee"
    poll_interval_sec: int = 180
    keywords: list[str] = field(default_factory=lambda: ["나눔"])
    exclude_keywords: list[str] = field(default_factory=list)
    # 제외할 '말머리(카테고리)' 목록. 이 말머리가 붙은 글은 리스트 단계에서
    # 아예 후보에서 빼버린다. '원두후기' 탭에는 '나눔 원두 후기'도 올라와
    # 키워드/AI로도 새기 쉬우므로, 말머리 자체로 먼저 걸러 오탐을 줄인다.
    exclude_categories: list[str] = field(default_factory=lambda: ["원두후기"])
    seen_limit: int = 1000
    # AI(제미나이) 판별용. 키가 비어 있으면 AI를 끄고 키워드 규칙만 쓴다.
    gemini_api_key: str = ""
    # 무료 등급은 모델마다 '하루 호출 수(RPD)' 한도가 다르다. 최신/큰 모델일수록
    # 한도가 짜다(예: gemini-3.5-flash는 하루 20회). flash-lite 계열이 무료
    # RPD가 가장 넉넉(약 1,000회)하면서 system_instruction·JSON 모드를 지원한다.
    gemini_model: str = DEFAULT_GEMINI_MODEL
    # 'AI 전수검사' 앞단의 느슨한 사전 필터(네거티브 게이트)용 신호 키워드.
    # 제목/본문에 이 신호가 하나라도 있는 글만 AI에게 보내, 잡담/질문 같은
    # '나눔과 무관한 글'에 AI 호출(=무료 한도)을 낭비하지 않는다.
    # 재현율을 위해 '나눔' 단어 외에 룰렛/추첨/드림/택비/고닉 등 디시 나눔
    # 슬랭까지 넓게 잡는다. (제외어는 보지 않고 '포함'만 본다)
    # 빈 리스트([])로 두면 사전 필터를 끄고 모든 새 글을 AI에 보낸다(순수 전수검사).
    ai_prefilter_keywords: list[str] = field(
        default_factory=lambda: list(DEFAULT_PREFILTER_KEYWORDS)
    )

    @property
    def list_url(self) -> str:
        """감시할 마이너 갤러리 리스트 URL.

        커피갤러리는 '마이너 갤러리'이므로 경로가 /mgallery/board/lists/ 이다.
        (정식 갤러리와 경로가 다르니 주의)
        """
        return f"https://gall.dcinside.com/mgallery/board/lists/?id={self.gallery_id}"


def _split_keywords(raw: str | None) -> list[str] | None:
    """쉼표로 구분된 환경변수 문자열을 키워드 리스트로 변환한다.

    예: "나눔후기,마감, 나눔완료" → ["나눔후기", "마감", "나눔완료"]
    값이 없으면 None 을 반환해 호출부에서 기본값을 쓰게 한다.
    """
    if not raw:
        return None
    items = [part.strip() for part in raw.split(",")]
    return [item for item in items if item]  # 빈 항목 제거


def _build_config(
    webhook: str,
    gallery_id: str,
    poll_interval_sec: int,
    keywords: list[str] | None,
    exclude_keywords: list[str] | None,
    exclude_categories: list[str] | None,
    seen_limit: int,
    gemini_api_key: str = "",
    gemini_model: str = DEFAULT_GEMINI_MODEL,
    ai_prefilter_keywords: list[str] | None = None,
) -> Config:
    """공통 검증 후 Config 를 생성한다. (파일/환경변수 두 경로가 공유)"""
    # 필수값 검증 — 웹훅 URL이 비었거나 예시 그대로면 동작 불가
    webhook = (webhook or "").strip()
    if not webhook or not webhook.startswith("http"):
        raise ConfigError(
            "discord_webhook_url 이 비어 있거나 잘못되었습니다.\n"
            "→ config.json 의 discord_webhook_url 또는 "
            "환경변수 DISCORD_WEBHOOK_URL 에 실제 웹훅 URL을 넣어주세요."
        )

    return Config(
        discord_webhook_url=webhook,
        gallery_id=gallery_id or "coffee",
        poll_interval_sec=poll_interval_sec,
        keywords=keywords or ["나눔"],
        exclude_keywords=exclude_keywords or [],
        # None(미설정)이면 기본값 ["원두후기"]를 쓰고, 빈 리스트([])를 주면
        # '아무 말머리도 제외하지 않음'으로 존중한다. (의도적 비활성화 허용)
        exclude_categories=(
            exclude_categories if exclude_categories is not None else ["원두후기"]
        ),
        seen_limit=seen_limit,
        # AI는 선택 기능 — 키가 없으면 빈 문자열로 두고 키워드 규칙만 쓴다.
        gemini_api_key=(gemini_api_key or "").strip(),
        gemini_model=(gemini_model or DEFAULT_GEMINI_MODEL).strip(),
        # None(미설정)이면 기본 신호 목록을 쓰고, 빈 리스트([])를 주면
        # '사전 필터 끔(전수검사)'으로 존중한다. (exclude_categories 와 같은 규칙)
        ai_prefilter_keywords=(
            ai_prefilter_keywords
            if ai_prefilter_keywords is not None
            else list(DEFAULT_PREFILTER_KEYWORDS)
        ),
    )


def _load_from_file(path: str) -> Config:
    """config.json 파일에서 설정을 읽는다."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"config.json 형식이 잘못되었습니다: {e}") from e

    return _build_config(
        webhook=raw.get("discord_webhook_url", ""),
        gallery_id=raw.get("gallery_id", "coffee"),
        poll_interval_sec=int(raw.get("poll_interval_sec", 180)),
        keywords=raw.get("keywords"),
        exclude_keywords=raw.get("exclude_keywords"),
        exclude_categories=raw.get("exclude_categories"),
        seen_limit=int(raw.get("seen_limit", 1000)),
        gemini_api_key=raw.get("gemini_api_key", ""),
        gemini_model=raw.get("gemini_model", DEFAULT_GEMINI_MODEL),
        ai_prefilter_keywords=raw.get("ai_prefilter_keywords"),
    )


def _load_from_env() -> Config:
    """환경변수에서 설정을 읽는다. (Railway 등 클라우드 배포용)

    지원 환경변수:
      DISCORD_WEBHOOK_URL  (필수)
      GALLERY_ID, POLL_INTERVAL_SEC, SEEN_LIMIT (선택)
      KEYWORDS, EXCLUDE_KEYWORDS, EXCLUDE_CATEGORIES  (선택, 쉼표로 구분)
      AI_PREFILTER_KEYWORDS  (선택, 쉼표로 구분. AI 전수검사 사전 필터 신호)
      GEMINI_API_KEY, GEMINI_MODEL  (선택, AI 판별용)
    """
    env = os.environ
    if not env.get("DISCORD_WEBHOOK_URL"):
        # 파일도 없고 환경변수도 없는 경우 → 둘 중 하나를 채우라고 안내
        raise ConfigError(
            "설정을 찾을 수 없습니다.\n"
            f"→ 로컬 실행: config.example.json 을 config.json 으로 복사 후 웹훅 URL 입력\n"
            "→ 클라우드(Railway 등): 환경변수 DISCORD_WEBHOOK_URL 을 설정"
        )

    return _build_config(
        webhook=env.get("DISCORD_WEBHOOK_URL", ""),
        gallery_id=env.get("GALLERY_ID", "coffee"),
        poll_interval_sec=int(env.get("POLL_INTERVAL_SEC", "180")),
        keywords=_split_keywords(env.get("KEYWORDS")),
        exclude_keywords=_split_keywords(env.get("EXCLUDE_KEYWORDS")),
        exclude_categories=_split_keywords(env.get("EXCLUDE_CATEGORIES")),
        seen_limit=int(env.get("SEEN_LIMIT", "1000")),
        gemini_api_key=env.get("GEMINI_API_KEY", ""),
        gemini_model=env.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        ai_prefilter_keywords=_split_keywords(env.get("AI_PREFILTER_KEYWORDS")),
    )


def load_config(path: str = DEFAULT_CONFIG_PATH) -> Config:
    """설정을 로드해 Config 를 반환한다.

    config.json 파일이 있으면 그걸 우선 사용하고,
    없으면 환경변수에서 읽는다(클라우드 배포 대응).

    Raises:
        ConfigError: 설정을 찾을 수 없거나, 형식 오류이거나, 필수값이 비었을 때.
    """
    if os.path.exists(path):
        return _load_from_file(path)
    return _load_from_env()
