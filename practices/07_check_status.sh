#!/bin/bash
################################################################################
# Script: 07_check_status.sh
# Description: Check system status and data health
#
# Parameters: None
#
# What it checks:
#   1. ClickHouse Docker container status
#   2. ClickHouse connection and ping
#   3. Database tables existence
#   4. Data statistics (tickers, date ranges, record counts)
#   5. Data quality (duplicates, missing values, validity)
#   6. Recent ingestion log entries
#   7. Cron job status (if configured)
#
# Usage:
#   ./practices/07_check_status.sh
#
# Use this to:
#   - Verify system is healthy
#   - Debug issues
#   - Check data before backtest
#   - Monitor after automated updates
################################################################################

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "###################################################"
echo "#                                                 #"
echo "#  System Status Check                           #"
echo "#                                                 #"
echo "###################################################"
echo ""

# Check 1: Docker container
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. ClickHouse Container Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if docker ps | grep -q clickhouse-server; then
    echo "✓ ClickHouse container is running"
    docker ps | grep clickhouse-server
else
    echo "✗ ClickHouse container is NOT running"
    echo "  Run: docker compose up -d"
fi
echo ""

# Check 2: ClickHouse connection
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. ClickHouse Connection"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if curl -s http://localhost:8123/ping > /dev/null 2>&1; then
    echo "✓ ClickHouse is responding"
    echo "  Response: $(curl -s http://localhost:8123/ping)"
else
    echo "✗ ClickHouse is not responding"
    echo "  Check container logs: docker logs clickhouse-server"
fi
echo ""

# Check 3: Tables
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Database Tables"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker exec clickhouse-server clickhouse-client --password password \
    --query "SHOW TABLES" 2>/dev/null || echo "✗ Cannot query tables"
echo ""

# Check 4: Data statistics
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. Data Statistics"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TOTAL_RECORDS=$(docker exec clickhouse-server clickhouse-client --password password \
    --query "SELECT COUNT(*) FROM stock_ohlcv" 2>/dev/null || echo "0")

echo "Total records: $TOTAL_RECORDS"
echo ""

if [ "$TOTAL_RECORDS" -gt 0 ]; then
    echo "Per-ticker breakdown:"
    docker exec clickhouse-server clickhouse-client --password password \
        --query "SELECT
            ticker,
            COUNT(*) as records,
            MIN(date) as first_date,
            MAX(date) as last_date,
            round(AVG(close), 2) as avg_close
        FROM stock_ohlcv
        GROUP BY ticker
        ORDER BY ticker" \
        --format PrettyCompact 2>/dev/null || echo "✗ Cannot query data"
else
    echo "⚠ No data in database"
    echo "  Run: ./practices/02_collect_data.sh"
fi
echo ""

# Check 5: Data quality
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. Data Quality Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$TOTAL_RECORDS" -gt 0 ]; then
    python "$PROJECT_DIR/scripts/verify_data.py" --all
else
    echo "⚠ Skipped (no data)"
fi
echo ""

# Check 6: Recent ingestion log
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. Recent Ingestion Activity"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

INGESTION_COUNT=$(docker exec clickhouse-server clickhouse-client --password password \
    --query "SELECT COUNT(*) FROM ingestion_log" 2>/dev/null || echo "0")

if [ "$INGESTION_COUNT" -gt 0 ]; then
    echo "Ingestion history (last 10 entries):"
    docker exec clickhouse-server clickhouse-client --password password \
        --query "SELECT
            ticker,
            start_date,
            end_date,
            records_inserted,
            status,
            updated_at
        FROM ingestion_log
        ORDER BY updated_at DESC
        LIMIT 10" \
        --format PrettyCompact 2>/dev/null || echo "✗ Cannot query ingestion log"
else
    echo "⚠ No ingestion history"
fi
echo ""

# Check 7: Cron jobs
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "7. Automation Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if crontab -l 2>/dev/null | grep -q "update_stock_data.sh"; then
    echo "✓ Cron job configured:"
    crontab -l 2>/dev/null | grep "update_stock_data.sh" || true
    echo ""

    # Check recent cron logs
    if [ -f "$PROJECT_DIR/logs/cron_update.log" ]; then
        echo "Last cron update (from log):"
        tail -20 "$PROJECT_DIR/logs/cron_update.log" | grep -E "(Update started|Update completed|Update failed)" | tail -5
    fi
else
    echo "⚠ No cron job configured"
    echo "  Setup automation: ./practices/06_setup_automation.sh"
fi
echo ""

# Summary
echo "###################################################"
echo "#                                                 #"
echo "#  Status Check Complete                         #"
echo "#                                                 #"
echo "###################################################"
echo ""

if [ "$TOTAL_RECORDS" -eq 0 ]; then
    echo "⚠ Action Required: No data in database"
    echo "  Next: ./practices/02_collect_data.sh \"TICKER\""
elif docker ps | grep -q clickhouse-server; then
    echo "✓ System is operational"
    echo "  Ready to run backtests"
else
    echo "⚠ Action Required: Start ClickHouse"
    echo "  Next: docker compose up -d"
fi
echo ""
