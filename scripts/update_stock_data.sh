#!/bin/bash

# ================================================================
# Stock Data Update Script for Cron
# ================================================================
# Description: Daily incremental update of stock data from Yahoo Finance
# Usage: ./scripts/update_stock_data.sh
# ================================================================

# Project settings
PROJECT_DIR="/home/jai/class/Stock"
CONFIG_FILE="$PROJECT_DIR/config.yaml"
UPDATE_SCRIPT="$PROJECT_DIR/scripts/update_data.py"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/update_$(date +%Y%m%d_%H%M%S).log"

# Python settings
PYTHON_BIN="/home/jai/anaconda3/bin/python3"

# Create log directory if not exists
mkdir -p "$LOG_DIR"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Error handling
set -o pipefail

# ================================================================
# Start update process
# ================================================================

log "========================================="
log "Starting stock data update"
log "========================================="
log "Project directory: $PROJECT_DIR"
log "Config file: $CONFIG_FILE"
log "Python: $PYTHON_BIN"

# Change to project directory
cd "$PROJECT_DIR" || {
    log "ERROR: Failed to change directory to $PROJECT_DIR"
    exit 1
}

# Check if Python exists
if [ ! -f "$PYTHON_BIN" ]; then
    log "ERROR: Python not found at $PYTHON_BIN"
    exit 1
fi

# Check if update script exists
if [ ! -f "$UPDATE_SCRIPT" ]; then
    log "ERROR: Update script not found at $UPDATE_SCRIPT"
    exit 1
fi

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    log "ERROR: Config file not found at $CONFIG_FILE"
    exit 1
fi

# Check if ClickHouse is running
log "Checking ClickHouse status..."
if ! curl -s http://localhost:8123/ping > /dev/null 2>&1; then
    log "ERROR: ClickHouse is not running or not responding"
    log "Please start ClickHouse with: docker compose up -d"
    exit 1
fi
log "ClickHouse is running"

# Run update script
log "Running update script..."
log "Command: $PYTHON_BIN $UPDATE_SCRIPT --config $CONFIG_FILE"

if "$PYTHON_BIN" "$UPDATE_SCRIPT" --config "$CONFIG_FILE" 2>&1 | tee -a "$LOG_FILE"; then
    log "========================================="
    log "Update completed successfully"
    log "========================================="
    exit 0
else
    log "========================================="
    log "ERROR: Update failed with exit code $?"
    log "========================================="
    exit 1
fi
