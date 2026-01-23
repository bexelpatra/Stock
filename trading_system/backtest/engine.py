"""
백테스팅 엔진 모듈.

[ 역할 ]
    과거 데이터에 전략을 적용하여 가상 매매를 시뮬레이션하고 성과를 측정.
    시스템의 핵심 실행 루프를 담당.

[ 실행 흐름 ]
    run_backtest() 호출 시:
        1. 모든 종목의 거래일 합집합 추출
        2. 각 거래일에 대해 _simulate_day() 호출
           → 종목별로 strategy.generate_signal() 호출
           → Signal이 BUY/SELL이면 _execute_buy/sell() 실행
           → portfolio에 거래 반영
        3. 일별 총 자산 가치 기록 (daily_values)
        4. metrics.calculate_metrics()로 성과 지표 계산

[ 의존성 ]
    - core/trading_strategy.py::TradingStrategy (전략 인터페이스)
    - data/portfolio.py::Portfolio (포지션/거래기록 관리)
    - backtest/metrics.py::calculate_metrics() (성과 계산)

[ 호출하는 곳 ]
    - run_backtest.py (진입점)에서 생성 및 실행
"""

import logging
from datetime import date
from typing import Any

import pandas as pd

from trading_system.backtest.metrics import BacktestMetrics, calculate_metrics
from trading_system.core.trading_strategy import PositionInfo, SignalType, TradingStrategy
from trading_system.data.portfolio import Portfolio

logger = logging.getLogger("trading_system.backtest")


