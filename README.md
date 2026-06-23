# Numno — 디시 커피갤러리 나눔글 알림 서비스

디시인사이드 **커피 마이너 갤러리**([gall.dcinside.com/mgallery/board/lists/?id=coffee](https://gall.dcinside.com/mgallery/board/lists/?id=coffee))에
**나눔글이 올라오면 디스코드로 즉시 알려주는** 백그라운드 서비스입니다.

커피갤러리에는 '나눔' 전용 말머리가 없어서, 게시글 **제목에 "나눔"이 들어간 글**을 키워드로 잡아냅니다.

---

## 동작 방식 (한눈에)

```
[3분마다] 리스트 긁기 → '원두후기' 말머리 글 제외 → 처음 보는 글? →
          본문 가져오기 → AI가 '원두 나눔'인지 판단 → 디스코드 웹훅 알림
            └ 이미 본 글 / AI가 '후기·드립백·장비·잡담 등'으로 판정 → 무시
```

- **0단계 말머리 제외**: '원두후기' 탭 글은 리스트 단계에서 아예 후보에서 뺍니다.
  (이 탭엔 '나눔 원두 후기'도 올라와 키워드/AI로도 새기 쉬워, 말머리로 먼저 거릅니다)
- **AI 전수검사(핵심)**: AI(Gemini)가 켜져 있으면 **키워드로 미리 거르지 않고**,
  처음 보는 글의 **본문을 곧바로 AI에게 보여** '지금 나눠주는 **원두** 나눔글'인지
  판단합니다. 커피갤 나눔글은 "나눔"이라는 단어 없이 **"룰렛·추첨·줄서기"** 같은
  슬랭으로만 쓰는 경우가 많아, 키워드로 1차 필터링하면 진짜 나눔글을 **놓치기**
  때문입니다(미탐). AI는 본문 '의미'를 읽으므로 단어가 없어도 잡아냅니다.
  → "원두 나눔 잘 받았어요 **후기**"는 물론, **드립백·캡슐·장비** 등 원두가 아닌
    '짬뽕 나눔글'도 AI가 걸러내고 **원두 나눔만** 알립니다(OvR: 원두 vs 나머지).
- **느슨한 사전 필터(한도 절약)**: AI에 보내기 전에, 제목/본문에 나눔 신호
  (`나눔·룰렛·추첨·택비·고닉` 등)가 **하나라도** 있는 글만 추립니다. 잡담/질문처럼
  신호가 전혀 없는 글엔 AI를 부르지 않아 **무료 호출 한도(하루 N회)를 아낍니다**.
  신호 목록이 넓어 진짜 나눔글은 거의 다 통과하고, `[]`로 두면 필터를 끕니다.
- **AI는 선택 기능**: Gemini 키가 없으면 AI를 끄고 **키워드 규칙만으로** 동작합니다
  (제목/본문에 `나눔` 같은 포함 키워드가 있고 제외어가 없으면 후보).
  AI 호출이 일시적으로 실패(503 과부하 등)하면 **지수 백오프로 몇 번 재시도**하고,
  그래도 안 되면 받아둔 본문으로 **키워드 규칙에 안전하게 대체(fallback)**되어
  서비스가 멈추지 않습니다.
- **중복 알림 방지**: 한 번 처리한 글 번호를 `data/seen_posts.json`에 저장합니다.
- **과거 글 폭탄 방지**: 처음 켤 때 올라와 있던 글들은 알림 없이 '본 것'으로만 등록합니다.

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
  "exclude_keywords": ["후기", "나눔받", "나눔 받", "나눔완료"],
  "exclude_categories": ["원두후기"],
  "ai_prefilter_keywords": ["나눔", "룰렛", "추첨", "당첨", "응모", "선착", "드림", "드려", "드릴", "쏜다", "쏠게", "쏩니", "착불", "반택", "택비", "택배비", "무료", "고닉"],
  "seen_limit": 1000,
  "gemini_api_key": "구글_AI_스튜디오에서_받은_무료_API_키",
  "gemini_model": "gemini-2.5-flash-lite"
}
```

| 설정값 | 설명 |
|---|---|
| `discord_webhook_url` | (필수) 알림 보낼 디스코드 웹훅 URL |
| `gallery_id` | 감시할 갤러리 id (기본 `coffee`) |
| `poll_interval_sec` | 폴링 주기(초). 너무 짧으면 차단될 수 있어 기본 180초 권장 |
| `keywords` | 나눔글로 볼 포함 키워드 (**AI가 꺼졌을 때만** 사용. AI 켜짐이면 전수검사라 미사용) |
| `exclude_keywords` | 오탐 제거용 제외 키워드 (**AI가 꺼졌을 때만** 사용) |
| `exclude_categories` | 제외할 말머리 목록. 이 말머리 글은 리스트에서 통째로 거름 (기본 `["원두후기"]`, `[]`로 두면 비활성화) |
| `ai_prefilter_keywords` | **AI 전수검사 사전 필터** 신호. 제목/본문에 이 신호가 하나라도 있는 글만 AI에 보내 무료 호출 한도를 아낌 (기본 넓은 슬랭 목록, `[]`로 두면 필터 끄고 모든 글을 AI에 보냄) |
| `seen_limit` | 기억할 최근 글 개수 |
| `gemini_api_key` | (선택) AI 판별용 Gemini 무료 API 키. **비워두면 AI를 끄고 키워드만 사용** |
| `gemini_model` | (선택) 사용할 Gemini 모델. 기본 `gemini-2.5-flash-lite`(무료 일일 한도가 가장 넉넉) |

### 🤖 AI 판별용 Gemini 무료 키 받기

1. [Google AI Studio](https://aistudio.google.com/apikey)에 구글 계정으로 로그인합니다.
2. **Create API key** 를 눌러 키를 발급받습니다. (개인용 무료 등급으로 충분합니다)
3. 발급된 키를 `config.json`의 `gemini_api_key`(또는 환경변수 `GEMINI_API_KEY`)에 넣습니다.

> 무료 등급은 모델마다 **하루 호출 수(RPD)** 한도가 다릅니다. 최신/큰 모델일수록 짜서
> (예: `gemini-3.5-flash`는 하루 20회) 금방 소진됩니다. 기본값 `gemini-2.5-flash-lite`는
> 무료 RPD가 가장 넉넉(약 1,000회)하면서 필요한 기능(시스템 지침·JSON 모드)을 지원합니다.
> 여기에 위 **사전 필터**가 잡담/질문을 걸러줘 호출량을 크게 줄입니다. 그래도 한도에
> 걸리면 한도가 더 큰 모델로 바꾸거나 `ai_prefilter_keywords` 신호를 좁히세요.
> (한 번 본 글은 다시 부르지 않습니다)

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

## ☁️ Railway 배포 (24시간 상시 실행)

내 PC를 계속 켜둘 필요 없이, [Railway](https://railway.app)에 올려 24시간 돌릴 수 있습니다.
이 저장소에는 Railway용 `Procfile`과 `railway.json`이 포함되어 있습니다.

### 설정은 파일 대신 "환경변수"로

클라우드에는 `config.json`(웹훅 URL 등 비밀정보)을 올리지 않습니다.
대신 Railway 대시보드의 **Variables(환경변수)**에 값을 넣습니다.
코드가 `config.json`이 없으면 자동으로 환경변수에서 설정을 읽습니다.

| 환경변수 | 필수 | 설명 | 예시 |
|---|:---:|---|---|
| `DISCORD_WEBHOOK_URL` | ✅ | 디스코드 웹훅 URL | `https://discord.com/api/webhooks/...` |
| `DATA_DIR` | ✅(권장) | '본 글' 기록 저장 경로(아래 Volume 참고) | `/data` |
| `GALLERY_ID` | | 갤러리 id | `coffee` |
| `POLL_INTERVAL_SEC` | | 폴링 주기(초) | `180` |
| `KEYWORDS` | | 나눔 키워드(쉼표 구분) | `나눔` |
| `EXCLUDE_KEYWORDS` | | 제외 키워드(쉼표 구분, AI 꺼졌을 때만 사용) | `후기,나눔받,나눔완료` |
| `EXCLUDE_CATEGORIES` | | 제외 말머리(쉼표 구분, 기본 `원두후기`) | `원두후기` |
| `AI_PREFILTER_KEYWORDS` | | AI 전수검사 사전 필터 신호(쉼표 구분) | `나눔,룰렛,추첨,드림,택비,고닉` |
| `SEEN_LIMIT` | | 기억할 최근 글 개수 | `1000` |
| `GEMINI_API_KEY` | | AI 판별용 Gemini 무료 키(없으면 AI 끔) | `AIza...` |
| `GEMINI_MODEL` | | 사용할 Gemini 모델 | `gemini-2.5-flash-lite` |

### ⚠️ 꼭 알아야 할 점: Volume(영구 디스크) 연결

Railway 컨테이너는 **재배포·재시작 때마다 디스크가 초기화**됩니다.
그냥 두면 '이미 본 글' 기록(`seen_posts.json`)이 사라져,
재시작 순간 올라와 있던 나눔글을 **알림 없이 놓칠 수 있습니다.**

이를 막으려면 **Volume**을 붙이고, 그 경로를 `DATA_DIR`로 지정하세요.

### 배포 순서

1. 이 저장소를 GitHub에 올립니다. (`config.json`은 `.gitignore`로 제외되어 안전)
2. Railway에서 **New Project → Deploy from GitHub repo**로 이 저장소를 선택합니다.
3. 서비스 설정 → **Variables**에 위 표의 환경변수를 입력합니다.
4. 서비스 설정 → **Volumes**에서 새 Volume을 추가하고 **Mount path를 `/data`**로 지정합니다.
   (그리고 `DATA_DIR` 환경변수도 `/data`로 맞춰주세요.)
5. 배포가 끝나면 **Deploy Logs**에 `Numno 시작 ...` / `폴링 완료 ...` 로그가 보이는지 확인합니다.

> 💡 이 서비스는 웹서버가 아니라 **상시 워커(worker)**라 외부 포트를 열지 않습니다.
> Railway는 무료 크레딧을 사용량만큼 소진하니, `POLL_INTERVAL_SEC`을 너무 짧게 두지 마세요(기본 180초 권장).

---

## 폴더 구조

```
Numno/
├── config.json          # 내 설정 (직접 만들기, git 제외)
├── config.example.json  # 설정 예시
├── Procfile             # Railway/Heroku 실행 명령 (worker)
├── railway.json         # Railway 배포 설정
├── requirements.txt
├── src/
│   ├── main.py          # 진입점 + 폴링 루프 (키워드→본문→AI 판별 조합)
│   ├── config.py        # 설정 로드/검증
│   ├── models.py        # Post 데이터 모델
│   ├── scraper.py       # 리스트 크롤링/파싱
│   ├── detector.py      # 나눔글 1차 판별 (키워드)
│   ├── post_fetcher.py  # 게시글 본문 가져오기 (AI 입력용)
│   ├── ai_classifier.py # 나눔글 2차 판별 (Gemini AI)
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
