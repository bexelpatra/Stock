"""
증권사 API 추상 클래스 정의.

[ 역할 ]
    증권사와의 통신을 추상화하는 인터페이스 정의.
    실제 증권사(한투, 키움 등) 교체 시 이 클래스만 구현하면 됨.

[ 구현체 ]
    - brokers/mock_broker.py::MockBroker  (테스트/백테스트용)
    - brokers/kis_broker.py              (한국투자증권 - 향후 구현)

[ 호출하는 곳 ]
    - backtest/engine.py에서 MockBroker 사용 (현재)
    - 실전 매매 시 실제 구현체 주입
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ─── 주문 관련 Enum / Dataclass ─────────────────────────────────────────────

class OrderType(Enum):
    """주문 타입: 시장가(MARKET) 또는 지정가(LIMIT)."""
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(Enum):
    """주문 상태 추적용."""
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class OrderResult:
    """buy_order(), sell_order()의 반환값. 주문 체결 결과를 담는다."""
    order_id: str
    ticker: str
    quantity: int          # 요청 수량
    price: float           # 요청 가격
    status: OrderStatus
    filled_quantity: int = 0   # 실제 체결 수량
    filled_price: float = 0.0  # 실제 체결 가격
    message: str = ""


@dataclass
class AccountInfo:
    """get_account_info()의 반환값."""
    account_id: str
    total_assets: float     # 총 자산 (현금 + 보유종목 평가)
    available_cash: float   # 주문 가능 현금
    total_profit: float     # 총 손익 금액
    profit_rate: float      # 총 수익률 (%)


@dataclass
class Holding:
    """get_holdings()에서 반환하는 개별 보유 종목 정보."""
    ticker: str
    name: str
    quantity: int
    avg_price: float        # 평균 매수가
    current_price: float    # 현재가
    profit: float           # 평가 손익
    profit_rate: float      # 수익률 (%)


# ─── 추상 클래스 ────────────────────────────────────────────────────────────

class BrokerAPI(ABC):
    """증권사 API 추상 클래스.

    모든 증권사 구현체는 이 클래스를 상속받아 아래 메서드를 구현해야 한다.
    """

    @abstractmethod
    def connect(self) -> bool:
        """API 연결."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """API 연결 해제."""
        ...

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        """계좌 정보 조회."""
        ...

    @abstractmethod
    def get_balance(self) -> float:
        """잔고(가용 현금) 조회."""
        ...

    @abstractmethod
    def get_holdings(self) -> list[Holding]:
        """보유 종목 조회."""
        ...

    @abstractmethod
    def buy_order(
        self,
        ticker: str,
        quantity: int,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.MARKET,
    ) -> OrderResult:
        """매수 주문.

        Args:
            ticker: 종목 코드
            quantity: 주문 수량
            price: 주문 가격 (지정가 주문 시)
            order_type: 주문 타입 (시장가/지정가)
        """
        ...

    @abstractmethod
    def sell_order(
        self,
        ticker: str,
        quantity: int,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.MARKET,
    ) -> OrderResult:
        """매도 주문.

        Args:
            ticker: 종목 코드
            quantity: 주문 수량
            price: 주문 가격 (지정가 주문 시)
            order_type: 주문 타입 (시장가/지정가)
        """
        ...

    @abstractmethod
    def get_current_price(self, ticker: str) -> float:
        """현재가 조회."""
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """주문 취소."""
        ...

    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderResult:
        """주문 상태 조회."""
        ...
