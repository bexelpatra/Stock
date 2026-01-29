# Practices - Integrated Shell Scripts

This folder contains ready-to-use shell scripts that integrate all the Python functions into simple workflows.

## Quick Start Guide

### First Time Setup & Backtest

```bash
# Complete workflow: setup → collect data → backtest
./practices/05_full_workflow.sh "^GSPC" "2024-01-01" "2024-12-31"
```

That's it! This will set up everything and run a backtest.

---

## Quick Reference

| Script | Purpose | Key Use Case |
|--------|---------|--------------|
| `01_setup_system.sh` | Initialize system | First time setup |
| `02_collect_data.sh` | Collect historical data | Initial data gathering |
| `03_update_data.sh` | Incremental updates | Daily maintenance |
| `04_run_backtest.sh` | Execute backtest | Strategy testing |
| `05_full_workflow.sh` | Complete end-to-end | Beginners, quick testing |
| `06_setup_automation.sh` | Configure cron | Production automation |
| `07_check_status.sh` | System health check | Monitoring, debugging |
| `08_check_ticker_data.sh` | Validate ticker data | Pre-flight checks |

---

## Individual Scripts

### 1. System Setup
**Script:** `01_setup_system.sh`
**What it does:** Start ClickHouse, create database schema
**When to use:** First time setup, or after system reset

```bash
./practices/01_setup_system.sh
```

**No parameters needed**

---

### 2. Collect Initial Data
**Script:** `02_collect_data.sh`
**What it does:** Fetch historical stock data from Yahoo Finance
**When to use:** First data collection for new tickers

```bash
# Parameters: TICKERS [START_DATE] [END_DATE]

# Examples (fetches maximum historical data by default):
./practices/02_collect_data.sh "^GSPC"
./practices/02_collect_data.sh "005930.KS,000660.KS"
./practices/02_collect_data.sh "AAPL,MSFT"

# Or with specific date range:
./practices/02_collect_data.sh "^GSPC" "2020-01-01" "2024-12-31"
```

**Parameters:**
- `TICKERS` (required): Comma-separated ticker list
  - Korean stocks: Add `.KS` suffix (e.g., `005930.KS`)
  - US stocks: Use normal symbols (e.g., `AAPL`)
  - Indices: Use Yahoo format (e.g., `^GSPC` for S&P 500)
- `START_DATE` (optional): YYYY-MM-DD, default = 1970-01-01 (maximum historical data from IPO)
- `END_DATE` (optional): YYYY-MM-DD, default = today

---

### 3. Update Data (Incremental)
**Script:** `03_update_data.sh`
**What it does:** Update data incrementally (only new data since last update)
**When to use:** Daily updates, maintenance

```bash
# Parameters: [MODE] [TICKERS] [MAX_LOOKBACK_DAYS]

# Examples:
./practices/03_update_data.sh                              # Use config.yaml
./practices/03_update_data.sh config                       # Same as above
./practices/03_update_data.sh tickers "^GSPC,005930.KS"    # Specific tickers (fetches from IPO)
./practices/03_update_data.sh tickers "AAPL" 365           # New ticker with custom lookback days
```

**Parameters:**
- `MODE` (optional):
  - `config` (default): Use tickers from config.yaml
  - `tickers`: Specify tickers manually
- `TICKERS` (if MODE=tickers): Comma-separated list
- `MAX_LOOKBACK_DAYS` (optional): Days to look back for new tickers (default: 20000 ≈ 54 years, fetches from IPO)

**Much faster than full collection!**

---

### 4. Run Backtest
**Script:** `04_run_backtest.sh`
**What it does:** Execute trading strategy backtest
**When to use:** After data collection, testing strategies

```bash
# Parameters: [SOURCE] [CONFIG]

# Examples:
./practices/04_run_backtest.sh                    # Use ClickHouse data
./practices/04_run_backtest.sh clickhouse         # Same as above
./practices/04_run_backtest.sh sample             # Use random sample data
./practices/04_run_backtest.sh clickhouse my.yaml # Custom config
```

**Parameters:**
- `SOURCE` (optional):
  - `clickhouse` (default): Use real data from database
  - `sample`: Use randomly generated data (for testing)
- `CONFIG` (optional): Path to config file (default: config.yaml)

**Strategy parameters are in config.yaml**

---

### 5. Full Workflow (All-in-One)
**Script:** `05_full_workflow.sh`
**What it does:** Complete end-to-end: setup → collect → backtest
**When to use:** First time, testing new tickers

```bash
# Parameters: TICKERS [START_DATE] [END_DATE]

# Examples:
./practices/05_full_workflow.sh "^GSPC"
./practices/05_full_workflow.sh "005930.KS,000660.KS" "2023-01-01" "2024-12-31"
./practices/05_full_workflow.sh "AAPL,MSFT,GOOGL,NVDA" "2024-01-01" "2024-12-31"
```

**Parameters:** Same as `02_collect_data.sh`

**Best for beginners!**

---

### 6. Setup Automation
**Script:** `06_setup_automation.sh`
**What it does:** Configure cron job for daily automatic updates
**When to use:** After initial setup, for production use

```bash
# Parameters: [SCHEDULE]

# Examples:
./practices/06_setup_automation.sh                    # Weekday 7 PM (default)
./practices/06_setup_automation.sh weekday_evening    # Mon-Fri 7 PM
./practices/06_setup_automation.sh daily_evening      # Every day 7 PM
./practices/06_setup_automation.sh weekday_morning    # Mon-Fri 9 AM
./practices/06_setup_automation.sh custom             # Enter custom schedule
```

