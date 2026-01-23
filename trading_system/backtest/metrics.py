"""
백테스트 성과 지표 계산 모듈.

[ 역할 ]
    백테스트 결과(거래기록 + 일별 자산가치)를 받아 성과 지표를 계산.
    calculate_metrics() 함수가 핵심.

[ 계산하는 지표 ]
    - 총 수익률 / 연환산 수익률
    - 샤프 비율 (위험 대비 수익)
    - MDD (최대 낙폭)
    - 승률, 평균 수익/손실, 수익 팩터
    - 연속 승/패

[ 호출하는 곳 ]
    - backtest/engine.py::BacktestEngine.run_backtest() 완료 시 호출

[ 입력 데이터 ]
    - trade_history: data/portfolio.py::Portfolio.trade_history (매도 거래만 분석)
    - daily_values: engine.py에서 매일 기록한 총 자산 리스트
"""

from dataclasses import dataclass
from typing import Any

import numpy as np

from trading_system.data.portfolio import TradeRecord


@dataclass
class BacktestMetrics:
    """백테스트 성과 지표. summary()로 포맷된 리포트 출력 가능."""
    total_return: float = 0.0         # 총 수익률 (%)
    annual_return: float = 0.0        # 연환산 수익률 (%)
    sharpe_ratio: float = 0.0         # 샤프 비율 (높을수록 좋음, 1 이상 양호)
    max_drawdown: float = 0.0         # 최대 낙폭 MDD (%)
    win_rate: float = 0.0             # 승률 (%)
    avg_profit: float = 0.0           # 수익 거래 평균 이익 (원)
    avg_loss: float = 0.0             # 손실 거래 평균 손실 (원)
    profit_factor: float = 0.0        # 총이익 / 총손실 (1 이상이면 수익)
    total_trades: int = 0             # 매도 거래 횟수
    winning_trades: int = 0           # 수익 거래 수
    losing_trades: int = 0            # 손실 거래 수
    avg_holding_days: float = 0.0     # 평균 보유 기간
    max_consecutive_wins: int = 0     # 최대 연속 수익
    max_consecutive_losses: int = 0   # 최대 연속 손실

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환."""
        from dataclasses import asdict
        return asdict(self)

    def summary(self) -> str:
        """성과 요약 문자열."""
        lines = [
            "=" * 50,
            "백테스트 성과 리포트",
            "=" * 50,
            f"총 수익률:       {self.total_return:>10.2f}%",
            f"연환산 수익률:    {self.annual_return:>10.2f}%",
            f"샤프 비율:       {self.sharpe_ratio:>10.2f}",
            f"최대 낙폭(MDD):  {self.max_drawdown:>10.2f}%",
            "-" * 50,
            f"총 거래 횟수:    {self.total_trades:>10d}",
            f"승률:            {self.win_rate:>10.2f}%",
            f"수익 거래:       {self.winning_trades:>10d}",
            f"손실 거래:       {self.losing_trades:>10d}",
            f"평균 수익:       {self.avg_profit:>10,.0f}원",
            f"평균 손실:       {self.avg_loss:>10,.0f}원",
            f"수익 팩터:       {self.profit_factor:>10.2f}",
            "-" * 50,
            f"최대 연속 수익:  {self.max_consecutive_wins:>10d}",
            f"최대 연속 손실:  {self.max_consecutive_losses:>10d}",
            "=" * 50,
        ]
        return "\n".join(lines)


def calculate_metrics(
    trade_history: list[TradeRecord],
    daily_values: list[float],
    initial_cash: float,
    trading_days: int,
) -> BacktestMetrics:
    """성과 지표 계산. engine.py에서 백테스트 완료 후 호출됨.

    Args:
        trade_history: Portfolio.trade_history (매수+매도 전체)
        daily_values: 일별 총 자산 리스트 (현금 + 보유종목 평가)
        initial_cash: 초기 자금
        trading_days: 백테스트 기간 중 총 거래일 수
    """
    metrics = BacktestMetrics()

    if not daily_values:
        return metrics

    # ─── 수익률 계산 ─────────────────────────────────────────────────────
    final_value = daily_values[-1]
    metrics.total_return = (final_value - initial_cash) / initial_cash * 100

    # 연환산: (최종/초기)^(1/년수) - 1
    if trading_days > 0:
        years = trading_days / 252  # 한국 기준 연간 약 252 거래일
        if years > 0:
            total_ratio = final_value / initial_cash
            metrics.annual_return = (total_ratio ** (1 / years) - 1) * 100

    # ─── 샤프 비율 ────────────────────────────────────────────────────────
    # 일별 수익률로 계산. 샤프 = (평균 초과수익 / 표준편차) * sqrt(252)
    daily_returns = []
    for i in range(1, len(daily_values)):
        if daily_values[i - 1] > 0:
            ret = (daily_values[i] - daily_values[i - 1]) / daily_values[i - 1]
            daily_returns.append(ret)

    if daily_returns:
        returns_arr = np.array(daily_returns)
        risk_free_daily = 0.03 / 252
        excess_returns = returns_arr - risk_free_daily
        if np.std(excess_returns) > 0:
            metrics.sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)

    # ─── MDD (Maximum Drawdown) ────────────────────────────────────────────
    # 고점 대비 최대 하락폭. 낮을수록 좋음.
    if daily_values:
        peak = daily_values[0]
        max_dd = 0.0
        for value in daily_values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100
            if dd > max_dd:
                max_dd = dd
        metrics.max_drawdown = max_dd

    # ─── 거래 기반 지표 (매도 거래만 분석) ─────────────────────────────────
    # 매수는 비용 발생일 뿐, 수익 실현은 매도 시에만 발생
    sell_trades = [t for t in trade_history if t.side == "sell"]
    metrics.total_trades = len(sell_trades)

    if sell_trades:
        profits = [t.profit for t in sell_trades]
        winners = [p for p in profits if p > 0]
        losers = [p for p in profits if p <= 0]

        metrics.winning_trades = len(winners)
        metrics.losing_trades = len(losers)
        metrics.win_rate = len(winners) / len(sell_trades) * 100

        if winners:
            metrics.avg_profit = sum(winners) / len(winners)
        if losers:
            metrics.avg_loss = sum(losers) / len(losers)

        total_profit = sum(winners) if winners else 0
        total_loss = abs(sum(losers)) if losers else 0
        metrics.profit_factor = total_profit / total_loss if total_loss > 0 else float("inf")

        # 연속 승패
        consecutive_wins = 0
        consecutive_losses = 0
        max_wins = 0
        max_losses = 0
        for p in profits:
            if p > 0:
                consecutive_wins += 1
                consecutive_losses = 0
                max_wins = max(max_wins, consecutive_wins)
            else:
                consecutive_losses += 1
                consecutive_wins = 0
                max_losses = max(max_losses, consecutive_losses)
        metrics.max_consecutive_wins = max_wins
        metrics.max_consecutive_losses = max_losses

    return metrics
