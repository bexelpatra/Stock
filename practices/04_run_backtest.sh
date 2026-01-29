#!/bin/bash
################################################################################
# Script: 04_run_backtest.sh
# Description: Run trading strategy backtest
#
# Parameters:
#   $1 - SOURCE (optional): Data source to use
#        - "clickhouse": Use real data from ClickHouse DB (default)
#        - "sample": Use randomly generated sample data
#   $2 - CONFIG (optional): Path to config file
#        Default: config.yaml
#
# What it does:
#   1. Loads configuration from config.yaml
#   2. Loads historical data (from ClickHouse or generates sample)
#   3. Runs backtest with configured strategy
#   4. Displays performance metrics and trade summary
#
# Configuration (edit config.yaml):
#   Strategy Parameters:
#     - total_seed: Total capital (default: 10,000,000 KRW)
#     - split_count: Number of split buys (default: 5)
#     - buy_threshold: Buy when stock drops X% (default: 2.0%)
#     - sell_profit_rate: Sell at profit target (default: 3.0%)
#     - stop_loss_rate: Stop loss threshold (default: 5.0%)
#     - tickers: List of stocks to trade
#
#   Backtest Period:
#     - start_date: Backtest start (YYYY-MM-DD)
#     - end_date: Backtest end (YYYY-MM-DD)
#
#   Trading Costs:
#     - commission_rate: Broker commission (default: 0.015%)
#     - tax_rate: Transaction tax (default: 0.23%)
#     - slippage_rate: Slippage (default: 0.1%)
#
# Usage Examples:
#   # Run with ClickHouse data (default)
#   ./practices/04_run_backtest.sh
#   ./practices/04_run_backtest.sh clickhouse
#
#   # Run with sample/random data (for testing)
#   ./practices/04_run_backtest.sh sample
#
#   # Use custom config file
#   ./practices/04_run_backtest.sh clickhouse my_config.yaml
#
# Output:
#   - Total return percentage
#   - Win rate
#   - Number of trades
#   - Max drawdown
#   - Sharpe ratio
#   - Recent trade details
#
# Prerequisites:
#   - For ClickHouse mode: Data collected (run 02_collect_data.sh)
#   - For sample mode: None (generates random data)
################################################################################

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Parse parameters
SOURCE="${1:-clickhouse}"
CONFIG="${2:-config.yaml}"

# Validate source
if [ "$SOURCE" != "clickhouse" ] && [ "$SOURCE" != "sample" ]; then
    echo "Error: Invalid SOURCE '$SOURCE'. Use 'clickhouse' or 'sample'"
    exit 1
fi

echo "==================================================="
echo "  Backtest Execution"
echo "==================================================="
echo ""
echo "Data Source: $SOURCE"
echo "Config File: $CONFIG"
echo ""

# Run backtest
python "$PROJECT_DIR/run_backtest.py" --source "$SOURCE" --config "$CONFIG"

echo ""
echo "==================================================="
echo "  Backtest Complete!"
echo "==================================================="
echo ""
echo "Tips:"
echo "  - Edit config.yaml to adjust strategy parameters"
echo "  - Change backtest period (start_date, end_date)"
echo "  - Try different tickers"
echo "  - Adjust buy_threshold, sell_profit_rate, etc."
echo ""
