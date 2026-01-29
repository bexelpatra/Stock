#!/bin/bash
################################################################################
# Script: 03_update_data.sh
# Description: Incrementally update stock data (only fetch new data since last update)
#
# Parameters:
#   $1 - MODE (optional): "config" or "tickers"
#        - "config": Use ticker list from config.yaml (default)
#        - "tickers": Specify tickers manually (requires $2)
#   $2 - TICKERS (optional): Comma-separated tickers (only if MODE=tickers)
#   $3 - MAX_LOOKBACK_DAYS (optional): Days to look back for new tickers (default: 20000 ≈ 54 years, maximum historical data)
#
# What it does:
#   1. Checks ingestion_log for last update date per ticker
#   2. Fetches only new data (from last_date + 1 to today)
#   3. Skips if data is already up-to-date
#   4. Updates ingestion_log
#   5. Verifies data quality
#
# Usage Examples:
#   # Update all tickers from config.yaml
#   ./practices/03_update_data.sh
#   ./practices/03_update_data.sh config
#
#   # Update specific tickers
#   ./practices/03_update_data.sh tickers "^GSPC,005930.KS"
#
#   # Update specific tickers with custom lookback for new tickers
#   ./practices/03_update_data.sh tickers "AAPL,MSFT" 90
#
# Use Case:
#   - Run this daily (manually or via cron) to keep data current
#   - Much faster than full re-collection
#   - Automatically handles new tickers
#
# Prerequisites:
#   - Initial data collected (run 02_collect_data.sh first)
#   - ClickHouse running
################################################################################

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Parse parameters
MODE="${1:-config}"
TICKERS="$2"
MAX_LOOKBACK_DAYS="${3:-20000}"

echo "==================================================="
echo "  Incremental Data Update"
echo "==================================================="
echo ""

# Build command based on mode
if [ "$MODE" = "config" ]; then
    echo "Mode: Using tickers from config.yaml"
    CMD="python $PROJECT_DIR/scripts/update_data.py --config $PROJECT_DIR/config.yaml"
elif [ "$MODE" = "tickers" ]; then
    if [ -z "$TICKERS" ]; then
        echo "Error: TICKERS required when MODE=tickers"
        echo ""
        echo "Usage: $0 tickers \"TICKER1,TICKER2\" [MAX_LOOKBACK_DAYS]"
        exit 1
    fi
    echo "Mode: Manual ticker list"
    echo "Tickers: $TICKERS"
    CMD="python $PROJECT_DIR/scripts/update_data.py --tickers \"$TICKERS\" --max-lookback-days $MAX_LOOKBACK_DAYS"
else
    echo "Error: Invalid MODE '$MODE'. Use 'config' or 'tickers'"
    exit 1
fi

echo ""

# Execute update
echo "[1/2] Updating data..."
eval $CMD

# Verify all data
echo ""
echo "[2/2] Verifying all data..."
python "$PROJECT_DIR/scripts/verify_data.py" --all

echo ""
echo "==================================================="
echo "  Update Complete!"
echo "==================================================="
echo ""
echo "Data is now up-to-date."
echo "Run backtest: ./practices/04_run_backtest.sh"
echo ""
