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
    """전략 설정. config.yaml의 strategy 섹션에 대응.

    전략별 파라미터는 params dict에 자유롭게 넣는다.
    각 전략 클래스의 DEFAULT_PARAMS가 기본값 역할을 하므로,
    여기서는 오버라이드할 값만 지정하면 된다.
    """
    name: str = "split_buy"
    tickers: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)


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
class DatabaseConfig:
    """데이터베이스 설정. config.yaml의 database 섹션에 대응."""
    host: str = "localhost"
    port: int = 8123
    database: str = "default"
    user: str = "default"
    password: str = "password"
    use_adjusted_close: bool = True


@dataclass
class DataIngestionConfig:
    """데이터 수집 설정. config.yaml의 data_ingestion 섹션에 대응."""
    default_lookback_days: int = 365
    max_retries: int = 3
    retry_delay: int = 5


@dataclass
class Config:
    """전체 설정. from_yaml() 또는 from_json()으로 파일에서 로드."""
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    data_ingestion: DataIngestionConfig = field(default_factory=DataIngestionConfig)
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
        database_data = data.get("database", {})
        data_ingestion_data = data.get("data_ingestion", {})

        # strategy 섹션 파싱: name, tickers는 직접 필드, 나머지는 모두 params로
        strategy_name = strategy_data.get("name", "split_buy")
        strategy_tickers = strategy_data.get("tickers", [])
        # params가 명시적으로 있으면 그것을 사용, 없으면 name/tickers 외 나머지를 params로
        if "params" in strategy_data:
            strategy_params = strategy_data["params"]
        else:
            strategy_params = {
                k: v for k, v in strategy_data.items()
                if k not in ("name", "tickers")
            }
        strategy = StrategyConfig(
            name=strategy_name,
            tickers=strategy_tickers,
            params=strategy_params,
        )
        backtest = BacktestConfig(**{
            k: v for k, v in backtest_data.items()
            if k in BacktestConfig.__dataclass_fields__
        })
        database = DatabaseConfig(**{
            k: v for k, v in database_data.items()
            if k in DatabaseConfig.__dataclass_fields__
        })
        data_ingestion = DataIngestionConfig(**{
            k: v for k, v in data_ingestion_data.items()
            if k in DataIngestionConfig.__dataclass_fields__
        })

        return cls(
            strategy=strategy,
            backtest=backtest,
            database=database,
            data_ingestion=data_ingestion,
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
