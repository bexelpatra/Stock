"""
가중치 기반 다중 자산 MA 전략 구현.

[ 역할 ]
    MACrossStrategy를 상속한 가중치 기반 다중 자산 전략.
    종목별 목표 비중(weights)에 따라 자산을 배분.

[ 전략 흐름 ]
    매일 generate_signal() 호출됨 (← backtest/engine.py에서, 종목별)
        ├── is_above_ma()로 현재가와 MA 비교
        ├── 가격 > MA → 목표 비중(total_seed × weight)만큼 매수 (이미 보유분 차감)
        └── 가격 < MA → 해당 자산 전량 매도
    weights에 없는 티커는 거래하지 않음

[ 파라미터 ]
    total_seed:           총 시드머니
    ma_period:            이동평균선 기간 (일)
    min_volume_threshold: 최소 거래량
    weights:              종목별 비중 dict (예: {"^GSPC": 0.6, "GLD": 0.4})
"""

from typing import Any

import pandas as pd

from trading_system.core.trading_strategy import (
    PositionInfo,
    Signal,
    SignalType,
)
from trading_system.strategies import register
from trading_system.strategies.ma_cross_strategy import MACrossStrategy


@register("weighted_ma")
class WeightedMAStrategy(MACrossStrategy):
    """가중치 기반 다중 자산 MA 전략."""

    DEFAULT_PARAMS = {
        **MACrossStrategy.DEFAULT_PARAMS,
        "weights": {},
    }

    def __init__(self, params: dict[str, Any] | None = None):
        merged = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__(params=merged)
        self.name = "weighted_ma"

    @property
    def weights(self) -> dict[str, float]:
        return dict(self.params.get("weights", {}))

    def generate_signal(
        self,
        market_data: pd.DataFrame,
        position_info: PositionInfo,
        available_cash: float,
    ) -> Signal:
        """가중치 기반 시그널 생성."""
        ticker = position_info.ticker

        # weights에 없는 티커는 거래하지 않음
        if ticker not in self.weights:
            return Signal(
                signal_type=SignalType.HOLD,
                ticker=ticker,
                reason=f"weights에 미포함 ({ticker})",
            )

        if market_data.empty or len(market_data) < self.ma_period:
            return Signal(
                signal_type=SignalType.HOLD,
                ticker=ticker,
                reason=f"데이터 부족 (최소 {self.ma_period}일 필요)",
            )

        current_price = float(market_data.iloc[-1]["close"])
        above, _, ma_value = self.is_above_ma(market_data)

        if ma_value is None:
            return Signal(
                signal_type=SignalType.HOLD,
                ticker=ticker,
                reason="MA 계산 불가",
            )

        weight = self.weights[ticker]

        # 가격 < MA → 전량 매도
        if not above and position_info.quantity > 0:
            profit_rate = (current_price - position_info.avg_price) / position_info.avg_price * 100 if position_info.avg_price > 0 else 0
            return Signal(
                signal_type=SignalType.SELL,
                ticker=ticker,
                price=current_price,
                quantity=position_info.quantity,
                reason=f"가격이 MA{self.ma_period} 하회 (현재: {current_price:,.0f}, MA: {ma_value:,.0f}, 비중: {weight:.0%}, 수익률: {profit_rate:.2f}%)",
            )

        # 가격 > MA → 목표 비중만큼 매수 (이미 보유분 차감)
        if above:
            total_seed = float(self.params["total_seed"])
            target_amount = total_seed * weight
            current_holding_value = position_info.quantity * current_price
            deficit = target_amount - current_holding_value

            if deficit > current_price:  # 최소 1주 이상 매수 가능해야
                buy_amount = min(deficit, available_cash)
                qty = int(buy_amount // current_price)
                if qty > 0:
                    return Signal(
                        signal_type=SignalType.BUY,
                        ticker=ticker,
                        price=current_price,
                        quantity=qty,
                        reason=f"목표 비중 매수 (MA{self.ma_period} 상회, 비중: {weight:.0%}, 목표: {target_amount:,.0f}, 현재: {current_holding_value:,.0f})",
                    )

        ma_str = f"{ma_value:,.0f}" if ma_value else "N/A"
        return Signal(
            signal_type=SignalType.HOLD,
            ticker=ticker,
            reason=f"조건 미충족 (현재가: {current_price:,.0f}, MA{self.ma_period}: {ma_str}, 비중: {weight:.0%})",
        )

    def calculate_position_size(self, available_cash: float, signal: Signal) -> int:
        """weighted_ma에서는 generate_signal 내에서 직접 수량을 계산하므로 fallback용."""
        if signal.price <= 0:
            return 0

        total_seed = float(self.params["total_seed"])
        # 전체 비중의 합으로 나눔 (기본적으로 전체 시드를 사용)
        buy_amount = min(total_seed, available_cash)
        return int(buy_amount // signal.price)
