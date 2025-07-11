# 🚀 Setup Instructions for ORB-15 Momentum

## 📁 Repository Setup

### 1. Initialize Git Repository

```bash
cd /Users/Joseph/repos/ORB-15-Momentum

# Initialize git
git init

# Add all files
git add .

# Initial commit
git commit -m "🚀 Initial commit: ORB-15 Momentum Trading System

- Complete ORB strategy implementation
- Configurable parameters via CLI/JSON
- PostgreSQL integration for trade logging
- Comprehensive backtesting framework
- Paper and live trading support
- IBKR TWS/Gateway integration"

# Add remote origin (when ready)
# git remote add origin https://github.com/your-username/ORB-15-Momentum.git
# git push -u origin main
```

### 2. Virtual Environment Setup

```bash
# Create virtual environment
python -m venv orb_env

# Activate environment
source orb_env/bin/activate  # Linux/Mac
# orb_env\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import ib_insync; print('✅ ib_insync installed')"
python -c "import pandas; print('✅ pandas installed')"
python -c "import psycopg2; print('✅ psycopg2 installed')"
```

### 3. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env  # or your preferred editor

# Edit JSON config
nano configs/orb_config.json
```

### 4. Testing

```bash
# Test strategy logic
python test_orb_strategy.py

# Test with IBKR connection (ensure TWS is running)
python test_orb_strategy.py --live

# Validate configuration
python orb_trader.py --help
```

### 5. First Run

```bash
# Paper trading first
python orb_trader.py --paper --debug

# Live trading (after successful paper testing)
python orb_trader.py --max-position 500  # Start small
```

## 🔧 Development Setup

### IDE Configuration

For VS Code, create `.vscode/settings.json`:

```json
{
    "python.pythonPath": "./orb_env/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black"
}
```

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Set up git hooks
pre-commit install

# Run on all files
pre-commit run --all-files
```

## 📊 Database Setup (Optional)

If you want separate database for ORB strategy:

```bash
# Create new database
createdb orb_trading_db

# Set up tables (modify postgresql_storage.py accordingly)
python -c "
from src.core.postgresql_storage import PostgreSQLStorage
storage = PostgreSQLStorage('ORB15_MOMENTUM')
print('✅ Database initialized')
"
```

## 🚨 Important Notes

1. **Client ID**: Default is 5, ensure it doesn't conflict with other systems
2. **Port**: 7496 (live) or 7497 (paper) - make sure TWS is configured correctly
3. **Permissions**: Ensure IBKR account has trading permissions for stocks
4. **Data**: Real-time market data subscription recommended for live trading

## 📝 Next Steps

1. Run paper trading for at least a week
2. Monitor logs and performance
3. Adjust position sizing based on comfort level
4. Scale up gradually after proving profitability

---

**Setup Date**: July 2025  
**System**: ORB-15 Momentum v1.0.0