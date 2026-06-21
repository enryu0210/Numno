"""설정 로드 및 검증.

config.json 을 읽어 Config 객체로 만든다.
필수값(웹훅 URL)이 비어 있으면 친절한 한국어 메시지로 즉시 종료시킨다.
"""

import json
import os
from dataclasses import dataclass, field

# 이 파일(src/config.py) 기준으로 프로젝트 루트 경로를 계산한다.
# 어디서 실행하든(작업 스케줄러 등) 경로가 어긋나지 않게 하기 위함.
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_SRC_DIR)
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")


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

    @property
    def list_url(self) -> str:
        """감시할 마이너 갤러리 리스트 URL.

        커피갤러리는 '마이너 갤러리'이므로 경로가 /mgallery/board/lists/ 이다.
        (정식 갤러리와 경로가 다르니 주의)
        """
        return f"https://gall.dcinside.com/mgallery/board/lists/?id={self.gallery_id}"


def load_config(path: str = DEFAULT_CONFIG_PATH) -> Config:
    """config.json 을 읽어 Config 를 반환한다.

    Args:
        path: 설정 파일 경로. 기본값은 프로젝트 루트의 config.json.

    Raises:
        ConfigError: 파일이 없거나, JSON 형식 오류이거나, 필수값이 비었을 때.
    """
    # 1) 파일 존재 확인 — 없으면 예시 파일을 복사하라고 안내
    if not os.path.exists(path):
        raise ConfigError(
            f"설정 파일이 없습니다: {path}\n"
            "→ config.example.json 을 config.json 으로 복사한 뒤 "
            "디스코드 웹훅 URL을 채워주세요."
        )

    # 2) JSON 파싱 (형식이 깨졌으면 어디가 문제인지 알려줌)
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"config.json 형식이 잘못되었습니다: {e}") from e

    # 3) 필수값 검증 — 웹훅 URL이 비었거나 예시 그대로면 동작 불가
    webhook = (raw.get("discord_webhook_url") or "").strip()
    if not webhook or not webhook.startswith("http"):
        raise ConfigError(
            "discord_webhook_url 이 비어 있거나 잘못되었습니다.\n"
            "→ config.json 에 실제 디스코드 웹훅 URL을 넣어주세요."
        )

    # 4) 기본값과 병합하여 Config 생성
    return Config(
        discord_webhook_url=webhook,
        gallery_id=raw.get("gallery_id", "coffee"),
        poll_interval_sec=int(raw.get("poll_interval_sec", 180)),
        keywords=raw.get("keywords") or ["나눔"],
        exclude_keywords=raw.get("exclude_keywords") or [],
        seen_limit=int(raw.get("seen_limit", 1000)),
    )
