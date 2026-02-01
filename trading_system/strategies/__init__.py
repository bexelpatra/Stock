"""
전략 모듈.

[ 전략 등록 방식 ]
    @register("전략이름") 데코레이터를 붙이면 STRATEGY_REGISTRY에 자동 등록.
    run_backtest.py에서 이름만으로 전략 클래스를 찾아 생성할 수 있다.

[ 새 전략 추가 방법 ]
    1. 이 디렉토리에 새 .py 파일 생성
    2. TradingStrategy를 상속받는 클래스 작성
    3. @register("이름") 데코레이터 추가
    4. config.yaml에서 strategy.name을 해당 이름으로 설정
    → 끝. run_backtest.py 수정 불필요.
"""

from importlib import import_module
from pathlib import Path
from typing import Any

from trading_system.core.trading_strategy import TradingStrategy

# 전략 이름 → 전략 클래스 매핑
STRATEGY_REGISTRY: dict[str, type[TradingStrategy]] = {}


def register(name: str):
    """전략 클래스를 STRATEGY_REGISTRY에 등록하는 데코레이터."""
    def decorator(cls: type[TradingStrategy]):
        STRATEGY_REGISTRY[name] = cls
        return cls
    return decorator


def create_strategy(name: str, params: dict[str, Any] | None = None) -> TradingStrategy:
    """이름으로 전략 인스턴스를 생성.

    Args:
        name: 등록된 전략 이름 (예: "split_buy", "ma_strategy")
        params: 전략 파라미터 (각 전략의 DEFAULT_PARAMS를 오버라이드)

    Raises:
        ValueError: 등록되지 않은 전략 이름
    """
    if name not in STRATEGY_REGISTRY:
        available = ", ".join(sorted(STRATEGY_REGISTRY.keys()))
        raise ValueError(f"알 수 없는 전략: '{name}'. 사용 가능: {available}")
    return STRATEGY_REGISTRY[name](params=params)


def list_strategies() -> list[str]:
    """등록된 전략 이름 목록 반환."""
    return sorted(STRATEGY_REGISTRY.keys())


def _auto_discover():
    """이 디렉토리의 모든 전략 모듈을 자동 임포트하여 @register가 실행되게 한다."""
    strategies_dir = Path(__file__).parent
    for py_file in strategies_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        module_name = f"trading_system.strategies.{py_file.stem}"
        import_module(module_name)


# 모듈 로드 시 자동 탐색
_auto_discover()
