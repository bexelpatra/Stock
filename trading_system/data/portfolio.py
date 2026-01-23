"""
포트폴리오 관리 모듈.

[ 역할 ]
    현금, 보유 종목(Position), 거래 기록(TradeRecord)을 통합 관리.
    백테스트 엔진이 매수/매도 실행 시 이 클래스를 통해 상태를 갱신.

[ 주요 클래스 ]
    Position    - 개별 종목의 수량/평균가/매수횟수 추적
    TradeRecord - 개별 거래 내역 (매수/매도, 손익 포함)
    Portfolio   - 전체 포트폴리오 (현금 + 포지션들 + 거래내역)

[ 호출하는 곳 ]
    - backtest/engine.py::BacktestEngine._execute_buy/sell()에서
      portfolio.execute_buy/sell() 호출하여 상태 갱신
    - backtest/metrics.py에서 portfolio.trade_history로 성과 계산
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Position:
    """개별 종목 포지션. Portfolio 내부에서 종목별로 관리됨."""
    ticker: str
    quantity: int = 0           # 보유 수량
    avg_price: float = 0.0      # 평균 매수가 (매수 시마다 가중평균 갱신)
    buy_count: int = 0          # 현재까지 분할매수 횟수
    total_invested: float = 0.0  # 총 투입 금액

    @property
    def market_value(self) -> float:
        """현재 시장 가치 (현재가 기준 갱신 필요)."""
        return self.quantity * self.avg_price

    def update_on_buy(self, quantity: int, price: float) -> None:
        """매수 시 포지션 업데이트."""
        total_cost = self.avg_price * self.quantity + price * quantity
        self.quantity += quantity
        self.avg_price = total_cost / self.quantity if self.quantity > 0 else 0.0
        self.buy_count += 1
        self.total_invested += price * quantity

    def update_on_sell(self, quantity: int) -> float:
        """매도 시 포지션 업데이트. 실현 손익 반환."""
        if quantity > self.quantity:
            quantity = self.quantity
        self.quantity -= quantity
        if self.quantity == 0:
            self.avg_price = 0.0
            self.buy_count = 0
            self.total_invested = 0.0
        return 0.0  # 실현손익은 외부에서 계산

    def reset(self) -> None:
        """포지션 초기화."""
        self.quantity = 0
        self.avg_price = 0.0
        self.buy_count = 0
        self.total_invested = 0.0


@dataclass
class TradeRecord:
    """개별 거래 기록. metrics.py에서 승률/수익 계산에 사용됨."""
    date: str
    ticker: str
    side: str           # "buy" or "sell"
    quantity: int
    price: float        # 체결 가격 (슬리피지 적용 후)
    commission: float = 0.0
    tax: float = 0.0    # 매도세 (매도 시에만)
    profit: float = 0.0       # 실현 손익 (매도 시에만)
    profit_rate: float = 0.0  # 수익률 % (매도 시에만)
    reason: str = ""          # 시그널 사유 (로깅용)


class Portfolio:
    """포트폴리오 관리 클래스.

    BacktestEngine이 소유하며, 매수/매도 실행 결과를 반영.
    trade_history는 백테스트 종료 후 metrics 계산에 사용됨.
    """

    def __init__(self, initial_cash: float):
        self.initial_cash = initial_cash
        self.cash = initial_cash                    # 가용 현금
        self.positions: dict[str, Position] = {}    # ticker → Position
        self.trade_history: list[TradeRecord] = []  # 전체 거래 내역
        self._daily_loss: float = 0.0               # 당일 누적 손실 (리스크 관리용)
        self._last_trade_date: str = ""

    @property
    def total_invested(self) -> float:
        """총 투자 금액."""
        return sum(p.avg_price * p.quantity for p in self.positions.values())

    @property
    def total_assets(self) -> float:
        """총 자산 (현금 + 투자)."""
        return self.cash + self.total_invested

    @property
    def total_profit(self) -> float:
        """총 손익."""
        return self.total_assets - self.initial_cash

    @property
    def total_profit_rate(self) -> float:
        """총 수익률."""
        if self.initial_cash == 0:
            return 0.0
        return (self.total_assets - self.initial_cash) / self.initial_cash * 100

    def get_position(self, ticker: str) -> Position:
        """종목 포지션 조회. 없으면 빈 포지션 생성."""
        if ticker not in self.positions:
            self.positions[ticker] = Position(ticker=ticker)
        return self.positions[ticker]

    def execute_buy(
        self,
        ticker: str,
        quantity: int,
        price: float,
        commission: float = 0.0,
        date: str = "",
        reason: str = "",
    ) -> bool:
        """매수 실행."""
        total_cost = price * quantity + commission
        if total_cost > self.cash:
            return False

        self.cash -= total_cost
        position = self.get_position(ticker)
        position.update_on_buy(quantity, price)

        self.trade_history.append(TradeRecord(
            date=date,
            ticker=ticker,
            side="buy",
            quantity=quantity,
            price=price,
            commission=commission,
            reason=reason,
        ))
        return True

    def execute_sell(
        self,
        ticker: str,
        quantity: int,
        price: float,
        commission: float = 0.0,
        tax: float = 0.0,
        date: str = "",
        reason: str = "",
    ) -> bool:
        """매도 실행."""
        position = self.get_position(ticker)
        if position.quantity < quantity:
            return False

        avg_price = position.avg_price
        revenue = price * quantity - commission - tax
        self.cash += revenue

        profit = (price - avg_price) * quantity - commission - tax
        profit_rate = (price - avg_price) / avg_price * 100 if avg_price > 0 else 0.0

        position.update_on_sell(quantity)

        # 일일 손실 추적
        if date != self._last_trade_date:
            self._daily_loss = 0.0
            self._last_trade_date = date
        if profit < 0:
            self._daily_loss += abs(profit)

        self.trade_history.append(TradeRecord(
            date=date,
            ticker=ticker,
            side="sell",
            quantity=quantity,
            price=price,
            commission=commission,
            tax=tax,
            profit=profit,
            profit_rate=profit_rate,
            reason=reason,
        ))
        return True

    @property
    def daily_loss(self) -> float:
        """당일 손실 금액."""
        return self._daily_loss

    def get_holding_tickers(self) -> list[str]:
        """보유 종목 코드 목록."""
        return [t for t, p in self.positions.items() if p.quantity > 0]

    def get_summary(self) -> dict[str, Any]:
        """포트폴리오 요약."""
        return {
            "initial_cash": self.initial_cash,
            "current_cash": self.cash,
            "total_invested": self.total_invested,
            "total_assets": self.total_assets,
            "total_profit": self.total_profit,
            "total_profit_rate": self.total_profit_rate,
            "num_holdings": len(self.get_holding_tickers()),
            "num_trades": len(self.trade_history),
        }
