"""
이동평균선 기반 전략 구현.

[ 역할 ]
    core/trading_strategy.py::TradingStrategy의 구현체.
    "이동평균선 교차 전략: 가격이 이동평균선 위로 올라가면 매수, 아래로 내려가면 전량 매도"

[ 전략 흐름 ]
    매일 generate_signal() 호출됨 (← backtest/engine.py에서)
        ├── 이동평균선 계산
        ├── 보유 중이면 should_sell() 먼저 체크
        │     └── 현재가 < 이동평균선 → SELL (전량 매도)
        │
        └── should_buy() 체크
              ├── 현재가 > 이동평균선?
              ├── 거래량 >= min_volume_threshold?
              └── 모두 충족 시 → BUY

[ 파라미터 (config.yaml의 strategy 섹션에서 로드) ]
    total_seed:           총 시드머니
    ma_period:            이동평균선 기간 (일)
    position_size_pct:    1회 매수 비율 (%)
    min_volume_threshold: 최소 거래량
    max_position_per_stock: 종목당 최대 비중 (%)

[ 커스텀 전략 만들기 ]
    이 파일을 참고하여 TradingStrategy를 상속받는 새 클래스 작성.
    generate_signal, calculate_position_size, should_buy, should_sell 구현.
"""

from typing import Any

import pandas as pd

from trading_system.core.trading_strategy import (
    PositionInfo,
    Signal,
    SignalType,
    TradingStrategy,
)


