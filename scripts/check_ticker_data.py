#!/usr/bin/env python3
"""
Validate whether requested tickers have data in ClickHouse.

This script provides comprehensive pre-flight checks before running backtests
or other operations that require ticker data.
"""
import argparse
import sys
from pathlib import Path
from datetime import date, datetime
from typing import List, Dict, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from trading_system.ingestion.clickhouse_schema import get_client, get_date_range
import yaml


class TickerDataChecker:
    """Check if ticker data exists and is valid"""

    def __init__(self, client):
        self.client = client

    def get_available_tickers(self) -> List[str]:
        """Get list of all tickers with data in ClickHouse"""
        query = "SELECT DISTINCT ticker FROM stock_ohlcv ORDER BY ticker"
        result = self.client.query(query)
        return [row[0] for row in result.result_rows]

    def check_ticker_exists(self, ticker: str) -> bool:
        """Check if ticker has any data"""
        query = "SELECT COUNT(*) FROM stock_ohlcv WHERE ticker = %(ticker)s"
        result = self.client.query(query, parameters={"ticker": ticker})
        count = result.result_rows[0][0]
        return count > 0

    def get_ticker_info(self, ticker: str) -> Dict:
        """Get detailed information about ticker data"""
        query = """
            SELECT
                COUNT(*) as record_count,
                MIN(date) as first_date,
                MAX(date) as last_date,
                MIN(close) as min_price,
                MAX(close) as max_price,
                AVG(volume) as avg_volume
            FROM stock_ohlcv
            WHERE ticker = %(ticker)s
        """
        result = self.client.query(query, parameters={"ticker": ticker})

        if not result.result_rows:
            return None

        row = result.result_rows[0]
        return {
            'ticker': ticker,
            'record_count': row[0],
            'first_date': row[1],
            'last_date': row[2],
            'min_price': row[3],
            'max_price': row[4],
            'avg_volume': row[5],
            'exists': row[0] > 0
        }

    def check_date_range_coverage(self, ticker: str, start_date: date, end_date: date) -> Dict:
        """Check if ticker has data for the requested date range"""
        query = """
            SELECT
                COUNT(*) as records_in_range,
                MIN(date) as actual_start,
                MAX(date) as actual_end
            FROM stock_ohlcv
            WHERE ticker = %(ticker)s
              AND date >= %(start_date)s
              AND date <= %(end_date)s
        """
        result = self.client.query(query, parameters={
            "ticker": ticker,
            "start_date": start_date,
            "end_date": end_date
        })

        if not result.result_rows:
            return {
                'has_data': False,
                'records_in_range': 0,
                'actual_start': None,
                'actual_end': None
            }

        row = result.result_rows[0]
        return {
            'has_data': row[0] > 0,
            'records_in_range': row[0],
            'actual_start': row[1],
            'actual_end': row[2]
        }

    def check_ingestion_status(self, ticker: str) -> Dict:
        """Check ingestion log for ticker"""
        query = """
            SELECT
                last_date,
                last_ingestion,
                record_count,
                status
            FROM ingestion_log
            WHERE ticker = %(ticker)s
            ORDER BY last_ingestion DESC
            LIMIT 1
        """
        result = self.client.query(query, parameters={"ticker": ticker})

        if not result.result_rows:
            return {'has_log': False}

        row = result.result_rows[0]
        return {
            'has_log': True,
            'last_date': row[0],
            'last_ingestion': row[1],
            'record_count': row[2],
            'status': row[3]
        }


