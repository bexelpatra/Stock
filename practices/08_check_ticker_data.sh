#!/bin/bash
################################################################################
# Script: 08_check_ticker_data.sh
# Description: Check if requested tickers have data in ClickHouse
#
# Parameters:
#   $1 - MODE (optional): "list", "config", or "tickers"
#        - "list": List all available tickers in database
#        - "config": Check tickers from config.yaml (default)
#        - "tickers": Check specific tickers (requires $2)
#   $2 - TICKERS (optional): Comma-separated tickers (only if MODE=tickers)
#   $3 - START_DATE (optional): Check data from this date (YYYY-MM-DD)
#   $4 - END_DATE (optional): Check data until this date (YYYY-MM-DD)
#
# What it checks:
#   1. Whether ticker exists in database
#   2. Number of records available
#   3. Date range coverage
#   4. Price range
#   5. Last ingestion status (verbose mode)
#   6. Coverage for specific date range (if dates provided)
#
# Usage Examples:
#   # List all available tickers
#   ./practices/08_check_ticker_data.sh list
#
#   # Check tickers from config.yaml
#   ./practices/08_check_ticker_data.sh
#   ./practices/08_check_ticker_data.sh config
#
#   # Check specific tickers
#   ./practices/08_check_ticker_data.sh tickers "^GSPC,AAPL,MSFT"
#
#   # Check if tickers have data for specific date range
#   ./practices/08_check_ticker_data.sh tickers "^GSPC,AAPL" "2024-01-01" "2024-12-31"
#
#   # Check config tickers for date range
#   ./practices/08_check_ticker_data.sh config "" "2024-01-01" "2024-12-31"
#
# Exit codes:
#   0 - All requested tickers have data
#   1 - One or more tickers missing data
#
# Use before:
#   - Running backtests
#   - Starting workflows
#   - Validating data collection
################################################################################

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Parse parameters
MODE="${1:-config}"
TICKERS="$2"
START_DATE="$3"
END_DATE="$4"

echo "==================================================="
echo "  Ticker Data Availability Check"
echo "==================================================="
echo ""

# Build command based on mode
if [ "$MODE" = "list" ]; then
    echo "Mode: List all available tickers"
    CMD="python $PROJECT_DIR/scripts/check_ticker_data.py --list-all"

elif [ "$MODE" = "config" ]; then
    echo "Mode: Check tickers from config.yaml"
    CMD="python $PROJECT_DIR/scripts/check_ticker_data.py --config $PROJECT_DIR/config.yaml"

    # Add date range if provided
    if [ -n "$START_DATE" ]; then
        CMD="$CMD --start-date $START_DATE"
    fi
    if [ -n "$END_DATE" ]; then
        CMD="$CMD --end-date $END_DATE"
    fi

elif [ "$MODE" = "tickers" ]; then
    if [ -z "$TICKERS" ]; then
        echo "Error: TICKERS required when MODE=tickers"
        echo ""
        echo "Usage: $0 tickers \"TICKER1,TICKER2\" [START_DATE] [END_DATE]"
        exit 1
    fi

    echo "Mode: Check specific tickers"
    echo "Tickers: $TICKERS"
    CMD="python $PROJECT_DIR/scripts/check_ticker_data.py --tickers \"$TICKERS\""

    # Add date range if provided
    if [ -n "$START_DATE" ]; then
        CMD="$CMD --start-date $START_DATE"
    fi
    if [ -n "$END_DATE" ]; then
        CMD="$CMD --end-date $END_DATE"
    fi

else
    echo "Error: Invalid MODE '$MODE'"
    echo "Use: list, config, or tickers"
    exit 1
fi

echo ""

# Execute check
eval $CMD
EXIT_CODE=$?

echo ""

# Provide guidance based on result
if [ $EXIT_CODE -ne 0 ]; then
    echo "==================================================="
    echo "  Action Required: Missing Ticker Data"
    echo "==================================================="
    echo ""
    echo "Next steps:"
    echo "  1. Collect missing data: ./practices/02_collect_data.sh \"TICKER\""
    echo "  2. Update existing data: ./practices/03_update_data.sh"
    echo "  3. Check system status: ./practices/07_check_status.sh"
    echo ""
else
    echo "==================================================="
    echo "  All Requested Tickers Available"
    echo "==================================================="
    echo ""
    echo "Ready to run backtests!"
    echo ""
fi

exit $EXIT_CODE
