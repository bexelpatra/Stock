"""
로깅 모듈.

[ 역할 ]
    파일 + 콘솔 로거를 설정. 매매 실행 내역, 에러 등을 기록.

[ 로그 파일 위치 ]
    {log_dir}/{name}_{YYYYMMDD}.log (예: logs/trading_system_20240601.log)

[ 호출하는 곳 ]
    - run_backtest.py에서 setup_logger() 호출
    - backtest/engine.py에서 logging.getLogger("trading_system.backtest") 사용
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(
    name: str = "trading_system",
    level: str = "INFO",
    log_dir: str = "logs",
    console: bool = True,
) -> logging.Logger:
    """로거 설정. 파일 핸들러(일별) + 콘솔 핸들러 등록."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 파일 핸들러
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    file_handler = logging.FileHandler(
        log_path / f"{name}_{today}.log",
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 콘솔 핸들러
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
