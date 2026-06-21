"""게시글 데이터 모델.

스크래퍼가 파싱한 갤러리 게시글 한 건을 표현한다.
이 데이터클래스를 중심으로 scraper → detector → notifier 가 데이터를 주고받는다.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Post:
    """디시 갤러리 게시글 한 건.

    Attributes:
        no: 게시글 고유번호. 중복 알림 방지의 '키'로 사용된다. (예: 402992)
        title: 게시글 제목. 나눔글 판별의 기준이 된다.
        category: 말머리 (예: "잡담", "질문", "정보"). 없으면 빈 문자열.
        author: 글쓴이 닉네임.
        url: 게시글 바로가기 절대 URL.
        date: 작성 시각 문자열 (리스트에 표시된 그대로).
    """

    no: int
    title: str
    category: str
    author: str
    url: str
    date: str
