"""나눔글 판별 로직.

커피갤러리에는 '나눔' 전용 말머리가 없으므로, 유저가 제목에 직접 쓴
"나눔" 같은 키워드로 판별한다.

판별 규칙(단순함을 최우선):
  - 제목에 keywords 중 하나라도 포함  → 나눔글 후보
  - 단, exclude_keywords 중 하나라도 포함되면 제외 (오탐 거르기)

예시:
  "에티오피아 원두 나눔합니다"  → True  ('나눔' 포함, 제외어 없음)
  "지난번 나눔후기 올립니다"   → False ('나눔후기'가 제외어)
  "나눔 받아가신 분~"          → False ('나눔 받'이 제외어)
  "라떼 아트 후기"             → False ('나눔' 없음)
"""

from .models import Post


def _normalize(text: str) -> str:
    """비교용으로 제목을 정규화한다.

    공백을 모두 제거하여 "나눔 합니다"와 "나눔합니다"를 같게 본다.
    (키워드/제외어도 같은 방식으로 정규화해 비교한다)
    """
    return "".join(text.split()).lower()


def is_giveaway(post: Post, keywords: list[str], exclude_keywords: list[str]) -> bool:
    """게시글이 '알릴 만한 나눔글'인지 판별한다.

    Args:
        post: 검사할 게시글.
        keywords: 나눔글로 볼 키워드 목록 (예: ["나눔"]).
        exclude_keywords: 오탐 제거용 제외 키워드 목록 (예: ["나눔후기"]).

    Returns:
        나눔글이면 True.
    """
    title = _normalize(post.title)

    # 1) 제외어가 하나라도 있으면 즉시 탈락
    for ex in exclude_keywords:
        if _normalize(ex) in title:
            return False

    # 2) 포함 키워드가 하나라도 있으면 나눔글
    for kw in keywords:
        if _normalize(kw) in title:
            return True

    return False
