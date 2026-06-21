# Numno — 디시 커피갤러리 나눔글 알림 서비스

디시인사이드 **커피 마이너 갤러리**([gall.dcinside.com/mgallery/board/lists/?id=coffee](https://gall.dcinside.com/mgallery/board/lists/?id=coffee))에
**나눔글이 올라오면 디스코드로 즉시 알려주는** 백그라운드 서비스입니다.

커피갤러리에는 '나눔' 전용 말머리가 없어서, 게시글 **제목에 "나눔"이 들어간 글**을 키워드로 잡아냅니다.

---

## 동작 방식 (한눈에)

```
[3분마다] 갤러리 리스트 긁기 → 처음 보는 글인가? → 제목에 '나눔' 있나? → 디스코드 웹훅 알림
                                    └ 이미 본 글/나눔 아님 → 무시
```

- **중복 알림 방지**: 한 번 처리한 글 번호를 `data/seen_posts.json`에 저장합니다.
- **과거 글 폭탄 방지**: 처음 켤 때 올라와 있던 글들은 알림 없이 '본 것'으로만 등록합니다.
- **오탐 방지**: "나눔후기", "나눔 받았어요", "나눔 마감" 같은 제목은 제외합니다(설정에서 조정 가능).

---

## 설치

```bash
pip install -r requirements.txt
```

## 설정

1. `config.example.json`을 `config.json`으로 복사합니다.
2. `config.json`을 열어 **디스코드 웹훅 URL**을 넣습니다.
   (디스코드 채널 → 설정 → 연동 → 웹훅 → 새 웹훅 → URL 복사)

```json
{
  "discord_webhook_url": "https://discord.com/api/webhooks/...",
  "gallery_id": "coffee",
  "poll_interval_sec": 180,
  "keywords": ["나눔"],
  "exclude_keywords": ["나눔후기", "나눔받", "나눔 받", "마감", "나눔완료"],
  "seen_limit": 1000
}
```

| 설정값 | 설명 |
|---|---|
| `discord_webhook_url` | (필수) 알림 보낼 디스코드 웹훅 URL |
| `gallery_id` | 감시할 갤러리 id (기본 `coffee`) |
| `poll_interval_sec` | 폴링 주기(초). 너무 짧으면 차단될 수 있어 기본 180초 권장 |
| `keywords` | 나눔글로 볼 제목 키워드 |
| `exclude_keywords` | 오탐 제거용 제외 키워드 |
| `seen_limit` | 기억할 최근 글 개수 |

## 실행

```bash
# 상시 백그라운드 루프 (기본)
python -m src.main

# 1회만 폴링 후 종료 (테스트)
python -m src.main --once

# 웹훅 대신 콘솔에만 출력 (실제 알림 없이 동작 확인)
python -m src.main --once --dry-run
```

## 테스트

```bash
python -m pytest tests/ -v
```

---

## 폴더 구조

```
Numno/
├── config.json          # 내 설정 (직접 만들기, git 제외)
├── config.example.json  # 설정 예시
├── requirements.txt
├── src/
│   ├── main.py          # 진입점 + 폴링 루프
│   ├── config.py        # 설정 로드/검증
│   ├── models.py        # Post 데이터 모델
│   ├── scraper.py       # 리스트 크롤링/파싱
│   ├── detector.py      # 나눔글 판별
│   ├── notifier.py      # 디스코드 웹훅 전송
│   ├── storage.py       # 본 글 저장(중복 방지)
│   └── logger.py        # 로깅
├── data/                # seen_posts.json (자동 생성, git 제외)
├── logs/                # 실행 로그 (자동 생성, git 제외)
└── tests/
    └── test_detector.py
```

## 참고 / 주의

- 폴링이 너무 잦으면 디시가 IP를 일시 차단할 수 있습니다. 기본 3분 간격을 권장합니다.
- 키워드 방식이라 "나눔"을 안 쓴 나눔글은 놓칠 수 있습니다. `keywords`를 운영하며 다듬으세요.
- 디시 HTML 구조가 바뀌면 파싱이 깨질 수 있습니다. 그럴 땐 `src/scraper.py`만 수정하면 됩니다.
