"""
=============================================================================
주식 자동매매 시스템 (Trading System)
=============================================================================

[ 시스템 전체 구조 ]

    run_backtest.py (진입점)
         │
         ├── utils/config.py        ← config.yaml 설정 로드
         ├── utils/logger.py        ← 로깅
         │
         ├── strategies/            ← 매매 전략 (시그널 생성)
         │     └── split_buy_strategy.py
         │
         └── backtest/engine.py     ← 백테스트 실행 엔진
               │
               ├── data/portfolio.py    ← 포지션/거래기록 관리
               └── backtest/metrics.py  ← 성과 지표 계산


[ 핵심 추상 클래스 (core/) - 모든 구현체의 부모 ]

    core/broker_api.py       → brokers/mock_broker.py (테스트용 구현)
                             → brokers/kis_broker.py  (실제 증권사 연동 시 구현)

    core/data_provider.py    → brokers/mock_broker.py::MockDataProvider (테스트용)

    core/trading_strategy.py → strategies/split_buy_strategy.py (분할매수 전략)


[ 데이터 흐름 ]

    1. config.yaml에서 전략 파라미터 로드
    2. DataProvider가 OHLCV 데이터 제공
    3. TradingStrategy가 데이터 + 포지션 정보로 시그널(매수/매도/홀드) 생성
    4. BacktestEngine이 시그널에 따라 Portfolio에 매수/매도 실행
    5. metrics.py가 거래 결과로 성과 지표 계산


[ 실전 매매 시 흐름 (향후 구현) ]

    1. BrokerAPI 실제 구현체로 증권사 연결
    2. DataProvider로 실시간 데이터 수신
    3. 스케줄러가 주기적으로 전략의 generate_signal() 호출
    4. 시그널 발생 시 BrokerAPI로 실제 주문 실행
"""
