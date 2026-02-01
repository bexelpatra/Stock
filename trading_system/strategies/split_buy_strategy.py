"""
분할매수-목표수익 전략 구현.

[ 역할 ]
    core/trading_strategy.py::TradingStrategy의 구현체.
    "n일 전보다 떨어지면 분할 매수, 목표 수익률 도달 시 전량 매도" 전략.

[ 전략 흐름 ]
    매일 generate_signal() 호출됨 (← backtest/engine.py에서)
        ├── 보유 중이면 should_sell() 먼저 체크
        │     ├── 수익률 >= sell_profit_rate → SELL (익절)
        │     └── 수익률 <= -stop_loss_rate → SELL (손절)
        │
        └── should_buy() 체크
              ├── n일 전 종가 대비 buy_threshold% 이상 하락?
              ├── 거래량 >= min_volume_threshold?
              ├── 매수 횟수 < split_count?
              └── 모두 충족 시 → BUY (position_size만큼)

[ 파라미터 (config.yaml의 strategy 섹션에서 로드) ]
    total_seed:           총 시드머니 (분할 매수 기준 금액)
    split_count:          분할 매수 횟수 (position_size = total_seed / split_count)
    buy_threshold:        매수 기준 하락률 (%)
    lookback_days:        비교 기준 일수 (1~2일)
    sell_profit_rate:     목표 수익률 (%)
    stop_loss_rate:       손절 비율 (%)
    min_volume_threshold: 최소 거래량

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
from trading_system.strategies import register


@register("split_buy")
class SplitBuyStrategy(TradingStrategy):
    """분할매수-목표수익 전략 구현체."""

    # config.yaml에서 오버라이드 가능한 기본값
    DEFAULT_PARAMS = {
        "total_seed": 10_000_000,        # 총 시드머니
        "split_count": 5,                # 분할 매수 횟수
        "buy_threshold": 2.0,            # 매수 기준 하락률 (%)
        "lookback_days": 1,              # n일 전과 비교
        "sell_profit_rate": 3.0,         # 익절 목표 수익률 (%)
        "stop_loss_rate": 5.0,           # 손절 비율 (%)
        "max_position_per_stock": 30.0,  # 종목당 최대 비중 (%)
        "min_volume_threshold": 10_000,  # 최소 거래량
        "max_loss_per_day": 500_000,     # 일일 최대 손실 한도
    }

    def __init__(self, params: dict[str, Any] | None = None):
        # DEFAULT_PARAMS를 기본으로 하고, 전달된 params로 오버라이드
        merged = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__(name="split_buy", params=merged)

    @property
    def split_count(self) -> int:
        return int(self.params["split_count"])

    @property
    def buy_threshold(self) -> float:
        return float(self.params["buy_threshold"])

    @property
    def lookback_days(self) -> int:
        return int(self.params["lookback_days"])

    @property
    def sell_profit_rate(self) -> float:
        return float(self.params["sell_profit_rate"])

    @property
    def stop_loss_rate(self) -> float:
        return float(self.params["stop_loss_rate"])

    @property
    def min_volume_threshold(self) -> int:
        return int(self.params["min_volume_threshold"])

    @property
    def max_loss_per_day(self) -> float:
        return float(self.params["max_loss_per_day"])

    def generate_signal(
        self,
        market_data: pd.DataFrame,
        position_info: PositionInfo,
        available_cash: float,
    ) -> Signal:
        """매매 시그널 생성. 매도 우선 판단 후 매수 판단."""
        if market_data.empty or len(market_data) < self.lookback_days + 1:
            return Signal(signal_type=SignalType.HOLD, ticker=position_info.ticker, reason="데이터 부족")

        current_price = float(market_data.iloc[-1]["close"])
        ticker = position_info.ticker

        # 매도를 먼저 체크 → 익절/손절 기회를 놓치지 않기 위해
        if position_info.quantity > 0:
            should_sell, sell_reason = self.should_sell(market_data, position_info)
            if should_sell:
                return Signal(
                    signal_type=SignalType.SELL,
                    ticker=ticker,
                    price=current_price,
                    quantity=position_info.quantity,
                    reason=sell_reason,
                )

        # 매수 조건 체크
        should_buy, buy_reason = self.should_buy(market_data, position_info, available_cash)
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

        return Signal(signal_type=SignalType.HOLD, ticker=ticker, reason="조건 미충족")

    def calculate_position_size(self, available_cash: float, signal: Signal) -> int:
        """1회 매수 수량 계산.

        position_size = total_seed / split_count
        실제 매수 금액 = min(position_size, 가용현금)
        수량 = 매수 금액 // 현재가
        """
        if signal.price <= 0:
            return 0

        position_size = float(self.params["total_seed"]) / self.split_count
        buy_amount = min(position_size, available_cash)
        quantity = int(buy_amount // signal.price)
        return quantity

    def should_buy(
        self,
        market_data: pd.DataFrame,
        position_info: PositionInfo,
        available_cash: float,
    ) -> tuple[bool, str]:
        """매수 조건 판단."""
        if len(market_data) < self.lookback_days + 1:
            return False, "데이터 부족"

        current_price = float(market_data.iloc[-1]["close"])
        current_volume = int(market_data.iloc[-1]["volume"])
        n_days_ago_close = float(market_data.iloc[-(self.lookback_days + 1)]["close"])

        # 매수 가능 횟수 체크
        if position_info.buy_count >= self.split_count:
            return False, f"최대 매수 횟수({self.split_count}) 도달"

        # 가용 현금 체크
        position_size = float(self.params["total_seed"]) / self.split_count
        if available_cash < position_size * 0.5:  # 최소 절반은 있어야
            return False, "가용 현금 부족"

        # 거래량 조건
        if current_volume < self.min_volume_threshold:
            return False, f"거래량 부족 ({current_volume} < {self.min_volume_threshold})"

        # 가격 하락 조건: n일 전 종가 대비 buy_threshold% 초과 하락
        # buy_threshold=0이면 조금이라도 떨어지면 매수 (같으면 안 사고, 떨어져야 삼)
        if n_days_ago_close <= 0:
            return False, "기준가 오류"

        drop_rate = (n_days_ago_close - current_price) / n_days_ago_close * 100
        if drop_rate <= self.buy_threshold:  # < 에서 <= 로 변경 (가격이 떨어져야만 매수)
            return False, f"하락률 부족 ({drop_rate:.2f}% <= {self.buy_threshold}%)"

        return True, f"{self.lookback_days}일 전 대비 {drop_rate:.2f}% 하락"

    def should_sell(
        self,
        market_data: pd.DataFrame,
        position_info: PositionInfo,
    ) -> tuple[bool, str]:
        """매도 조건 판단."""
        if position_info.quantity <= 0 or position_info.avg_price <= 0:
            return False, "보유 수량 없음"

        current_price = float(market_data.iloc[-1]["close"])
        avg_price = position_info.avg_price

        profit_rate = (current_price - avg_price) / avg_price * 100

        # 목표 수익률 도달 → 매도
        if profit_rate >= self.sell_profit_rate:
            return True, f"목표 수익률 도달 ({profit_rate:.2f}% >= {self.sell_profit_rate}%)"

        # 손절 조건 (손절률이 설정되어 있을 때만)
        if self.stop_loss_rate > 0 and profit_rate <= -self.stop_loss_rate:
            return True, f"손절 ({profit_rate:.2f}% <= -{self.stop_loss_rate}%)"

        return False, f"현재 수익률: {profit_rate:.2f}%"
