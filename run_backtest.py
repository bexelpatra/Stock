"""
백테스트 실행 스크립트 (시스템 진입점).

[ 사용법 ]
    # 기본 실행 (config.yaml의 전략 사용)
    python run_backtest.py

    # 전략 지정
    python run_backtest.py --strategy split_buy
    python run_backtest.py --strategy ma_strategy

    # 파라미터 오버라이드
    python run_backtest.py --strategy ma_strategy -p ma_period=200 -p position_size_pct=50

    # 샘플 데이터로 테스트
    python run_backtest.py --sample
    python run_backtest.py --strategy split_buy --sample

    # ClickHouse 데이터 사용
    python run_backtest.py --source clickhouse

    # 여러 전략 비교
    python run_backtest.py --compare split_buy ma_strategy
    python run_backtest.py --compare split_buy ma_strategy --sample

    # 등록된 전략 목록 확인
    python run_backtest.py --list
"""

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from trading_system.backtest.engine import BacktestEngine
from trading_system.backtest.metrics import BacktestMetrics
from trading_system.strategies import create_strategy, list_strategies
from trading_system.utils.config import Config
from trading_system.utils.logger import setup_logger
from trading_system.data.clickhouse_provider import ClickHouseDataProvider


def generate_sample_data(
    ticker: str,
    start_date: date,
    end_date: date,
    initial_price: float = 70000,
    volatility: float = 0.02,
) -> pd.DataFrame:
    """백테스트용 샘플 주가 데이터 생성."""
    np.random.seed(hash(ticker) % 2**32)

    dates = pd.bdate_range(start=start_date, end=end_date)
    n = len(dates)

    returns = np.random.normal(0.0002, volatility, n)
    prices = initial_price * np.cumprod(1 + returns)

    data = []
    for i, d in enumerate(dates):
        close = prices[i]
        high = close * (1 + abs(np.random.normal(0, 0.01)))
        low = close * (1 - abs(np.random.normal(0, 0.01)))
        open_price = close * (1 + np.random.normal(0, 0.005))
        volume = int(np.random.lognormal(12, 1))

        data.append({
            "date": d.date(),
            "open": round(open_price, 0),
            "high": round(high, 0),
            "low": round(low, 0),
            "close": round(close, 0),
            "volume": volume,
        })

    return pd.DataFrame(data)


def parse_param(param_str: str) -> tuple[str, object]:
    """'key=value' 문자열을 파싱하여 (key, value) 반환. 숫자면 자동 변환."""
    key, _, value = param_str.partition("=")
    key = key.strip()
    value = value.strip()

    # 숫자 자동 변환
    try:
        if "." in value:
            return key, float(value)
        return key, int(value)
    except ValueError:
        # bool 변환
        if value.lower() in ("true", "yes"):
            return key, True
        if value.lower() in ("false", "no"):
            return key, False
        return key, value


def load_data(config: Config, source: str) -> dict[str, pd.DataFrame]:
    """데이터 소스에서 OHLCV 데이터 로드."""
    start = date.fromisoformat(config.backtest.start_date)
    end = date.fromisoformat(config.backtest.end_date)
    tickers = config.strategy.tickers or ["005930.KS", "000660.KS"]

    if source == "sample":
        print("샘플 데이터 생성 중...")
        data = {}
        for ticker in tickers:
            initial_price = 70000 if "005930" in ticker else 150000
            data[ticker] = generate_sample_data(
                ticker=ticker,
                start_date=start,
                end_date=end,
                initial_price=initial_price,
            )
            print(f"  {ticker}: {len(data[ticker])}일 데이터")
        return data

    elif source == "clickhouse":
        print("ClickHouse에서 데이터 조회 중...")
        provider = ClickHouseDataProvider(
            host=config.database.host,
            port=config.database.port,
            database=config.database.database,
            user=config.database.user,
            password=config.database.password,
            use_adjusted_close=config.database.use_adjusted_close,
        )

        available_tickers = provider.get_tickers()
        print(f"  ClickHouse에 저장된 티커: {available_tickers}")

        data = {}
        for ticker in tickers:
            if ticker not in available_tickers:
                print(f"  [SKIP] {ticker}: ClickHouse에 데이터 없음")
                continue

            df = provider.get_ohlcv(ticker, start, end)
            if df.empty:
                print(f"  [SKIP] {ticker}: 기간 내 데이터 없음")
                continue

            data[ticker] = df
            print(f"  {ticker}: {len(df)}일 데이터 로드")

        if not data:
            print("\n오류: 백테스트할 데이터가 없습니다.")
            print("  1. scripts/ingest_data.py로 데이터 수집")
            print("  2. --source sample 옵션으로 샘플 데이터 사용")
        return data

    else:
        print(f"오류: 알 수 없는 데이터 소스: {source}")
        return {}


def run_single(config: Config, strategy_name: str, strategy_params: dict, data: dict[str, pd.DataFrame]) -> BacktestMetrics | None:
    """단일 전략 백테스트 실행."""
    start = date.fromisoformat(config.backtest.start_date)
    end = date.fromisoformat(config.backtest.end_date)

    strategy = create_strategy(strategy_name, params=strategy_params)

    engine = BacktestEngine(
        initial_cash=config.backtest.initial_cash,
        commission_rate=config.backtest.commission_rate,
        tax_rate=config.backtest.tax_rate,
        slippage_rate=config.backtest.slippage_rate,
    )

    metrics = engine.run_backtest(strategy, data, start, end)

    # 거래 내역 요약
    report = engine.generate_report()
    trades = report["trades"]
    buy_trades = [t for t in trades if t["side"] == "buy"]
    sell_trades = [t for t in trades if t["side"] == "sell"]

    return metrics, len(buy_trades), len(sell_trades), sell_trades


