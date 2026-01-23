"""
테스트/백테스트용 Mock 브로커 및 데이터 제공자 구현.

[ 역할 ]
    실제 증권사 API 없이 매매를 시뮬레이션.
    수수료, 세금, 슬리피지를 적용하여 현실적인 체결을 모사.

[ 포함 클래스 ]
    MockDataProvider - core/data_provider.py::DataProvider 구현체
                       미리 로드된 DataFrame에서 OHLCV 데이터 제공

    MockBroker       - core/broker_api.py::BrokerAPI 구현체
                       가상 잔고로 매수/매도 시뮬레이션

[ 호출하는 곳 ]
    - backtest/engine.py에서는 MockBroker를 직접 사용하지 않고
      Portfolio를 통해 매매를 실행 (동일한 수수료/슬리피지 로직 적용)
    - 단위 테스트에서 MockBroker/MockDataProvider 활용

[ 실전 교체 ]
    실제 증권사 연동 시 이 파일 대신 kis_broker.py 등을 사용
"""

import uuid
from datetime import date
from typing import Optional

import pandas as pd

from trading_system.core.broker_api import (
    AccountInfo,
    BrokerAPI,
    Holding,
    OrderResult,
    OrderStatus,
    OrderType,
)
from trading_system.core.data_provider import DataProvider, OHLCV


# ─── Mock 데이터 제공자 ──────────────────────────────────────────────────────

