"""'이미 본 글' 저장소.

한 번 처리한 게시글 번호를 파일에 저장해, 재시작하거나 다음 폴링 때
같은 글을 또 알리지 않도록 한다(중복 알림 방지).

저장 형식은 단순한 JSON 배열(글 번호 목록)이다.
"""

import json
import os
import tempfile

# DATA_DIR 은 config 에서 한 곳에 정의한다.
# (로컬은 프로젝트의 data/, 클라우드는 DATA_DIR 환경변수로 영구 디스크 지정)
from .config import DATA_DIR

_SEEN_FILE = os.path.join(DATA_DIR, "seen_posts.json")


class SeenStore:
    """이미 처리한 게시글 번호 집합을 관리한다."""

    def __init__(self, limit: int = 1000, path: str = _SEEN_FILE):
        """
        Args:
            limit: 보관할 최대 글 번호 개수. 초과 시 가장 오래된 것부터 버린다.
            path: 저장 파일 경로.
        """
        self.limit = limit
        self.path = path
        # 순서 유지를 위해 list 로 보관(오래된 것이 앞). 조회는 set 으로 빠르게.
        self._order: list[int] = []
        self._set: set[int] = set()

    @property
    def is_empty(self) -> bool:
        """저장된 글이 하나도 없는지 여부. (첫 실행 부트스트랩 판단에 사용)"""
        return len(self._order) == 0

    def exists(self) -> bool:
        """seen 파일이 디스크에 존재하는지 여부."""
        return os.path.exists(self.path)

    def load(self) -> None:
        """파일에서 글 번호 목록을 읽어온다. 파일이 없거나 깨졌으면 빈 상태로 시작."""
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 정수 리스트만 받아들인다(손상 데이터 방어).
            nums = [int(n) for n in data if isinstance(n, (int, str)) and str(n).isdigit()]
        except (json.JSONDecodeError, ValueError, OSError):
            # 파일이 깨졌으면 무시하고 새로 시작 (서비스가 멈추지 않게)
            nums = []
        self._order = nums
        self._set = set(nums)

    def contains(self, no: int) -> bool:
        """해당 글 번호를 이미 본 적 있는지."""
        return no in self._set

    def add(self, no: int) -> None:
        """글 번호를 본 것으로 등록한다. limit 초과 시 오래된 것부터 제거."""
        if no in self._set:
            return
        self._order.append(no)
        self._set.add(no)
        # limit 초과분은 앞(오래된 것)에서 잘라낸다.
        while len(self._order) > self.limit:
            oldest = self._order.pop(0)
            self._set.discard(oldest)

    def save(self) -> None:
        """현재 상태를 파일에 원자적으로 저장한다.

        임시 파일에 먼저 쓴 뒤 교체(os.replace)하여, 저장 도중 중단되어도
        기존 파일이 손상되지 않게 한다.
        """
        os.makedirs(DATA_DIR, exist_ok=True)
        # 같은 디렉터리에 임시 파일 생성(같은 볼륨이어야 os.replace 가 원자적)
        fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._order, f, ensure_ascii=False)
            os.replace(tmp_path, self.path)
        except OSError:
            # 저장 실패 시 임시 파일 정리
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
