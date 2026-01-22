# Configuration and state management
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Global bot state
bot_state = {
    "is_running": False,
    "mode": "live",  # paper or live
    "current_position": None,
    "daily_trades": 0,
    "daily_pnl": 0.0,
    "daily_max_loss_triggered": False,
    "last_supertrend_signal": None,
    "index_ltp": 0.0,
    "supertrend_value": 0.0,
    "trailing_sl": None,
    "entry_price": 0.0,
    "current_option_ltp": 0.0,
    "max_drawdown": 0.0,
    "selected_index": "NIFTY",  # Default index
}

# Configuration (can be updated from frontend)
config = {
    "dhan_access_token": "",
    "dhan_client_id": "",
    "order_qty": 1,  # Number of lots (will be multiplied by lot_size)
    "max_trades_per_day": 5,
    "daily_max_loss": 2000,
    "trail_start_profit": 10,
    "trail_step": 5,
    "trailing_sl_distance": 10,
    "supertrend_period": 7,
    "supertrend_multiplier": 4,
    "candle_interval": 5,  # seconds
    "selected_index": "NIFTY",  # Default index
}

# SQLite Database path
DB_PATH = ROOT_DIR / 'data' / 'trading.db'

# Ensure directories exist
(ROOT_DIR / 'logs').mkdir(exist_ok=True)
(ROOT_DIR / 'data').mkdir(exist_ok=True)
