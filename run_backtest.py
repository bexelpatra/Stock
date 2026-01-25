"""
백테스트 실행 스크립트 (시스템 진입점).

[ 실행 흐름 ]
    1. config.yaml 로드          → utils/config.py::Config
    2. 로거 설정                 → utils/logger.py::setup_logger
    3. 전략 객체 생성            → strategies/split_buy_strategy.py::SplitBuyStrategy
    4. 백테스트 엔진 생성        → backtest/engine.py::BacktestEngine
    5. 데이터 준비 (샘플 or 실제)
    6. engine.run_backtest() 실행
    7. 성과 리포트 출력          → backtest/metrics.py::BacktestMetrics.summary()

[ 사용법 ]
    python run_backtest.py                    # config.yaml 사용
    python run_backtest.py --config my.yaml   # 커스텀 설정
    python run_backtest.py --sample           # 샘플 랜덤 데이터로 테스트
"""

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# 내부 모듈 임포트 (trading_system 패키지)
from trading_system.backtest.engine import BacktestEngine
from trading_system.strategies.split_buy_strategy import SplitBuyStrategy
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
    """백테스트용 샘플 주가 데이터 생성.

    랜덤 워크 기반의 시뮬레이션 데이터를 생성합니다.
    """
    np.random.seed(hash(ticker) % 2**32)

    dates = pd.bdate_range(start=start_date, end=end_date)
    n = len(dates)

    # 랜덤 워크 기반 종가 생성
    returns = np.random.normal(0.0002, volatility, n)
    prices = initial_price * np.cumprod(1 + returns)

    # OHLCV 생성
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


def main():
    parser = argparse.ArgumentParser(description="주식 백테스트 실행")
    parser.add_argument("--config", type=str, default="config.yaml", help="설정 파일 경로")
    parser.add_argument("--sample", action="store_true", help="샘플 데이터로 테스트")
    parser.add_argument("--source", type=str, default="sample", choices=["sample", "clickhouse"],
                        help="데이터 소스 (sample: 샘플 데이터, clickhouse: ClickHouse DB)")
    args = parser.parse_args()

    # ─── 1단계: 설정 파일 로드 ────────────────────────────────────────────
    config_path = Path(args.config)
    if config_path.exists():
        config = Config.from_yaml(config_path)
    else:
        print(f"설정 파일 없음: {config_path}, 기본값 사용")
        config = Config()

    # ─── 2단계: 로거 설정 ─────────────────────────────────────────────────
    logger = setup_logger(level=config.log_level, log_dir=config.log_dir)

    # ─── 3단계: 전략 생성 (config에서 파라미터 주입) ──────────────────────
    strategy = SplitBuyStrategy(params={
        "total_seed": config.strategy.total_seed,
        "split_count": config.strategy.split_count,
        "buy_threshold": config.strategy.buy_threshold,
        "lookback_days": config.strategy.lookback_days,
        "sell_profit_rate": config.strategy.sell_profit_rate,
        "stop_loss_rate": config.strategy.stop_loss_rate,
        "min_volume_threshold": config.strategy.min_volume_threshold,
    })

    # ─── 4단계: 백테스트 엔진 생성 (수수료/세금/슬리피지 설정) ─────────────
    engine = BacktestEngine(
        initial_cash=config.backtest.initial_cash,
        commission_rate=config.backtest.commission_rate,
        tax_rate=config.backtest.tax_rate,
        slippage_rate=config.backtest.slippage_rate,
    )

    # ─── 5단계: 데이터 준비 ──────────────────────────────────────────────────
    start = date.fromisoformat(config.backtest.start_date)
    end = date.fromisoformat(config.backtest.end_date)
    tickers = config.strategy.tickers or ["005930.KS", "000660.KS"]

    # 호환성: --sample 옵션이 있으면 source를 sample로 설정
    if args.sample:
        args.source = "sample"

    if args.source == "sample":
        # 샘플 모드: 랜덤 워크 기반 가상 데이터 생성
        print("샘플 데이터 생성 중...")
        data = {}
        for ticker in tickers:
            # Yahoo Finance 형식(.KS)이면 제거
            ticker_clean = ticker.replace(".KS", "")
            initial_price = 70000 if "005930" in ticker else 150000
            data[ticker] = generate_sample_data(
                ticker=ticker,
                start_date=start,
                end_date=end,
                initial_price=initial_price,
            )
            print(f"  {ticker}: {len(data[ticker])}일 데이터")

    elif args.source == "clickhouse":
        # ClickHouse 모드: 실제 데이터베이스에서 데이터 조회
        print("ClickHouse에서 데이터 조회 중...")
        provider = ClickHouseDataProvider(
            host=config.database.host,
            port=config.database.port,
            database=config.database.database,
            user=config.database.user,
            password=config.database.password,
            use_adjusted_close=config.database.use_adjusted_close,
        )

        # 사용 가능한 티커 확인
        available_tickers = provider.get_tickers()
        print(f"  ClickHouse에 저장된 티커: {available_tickers}")

        data = {}
        for ticker in tickers:
            if ticker not in available_tickers:
                print(f"  ⚠️  {ticker}: ClickHouse에 데이터 없음 (건너뜀)")
                continue

            df = provider.get_ohlcv(ticker, start, end)
            if df.empty:
                print(f"  ⚠️  {ticker}: 기간 내 데이터 없음 (건너뜀)")
                continue

            data[ticker] = df
            print(f"  ✓ {ticker}: {len(df)}일 데이터 로드")

        if not data:
            print("\n오류: 백테스트할 데이터가 없습니다.")
            print("다음 중 하나를 수행하세요:")
            print("  1. scripts/ingest_data.py로 데이터 수집")
            print("  2. --source sample 옵션으로 샘플 데이터 사용")
            return

    else:
        print(f"오류: 알 수 없는 데이터 소스: {args.source}")
        return

    # ─── 6단계: 백테스트 실행 ─────────────────────────────────────────────
    print("\n백테스트 실행 중...")
    metrics = engine.run_backtest(strategy, data, start, end)

    # ─── 7단계: 결과 출력 ──────────────────────────────────────────────────
    print("\n" + metrics.summary())

    # 거래 내역 요약
    report = engine.generate_report()
    trades = report["trades"]
    if trades:
        print(f"\n총 거래 횟수: {len(trades)}")
        buy_trades = [t for t in trades if t["side"] == "buy"]
        sell_trades = [t for t in trades if t["side"] == "sell"]
        print(f"  매수: {len(buy_trades)}회")
        print(f"  매도: {len(sell_trades)}회")

        if sell_trades:
            print("\n최근 매도 거래 (최대 5건):")
            for t in sell_trades[-5:]:
                profit_str = f"+{t['profit']:,.0f}" if t['profit'] > 0 else f"{t['profit']:,.0f}"
                print(f"  [{t['date']}] {t['ticker']} {t['quantity']}주 @ {t['price']:,.0f}원 → {profit_str}원")


if __name__ == "__main__":
    main()