def print_single_result(strategy_name: str, metrics: BacktestMetrics, buy_count: int, sell_count: int, sell_trades: list):
    """단일 전략 결과 출력."""
    print(f"\n[전략: {strategy_name}]")
    print(metrics.summary())
    print(f"\n총 거래 횟수: {buy_count + sell_count}")
    print(f"  매수: {buy_count}회")
    print(f"  매도: {sell_count}회")

    if sell_trades:
        print("\n최근 매도 거래 (최대 5건):")
        for t in sell_trades[-5:]:
            profit_str = f"+{t['profit']:,.0f}" if t['profit'] > 0 else f"{t['profit']:,.0f}"
            print(f"  [{t['date']}] {t['ticker']} {t['quantity']}주 @ {t['price']:,.0f}원 -> {profit_str}원")


def print_comparison(results: dict[str, BacktestMetrics], config: Config):
    """여러 전략 비교 결과 출력."""
    tickers = config.strategy.tickers or ["(default)"]
    period = f"{config.backtest.start_date} ~ {config.backtest.end_date}"

    names = list(results.keys())
    col_width = max(14, max(len(n) for n in names) + 2)

    print(f"\n{'=' * (20 + col_width * len(names))}")
    print(f"전략 비교 결과 ({', '.join(tickers)}, {period})")
    print(f"{'=' * (20 + col_width * len(names))}")

    # 헤더
    header = f"{'':>20}" + "".join(f"{n:>{col_width}}" for n in names)
    print(header)
    print("-" * len(header))

    # 지표 행
    rows = [
        ("총 수익률", lambda m: f"{m.total_return:.2f}%"),
        ("연환산 수익률", lambda m: f"{m.annual_return:.2f}%"),
        ("샤프 비율", lambda m: f"{m.sharpe_ratio:.2f}"),
        ("최대 낙폭(MDD)", lambda m: f"{m.max_drawdown:.2f}%"),
        ("총 거래 횟수", lambda m: f"{m.total_trades}"),
        ("승률", lambda m: f"{m.win_rate:.1f}%"),
        ("수익 팩터", lambda m: f"{m.profit_factor:.2f}"),
        ("평균 수익", lambda m: f"{m.avg_profit:,.0f}원"),
        ("평균 손실", lambda m: f"{m.avg_loss:,.0f}원"),
        ("최대 연속 수익", lambda m: f"{m.max_consecutive_wins}"),
        ("최대 연속 손실", lambda m: f"{m.max_consecutive_losses}"),
    ]

    for label, fmt in rows:
        row = f"{label:>20}" + "".join(f"{fmt(results[n]):>{col_width}}" for n in names)
        print(row)

    print(f"{'=' * (20 + col_width * len(names))}")


def main():
    parser = argparse.ArgumentParser(description="주식 백테스트 실행")
    parser.add_argument("--config", type=str, default="config.yaml", help="설정 파일 경로")
    parser.add_argument("--strategy", type=str, default=None, help="전략 이름 (config.yaml 대신 지정)")
    parser.add_argument("-p", "--param", action="append", default=[], help="파라미터 오버라이드 (예: -p ma_period=200)")
    parser.add_argument("--sample", action="store_true", help="샘플 데이터로 테스트")
    parser.add_argument("--source", type=str, default="sample", choices=["sample", "clickhouse"], help="데이터 소스")
    parser.add_argument("--compare", nargs="+", metavar="STRATEGY", help="여러 전략 비교 (예: --compare split_buy ma_strategy)")
    parser.add_argument("--list", action="store_true", help="등록된 전략 목록 출력")
    args = parser.parse_args()

    # 전략 목록 출력
    if args.list:
        print("등록된 전략:")
        for name in list_strategies():
            print(f"  - {name}")
        return

    # 설정 로드
    config_path = Path(args.config)
    if config_path.exists():
        config = Config.from_yaml(config_path)
    else:
        print(f"설정 파일 없음: {config_path}, 기본값 사용")
        config = Config()

    # 로거
    logger = setup_logger(level=config.log_level, log_dir=config.log_dir)

    # --sample 호환
    if args.sample:
        args.source = "sample"

    # 데이터 로드 (한 번만)
    data = load_data(config, args.source)
    if not data:
        return

    # ─── 비교 모드 ───────────────────────────────────────────────────────
    if args.compare:
        print(f"\n{len(args.compare)}개 전략 비교 실행...")
        results = {}
        for name in args.compare:
            print(f"\n--- {name} 실행 중 ---")
            # 비교 모드에서는 config의 params를 기본으로 사용
            result = run_single(config, name, config.strategy.params, data)
            if result:
                metrics, _, _, _ = result
                results[name] = metrics
        if results:
            print_comparison(results, config)
        return

    # ─── 단일 실행 모드 ─────────────────────────────────────────────────
    strategy_name = args.strategy or config.strategy.name
    strategy_params = dict(config.strategy.params)

    # CLI 파라미터 오버라이드
    for p in args.param:
        key, value = parse_param(p)
        strategy_params[key] = value

    print(f"\n전략: {strategy_name}")
    if args.param:
        print(f"파라미터 오버라이드: {dict(parse_param(p) for p in args.param)}")

    result = run_single(config, strategy_name, strategy_params, data)
    if result:
        metrics, buy_count, sell_count, sell_trades = result
        print_single_result(strategy_name, metrics, buy_count, sell_count, sell_trades)


if __name__ == "__main__":
    main()
