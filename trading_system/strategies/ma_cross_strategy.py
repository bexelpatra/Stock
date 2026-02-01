"""
이동평균 교차(MA Cross) 전략 구현.

[ 역할 ]
    core/trading_strategy.py::TradingStrategy의 구현체.
    "가격이 이동평균선 위로 올라가면 매수, 아래로 내려가면 전량 매도"
    ma_strategy.py와 유사하나, weighted_ma_strategy의 베이스 클래스 역할.

[ 전략 흐름 ]
    매일 generate_signal() 호출됨 (← backtest/engine.py에서)
        ├── is_above_ma()로 현재가와 MA 비교
        ├── 보유 중이면 should_sell() 먼저 체크
        │     └── 현재가 < MA → SELL (전량 매도)
        └── should_buy() 체크
              └── 미보유 + 현재가 > MA → BUY

[ 파라미터 (config.yaml의 strategy 섹션에서 로드) ]
    total_seed:           총 시드머니
    ma_period:            이동평균선 기간 (일)
    position_size_pct:    1회 매수 비율 (%)
    min_volume_threshold: 최소 거래량
"""

from typing import Any

import pandas as pd

from trading_system.core.trading_strategy import (
    PositionInfo,
    Signal,
    SignalType,
    TradingStrategy,
)
from trading_system.strategies import register


@register("ma_cross")
class MACrossStrategy(TradingStrategy):
    """이동평균 교차 전략 구현체."""

    DEFAULT_PARAMS = {
        "total_seed": 10_000_000,
        "ma_period": 120,
        "position_size_pct": 100.0,
        "min_volume_threshold": 0,
    }

    def __init__(self, params: dict[str, Any] | None = None):
        merged = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__(name="ma_cross", params=merged)

    @property
    def ma_period(self) -> int:
        return int(self.params["ma_period"])

    @property
    def position_size_pct(self) -> float:
        return float(self.params["position_size_pct"])

    @property
    def min_volume_threshold(self) -> int:
        return int(self.params["min_volume_threshold"])

    def is_above_ma(self, market_data: pd.DataFrame) -> tuple[bool, float, float | None]:
        """현재가가 이동평균선 위에 있는지 판단.

        Returns:
            (가격 > MA 여부, 현재가, MA값 또는 None)
        """
        if market_data.empty:
            return False, 0.0, None

        current_price = float(market_data.iloc[-1]["close"])

        if len(market_data) < self.ma_period:
            return False, current_price, None

        ma_value = float(market_data["close"].tail(self.ma_period).mean())
        return current_price > ma_value, current_price, ma_value

    def should_buy(
        self,
        market_data: pd.DataFrame,
        position_info: PositionInfo,
        available_cash: float,
    ) -> tuple[bool, str]:
        """매수 조건: 미보유 + 가격 > MA."""
        above, current_price, ma_value = self.is_above_ma(market_data)

        if ma_value is None:
            return False, f"데이터 부족 (최소 {self.ma_period}일 필요)"

        if position_info.quantity > 0:
            return False, "이미 보유 중"

        if not above:
            return False, f"가격이 MA 이하 (현재: {current_price:,.0f}, MA{self.ma_period}: {ma_value:,.0f})"

        if self.min_volume_threshold > 0:
            current_volume = int(market_data.iloc[-1]["volume"])
            if current_volume < self.min_volume_threshold:
                return False, f"거래량 부족 ({current_volume:,} < {self.min_volume_threshold:,})"

        diff_pct = (current_price - ma_value) / ma_value * 100
        return True, f"가격이 MA{self.ma_period} 돌파 (현재: {current_price:,.0f}, MA: {ma_value:,.0f}, +{diff_pct:.2f}%)"

    def should_sell(
        self,
        market_data: pd.DataFrame,
        position_info: PositionInfo,
    ) -> tuple[bool, str]:
        """매도 조건: 보유 중 + 가격 < MA → 전량 매도."""
        if position_info.quantity <= 0:
            return False, "보유 수량 없음"

        above, current_price, ma_value = self.is_above_ma(market_data)

        if ma_value is None:
            return False, "MA 계산 불가"

        if not above:
            profit_rate = (current_price - position_info.avg_price) / position_info.avg_price * 100 if position_info.avg_price > 0 else 0
            return True, f"가격이 MA{self.ma_period} 하회 (현재: {current_price:,.0f}, MA: {ma_value:,.0f}, 수익률: {profit_rate:.2f}%)"

        return False, f"홀딩 (현재가: {current_price:,.0f} > MA{self.ma_period}: {ma_value:,.0f})"

    def generate_signal(
        self,
        market_data: pd.DataFrame,
        position_info: PositionInfo,
        available_cash: float,
    ) -> Signal:
        """매매 시그널 생성. 매도 우선 판단 후 매수 판단."""
        ticker = position_info.ticker

        if market_data.empty or len(market_data) < self.ma_period:
            return Signal(
                signal_type=SignalType.HOLD,
                ticker=ticker,
                reason=f"데이터 부족 (최소 {self.ma_period}일 필요)",
            )

        current_price = float(market_data.iloc[-1]["close"])

        # 매도 우선
        if position_info.quantity > 0:
            sell, reason = self.should_sell(market_data, position_info)
            if sell:
                return Signal(
                    signal_type=SignalType.SELL,
                    ticker=ticker,
                    price=current_price,
                    quantity=position_info.quantity,
                    reason=reason,
                )

        # 매수
        buy, reason = self.should_buy(market_data, position_info, available_cash)
        if buy:
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
                    reason=reason,
                )

        _, _, ma_value = self.is_above_ma(market_data)
        ma_str = f"{ma_value:,.0f}" if ma_value else "N/A"
        return Signal(
            signal_type=SignalType.HOLD,
            ticker=ticker,
            reason=f"조건 미충족 (현재가: {current_price:,.0f}, MA{self.ma_period}: {ma_str})",
        )

    def calculate_position_size(self, available_cash: float, signal: Signal) -> int:
        """매수 수량 계산: total_seed * position_size_pct / 100."""
        if signal.price <= 0:
            return 0

        position_size = float(self.params["total_seed"]) * self.position_size_pct / 100
        buy_amount = min(position_size, available_cash)
        return int(buy_amount // signal.price)
