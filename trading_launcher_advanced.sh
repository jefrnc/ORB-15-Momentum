#!/bin/bash

# ORB-15 Momentum Trading Launcher
# Enhanced launcher with environment checks and multiple options

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project paths
PROJECT_DIR="/Users/Joseph/repos/ORB-15-Momentum"
VENV_NAME="orb_env"
LOG_DIR="$PROJECT_DIR/logs"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to print colored messages
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Check if project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    print_message $RED "Error: Project directory not found at $PROJECT_DIR"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "$PROJECT_DIR/$VENV_NAME" ]; then
    print_message $YELLOW "Virtual environment not found. Creating it now..."
    cd "$PROJECT_DIR"
    python3 -m venv $VENV_NAME
    source $VENV_NAME/bin/activate
    pip install -r requirements.txt
else
    print_message $GREEN "Virtual environment found."
fi

# Get command line argument for which script to run
SCRIPT_CHOICE=${1:-"menu"}

# Function to launch a script
launch_script() {
    local script_name=$1
    local script_desc=$2
    
    osascript -e "tell application \"Terminal\"
        activate
        set newTab to do script \"cd $PROJECT_DIR && source $VENV_NAME/bin/activate && echo '🚀 Launching $script_desc...' && python3 $script_name\"
        set current settings of newTab to settings set \"Pro\"
    end tell"
}

# Menu function
show_menu() {
    clear
    print_message $GREEN "═══════════════════════════════════════"
    print_message $GREEN "   ORB-15 Momentum Trading Launcher    "
    print_message $GREEN "═══════════════════════════════════════"
    echo ""
    echo "Select an option:"
    echo "1) Live Trading (orb_trader.py)"
    echo "2) Simple Trading (orb_trader_simple.py)"
    echo "3) Backtest Full Year (backtest_2025_full.py)"
    echo "4) Real Backtest (backtest_real.py)"
    echo "5) Simple Backtest (backtest_simple.py)"
    echo "6) Optimize Strategy (optimize_strategy.py)"
    echo "7) Portfolio Simulation (portfolio_simulation_2025.py)"
    echo "8) Test Connection (test_connection.py)"
    echo "9) Open Terminal in Project"
    echo "0) Exit"
    echo ""
    read -p "Enter your choice [0-9]: " choice
    
    case $choice in
        1) launch_script "orb_trader.py" "Live ORB Trader";;
        2) launch_script "orb_trader_simple.py" "Simple ORB Trader";;
        3) launch_script "backtest_2025_full.py" "Full Year Backtest";;
        4) launch_script "backtest_real.py" "Real Backtest";;
        5) launch_script "backtest_simple.py" "Simple Backtest";;
        6) launch_script "optimize_strategy.py" "Strategy Optimizer";;
        7) launch_script "portfolio_simulation_2025.py" "Portfolio Simulator";;
        8) launch_script "test_connection.py" "Connection Test";;
        9) osascript -e "tell application \"Terminal\"
            activate
            do script \"cd $PROJECT_DIR && source $VENV_NAME/bin/activate && clear && echo 'ORB-15 Environment Activated' && echo '═══════════════════════════' && echo '' && echo 'Available commands:' && echo '  python orb_trader.py - Start live trading' && echo '  python backtest_2025_full.py - Run backtest' && echo '  ls configs/ - View configuration files' && echo ''\"
        end tell";;
        0) exit 0;;
        *) print_message $RED "Invalid option. Please try again."
           sleep 2
           show_menu;;
    esac
}

# Direct launch based on argument
case $SCRIPT_CHOICE in
    "trader"|"live")
        launch_script "orb_trader.py" "Live ORB Trader"
        ;;
    "simple")
        launch_script "orb_trader_simple.py" "Simple ORB Trader"
        ;;
    "backtest")
        launch_script "backtest_2025_full.py" "Full Year Backtest"
        ;;
    "optimize")
        launch_script "optimize_strategy.py" "Strategy Optimizer"
        ;;
    "test")
        launch_script "test_connection.py" "Connection Test"
        ;;
    "menu"|*)
        show_menu
        ;;
esac