def load_config(config_path: str) -> dict:
    """Load config.yaml"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


def format_date(d) -> str:
    """Format date for display"""
    if d is None:
        return "N/A"
    if isinstance(d, str):
        return d
    return d.strftime('%Y-%m-%d')


def main():
    parser = argparse.ArgumentParser(
        description='Check if ticker data is available in ClickHouse'
    )

    parser.add_argument(
        '--tickers',
        type=str,
        help='Comma-separated ticker symbols to check'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to config.yaml (uses tickers from config if --tickers not provided)'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='Check if data exists from this date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='Check if data exists until this date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--list-all',
        action='store_true',
        help='List all available tickers in database'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed information'
    )

    # ClickHouse connection
    parser.add_argument('--host', type=str, default='localhost')
    parser.add_argument('--port', type=int, default=8123)
    parser.add_argument('--database', type=str, default='default')
    parser.add_argument('--user', type=str, default='default')
    parser.add_argument('--password', type=str, default='password')

    args = parser.parse_args()

    # Connect to ClickHouse
    try:
        client = get_client(
            host=args.host,
            port=args.port,
            database=args.database,
            user=args.user,
            password=args.password
        )
    except Exception as e:
        print(f"✗ Failed to connect to ClickHouse: {e}")
        sys.exit(1)

    checker = TickerDataChecker(client)

    # List all tickers
    if args.list_all:
        print("Available tickers in ClickHouse:")
        print("=" * 50)
        available = checker.get_available_tickers()
        if available:
            for ticker in available:
                info = checker.get_ticker_info(ticker)
                print(f"  {ticker:15s} | {info['record_count']:6d} records | "
                      f"{format_date(info['first_date'])} to {format_date(info['last_date'])}")
            print(f"\nTotal: {len(available)} tickers")
        else:
            print("  No tickers found in database")
        return

    # Get tickers to check
    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(',')]
    else:
        config = load_config(args.config)
        tickers = config.get('strategy', {}).get('tickers', [])

    if not tickers:
        print("Error: No tickers specified")
        print("Use --tickers or ensure config.yaml has tickers defined")
        sys.exit(1)

    # Parse date range if provided
    start_date = None
    end_date = None
    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()

    # Check each ticker
    print("=" * 70)
    print("Ticker Data Availability Check")
    print("=" * 70)
    print()

    all_available = True
    results = []

    for ticker in tickers:
        print(f"Checking {ticker}...")
        print("-" * 70)

        # Check if exists
        exists = checker.check_ticker_exists(ticker)

        if not exists:
            print(f"  ✗ No data found in ClickHouse")
            all_available = False
            results.append({
                'ticker': ticker,
                'status': 'missing',
                'exists': False
            })
            print()
            continue

        # Get ticker info
        info = checker.get_ticker_info(ticker)
        print(f"  ✓ Data exists")
        print(f"  Records:    {info['record_count']:,}")
        print(f"  Date Range: {format_date(info['first_date'])} to {format_date(info['last_date'])}")
        print(f"  Price Range: ${info['min_price']:.2f} - ${info['max_price']:.2f}")

        # Check date range coverage if specified
        if start_date and end_date:
            coverage = checker.check_date_range_coverage(ticker, start_date, end_date)
            if coverage['has_data']:
                print(f"  ✓ Has data for requested range ({start_date} to {end_date})")
                print(f"    Records in range: {coverage['records_in_range']}")
                print(f"    Actual coverage: {format_date(coverage['actual_start'])} to {format_date(coverage['actual_end'])}")
            else:
                print(f"  ✗ No data for requested range ({start_date} to {end_date})")
                all_available = False

        # Check ingestion log
        if args.verbose:
            log = checker.check_ingestion_status(ticker)
            if log['has_log']:
                print(f"  Last Update: {log['last_ingestion']}")
                print(f"  Last Date:   {format_date(log['last_date'])}")
                print(f"  Status:      {log['status']}")

        results.append({
            'ticker': ticker,
            'status': 'ok',
            'exists': True,
            'info': info
        })

        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    ok_count = sum(1 for r in results if r['exists'])
    missing_count = len(results) - ok_count

    print(f"Total tickers checked: {len(results)}")
    print(f"  ✓ Available: {ok_count}")
    print(f"  ✗ Missing:   {missing_count}")

    if missing_count > 0:
        print("\nMissing tickers:")
        for r in results:
            if not r['exists']:
                print(f"  - {r['ticker']}")
        print("\nTo collect data for missing tickers:")
        missing_tickers = ','.join([r['ticker'] for r in results if not r['exists']])
        print(f"  ./practices/02_collect_data.sh \"{missing_tickers}\"")

    print()

    # Exit code
    sys.exit(0 if all_available else 1)


if __name__ == '__main__':
    main()