class BacktestEngine:
    """백테스팅 엔진. run_backtest()로 시뮬레이션 실행."""

    def __init__(
        self,
        initial_cash: float = 10_000_000,
        commission_rate: float = 0.00015,   # 매수/매도 수수료율
        tax_rate: float = 0.0023,           # 매도세율
        slippage_rate: float = 0.001,       # 슬리피지율
    ):
        self.initial_cash = initial_cash
        self.commission_rate = commission_rate
        self.tax_rate = tax_rate
        self.slippage_rate = slippage_rate

        # 백테스트 실행 후 채워지는 결과
        self.portfolio: Portfolio | None = None       # 최종 포트폴리오 상태
        self.daily_values: list[float] = []           # 일별 총 자산 (MDD/샤프 계산용)
        self.daily_dates: list[date] = []             # 일별 날짜
        self.metrics: BacktestMetrics | None = None   # 최종 성과 지표

    def run_backtest(
        self,
        strategy: TradingStrategy,
        data: dict[str, pd.DataFrame],
        start_date: date,
        end_date: date,
    ) -> BacktestMetrics:
        """백테스트 실행.

        Args:
            strategy: 매매 전략
            data: {ticker: OHLCV DataFrame} 형태의 데이터
            start_date: 시작일
            end_date: 종료일

        Returns:
            BacktestMetrics: 성과 지표
        """
        self.portfolio = Portfolio(self.initial_cash)
        self.daily_values = []
        self.daily_dates = []

        # 전체 거래일 추출
        all_dates: set[date] = set()
        for df in data.values():
            df_copy = df.copy()
            df_copy["date"] = pd.to_datetime(df_copy["date"]).dt.date
            dates = df_copy[(df_copy["date"] >= start_date) & (df_copy["date"] <= end_date)]["date"]
            all_dates.update(dates)

        trading_dates = sorted(all_dates)

        if not trading_dates:
            logger.warning("거래일이 없습니다.")
            return BacktestMetrics()

        logger.info(f"백테스트 시작: {trading_dates[0]} ~ {trading_dates[-1]} ({len(trading_dates)}일)")

        # 종목별 데이터 전처리
        ticker_data: dict[str, pd.DataFrame] = {}
        for ticker, df in data.items():
            df_copy = df.copy()
            df_copy["date"] = pd.to_datetime(df_copy["date"]).dt.date
            df_copy = df_copy.sort_values("date").reset_index(drop=True)
            ticker_data[ticker] = df_copy

        # 일별 시뮬레이션
        for current_date in trading_dates:
            self._simulate_day(strategy, ticker_data, current_date)

            # 일별 자산 가치 기록
            total_value = self._calculate_total_value(ticker_data, current_date)
            self.daily_values.append(total_value)
            self.daily_dates.append(current_date)

        # 성과 지표 계산
        self.metrics = calculate_metrics(
            trade_history=self.portfolio.trade_history,
            daily_values=self.daily_values,
            initial_cash=self.initial_cash,
            trading_days=len(trading_dates),
        )

        logger.info(f"백테스트 완료. 총 수익률: {self.metrics.total_return:.2f}%")
        return self.metrics

    def _simulate_day(
        self,
        strategy: TradingStrategy,
        ticker_data: dict[str, pd.DataFrame],
        current_date: date,
    ) -> None:
        """하루 시뮬레이션. 모든 종목에 대해 시그널 생성 → 주문 실행."""
        for ticker, df in ticker_data.items():
            # 전략에 전달할 데이터: 현재일까지의 과거 데이터 (미래 데이터 누출 방지)
            mask = df["date"] <= current_date
            available_data = df[mask]

            if available_data.empty:
                continue

            # 현재일 데이터 존재 여부 확인
            today_data = df[df["date"] == current_date]
            if today_data.empty:
                continue

            current_price = float(today_data.iloc[0]["close"])

            # 포지션 정보 구성
            position = self.portfolio.get_position(ticker)
            position_info = PositionInfo(
                ticker=ticker,
                quantity=position.quantity,
                avg_price=position.avg_price,
                buy_count=position.buy_count,
                max_buy_count=int(strategy.params.get("split_count", 5)),
            )

            # 시그널 생성
            signal = strategy.generate_signal(
                market_data=available_data.tail(30),
                position_info=position_info,
                available_cash=self.portfolio.cash,
            )

            # 시그널 실행
            if signal.signal_type == SignalType.BUY:
                self._execute_buy(ticker, signal.quantity, current_price, str(current_date), signal.reason)
            elif signal.signal_type == SignalType.SELL:
                self._execute_sell(ticker, signal.quantity, current_price, str(current_date), signal.reason)

    def _execute_buy(
        self,
        ticker: str,
        quantity: int,
        price: float,
        date_str: str,
        reason: str,
    ) -> None:
        """매수 실행. 슬리피지(가격↑) + 수수료 적용 후 portfolio에 반영."""
        exec_price = price * (1 + self.slippage_rate)  # 매수 시 불리하게
        commission = exec_price * quantity * self.commission_rate

        success = self.portfolio.execute_buy(
            ticker=ticker,
            quantity=quantity,
            price=exec_price,
            commission=commission,
            date=date_str,
            reason=reason,
        )
        if success:
            logger.debug(f"[{date_str}] 매수: {ticker} {quantity}주 @ {exec_price:,.0f}원 ({reason})")

    def _execute_sell(
        self,
        ticker: str,
        quantity: int,
        price: float,
        date_str: str,
        reason: str,
    ) -> None:
        """매도 실행. 슬리피지(가격↓) + 수수료 + 세금 적용 후 portfolio에 반영."""
        exec_price = price * (1 - self.slippage_rate)  # 매도 시 불리하게
        commission = exec_price * quantity * self.commission_rate
        tax = exec_price * quantity * self.tax_rate  # 매도세

        success = self.portfolio.execute_sell(
            ticker=ticker,
            quantity=quantity,
            price=exec_price,
            commission=commission,
            tax=tax,
            date=date_str,
            reason=reason,
        )
        if success:
            logger.debug(f"[{date_str}] 매도: {ticker} {quantity}주 @ {exec_price:,.0f}원 ({reason})")

    def _calculate_total_value(
        self,
        ticker_data: dict[str, pd.DataFrame],
        current_date: date,
    ) -> float:
        """현재일 기준 총 자산 가치 계산."""
        total = self.portfolio.cash
        for ticker in self.portfolio.get_holding_tickers():
            position = self.portfolio.get_position(ticker)
            if ticker in ticker_data:
                df = ticker_data[ticker]
                today = df[df["date"] == current_date]
                if not today.empty:
                    price = float(today.iloc[0]["close"])
                else:
                    price = position.avg_price
            else:
                price = position.avg_price
            total += position.quantity * price
        return total

    def generate_report(self) -> dict[str, Any]:
        """백테스트 리포트 생성."""
        if self.metrics is None or self.portfolio is None:
            return {"error": "백테스트를 먼저 실행하세요."}

        return {
            "metrics": self.metrics.to_dict(),
            "portfolio_summary": self.portfolio.get_summary(),
            "trade_count": len(self.portfolio.trade_history),
            "trades": [
                {
                    "date": t.date,
                    "ticker": t.ticker,
                    "side": t.side,
                    "quantity": t.quantity,
                    "price": t.price,
                    "profit": t.profit,
                    "reason": t.reason,
                }
                for t in self.portfolio.trade_history
            ],
        }
