# Database operations
import aiosqlite
from config import DB_PATH, config
import logging

logger = logging.getLogger(__name__)

async def init_db():
    """Initialize SQLite database"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE,
                entry_time TEXT,
                exit_time TEXT,
                option_type TEXT,
                strike INTEGER,
                expiry TEXT,
                entry_price REAL,
                exit_price REAL,
                qty INTEGER,
                pnl REAL,
                exit_reason TEXT,
                mode TEXT,
                index_name TEXT,
                created_at TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                total_trades INTEGER,
                total_pnl REAL,
                max_drawdown REAL,
                daily_stop_triggered INTEGER,
                mode TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        await db.commit()

async def load_config():
    """Load config from database"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute('SELECT key, value FROM config') as cursor:
                rows = await cursor.fetchall()
                for key, value in rows:
                    if key in config:
                        if key in ['order_qty', 'max_trades_per_day', 'candle_interval', 'supertrend_period']:
                            config[key] = int(value)
                        elif key in ['daily_max_loss', 'trail_start_profit', 'trail_step', 'trailing_sl_distance', 'supertrend_multiplier']:
                            config[key] = float(value)
                        else:
                            config[key] = value
    except Exception as e:
        logger.error(f"Error loading config: {e}")

async def save_config():
    """Save config to database"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            for key, value in config.items():
                await db.execute(
                    'INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)',
                    (key, str(value))
                )
            await db.commit()
    except Exception as e:
        logger.error(f"Error saving config: {e}")

async def save_trade(trade_data: dict):
    """Save trade to database"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO trades (trade_id, entry_time, option_type, strike, expiry, entry_price, qty, mode, index_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data['trade_id'],
            trade_data['entry_time'],
            trade_data['option_type'],
            trade_data['strike'],
            trade_data['expiry'],
            trade_data['entry_price'],
            trade_data['qty'],
            trade_data['mode'],
            trade_data.get('index_name', 'NIFTY'),
            trade_data['created_at']
        ))
        await db.commit()

async def update_trade_exit(trade_id: str, exit_time: str, exit_price: float, pnl: float, exit_reason: str):
    """Update trade with exit details"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            UPDATE trades 
            SET exit_time = ?, exit_price = ?, pnl = ?, exit_reason = ?
            WHERE trade_id = ?
        ''', (exit_time, exit_price, pnl, exit_reason, trade_id))
        await db.commit()

async def get_trades(limit: int = 50) -> list:
    """Get recent trades"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM trades ORDER BY created_at DESC LIMIT ?',
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
