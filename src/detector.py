"""나눔글 판별 로직(키워드 1차 필터).

커피갤러리에는 '나눔' 전용 말머리가 없으므로, 유저가 직접 쓴 "나눔" 같은
키워드로 1차 후보를 거른다. 제목에만 키워드를 안 쓰는 글도 많아서,
제목뿐 아니라 '본문 내용'에도 같은 키워드 규칙을 적용할 수 있게 만들었다.

판별 규칙(단순함을 최우선):
  - 텍스트에 keywords 중 하나라도 포함  → 나눔글 후보
  - 단, exclude_keywords 중 하나라도 포함되면 제외 (오탐 거르기)

예시(제목 기준):
  "에티오피아 원두 나눔합니다"  → True  ('나눔' 포함, 제외어 없음)
  "지난번 나눔후기 올립니다"   → False ('후기'가 제외어)
  "나눔 받아가신 분~"          → False ('나눔받'이 제외어)
  "라떼 아트 후기"             → False ('나눔' 없음)
"""

from .models import Post


def _normalize(text: str) -> str:
    """비교용으로 텍스트를 정규화한다.

    공백을 모두 제거하여 "나눔 합니다"와 "나눔합니다"를 같게 본다.
    (키워드/제외어도 같은 방식으로 정규화해 비교한다)
    """
    return "".join(text.split()).lower()


def is_giveaway_text(text: str, keywords: list[str], exclude_keywords: list[str]) -> bool:
    """임의의 텍스트(제목 또는 본문)가 나눔글 후보인지 키워드로 판별한다.

    제목과 본문 양쪽에서 똑같이 재사용하기 위한 핵심 함수다.

    Args:
        text: 검사할 텍스트(제목 또는 본문).
        keywords: 나눔글로 볼 키워드 목록 (예: ["나눔"]).
        exclude_keywords: 오탐 제거용 제외 키워드 목록 (예: ["후기"]).

    Returns:
        키워드 후보면 True.
    """
    norm = _normalize(text)

    # 1) 제외어가 하나라도 있으면 즉시 탈락
    for ex in exclude_keywords:
        if _normalize(ex) in norm:
            return False

    # 2) 포함 키워드가 하나라도 있으면 나눔글 후보
    for kw in keywords:
        if _normalize(kw) in norm:
            return True

    return False


def is_giveaway(post: Post, keywords: list[str], exclude_keywords: list[str]) -> bool:
    """게시글 '제목'이 나눔글 후보인지 판별한다. (제목 전용 진입점)

    본문까지 함께 보는 로직은 main 의 _is_real_giveaway 가 담당하고,
    여기서는 가장 싼 1차 게이트인 '제목' 검사만 책임진다.
    """
    return is_giveaway_text(post.title, keywords, exclude_keywords)
