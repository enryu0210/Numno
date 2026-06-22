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
    seen_limit: int = 1000
    # AI(제미나이) 판별용. 키가 비어 있으면 AI를 끄고 키워드 규칙만 쓴다.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"

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
    seen_limit: int,
    gemini_api_key: str = "",
    gemini_model: str = "gemini-2.5-flash",
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
        seen_limit=seen_limit,
        # AI는 선택 기능 — 키가 없으면 빈 문자열로 두고 키워드 규칙만 쓴다.
        gemini_api_key=(gemini_api_key or "").strip(),
        gemini_model=(gemini_model or "gemini-2.5-flash").strip(),
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
        seen_limit=int(raw.get("seen_limit", 1000)),
        gemini_api_key=raw.get("gemini_api_key", ""),
        gemini_model=raw.get("gemini_model", "gemini-2.5-flash"),
    )


def _load_from_env() -> Config:
    """환경변수에서 설정을 읽는다. (Railway 등 클라우드 배포용)

    지원 환경변수:
      DISCORD_WEBHOOK_URL  (필수)
      GALLERY_ID, POLL_INTERVAL_SEC, SEEN_LIMIT (선택)
      KEYWORDS, EXCLUDE_KEYWORDS  (선택, 쉼표로 구분)
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
        seen_limit=int(env.get("SEEN_LIMIT", "1000")),
        gemini_api_key=env.get("GEMINI_API_KEY", ""),
        gemini_model=env.get("GEMINI_MODEL", "gemini-2.5-flash"),
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