class MockDataProvider(DataProvider):
    """DataFrame 기반 Mock 데이터 제공자.

    사용법:
        provider = MockDataProvider()
        provider.load_data("005930", samsung_df)  # DataFrame 로드
        provider.set_current_date(date(2024, 6, 1))  # 시뮬레이션 날짜 설정
        ohlcv = provider.get_current_ohlcv("005930")
    """

    def __init__(self):
        self._data: dict[str, pd.DataFrame] = {}  # ticker → OHLCV DataFrame
        self._current_date: Optional[date] = None  # 시뮬레이션 현재일

    def load_data(self, ticker: str, df: pd.DataFrame) -> None:
        """데이터 로드.

        Args:
            ticker: 종목 코드
            df: OHLCV DataFrame (columns: date, open, high, low, close, volume)
        """
        df = df.copy()
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.date
        self._data[ticker] = df.sort_values("date").reset_index(drop=True)

    def set_current_date(self, current_date: date) -> None:
        """현재 날짜 설정 (백테스트 시뮬레이션용)."""
        self._current_date = current_date

    def get_ohlcv(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """OHLCV 데이터 조회."""
        if ticker not in self._data:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        df = self._data[ticker]
        mask = (df["date"] >= start_date) & (df["date"] <= end_date)
        return df[mask].copy().reset_index(drop=True)

    def get_current_ohlcv(self, ticker: str) -> OHLCV:
        """당일 OHLCV 조회."""
        if ticker not in self._data or self._current_date is None:
            raise ValueError(f"No data for {ticker} on {self._current_date}")

        df = self._data[ticker]
        row = df[df["date"] == self._current_date]
        if row.empty:
            raise ValueError(f"No data for {ticker} on {self._current_date}")

        r = row.iloc[0]
        return OHLCV(
            date=r["date"],
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=int(r["volume"]),
        )

    def get_tickers(self) -> list[str]:
        """로드된 종목 목록."""
        return list(self._data.keys())


# ─── Mock 브로커 ─────────────────────────────────────────────────────────────

class MockBroker(BrokerAPI):
    """Mock 브로커. 실제 주문 없이 가상 잔고로 매매 시뮬레이션.

    매수 시: 가격 * (1 + slippage) 로 불리하게 체결
    매도 시: 가격 * (1 - slippage) 로 불리하게 체결
    수수료: 체결금액 * commission_rate (매수/매도 모두)
    세금:   체결금액 * tax_rate (매도 시에만)
    """

    def __init__(
        self,
        initial_cash: float = 10_000_000,
        commission_rate: float = 0.00015,  # 0.015%
        tax_rate: float = 0.0023,          # 0.23% (매도세)
        slippage_rate: float = 0.001,      # 0.1%
    ):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.commission_rate = commission_rate
        self.tax_rate = tax_rate
        self.slippage_rate = slippage_rate

        self._holdings: dict[str, Holding] = {}       # ticker → Holding
        self._orders: dict[str, OrderResult] = {}     # order_id → OrderResult
        self._prices: dict[str, float] = {}           # ticker → 현재가 (set_price로 설정)
        self._connected = False

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def set_price(self, ticker: str, price: float) -> None:
        """종목 현재가 설정 (시뮬레이션용)."""
        self._prices[ticker] = price

    def get_account_info(self) -> AccountInfo:
        total_holdings_value = sum(
            h.current_price * h.quantity for h in self._holdings.values()
        )
        total_assets = self.cash + total_holdings_value
        total_profit = total_assets - self.initial_cash
        profit_rate = total_profit / self.initial_cash * 100 if self.initial_cash > 0 else 0.0

        return AccountInfo(
            account_id="MOCK_ACCOUNT",
            total_assets=total_assets,
            available_cash=self.cash,
            total_profit=total_profit,
            profit_rate=profit_rate,
        )

    def get_balance(self) -> float:
        return self.cash

    def get_holdings(self) -> list[Holding]:
        return list(self._holdings.values())

    def buy_order(
        self,
        ticker: str,
        quantity: int,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.MARKET,
    ) -> OrderResult:
        order_id = str(uuid.uuid4())[:8]

        if price is None:
            price = self._prices.get(ticker, 0.0)

        # 슬리피지 적용 (매수 시 가격 상승)
        exec_price = price * (1 + self.slippage_rate)
        commission = exec_price * quantity * self.commission_rate
        total_cost = exec_price * quantity + commission

        if total_cost > self.cash:
            return OrderResult(
                order_id=order_id,
                ticker=ticker,
                quantity=quantity,
                price=price,
                status=OrderStatus.FAILED,
                message="Insufficient cash",
            )

        self.cash -= total_cost

        # 보유 종목 업데이트
        if ticker in self._holdings:
            h = self._holdings[ticker]
            total_qty = h.quantity + quantity
            avg_price = (h.avg_price * h.quantity + exec_price * quantity) / total_qty
            h.quantity = total_qty
            h.avg_price = avg_price
        else:
            self._holdings[ticker] = Holding(
                ticker=ticker,
                name=ticker,
                quantity=quantity,
                avg_price=exec_price,
                current_price=exec_price,
                profit=0.0,
                profit_rate=0.0,
            )

        result = OrderResult(
            order_id=order_id,
            ticker=ticker,
            quantity=quantity,
            price=price,
            status=OrderStatus.FILLED,
            filled_quantity=quantity,
            filled_price=exec_price,
        )
        self._orders[order_id] = result
        return result

    def sell_order(
        self,
        ticker: str,
        quantity: int,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.MARKET,
    ) -> OrderResult:
        order_id = str(uuid.uuid4())[:8]

        if ticker not in self._holdings or self._holdings[ticker].quantity < quantity:
            return OrderResult(
                order_id=order_id,
                ticker=ticker,
                quantity=quantity,
                price=price or 0.0,
                status=OrderStatus.FAILED,
                message="Insufficient holdings",
            )

        if price is None:
            price = self._prices.get(ticker, 0.0)

        # 슬리피지 적용 (매도 시 가격 하락)
        exec_price = price * (1 - self.slippage_rate)
        commission = exec_price * quantity * self.commission_rate
        tax = exec_price * quantity * self.tax_rate
        revenue = exec_price * quantity - commission - tax

        self.cash += revenue

        h = self._holdings[ticker]
        h.quantity -= quantity
        if h.quantity == 0:
            del self._holdings[ticker]

        result = OrderResult(
            order_id=order_id,
            ticker=ticker,
            quantity=quantity,
            price=price,
            status=OrderStatus.FILLED,
            filled_quantity=quantity,
            filled_price=exec_price,
        )
        self._orders[order_id] = result
        return result

    def get_current_price(self, ticker: str) -> float:
        return self._prices.get(ticker, 0.0)

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self._orders:
            self._orders[order_id].status = OrderStatus.CANCELLED
            return True
        return False

    def get_order_status(self, order_id: str) -> OrderResult:
        if order_id not in self._orders:
            return OrderResult(
                order_id=order_id,
                ticker="",
                quantity=0,
                price=0.0,
                status=OrderStatus.FAILED,
                message="Order not found",
            )
        return self._orders[order_id]
