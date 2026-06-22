"""로깅 설정.

콘솔과 logs/numno.log 파일에 동시에 로그를 남긴다.
상시 백그라운드로 돌기 때문에, 나중에 무슨 일이 있었는지 추적하려면 파일 로그가 필수다.
"""

import logging
import os

# LOG_DIR 은 config 에서 한 곳에 정의한다.
# (로컬은 프로젝트의 logs/, 클라우드는 LOG_DIR 환경변수로 경로 지정 가능)
from .config import LOG_DIR

_LOG_FILE = os.path.join(LOG_DIR, "numno.log")


def get_logger(name: str = "numno") -> logging.Logger:
    """콘솔 + 파일 핸들러가 붙은 로거를 반환한다.

    여러 번 호출해도 핸들러가 중복 추가되지 않도록 가드한다.
    """
    logger = logging.getLogger(name)
    if logger.handlers:  # 이미 설정됨 → 그대로 반환
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 콘솔 출력
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    # 파일 출력 (logs 폴더가 없으면 만든다)
    os.makedirs(LOG_DIR, exist_ok=True)
    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
