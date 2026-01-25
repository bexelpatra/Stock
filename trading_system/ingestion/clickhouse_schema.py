"""
ClickHouse 데이터베이스 스키마 정의 및 연결 관리
"""
from typing import Optional, Tuple
from datetime import date, datetime
import clickhouse_connect
from clickhouse_connect.driver import Client


def get_client(
    host: str = "localhost",
    port: int = 8123,
    database: str = "default",
    user: str = "default",
    password: str = "password",
) -> Client:
    """
    ClickHouse 클라이언트 연결 생성

    Args:
        host: ClickHouse 호스트
        port: HTTP 포트 (기본값: 8123)
        database: 데이터베이스 이름
        user: 사용자 이름
        password: 비밀번호

    Returns:
        ClickHouse 클라이언트 객체
    """
    client = clickhouse_connect.get_client(
        host=host,
        port=port,
        database=database,
        username=user,
        password=password,
    )
    return client


def initialize_schema(client: Client) -> None:
    """
    필요한 테이블 생성 (이미 존재하면 무시)

    Args:
        client: ClickHouse 클라이언트
    """
    # stock_ohlcv 테이블 생성 (메인 데이터)
    create_ohlcv_table = """
    CREATE TABLE IF NOT EXISTS stock_ohlcv (
        ticker String,
        date Date,
        open Float64,
        high Float64,
        low Float64,
        close Float64,
        adjusted_close Float64,
        volume UInt64,
        source String DEFAULT 'yahoo',
        ingestion_time DateTime DEFAULT now()
    )
    ENGINE = MergeTree()
    PARTITION BY toYYYYMM(date)
    ORDER BY (ticker, date)
    SETTINGS index_granularity = 8192
    """

    # ingestion_log 테이블 생성 (메타데이터)
    create_log_table = """
    CREATE TABLE IF NOT EXISTS ingestion_log (
        ticker String,
        last_date Date,
        last_ingestion DateTime,
        record_count UInt32,
        status String
    )
    ENGINE = ReplacingMergeTree(last_ingestion)
    ORDER BY ticker
    """

    client.command(create_ohlcv_table)
    client.command(create_log_table)
    print("테이블 생성 완료 (또는 이미 존재)")


def verify_connection(client: Client) -> bool:
    """
    ClickHouse 연결 검증

    Args:
        client: ClickHouse 클라이언트

    Returns:
        연결 성공 시 True
    """
    try:
        result = client.command("SELECT 1")
        return result == 1
    except Exception as e:
        print(f"연결 실패: {e}")
        return False


def get_tickers(client: Client) -> list[str]:
    """
    저장된 모든 티커 목록 조회

    Args:
        client: ClickHouse 클라이언트

    Returns:
        티커 리스트
    """
    query = "SELECT DISTINCT ticker FROM stock_ohlcv ORDER BY ticker"
    result = client.query(query)
    return [row[0] for row in result.result_rows]


def get_date_range(client: Client, ticker: str) -> Optional[Tuple[date, date]]:
    """
    특정 티커의 날짜 범위 조회

    Args:
        client: ClickHouse 클라이언트
        ticker: 티커 심볼

    Returns:
        (최소 날짜, 최대 날짜) 튜플, 데이터가 없으면 None
    """
    query = """
        SELECT MIN(date) as min_date, MAX(date) as max_date
        FROM stock_ohlcv
        WHERE ticker = %(ticker)s
    """
    result = client.query(query, parameters={"ticker": ticker})

    if result.result_rows:
        min_date, max_date = result.result_rows[0]
        if min_date and max_date:
            return (min_date, max_date)

    return None


def get_record_count(client: Client, ticker: Optional[str] = None) -> int:
    """
    레코드 수 조회

    Args:
        client: ClickHouse 클라이언트
        ticker: 특정 티커 (None이면 전체)

    Returns:
        레코드 수
    """
    if ticker:
        query = "SELECT COUNT(*) FROM stock_ohlcv WHERE ticker = %(ticker)s"
        result = client.query(query, parameters={"ticker": ticker})
    else:
        query = "SELECT COUNT(*) FROM stock_ohlcv"
        result = client.query(query)

    return result.result_rows[0][0] if result.result_rows else 0


def get_last_ingestion_date(client: Client, ticker: str) -> Optional[date]:
    """
    특정 티커의 마지막 수집 날짜 조회 (ingestion_log에서)

    Args:
        client: ClickHouse 클라이언트
        ticker: 티커 심볼

    Returns:
        마지막 수집 날짜, 없으면 None
    """
    query = """
        SELECT last_date
        FROM ingestion_log
        WHERE ticker = %(ticker)s
        ORDER BY last_ingestion DESC
        LIMIT 1
    """
    result = client.query(query, parameters={"ticker": ticker})

    if result.result_rows:
        return result.result_rows[0][0]

    return None
