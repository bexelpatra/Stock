#!/bin/bash
################################################################################
# Script: 05_full_workflow.sh
# Description: Complete workflow - setup, collect data, and run backtest
#
# Parameters:
#   $1 - TICKERS (required): Comma-separated ticker list
#   $2 - START_DATE (optional): Data collection start date (YYYY-MM-DD)
#        Default: 1970-01-01 (maximum historical data from IPO)
#   $3 - END_DATE (optional): Data collection end date (YYYY-MM-DD)
#        Default: today
#
# What it does:
#   1. Ensures ClickHouse is running and schema exists
#   2. Collects historical data for specified tickers
#   3. Updates config.yaml with the tickers
#   4. Runs backtest
#   5. Shows summary of results
#
# Usage Examples:
#   # Maximum historical data (from IPO to today)
#   ./practices/05_full_workflow.sh "^GSPC"
#   ./practices/05_full_workflow.sh "AAPL,MSFT,GOOGL,NVDA"
#   ./practices/05_full_workflow.sh "005930.KS,000660.KS"
#
#   # Specific date range
#   ./practices/05_full_workflow.sh "^GSPC" "2020-01-01" "2024-12-31"
#   ./practices/05_full_workflow.sh "005930.KS,000660.KS" "2010-01-01" "2024-12-31"
#
#   # Mixed portfolio with maximum data
#   ./practices/05_full_workflow.sh "^GSPC,005930.KS,AAPL"
#
# This is ideal for:
#   - First-time users
#   - Testing new ticker combinations
#   - Complete end-to-end testing
#
# Prerequisites:
#   - Docker installed
#   - Internet connection
################################################################################

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Parse parameters
TICKERS="$1"
START_DATE="${2:-}"
END_DATE="${3:-}"

if [ -z "$TICKERS" ]; then
    echo "Error: TICKERS parameter is required"
    echo ""
    echo "Usage: $0 TICKERS [START_DATE] [END_DATE]"
    echo ""
    echo "Examples:"
    echo "  $0 \"^GSPC\""
    echo "  $0 \"005930.KS,000660.KS\" \"2023-01-01\" \"2024-12-31\""
    echo "  $0 \"AAPL,MSFT,GOOGL\" \"2024-01-01\" \"2024-12-31\""
    exit 1
fi

echo "###################################################"
echo "#                                                 #"
echo "#  Stock Trading System - Full Workflow          #"
echo "#                                                 #"
echo "###################################################"
echo ""
echo "Tickers:    $TICKERS"
echo "Start Date: ${START_DATE:-1970-01-01 (maximum historical data)}"
echo "End Date:   ${END_DATE:-today}"
echo ""
echo "Note: Fetches all available data from IPO date onwards"
echo ""
read -p "Press Enter to continue..."
echo ""

# Step 1: Setup system
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: System Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
"$SCRIPT_DIR/01_setup_system.sh"

# Step 2: Collect data
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: Data Collection"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -n "$START_DATE" ] && [ -n "$END_DATE" ]; then
    "$SCRIPT_DIR/02_collect_data.sh" "$TICKERS" "$START_DATE" "$END_DATE"
else
    "$SCRIPT_DIR/02_collect_data.sh" "$TICKERS"
fi

# Step 3: Update config.yaml with tickers
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3: Update Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Updating config.yaml with tickers..."

# Backup config
cp "$PROJECT_DIR/config.yaml" "$PROJECT_DIR/config.yaml.backup.$(date +%Y%m%d_%H%M%S)"

# Update tickers in config.yaml (preserving other settings)
python3 -c "
import yaml

config_path = '$PROJECT_DIR/config.yaml'
tickers_str = '$TICKERS'

# Read current config
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

# Update tickers
tickers_list = [t.strip() for t in tickers_str.split(',')]
config['strategy']['tickers'] = tickers_list

# Write back
with open(config_path, 'w') as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

print(f'✓ Updated config.yaml with {len(tickers_list)} tickers')
for ticker in tickers_list:
    print(f'  - {ticker}')
"

# Step 4: Run backtest
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 4: Run Backtest"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
"$SCRIPT_DIR/04_run_backtest.sh" clickhouse

# Final summary
echo ""
echo "###################################################"
echo "#                                                 #"
echo "#  Full Workflow Complete!                       #"
echo "#                                                 #"
echo "###################################################"
echo ""
echo "What was done:"
echo "  ✓ ClickHouse setup and schema created"
echo "  ✓ Historical data collected for: $TICKERS"
echo "  ✓ config.yaml updated with tickers"
echo "  ✓ Backtest executed with results above"
echo ""
echo "Next steps:"
echo "  - Edit config.yaml to tune strategy parameters"
echo "  - Run backtest again: ./practices/04_run_backtest.sh"
echo "  - Update data daily: ./practices/03_update_data.sh"
echo "  - Setup automation: ./practices/06_setup_automation.sh"
echo ""