class MovingAverageStrategy(TradingStrategy):
    """이동평균선 기반 전략 구현체."""

    # config.yaml에서 오버라이드 가능한 기본값
    DEFAULT_PARAMS = {
        "total_seed": 10_000_000,        # 총 시드머니
        "ma_period": 20,                 # 이동평균선 기간 (일)
        "position_size_pct": 20.0,       # 1회 매수 비율 (%)
        "min_volume_threshold": 10_000,  # 최소 거래량
        "max_position_per_stock": 30.0,  # 종목당 최대 비중 (%)
    }

    def __init__(self, params: dict[str, Any] | None = None):
        # DEFAULT_PARAMS를 기본으로 하고, 전달된 params로 오버라이드
        merged = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__(name="ma_strategy", params=merged)

    @property
    def ma_period(self) -> int:
        return int(self.params["ma_period"])

    @property
    def position_size_pct(self) -> float:
        return float(self.params["position_size_pct"])

    @property
    def min_volume_threshold(self) -> int:
        return int(self.params["min_volume_threshold"])

    def calculate_ma(self, market_data: pd.DataFrame) -> float | None:
        """이동평균선 계산.

        Args:
            market_data: OHLCV 데이터

        Returns:
            이동평균선 값 또는 None (데이터 부족 시)
        """
        if len(market_data) < self.ma_period:
            return None

        # 최근 ma_period 일간의 종가 평균
        recent_closes = market_data["close"].tail(self.ma_period)
        ma_value = float(recent_closes.mean())
        return ma_value

    def generate_signal(
        self,
        market_data: pd.DataFrame,
        position_info: PositionInfo,
        available_cash: float,
    ) -> Signal:
        """매매 시그널 생성. 매도 우선 판단 후 매수 판단."""
        if market_data.empty or len(market_data) < self.ma_period:
            return Signal(
                signal_type=SignalType.HOLD,
                ticker=position_info.ticker,
                reason=f"데이터 부족 (최소 {self.ma_period}일 필요)"
            )

        current_price = float(market_data.iloc[-1]["close"])
        ticker = position_info.ticker

        # 이동평균선 계산
        ma_value = self.calculate_ma(market_data)
        if ma_value is None:
            return Signal(
                signal_type=SignalType.HOLD,
                ticker=ticker,
                reason="이동평균선 계산 실패"
            )

        # 매도를 먼저 체크 → 손실을 빠르게 방지하기 위해
        if position_info.quantity > 0:
            should_sell, sell_reason = self.should_sell(market_data, position_info, ma_value)
            if should_sell:
                return Signal(
                    signal_type=SignalType.SELL,
                    ticker=ticker,
                    price=current_price,
                    quantity=position_info.quantity,
                    reason=sell_reason,
                )

        # 매수 조건 체크
        should_buy, buy_reason = self.should_buy(market_data, position_info, available_cash, ma_value)
        if should_buy:
            qty = self.calculate_position_size(available_cash, Signal(
                signal_type=SignalType.BUY,
                ticker=ticker,
                price=current_price,
            ))
            if qty > 0:
                return Signal(
                    signal_type=SignalType.BUY,
                    ticker=ticker,
                    price=current_price,
                    quantity=qty,
                    reason=buy_reason,
                )

        return Signal(
            signal_type=SignalType.HOLD,
            ticker=ticker,
            reason=f"조건 미충족 (현재가: {current_price:,.0f}, MA{self.ma_period}: {ma_value:,.0f})"
        )

    def calculate_position_size(self, available_cash: float, signal: Signal) -> int:
        """1회 매수 수량 계산.

        position_size = total_seed * position_size_pct / 100
        실제 매수 금액 = min(position_size, 가용현금)
        수량 = 매수 금액 // 현재가
        """
        if signal.price <= 0:
            return 0

        position_size = float(self.params["total_seed"]) * self.position_size_pct / 100
        buy_amount = min(position_size, available_cash)
        quantity = int(buy_amount // signal.price)
        return quantity

    def should_buy(
        self,
        market_data: pd.DataFrame,
        position_info: PositionInfo,
        available_cash: float,
        ma_value: float,
    ) -> tuple[bool, str]:
        """매수 조건 판단.

        조건: 현재가 > 이동평균선
        """
        if len(market_data) < self.ma_period:
            return False, "데이터 부족"

        current_price = float(market_data.iloc[-1]["close"])
        current_volume = int(market_data.iloc[-1]["volume"])

        # 이미 보유 중이면 매수하지 않음 (단일 포지션 전략)
        if position_info.quantity > 0:
            return False, "이미 보유 중"

        # 가용 현금 체크
        position_size = float(self.params["total_seed"]) * self.position_size_pct / 100
        if available_cash < position_size * 0.5:  # 최소 절반은 있어야
            return False, "가용 현금 부족"

        # 거래량 조건
        if current_volume < self.min_volume_threshold:
            return False, f"거래량 부족 ({current_volume:,} < {self.min_volume_threshold:,})"

        # 가격이 이동평균선보다 높아야 매수
        if current_price <= ma_value:
            return False, f"가격이 MA 이하 (현재: {current_price:,.0f}, MA{self.ma_period}: {ma_value:,.0f})"

        price_diff_pct = (current_price - ma_value) / ma_value * 100
        return True, f"가격이 MA{self.ma_period} 돌파 (현재: {current_price:,.0f}, MA: {ma_value:,.0f}, +{price_diff_pct:.2f}%)"

    def should_sell(
        self,
        market_data: pd.DataFrame,
        position_info: PositionInfo,
        ma_value: float,
    ) -> tuple[bool, str]:
        """매도 조건 판단.

        조건: 현재가 < 이동평균선 (전량 매도)
        """
        if position_info.quantity <= 0 or position_info.avg_price <= 0:
            return False, "보유 수량 없음"

        current_price = float(market_data.iloc[-1]["close"])
        avg_price = position_info.avg_price

        profit_rate = (current_price - avg_price) / avg_price * 100

        # 가격이 이동평균선 아래로 떨어지면 전량 매도
        if current_price < ma_value:
            return True, f"가격이 MA{self.ma_period} 하회 (현재: {current_price:,.0f}, MA: {ma_value:,.0f}, 수익률: {profit_rate:.2f}%)"

        return False, f"홀딩 (현재가: {current_price:,.0f} > MA{self.ma_period}: {ma_value:,.0f}, 수익률: {profit_rate:.2f}%)"
