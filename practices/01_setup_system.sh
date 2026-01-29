#!/bin/bash
################################################################################
# Script: 01_setup_system.sh
# Description: Initial system setup - starts ClickHouse, creates schema, verifies
#
# Parameters: None
#
# What it does:
#   1. Starts ClickHouse Docker container
#   2. Waits for ClickHouse to be ready
#   3. Creates database schema (stock_ohlcv, ingestion_log tables)
#   4. Verifies connection and schema creation
#
# Usage:
#   ./practices/01_setup_system.sh
#
# Prerequisites:
#   - Docker and docker-compose installed
#   - docker-compose.yml configured
################################################################################

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "==================================================="
echo "  Stock Trading System - Initial Setup"
echo "==================================================="
echo ""

# Step 1: Start ClickHouse
echo "[1/4] Starting ClickHouse Docker container..."
cd "$PROJECT_DIR"
docker compose up -d

# Step 2: Wait for ClickHouse to be ready
echo ""
echo "[2/4] Waiting for ClickHouse to be ready..."
sleep 5

MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8123/ping > /dev/null 2>&1; then
        echo "✓ ClickHouse is ready!"
        break
    fi
    echo "  Waiting... (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "✗ Error: ClickHouse failed to start"
    exit 1
fi

# Step 3: Initialize schema
echo ""
echo "[3/4] Creating database schema..."
python3 -c "
from trading_system.ingestion.clickhouse_schema import get_client, initialize_schema

client = get_client('localhost', 8123, 'default', password='password')
initialize_schema(client)
print('✓ Schema initialized successfully')
"

# Step 4: Verify setup
echo ""
echo "[4/4] Verifying setup..."
docker exec clickhouse-server clickhouse-client --password password \
    --query "SHOW TABLES" | head -10

echo ""
echo "==================================================="
echo "  Setup Complete!"
echo "==================================================="
echo ""
echo "Next steps:"
echo "  1. Collect data: ./practices/02_collect_data.sh"
echo "  2. Run backtest: ./practices/04_run_backtest.sh"
echo ""