**Parameters:**
- `SCHEDULE` (optional):
  - `weekday_evening` (default): Mon-Fri at 7:00 PM
  - `daily_evening`: Every day at 7:00 PM
  - `weekday_morning`: Mon-Fri at 9:00 AM
  - `custom`: Interactive prompt for custom cron schedule

**After setup:**
- View cron jobs: `crontab -l`
- Check logs: `tail -f logs/cron_update.log`

---

### 7. Check System Status
**Script:** `07_check_status.sh`
**What it does:** Complete system health check
**When to use:** Debugging, monitoring, verification

```bash
./practices/07_check_status.sh
```

**No parameters needed**

**Checks:**
- ClickHouse container status
- Database connection
- Data statistics (tickers, records, dates)
- Data quality (duplicates, validity)
- Ingestion history
- Cron job configuration

---

### 8. Check Ticker Data Availability
**Script:** `08_check_ticker_data.sh`
**What it does:** Verify if specific tickers have data before running backtests
**When to use:** Before backtests, validating data collection

```bash
# Parameters: [MODE] [TICKERS] [START_DATE] [END_DATE]

# Examples:
./practices/08_check_ticker_data.sh list                          # List all tickers
./practices/08_check_ticker_data.sh                               # Check config.yaml tickers
./practices/08_check_ticker_data.sh tickers "^GSPC,AAPL"          # Check specific tickers
./practices/08_check_ticker_data.sh tickers "AAPL" "2024-01-01" "2024-12-31"  # Check date range
```

**Parameters:**
- `MODE` (optional):
  - `list`: List all available tickers in database
  - `config` (default): Check tickers from config.yaml
  - `tickers`: Check specific tickers
- `TICKERS` (if MODE=tickers): Comma-separated list
- `START_DATE` (optional): Check data from this date (YYYY-MM-DD)
- `END_DATE` (optional): Check data until this date (YYYY-MM-DD)

**Exit codes:**
- 0: All tickers available
- 1: One or more tickers missing

**Perfect for pre-flight checks!**

---

## Common Workflows

### Beginner: Quick Test (Maximum Historical Data)
```bash
# One command to do everything - fetches all available historical data
./practices/05_full_workflow.sh "^GSPC"
./practices/05_full_workflow.sh "AAPL,MSFT,GOOGL"

# Verify data is available before backtest
./practices/08_check_ticker_data.sh
```

### Daily Use: Update and Backtest
```bash
# Update data
./practices/03_update_data.sh

# Verify tickers have data
./practices/08_check_ticker_data.sh

# Run backtest
./practices/04_run_backtest.sh
```

### Production: Automated Updates
```bash
# Setup once
./practices/06_setup_automation.sh

# Check status anytime
./practices/07_check_status.sh
```

### Advanced: Multiple Portfolios
```bash
# Collect maximum historical data for portfolio A (US tech)
./practices/02_collect_data.sh "AAPL,MSFT,GOOGL"

# Collect maximum historical data for portfolio B (Korean stocks)
./practices/02_collect_data.sh "005930.KS,000660.KS"

# Edit config.yaml to choose tickers, then backtest
./practices/04_run_backtest.sh
```

---

## Tips

1. **Make scripts executable** (if needed):
   ```bash
   chmod +x practices/*.sh
   ```

2. **View script help**: Most scripts show usage if run with wrong parameters

3. **Check status regularly**:
   ```bash
   ./practices/07_check_status.sh
   ```

4. **All scripts use absolute paths** - you can run them from anywhere:
   ```bash
   cd /tmp
   /home/jai/class/Stock/practices/07_check_status.sh  # Works!
   ```

5. **Logs location**:
   - Backtest logs: `logs/backtest_*.log`
   - Cron logs: `logs/cron_update.log`
   - Python logs: `logs/` directory

---

## Configuration

All scripts use `config.yaml` for settings. Key sections:

```yaml
strategy:
  total_seed: 10000000        # Total capital (KRW)
  split_count: 5              # Number of split buys
  buy_threshold: 2.0          # Buy when stock drops X%
  sell_profit_rate: 3.0       # Sell at profit target
  stop_loss_rate: 5.0         # Stop loss threshold
  tickers:                    # Stocks to trade
    - "^GSPC"
    - "005930.KS"

backtest:
  start_date: "2024-01-01"    # Backtest period
  end_date: "2024-12-31"
  initial_cash: 10000000
  commission_rate: 0.00015    # 0.015%
  tax_rate: 0.0023            # 0.23%
```

Edit `config.yaml` to adjust strategy and backtest parameters.

---

## Troubleshooting

**ClickHouse not running?**
```bash
docker compose up -d
```

**No data in database?**
```bash
./practices/02_collect_data.sh "^GSPC"
```

**Cron not working?**
```bash
# Check cron service
sudo systemctl status cron

# Check script permissions
ls -l scripts/update_stock_data.sh

# Test manually
./scripts/update_stock_data.sh
```

**Data quality issues?**
```bash
# Verify data
python scripts/verify_data.py --all

# Remove duplicates
docker exec clickhouse-server clickhouse-client --password password \
  --query "OPTIMIZE TABLE stock_ohlcv FINAL"
```

---

## Need Help?

1. Check system status: `./practices/07_check_status.sh`
2. Review logs: `tail -f logs/cron_update.log`
3. Read script comments: Each script has detailed documentation at the top
4. Check main documentation: `PROGRESS.md`, `HOW_TO_PROCEED.md`

---

**Happy Trading! 📈**
