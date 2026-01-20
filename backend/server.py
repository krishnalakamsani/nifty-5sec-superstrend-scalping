from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import json
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import sqlite3
import aiosqlite
from contextlib import asynccontextmanager
import httpx

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(ROOT_DIR / 'logs' / 'bot.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Ensure logs directory exists
(ROOT_DIR / 'logs').mkdir(exist_ok=True)
(ROOT_DIR / 'data').mkdir(exist_ok=True)

# SQLite Database path
DB_PATH = ROOT_DIR / 'data' / 'trading.db'

# Global state
bot_state = {
    "is_running": False,
    "mode": "live",  # paper or live
    "current_position": None,
    "daily_trades": 0,
    "daily_pnl": 0.0,
    "daily_max_loss_triggered": False,
    "last_supertrend_signal": None,
    "nifty_ltp": 0.0,
    "supertrend_value": 0.0,
    "trailing_sl": None,
    "entry_price": 0.0,
    "current_option_ltp": 0.0,
    "max_drawdown": 0.0,
}

# Configuration (can be updated from frontend)
config = {
    "dhan_access_token": "",
    "dhan_client_id": "",
    "order_qty": 50,  # 1 lot = 50 qty
    "max_trades_per_day": 5,
    "daily_max_loss": 2000,
    "trail_start_profit": 10,
    "trail_step": 5,
    "trailing_sl_distance": 10,
    "supertrend_period": 7,
    "supertrend_multiplier": 4,
    "candle_interval": 5,  # seconds
}

# WebSocket connections manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

manager = ConnectionManager()

# Database initialization
async def init_db():
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

# Pydantic models
class ConfigUpdate(BaseModel):
    dhan_access_token: Optional[str] = None
    dhan_client_id: Optional[str] = None
    order_qty: Optional[int] = None
    max_trades_per_day: Optional[int] = None
    daily_max_loss: Optional[float] = None
    trail_start_profit: Optional[float] = None
    trail_step: Optional[float] = None
    trailing_sl_distance: Optional[float] = None

class BotStatus(BaseModel):
    is_running: bool
    mode: str
    market_status: str
    connection_status: str

class Position(BaseModel):
    option_type: Optional[str] = None
    strike: Optional[int] = None
    expiry: Optional[str] = None
    entry_price: float = 0.0
    current_ltp: float = 0.0
    unrealized_pnl: float = 0.0
    trailing_sl: Optional[float] = None
    qty: int = 0

class Trade(BaseModel):
    trade_id: str
    entry_time: str
    exit_time: Optional[str] = None
    option_type: str
    strike: int
    expiry: str
    entry_price: float
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    exit_reason: Optional[str] = None

class DailySummary(BaseModel):
    total_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    daily_stop_triggered: bool = False

class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Load saved config from database
    await load_config()
    yield

app = FastAPI(lifespan=lifespan)
api_router = APIRouter(prefix="/api")

# Helper functions
def get_ist_time():
    """Get current IST time"""
    utc_now = datetime.now(timezone.utc)
    ist = utc_now + timedelta(hours=5, minutes=30)
    return ist

def is_market_open():
    """Check if market is open (9:15 AM - 3:30 PM IST)"""
    ist = get_ist_time()
    market_open = ist.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = ist.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= ist <= market_close and ist.weekday() < 5

def can_take_new_trade():
    """Check if new trades are allowed"""
    ist = get_ist_time()
    cutoff_time = ist.replace(hour=15, minute=20, second=0, microsecond=0)
    return ist < cutoff_time

def should_force_squareoff():
    """Check if it's time to force square off"""
    ist = get_ist_time()
    squareoff_time = ist.replace(hour=15, minute=25, second=0, microsecond=0)
    return ist >= squareoff_time

def round_to_nearest_50(price):
    """Round price to nearest 50 for ATM strike"""
    return round(price / 50) * 50

async def load_config():
    """Load config from database"""
    global config
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

# SuperTrend calculation
class SuperTrend:
    def __init__(self, period=7, multiplier=4):
        self.period = period
        self.multiplier = multiplier
        self.candles = []
        self.atr_values = []
        self.supertrend_values = []
        self.direction = 1  # 1 = GREEN (bullish), -1 = RED (bearish)
    
    def add_candle(self, high, low, close):
        """Add a new candle and calculate SuperTrend"""
        self.candles.append({'high': high, 'low': low, 'close': close})
        
        if len(self.candles) < self.period:
            return None, None
        
        # Calculate True Range
        tr = max(
            high - low,
            abs(high - self.candles[-2]['close']) if len(self.candles) > 1 else 0,
            abs(low - self.candles[-2]['close']) if len(self.candles) > 1 else 0
        )
        
        # Calculate ATR
        if len(self.atr_values) == 0:
            # Initial ATR is simple average of TR
            trs = []
            for i in range(max(0, len(self.candles) - self.period), len(self.candles)):
                if i > 0:
                    prev = self.candles[i-1]
                    curr = self.candles[i]
                    tr_val = max(
                        curr['high'] - curr['low'],
                        abs(curr['high'] - prev['close']),
                        abs(curr['low'] - prev['close'])
                    )
                else:
                    tr_val = self.candles[i]['high'] - self.candles[i]['low']
                trs.append(tr_val)
            atr = sum(trs) / len(trs) if trs else 0
        else:
            atr = (self.atr_values[-1] * (self.period - 1) + tr) / self.period
        
        self.atr_values.append(atr)
        
        # Calculate basic upper and lower bands
        hl2 = (high + low) / 2
        basic_upper = hl2 + (self.multiplier * atr)
        basic_lower = hl2 - (self.multiplier * atr)
        
        # Final bands calculation
        if len(self.supertrend_values) == 0:
            final_upper = basic_upper
            final_lower = basic_lower
        else:
            prev = self.supertrend_values[-1]
            prev_close = self.candles[-2]['close']
            
            final_lower = basic_lower if basic_lower > prev['lower'] or prev_close < prev['lower'] else prev['lower']
            final_upper = basic_upper if basic_upper < prev['upper'] or prev_close > prev['upper'] else prev['upper']
        
        # Direction
        if len(self.supertrend_values) == 0:
            direction = 1 if close > final_upper else -1
        else:
            prev = self.supertrend_values[-1]
            if prev['direction'] == 1:
                direction = -1 if close < final_lower else 1
            else:
                direction = 1 if close > final_upper else -1
        
        self.direction = direction
        supertrend_value = final_lower if direction == 1 else final_upper
        
        self.supertrend_values.append({
            'upper': final_upper,
            'lower': final_lower,
            'value': supertrend_value,
            'direction': direction
        })
        
        # Keep only last 100 values
        if len(self.candles) > 100:
            self.candles = self.candles[-100:]
            self.atr_values = self.atr_values[-100:]
            self.supertrend_values = self.supertrend_values[-100:]
        
        signal = "GREEN" if direction == 1 else "RED"
        return supertrend_value, signal

supertrend_indicator = SuperTrend(period=config['supertrend_period'], multiplier=config['supertrend_multiplier'])

# Dhan API helper class
class DhanAPI:
    BASE_URL = "https://api.dhan.co/v2"
    
    def __init__(self, access_token: str, client_id: str):
        self.access_token = access_token
        self.client_id = client_id
    
    def _headers(self):
        return {
            "access-token": self.access_token,
            "client-id": self.client_id,
            "Content-Type": "application/json"
        }
    
    async def get_nifty_ltp(self) -> float:
        """Get Nifty 50 spot LTP"""
        async with httpx.AsyncClient() as client:
            try:
                # Nifty 50 Index security ID
                response = await client.post(
                    f"{self.BASE_URL}/marketfeed/ltp",
                    json={"NSE_INDEX": [13]},  # 13 is Nifty 50 index
                    headers=self._headers(),
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get('data', {}).get('NSE_INDEX', {}).get('13', {}).get('last_price', 0)
            except Exception as e:
                logger.error(f"Error fetching Nifty LTP: {e}")
        return 0
    
    async def get_option_ltp(self, security_id: str) -> float:
        """Get option LTP"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/marketfeed/ltp",
                    json={"NSE_FNO": [int(security_id)]},
                    headers=self._headers(),
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get('data', {}).get('NSE_FNO', {}).get(security_id, {}).get('last_price', 0)
            except Exception as e:
                logger.error(f"Error fetching option LTP: {e}")
        return 0
    
    async def get_option_chain(self, underlying_scrip: int = 13) -> dict:
        """Get option chain for Nifty"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/optionchain",
                    json={
                        "UnderlyingScrip": underlying_scrip,
                        "UnderlyingSeg": "IDX_I"
                    },
                    headers=self._headers(),
                    timeout=15.0
                )
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                logger.error(f"Error fetching option chain: {e}")
        return {}
    
    async def place_order(self, security_id: str, transaction_type: str, qty: int) -> dict:
        """Place a market order"""
        async with httpx.AsyncClient() as client:
            try:
                order_data = {
                    "dhanClientId": self.client_id,
                    "transactionType": transaction_type,  # BUY or SELL
                    "exchangeSegment": "NSE_FNO",
                    "productType": "INTRADAY",
                    "orderType": "MARKET",
                    "validity": "DAY",
                    "securityId": security_id,
                    "quantity": str(qty),
                    "disclosedQuantity": "0",
                    "price": "0",
                    "triggerPrice": "0"
                }
                response = await client.post(
                    f"{self.BASE_URL}/orders",
                    json=order_data,
                    headers=self._headers(),
                    timeout=15.0
                )
                return response.json()
            except Exception as e:
                logger.error(f"Error placing order: {e}")
                return {"status": "error", "message": str(e)}
    
    async def get_positions(self) -> list:
        """Get current positions"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/positions",
                    headers=self._headers(),
                    timeout=10.0
                )
                if response.status_code == 200:
                    return response.json().get('data', [])
            except Exception as e:
                logger.error(f"Error fetching positions: {e}")
        return []

# Trading Bot Engine
class TradingBot:
    def __init__(self):
        self.running = False
        self.task = None
        self.dhan: Optional[DhanAPI] = None
        self.current_position = None
        self.entry_price = 0.0
        self.trailing_sl = None
        self.highest_profit = 0.0
    
    def initialize_dhan(self):
        if config['dhan_access_token'] and config['dhan_client_id']:
            self.dhan = DhanAPI(config['dhan_access_token'], config['dhan_client_id'])
            return True
        return False
    
    async def start(self):
        if self.running:
            return {"status": "error", "message": "Bot already running"}
        
        if not self.initialize_dhan():
            return {"status": "error", "message": "Dhan API credentials not configured"}
        
        self.running = True
        bot_state['is_running'] = True
        self.task = asyncio.create_task(self.run_loop())
        logger.info("Trading bot started")
        return {"status": "success", "message": "Bot started"}
    
    async def stop(self):
        self.running = False
        bot_state['is_running'] = False
        if self.task:
            self.task.cancel()
        logger.info("Trading bot stopped")
        return {"status": "success", "message": "Bot stopped"}
    
    async def squareoff(self):
        """Force square off current position"""
        if not self.current_position:
            return {"status": "error", "message": "No open position"}
        
        if bot_state['mode'] == 'paper':
            # Paper trading - simulate exit
            exit_price = bot_state['current_option_ltp']
            pnl = (exit_price - self.entry_price) * config['order_qty']
            await self.close_position(exit_price, pnl, "Force Square-off")
            return {"status": "success", "message": f"Position squared off (Paper). PnL: {pnl}"}
        else:
            # Live trading - place actual order
            if self.dhan:
                security_id = self.current_position.get('security_id', '')
                result = await self.dhan.place_order(security_id, "SELL", config['order_qty'])
                if result.get('orderId'):
                    exit_price = bot_state['current_option_ltp']
                    pnl = (exit_price - self.entry_price) * config['order_qty']
                    await self.close_position(exit_price, pnl, "Force Square-off")
                    return {"status": "success", "message": f"Position squared off. PnL: {pnl}"}
        
        return {"status": "error", "message": "Failed to square off"}
    
    async def close_position(self, exit_price: float, pnl: float, reason: str):
        """Close current position and save trade"""
        if not self.current_position:
            return
        
        trade_id = self.current_position.get('trade_id', '')
        
        # Update database
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''
                UPDATE trades 
                SET exit_time = ?, exit_price = ?, pnl = ?, exit_reason = ?
                WHERE trade_id = ?
            ''', (
                datetime.now(timezone.utc).isoformat(),
                exit_price,
                pnl,
                reason,
                trade_id
            ))
            await db.commit()
        
        # Update state
        bot_state['daily_pnl'] += pnl
        bot_state['current_position'] = None
        bot_state['trailing_sl'] = None
        bot_state['entry_price'] = 0
        
        if bot_state['daily_pnl'] < -config['daily_max_loss']:
            bot_state['daily_max_loss_triggered'] = True
        
        if pnl < 0 and abs(pnl) > bot_state['max_drawdown']:
            bot_state['max_drawdown'] = abs(pnl)
        
        self.current_position = None
        self.entry_price = 0
        self.trailing_sl = None
        self.highest_profit = 0
        
        logger.info(f"Position closed: {reason}, PnL: {pnl}")
    
    async def run_loop(self):
        """Main trading loop"""
        logger.info("Trading loop started")
        candle_start_time = datetime.now()
        high, low, close = 0, float('inf'), 0
        
        while self.running:
            try:
                # Check daily reset (9:15 AM IST)
                ist = get_ist_time()
                if ist.hour == 9 and ist.minute == 15:
                    bot_state['daily_trades'] = 0
                    bot_state['daily_pnl'] = 0.0
                    bot_state['daily_max_loss_triggered'] = False
                    bot_state['max_drawdown'] = 0.0
                
                # Force square-off at 3:25 PM
                if should_force_squareoff() and self.current_position:
                    await self.squareoff()
                
                # Check if trading is allowed
                if not is_market_open():
                    await asyncio.sleep(5)
                    continue
                
                if bot_state['daily_max_loss_triggered']:
                    await asyncio.sleep(5)
                    continue
                
                # Fetch market data
                if self.dhan:
                    nifty_ltp = await self.dhan.get_nifty_ltp()
                    if nifty_ltp > 0:
                        bot_state['nifty_ltp'] = nifty_ltp
                        
                        # Update candle data
                        if nifty_ltp > high:
                            high = nifty_ltp
                        if nifty_ltp < low:
                            low = nifty_ltp
                        close = nifty_ltp
                
                # Check if 5-second candle is complete
                elapsed = (datetime.now() - candle_start_time).total_seconds()
                if elapsed >= config['candle_interval']:
                    # Process candle and get SuperTrend signal
                    if high > 0 and low < float('inf'):
                        st_value, signal = supertrend_indicator.add_candle(high, low, close)
                        
                        if st_value and signal:
                            bot_state['supertrend_value'] = st_value
                            bot_state['last_supertrend_signal'] = signal
                            
                            # Trading logic
                            await self.process_signal(signal, close)
                    
                    # Reset candle
                    candle_start_time = datetime.now()
                    high, low, close = 0, float('inf'), 0
                
                # Update position PnL
                if self.current_position:
                    security_id = self.current_position.get('security_id', '')
                    if security_id and self.dhan:
                        option_ltp = await self.dhan.get_option_ltp(security_id)
                        if option_ltp > 0:
                            bot_state['current_option_ltp'] = option_ltp
                            
                            # Check trailing SL
                            await self.check_trailing_sl(option_ltp)
                
                # Broadcast state update
                await manager.broadcast({
                    "type": "state_update",
                    "data": {
                        "nifty_ltp": bot_state['nifty_ltp'],
                        "supertrend_signal": bot_state['last_supertrend_signal'],
                        "supertrend_value": bot_state['supertrend_value'],
                        "position": bot_state['current_position'],
                        "entry_price": bot_state['entry_price'],
                        "current_option_ltp": bot_state['current_option_ltp'],
                        "trailing_sl": bot_state['trailing_sl'],
                        "daily_pnl": bot_state['daily_pnl'],
                        "daily_trades": bot_state['daily_trades'],
                        "is_running": bot_state['is_running'],
                        "mode": bot_state['mode'],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                })
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(5)
    
    async def process_signal(self, signal: str, nifty_ltp: float):
        """Process SuperTrend signal"""
        # Check for position exit on signal reversal
        if self.current_position:
            position_type = self.current_position.get('option_type', '')
            
            # Exit CE on RED signal
            if position_type == 'CE' and signal == 'RED':
                exit_price = bot_state['current_option_ltp']
                pnl = (exit_price - self.entry_price) * config['order_qty']
                await self.close_position(exit_price, pnl, "SuperTrend Reversal")
                return
            
            # Exit PE on GREEN signal
            if position_type == 'PE' and signal == 'GREEN':
                exit_price = bot_state['current_option_ltp']
                pnl = (exit_price - self.entry_price) * config['order_qty']
                await self.close_position(exit_price, pnl, "SuperTrend Reversal")
                return
        
        # Check if new trade is allowed
        if self.current_position:
            return  # Only 1 trade at a time
        
        if not can_take_new_trade():
            return
        
        if bot_state['daily_trades'] >= config['max_trades_per_day']:
            return
        
        # Enter new position
        option_type = 'PE' if signal == 'RED' else 'CE'
        atm_strike = round_to_nearest_50(nifty_ltp)
        
        await self.enter_position(option_type, atm_strike, nifty_ltp)
    
    async def enter_position(self, option_type: str, strike: int, nifty_ltp: float):
        """Enter a new position"""
        # Get nearest weekly expiry (simplified - would need actual expiry dates)
        ist = get_ist_time()
        days_until_thursday = (3 - ist.weekday()) % 7
        if days_until_thursday == 0 and ist.hour >= 15:
            days_until_thursday = 7
        expiry_date = ist + timedelta(days=days_until_thursday)
        expiry = expiry_date.strftime("%Y-%m-%d")
        
        trade_id = f"T{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # In paper mode, simulate entry
        if bot_state['mode'] == 'paper':
            # Simulate option price (rough approximation)
            simulated_price = abs(nifty_ltp - strike) / 10 + 50  # Simplified
            entry_price = simulated_price
            security_id = f"NIFTY{strike}{option_type}"
        else:
            # Live trading - place actual order
            if self.dhan:
                # Would need to get actual security ID from option chain
                chain = await self.dhan.get_option_chain()
                # Find security ID for the strike
                security_id = ""  # Would extract from chain
                
                result = await self.dhan.place_order(security_id, "BUY", config['order_qty'])
                if not result.get('orderId'):
                    logger.error(f"Failed to place entry order: {result}")
                    return
                
                entry_price = result.get('price', 0)
        
        # Save position
        self.current_position = {
            'trade_id': trade_id,
            'option_type': option_type,
            'strike': strike,
            'expiry': expiry,
            'security_id': security_id if bot_state['mode'] == 'live' else f"SIM_{strike}_{option_type}",
            'entry_time': datetime.now(timezone.utc).isoformat()
        }
        self.entry_price = entry_price if bot_state['mode'] == 'live' else 100  # Simulated entry
        self.trailing_sl = None
        self.highest_profit = 0
        
        bot_state['current_position'] = self.current_position
        bot_state['entry_price'] = self.entry_price
        bot_state['daily_trades'] += 1
        
        # Save to database
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''
                INSERT INTO trades (trade_id, entry_time, option_type, strike, expiry, entry_price, qty, mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_id,
                datetime.now(timezone.utc).isoformat(),
                option_type,
                strike,
                expiry,
                self.entry_price,
                config['order_qty'],
                bot_state['mode'],
                datetime.now(timezone.utc).isoformat()
            ))
            await db.commit()
        
        logger.info(f"Entered position: {option_type} {strike} @ {self.entry_price}")
    
    async def check_trailing_sl(self, current_ltp: float):
        """Check and update trailing stop loss"""
        if not self.current_position:
            return
        
        profit_points = current_ltp - self.entry_price
        
        # Update highest profit
        if profit_points > self.highest_profit:
            self.highest_profit = profit_points
        
        # Activate trailing SL if profit >= trail_start_profit
        if profit_points >= config['trail_start_profit']:
            # Calculate trailing SL
            trail_levels = int((self.highest_profit - config['trail_start_profit']) / config['trail_step'])
            new_sl = self.entry_price + (trail_levels * config['trail_step'])
            
            if self.trailing_sl is None or new_sl > self.trailing_sl:
                self.trailing_sl = new_sl
                bot_state['trailing_sl'] = self.trailing_sl
        
        # Check if trailing SL is hit
        if self.trailing_sl and current_ltp <= self.trailing_sl:
            pnl = (current_ltp - self.entry_price) * config['order_qty']
            await self.close_position(current_ltp, pnl, "Trailing SL Hit")

# Global bot instance
trading_bot = TradingBot()

# API Routes
@api_router.get("/")
async def root():
    return {"message": "NiftyAlgo Trading Bot API"}

@api_router.get("/status")
async def get_status():
    return {
        "is_running": bot_state['is_running'],
        "mode": bot_state['mode'],
        "market_status": "open" if is_market_open() else "closed",
        "connection_status": "connected" if config['dhan_access_token'] else "disconnected",
        "daily_max_loss_triggered": bot_state['daily_max_loss_triggered']
    }

@api_router.get("/market/nifty")
async def get_nifty_data():
    return {
        "ltp": bot_state['nifty_ltp'],
        "supertrend_signal": bot_state['last_supertrend_signal'],
        "supertrend_value": bot_state['supertrend_value'],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@api_router.get("/position")
async def get_position():
    if not bot_state['current_position']:
        return {"has_position": False}
    
    unrealized_pnl = (bot_state['current_option_ltp'] - bot_state['entry_price']) * config['order_qty']
    
    return {
        "has_position": True,
        "option_type": bot_state['current_position'].get('option_type'),
        "strike": bot_state['current_position'].get('strike'),
        "expiry": bot_state['current_position'].get('expiry'),
        "entry_price": bot_state['entry_price'],
        "current_ltp": bot_state['current_option_ltp'],
        "unrealized_pnl": unrealized_pnl,
        "trailing_sl": bot_state['trailing_sl'],
        "qty": config['order_qty']
    }

@api_router.get("/trades")
async def get_trades(limit: int = Query(default=50, le=100)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM trades ORDER BY created_at DESC LIMIT ?',
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

@api_router.get("/summary")
async def get_daily_summary():
    return {
        "total_trades": bot_state['daily_trades'],
        "total_pnl": bot_state['daily_pnl'],
        "max_drawdown": bot_state['max_drawdown'],
        "daily_stop_triggered": bot_state['daily_max_loss_triggered']
    }

@api_router.get("/logs")
async def get_logs(level: str = Query(default="all"), limit: int = Query(default=100, le=500)):
    logs = []
    log_file = ROOT_DIR / 'logs' / 'bot.log'
    
    if log_file.exists():
        with open(log_file, 'r') as f:
            lines = f.readlines()[-limit:]
            for line in lines:
                try:
                    parts = line.strip().split(' - ')
                    if len(parts) >= 4:
                        timestamp = parts[0]
                        log_level = parts[2]
                        message = ' - '.join(parts[3:])
                        
                        if level == "all" or level.upper() == log_level:
                            logs.append({
                                "timestamp": timestamp,
                                "level": log_level,
                                "message": message
                            })
                except:
                    pass
    
    return logs

@api_router.get("/config")
async def get_config():
    return {
        "order_qty": config['order_qty'],
        "max_trades_per_day": config['max_trades_per_day'],
        "daily_max_loss": config['daily_max_loss'],
        "trail_start_profit": config['trail_start_profit'],
        "trail_step": config['trail_step'],
        "trailing_sl_distance": config['trailing_sl_distance'],
        "has_credentials": bool(config['dhan_access_token'] and config['dhan_client_id']),
        "mode": bot_state['mode']
    }

@api_router.post("/config/update")
async def update_config(update: ConfigUpdate):
    if update.dhan_access_token is not None:
        config['dhan_access_token'] = update.dhan_access_token
    if update.dhan_client_id is not None:
        config['dhan_client_id'] = update.dhan_client_id
    if update.order_qty is not None:
        config['order_qty'] = update.order_qty
    if update.max_trades_per_day is not None:
        config['max_trades_per_day'] = update.max_trades_per_day
    if update.daily_max_loss is not None:
        config['daily_max_loss'] = update.daily_max_loss
    if update.trail_start_profit is not None:
        config['trail_start_profit'] = update.trail_start_profit
    if update.trail_step is not None:
        config['trail_step'] = update.trail_step
    if update.trailing_sl_distance is not None:
        config['trailing_sl_distance'] = update.trailing_sl_distance
    
    await save_config()
    logger.info("Configuration updated")
    
    return {"status": "success", "message": "Configuration updated"}

@api_router.post("/config/mode")
async def set_mode(mode: str = Query(..., regex="^(paper|live)$")):
    if bot_state['current_position']:
        raise HTTPException(status_code=400, detail="Cannot change mode with open position")
    
    bot_state['mode'] = mode
    logger.info(f"Trading mode changed to: {mode}")
    return {"status": "success", "mode": mode}

@api_router.post("/bot/start")
async def start_bot():
    result = await trading_bot.start()
    return result

@api_router.post("/bot/stop")
async def stop_bot():
    result = await trading_bot.stop()
    return result

@api_router.post("/bot/squareoff")
async def squareoff_position():
    result = await trading_bot.squareoff()
    return result

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat", "timestamp": datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
