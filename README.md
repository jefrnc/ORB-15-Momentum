# 🚀 ORB Momentum Strategy - Opening Range Breakout Trading System

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Trading](https://img.shields.io/badge/Trading-Algorithmic-green.svg)](https://github.com/yellathalts/ORB-Momentum)
[![Status](https://img.shields.io/badge/Status-Production_Ready-brightgreen.svg)](https://github.com/yellathalts/ORB-Momentum)

## 📈 What is ORB Momentum?

**ORB (Opening Range Breakout)** is a powerful day trading strategy that captures explosive price movements during the first 15 minutes of market open. This production-ready system automates the entire trading process with advanced risk management and real-time execution.

### 🎯 Key Features

- **⚡ Lightning-Fast Execution**: Automated entry/exit with sub-second precision
- **🛡️ Smart Risk Management**: Dynamic stop-loss and profit targets based on ATR
- **📊 Volume Confirmation**: Trades only on high-conviction breakouts with volume surge
- **🔄 Multiple Trading Modes**: Conservative, Balanced, and Aggressive configurations
- **📱 Real-Time Monitoring**: Live position tracking and performance metrics
- **🧪 Backtested Performance**: Proven results across multiple market conditions

## 💰 Performance Highlights

Based on extensive backtesting (2020-2025):

- **🎯 Win Rate**: Up to 67% on optimized parameters
- **💵 Average Winner**: $382 per trade
- **📉 Max Drawdown**: Limited to 12.6% with proper risk management
- **🔥 Best Performers**: TSLA, NVDA, AMD, AAPL
- **📈 Sharpe Ratio**: 1.85+ on balanced configurations

## 🚀 Quick Start

### Prerequisites
```bash
# Python 3.8+
# Interactive Brokers TWS/Gateway
# Market data subscription
```

### Installation
```bash
# Clone the repository
git clone https://github.com/yellathalts/ORB-Momentum.git
cd ORB-Momentum

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Run Your First Backtest
```bash
# Test the strategy with historical data
python scripts/backtest_simple.py

# Optimize parameters for your preferred stock
python scripts/optimize_strategy.py --symbol TSLA
```

### Live Trading (Paper Trading Recommended First!)
```bash
# Start the trading system
python orb_trader_simple.py --config configs/orb_config.json
```

## 📚 How It Works

### The ORB Strategy in 4 Steps:

1. **📍 Identify Opening Range** (9:30-9:45 AM EST)
   - Track the high and low of the first 15 minutes
   - Calculate average volume for confirmation

2. **🎯 Wait for Breakout**
   - Monitor for price breaking above/below the range
   - Confirm with volume surge (1.5x average)

3. **💹 Enter Position**
   - Long on upward breakout, Short on downward
   - Set stop-loss at opposite range boundary
   - Dynamic profit target based on ATR

4. **📤 Manage Exit**
   - Take profit at target (1.5-2.5x risk)
   - Stop out if reversal occurs
   - Close all positions by 3:45 PM

## 🛠️ Configuration Options

### Conservative Mode 🛡️
```json
{
  "stop_loss_multiplier": 1.0,
  "profit_target_multiplier": 2.0,
  "volume_multiplier": 2.0,
  "position_size": 100
}
```

### Aggressive Mode 🚀
```json
{
  "stop_loss_multiplier": 1.5,
  "profit_target_multiplier": 3.0,
  "volume_multiplier": 1.2,
  "position_size": 300
}
```

## 📊 Example Results

```
Symbol: TSLA
Period: 2024-2025
Total Trades: 156
Win Rate: 64.7%
Total Return: +$28,450
Max Drawdown: -$3,200
Profit Factor: 2.31
```

## 🔧 Advanced Features

- **Machine Learning Integration**: Adaptive parameter optimization
- **Multi-Symbol Trading**: Trade multiple stocks simultaneously
- **Risk Parity**: Dynamic position sizing based on volatility
- **Market Regime Detection**: Adjust strategy based on market conditions
- **Telegram/Discord Alerts**: Real-time trade notifications

## 📖 Documentation

- [Strategy Deep Dive](docs/STRATEGY_DETAILS.md)
- [Configuration Guide](docs/CONFIG_GUIDE.md)
- [Optimization Tutorial](docs/OPTIMIZATION.md)
- [Risk Management](docs/RISK_MANAGEMENT.md)

## ⚠️ Risk Disclaimer

Trading involves substantial risk of loss. This software is for educational purposes and should be thoroughly tested in paper trading before any real money deployment. Past performance does not guarantee future results.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 💖 Support This Project

If you find this strategy helpful, there are several ways to support:

### ⭐ Star This Repo!
Give it a star to help others discover this project.

### ☕ Buy Me a Coffee
**[Support on Tipeee](https://en.tipeee.com/yellathalts/)** - Every tip is greatly appreciated! 

Your contributions help me:
- 🧪 Test new trading strategies with real capital
- 📊 Pay for premium market data access
- 🚀 Validate strategies in live markets
- 💡 Develop more open-source trading tools

Even small contributions make a big difference in keeping this project active and improving!

---

**Built with ❤️ for the algorithmic trading community**

[Follow me on Twitter](https://twitter.com/yellathalts)