"""
설정 관리 모듈.

[ 역할 ]
    config.yaml (또는 .json) 파일을 파싱하여 Config 객체로 변환.
    전략 파라미터, 백테스트 파라미터, 로깅 설정 등을 통합 관리.

[ 설정 파일 구조 (config.yaml) ]
    strategy:         → StrategyConfig (전략 파라미터)
    backtest:         → BacktestConfig (백테스트 파라미터)
    log_level:        → "INFO" / "DEBUG"
    log_dir:          → 로그 디렉토리 경로

[ 호출하는 곳 ]
    - run_backtest.py에서 Config.from_yaml()로 로드
    - 전략 생성 시 config.strategy의 값을 params로 전달
    - 엔진 생성 시 config.backtest의 값을 사용
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class StrategyConfig:
    """전략 설정. config.yaml의 strategy 섹션에 대응."""
    name: str = "split_buy"
    total_seed: float = 10_000_000
    split_count: int = 5
    buy_threshold: float = 2.0
    lookback_days: int = 1
    sell_profit_rate: float = 3.0
    max_position_per_stock: float = 30.0
    stop_loss_rate: float = 5.0
    max_loss_per_day: float = 500_000
    min_volume_threshold: int = 10_000
    price_comparison_method: str = "percentage"
    partial_sell_enabled: bool = False
    trailing_stop_enabled: bool = False
    holding_period_limit: int = 0  # 0 = 무제한
    order_type: str = "market"
    order_interval: float = 1.0
    max_retry: int = 3
    tickers: list[str] = field(default_factory=list)


@dataclass
class BacktestConfig:
    """백테스트 설정. config.yaml의 backtest 섹션에 대응."""
    start_date: str = "2024-01-01"
    end_date: str = "2024-12-31"
    initial_cash: float = 10_000_000
    commission_rate: float = 0.00015  # 0.015%
    tax_rate: float = 0.0023  # 매도 시 0.23%
    slippage_rate: float = 0.001  # 0.1%


@dataclass
class Config:
    """전체 설정. from_yaml() 또는 from_json()으로 파일에서 로드."""
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    log_level: str = "INFO"
    log_dir: str = "logs"

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        """YAML 파일에서 설정 로드."""
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls._from_dict(data)

    @classmethod
    def from_json(cls, path: str | Path) -> "Config":
        """JSON 파일에서 설정 로드."""
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "Config":
        """딕셔너리에서 Config 생성."""
        strategy_data = data.get("strategy", {})
        backtest_data = data.get("backtest", {})

        strategy = StrategyConfig(**{
            k: v for k, v in strategy_data.items()
            if k in StrategyConfig.__dataclass_fields__
        })
        backtest = BacktestConfig(**{
            k: v for k, v in backtest_data.items()
            if k in BacktestConfig.__dataclass_fields__
        })

        return cls(
            strategy=strategy,
            backtest=backtest,
            log_level=data.get("log_level", "INFO"),
            log_dir=data.get("log_dir", "logs"),
        )

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환."""
        from dataclasses import asdict
        return asdict(self)

    def save_yaml(self, path: str | Path) -> None:
        """YAML 파일로 저장."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, allow_unicode=True, default_flow_style=False)
