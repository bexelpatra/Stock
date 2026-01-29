#!/bin/bash
################################################################################
# Script: 02_collect_data.sh
# Description: Collect historical stock data from Yahoo Finance
#
# Parameters:
#   $1 - TICKERS (required): Comma-separated list of tickers
#        Examples: "^GSPC" or "005930.KS,000660.KS" or "AAPL,MSFT,GOOGL"
#        Note: Korean stocks need .KS suffix
#   $2 - START_DATE (optional): Start date in YYYY-MM-DD format
#        Default: 1970-01-01 (fetches maximum historical data from IPO)
#        Yahoo Finance will automatically start from IPO date if earlier
#   $3 - END_DATE (optional): End date in YYYY-MM-DD format
#        Default: today
#
# What it does:
#   1. Validates input parameters
#   2. Collects data from Yahoo Finance for specified tickers
#   3. Stores data in ClickHouse database
#   4. Updates ingestion log
#   5. Verifies collected data
#
# Usage Examples:
#   # Collect maximum historical data (from IPO to today)
#   ./practices/02_collect_data.sh "^GSPC"
#   ./practices/02_collect_data.sh "AAPL,MSFT,GOOGL"
#   ./practices/02_collect_data.sh "005930.KS,000660.KS"
#
#   # Collect with specific date range
#   ./practices/02_collect_data.sh "^GSPC" "2020-01-01" "2024-12-31"
#   ./practices/02_collect_data.sh "005930.KS,000660.KS" "2010-01-01" "2024-12-31"
#
# Prerequisites:
#   - ClickHouse running (run 01_setup_system.sh first)
#   - Internet connection (to access Yahoo Finance)
################################################################################

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Parse parameters
TICKERS="$1"
START_DATE="${2:-}"
END_DATE="${3:-}"

# Validate tickers parameter
if [ -z "$TICKERS" ]; then
    echo "Error: TICKERS parameter is required"
    echo ""
    echo "Usage: $0 TICKERS [START_DATE] [END_DATE]"
    echo ""
    echo "Examples:"
    echo "  $0 \"^GSPC\""
    echo "  $0 \"005930.KS,000660.KS\" \"2023-01-01\" \"2024-12-31\""
    echo "  $0 \"AAPL,MSFT\" \"2024-01-01\" \"2024-12-31\""
    exit 1
fi

echo "==================================================="
echo "  Data Collection"
echo "==================================================="
echo ""
echo "Tickers:    $TICKERS"
echo "Start Date: ${START_DATE:-1970-01-01 (maximum historical data)}"
echo "End Date:   ${END_DATE:-today}"
echo ""
echo "Note: Yahoo Finance will start from IPO date if 1970 is before IPO"
echo ""

# Build command
CMD="python $PROJECT_DIR/scripts/ingest_data.py --tickers \"$TICKERS\""
if [ -n "$START_DATE" ]; then
    CMD="$CMD --start-date \"$START_DATE\""
fi
if [ -n "$END_DATE" ]; then
    CMD="$CMD --end-date \"$END_DATE\""
fi

# Execute data collection
echo "[1/2] Collecting data from Yahoo Finance..."
eval $CMD

# Verify collected data
echo ""
echo "[2/2] Verifying collected data..."
IFS=',' read -ra TICKER_ARRAY <<< "$TICKERS"
for TICKER in "${TICKER_ARRAY[@]}"; do
    TICKER=$(echo "$TICKER" | xargs)  # Trim whitespace
    python "$PROJECT_DIR/scripts/verify_data.py" --ticker "$TICKER"
done

echo ""
echo "==================================================="
echo "  Data Collection Complete!"
echo "==================================================="
echo ""
echo "Next steps:"
echo "  1. Run backtest: ./practices/04_run_backtest.sh"
echo "  2. Update data daily: ./practices/03_update_data.sh"
echo ""
