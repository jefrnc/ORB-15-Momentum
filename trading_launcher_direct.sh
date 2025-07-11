#!/bin/bash

# Direct ORB Trading Launcher for Stream Deck
# Launches live trading immediately

osascript -e 'tell application "Terminal"
    activate
    set newTab to do script "cd /Users/Joseph/repos/ORB-15-Momentum && source /Users/Joseph/repos/ORB-15-Momentum/orb_env/bin/activate && echo \"🚀 ORB-15 Momentum Trader Starting...\" && echo \"═══════════════════════════════════\" && python3 /Users/Joseph/repos/ORB-15-Momentum/orb_trader.py"
    set current settings of newTab to settings set "Pro"
end tell'