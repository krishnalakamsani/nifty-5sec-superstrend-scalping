# Trading Bot Engine
import asyncio
from datetime import datetime, timezone, timedelta
import logging
import random

from config import bot_state, config, DB_PATH
from indices import get_index_config, round_to_strike
from utils import get_ist_time, is_market_open, can_take_new_trade, should_force_squareoff
from indicators import SuperTrend
from dhan_api import DhanAPI
from database import save_trade, update_trade_exit
import aiosqlite

logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self):
        self.running = False
        self.task = None
        self.dhan = None
        self.current_position = None
        self.entry_price = 0.0
        self.trailing_sl = None
        self.highest_profit = 0.0
        self.supertrend = SuperTrend(
            period=config['supertrend_period'],
            multiplier=config['supertrend_multiplier']
        )
        self.last_exit_candle_time = None
    
    def initialize_dhan(self):
        """Initialize Dhan API connection"""
        if config['dhan_access_token'] and config['dhan_client_id']:
            self.dhan = DhanAPI(config['dhan_access_token'], config['dhan_client_id'])
            return True
        return False
    
    def reset_supertrend(self):
        """Reset SuperTrend indicator"""
        self.supertrend = SuperTrend(
            period=config['supertrend_period'],
            multiplier=config['supertrend_multiplier']
        )
    
    async def start(self):
        """Start the trading bot"""
        if self.running:
            return {"status": "error", "message": "Bot already running"}
        
        if not self.initialize_dhan():
            return {"status": "error", "message": "Dhan API credentials not configured"}
        
        self.running = True
        bot_state['is_running'] = True
        self.reset_supertrend()
        self.task = asyncio.create_task(self.run_loop())
        logger.info(f"Trading bot started for {config['selected_index']}")
        return {"status": "success", "message": f"Bot started for {config['selected_index']}"}
    
    async def stop(self):
        """Stop the trading bot"""
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
        
        index_name = config['selected_index']
        index_config = get_index_config(index_name)
        qty = config['order_qty'] * index_config['lot_size']
        
        if bot_state['mode'] == 'paper':
            exit_price = bot_state['current_option_ltp']
            pnl = (exit_price - self.entry_price) * qty
            await self.close_position(exit_price, pnl, "Force Square-off")
            return {"status": "success", "message": f"Position squared off (Paper). PnL: {pnl:.2f}"}
        else:
            if self.dhan:
                security_id = self.current_position.get('security_id', '')
                result = await self.dhan.place_order(security_id, "SELL", qty)
                if result.get('orderId') or result.get('status') == 'success':
                    exit_price = bot_state['current_option_ltp']
                    pnl = (exit_price - self.entry_price) * qty
                    await self.close_position(exit_price, pnl, "Force Square-off")
                    return {"status": "success", "message": f"Position squared off. PnL: {pnl:.2f}"}
        
        return {"status": "error", "message": "Failed to square off"}
    
    async def close_position(self, exit_price: float, pnl: float, reason: str):
        """Close current position and save trade"""
        if not self.current_position:
            return
        
        trade_id = self.current_position.get('trade_id', '')
        
        # Update database
        await update_trade_exit(
            trade_id=trade_id,
            exit_time=datetime.now(timezone.utc).isoformat(),
            exit_price=exit_price,
            pnl=pnl,
            exit_reason=reason
        )
        
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
        
        logger.info(f"Position closed: {reason}, PnL: {pnl:.2f}")
    
    async def run_loop(self):
        """Main trading loop"""
        logger.info("Trading loop started")
        candle_start_time = datetime.now()
        high, low, close = 0, float('inf'), 0
        
        while self.running:
            try:
                index_name = config['selected_index']
                index_config = get_index_config(index_name)
                
                # Check daily reset (9:15 AM IST)
                ist = get_ist_time()
                if ist.hour == 9 and ist.minute == 15:
                    bot_state['daily_trades'] = 0
                    bot_state['daily_pnl'] = 0.0
                    bot_state['daily_max_loss_triggered'] = False
                    bot_state['max_drawdown'] = 0.0
                    self.last_exit_candle_time = None
                
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
                    has_position = self.current_position is not None
                    option_security_id = None
                    
                    if has_position:
                        security_id = self.current_position.get('security_id', '')
                        if security_id and not security_id.startswith('SIM_'):
                            option_security_id = int(security_id)
                    
                    # Fetch Index + Option LTP in single call if position exists
                    if option_security_id:
                        index_ltp, option_ltp = self.dhan.get_index_and_option_ltp(index_name, option_security_id)
                        if index_ltp > 0:
                            bot_state['index_ltp'] = index_ltp
                        if option_ltp > 0:
                            option_ltp = round(option_ltp / 0.05) * 0.05
                            bot_state['current_option_ltp'] = round(option_ltp, 2)
                    else:
                        index_ltp = self.dhan.get_index_ltp(index_name)
                        if index_ltp > 0:
                            bot_state['index_ltp'] = index_ltp
                    
                    # Update candle data
                    index_ltp = bot_state['index_ltp']
                    if index_ltp > 0:
                        if index_ltp > high:
                            high = index_ltp
                        if index_ltp < low:
                            low = index_ltp
                        close = index_ltp
                
                # Check if candle is complete
                elapsed = (datetime.now() - candle_start_time).total_seconds()
                if elapsed >= config['candle_interval']:
                    current_candle_time = datetime.now()
                    
                    if high > 0 and low < float('inf'):
                        st_value, signal = self.supertrend.add_candle(high, low, close)
                        
                        if st_value and signal:
                            bot_state['supertrend_value'] = st_value
                            bot_state['last_supertrend_signal'] = signal
                            
                            logger.info(f"Candle close: H={high:.2f} L={low:.2f} C={close:.2f} | SuperTrend={signal}")
                            
                            # Check trailing SL on candle close
                            if self.current_position:
                                option_ltp = bot_state['current_option_ltp']
                                sl_hit = await self.check_trailing_sl_on_close(option_ltp)
                                
                                if sl_hit:
                                    self.last_exit_candle_time = current_candle_time
                                    logger.info("Trailing SL hit on candle close")
                            
                            # Trading logic
                            can_trade = True
                            if self.last_exit_candle_time:
                                time_since_exit = (current_candle_time - self.last_exit_candle_time).total_seconds()
                                if time_since_exit < config['candle_interval']:
                                    can_trade = False
                                    logger.info(f"Waiting for candle close after exit ({time_since_exit:.1f}s)")
                            
                            if can_trade:
                                exited = await self.process_signal_on_close(signal, close)
                                if exited:
                                    self.last_exit_candle_time = current_candle_time
                    
                    # Reset candle
                    candle_start_time = datetime.now()
                    high, low, close = 0, float('inf'), 0
                
                # Handle paper mode simulation
                if self.current_position:
                    security_id = self.current_position.get('security_id', '')
                    
                    if security_id.startswith('SIM_'):
                        strike = self.current_position.get('strike', 0)
                        option_type = self.current_position.get('option_type', '')
                        index_ltp = bot_state['index_ltp']
                        
                        if strike and index_ltp:
                            distance_from_atm = abs(index_ltp - strike)
                            
                            if option_type == 'CE':
                                intrinsic = max(0, index_ltp - strike)
                            else:
                                intrinsic = max(0, strike - index_ltp)
                            
                            atm_time_value = 150
                            time_decay_factor = max(0, 1 - (distance_from_atm / 500))
                            time_value = atm_time_value * time_decay_factor
                            
                            simulated_ltp = intrinsic + time_value
                            tick_movement = random.choice([-0.10, -0.05, 0, 0.05, 0.10])
                            simulated_ltp += tick_movement
                            
                            simulated_ltp = round(simulated_ltp / 0.05) * 0.05
                            simulated_ltp = max(0.05, round(simulated_ltp, 2))
                            
                            bot_state['current_option_ltp'] = simulated_ltp
                
                # Broadcast state update
                await self.broadcast_state()
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(5)
    
    async def broadcast_state(self):
        """Broadcast current state to WebSocket clients"""
        from server import manager
        
        await manager.broadcast({
            "type": "state_update",
            "data": {
                "index_ltp": bot_state['index_ltp'],
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
                "selected_index": config['selected_index'],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        })
    
    async def check_trailing_sl(self, current_ltp: float):
        """Update trailing SL values"""
        if not self.current_position:
            return
        
        profit_points = current_ltp - self.entry_price
        
        if profit_points > self.highest_profit:
            self.highest_profit = profit_points
        
        if profit_points >= config['trail_start_profit']:
            trail_levels = int((self.highest_profit - config['trail_start_profit']) / config['trail_step'])
            new_sl = self.entry_price + (trail_levels * config['trail_step'])
            
            if self.trailing_sl is None or new_sl > self.trailing_sl:
                self.trailing_sl = new_sl
                bot_state['trailing_sl'] = self.trailing_sl
    
    async def check_trailing_sl_on_close(self, current_ltp: float) -> bool:
        """Check if trailing SL is hit on candle close"""
        if not self.current_position:
            return False
        
        await self.check_trailing_sl(current_ltp)
        
        if self.trailing_sl and current_ltp <= self.trailing_sl:
            index_config = get_index_config(config['selected_index'])
            qty = config['order_qty'] * index_config['lot_size']
            pnl = (current_ltp - self.entry_price) * qty
            logger.info(f"Trailing SL hit: LTP={current_ltp}, SL={self.trailing_sl}")
            await self.close_position(current_ltp, pnl, "Trailing SL Hit")
            return True
        
        return False
    
    async def process_signal_on_close(self, signal: str, index_ltp: float) -> bool:
        """Process SuperTrend signal on candle close"""
        exited = False
        index_name = config['selected_index']
        index_config = get_index_config(index_name)
        qty = config['order_qty'] * index_config['lot_size']
        
        # Check for exit on signal reversal
        if self.current_position:
            position_type = self.current_position.get('option_type', '')
            
            if position_type == 'CE' and signal == 'RED':
                exit_price = bot_state['current_option_ltp']
                pnl = (exit_price - self.entry_price) * qty
                logger.info("SuperTrend reversal: Exiting CE position")
                await self.close_position(exit_price, pnl, "SuperTrend Reversal")
                return True
            
            if position_type == 'PE' and signal == 'GREEN':
                exit_price = bot_state['current_option_ltp']
                pnl = (exit_price - self.entry_price) * qty
                logger.info("SuperTrend reversal: Exiting PE position")
                await self.close_position(exit_price, pnl, "SuperTrend Reversal")
                return True
        
        # Check if new trade allowed
        if self.current_position:
            return exited
        
        if not can_take_new_trade():
            return exited
        
        if bot_state['daily_trades'] >= config['max_trades_per_day']:
            return exited
        
        # Enter new position
        option_type = 'PE' if signal == 'RED' else 'CE'
        atm_strike = round_to_strike(index_ltp, index_name)
        
        logger.info(f"Candle close entry: {index_name} {option_type} @ strike {atm_strike}")
        await self.enter_position(option_type, atm_strike, index_ltp)
        
        return exited
    
    async def enter_position(self, option_type: str, strike: int, index_ltp: float):
        """Enter a new position"""
        index_name = config['selected_index']
        index_config = get_index_config(index_name)
        qty = config['order_qty'] * index_config['lot_size']
        
        trade_id = f"T{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Get expiry
        expiry = await self.dhan.get_nearest_expiry(index_name) if self.dhan else None
        if not expiry:
            ist = get_ist_time()
            expiry_day = index_config['expiry_day']
            days_until_expiry = (expiry_day - ist.weekday()) % 7
            if days_until_expiry == 0 and ist.hour >= 15:
                days_until_expiry = 7
            expiry_date = ist + timedelta(days=days_until_expiry)
            expiry = expiry_date.strftime("%Y-%m-%d")
        
        entry_price = 0
        security_id = ""
        
        # Get real entry price
        if self.dhan:
            try:
                security_id = await self.dhan.get_atm_option_security_id(index_name, strike, option_type, expiry)
                
                if security_id:
                    option_ltp = await self.dhan.get_option_ltp(
                        security_id=security_id,
                        strike=strike,
                        option_type=option_type,
                        expiry=expiry,
                        index_name=index_name
                    )
                    if option_ltp > 0:
                        entry_price = round(option_ltp / 0.05) * 0.05
                        entry_price = round(entry_price, 2)
                        logger.info(f"Got real entry price: {entry_price}")
            except Exception as e:
                logger.error(f"Error getting entry price: {e}")
        
        # Paper mode
        if bot_state['mode'] == 'paper':
            if not security_id:
                security_id = f"SIM_{index_name}_{strike}_{option_type}"
            
            if entry_price <= 0:
                distance = abs(index_ltp - strike)
                intrinsic = max(0, index_ltp - strike) if option_type == 'CE' else max(0, strike - index_ltp)
                time_value = 150 * max(0, 1 - (distance / 500))
                entry_price = round((intrinsic + time_value) / 0.05) * 0.05
                entry_price = round(entry_price, 2)
            
            logger.info(f"Paper trade: {index_name} {option_type} {strike} @ {entry_price}")
        
        # Live mode
        else:
            if not self.dhan:
                logger.error("Dhan API not initialized")
                return
            
            if not security_id:
                logger.error(f"Could not find security ID for {index_name} {strike} {option_type}")
                return
            
            result = await self.dhan.place_order(security_id, "BUY", qty)
            logger.info(f"Order result: {result}")
            
            if not result.get('orderId') and result.get('status') != 'success':
                logger.error(f"Failed to place order: {result}")
                return
            
            filled_price = result.get('price', 0) or result.get('averagePrice', 0)
            if filled_price > 0:
                entry_price = filled_price
            
            logger.info(f"Live trade: {index_name} {option_type} {strike} @ {entry_price}")
        
        # Save position
        self.current_position = {
            'trade_id': trade_id,
            'option_type': option_type,
            'strike': strike,
            'expiry': expiry,
            'security_id': security_id,
            'index_name': index_name,
            'entry_time': datetime.now(timezone.utc).isoformat()
        }
        self.entry_price = entry_price
        self.trailing_sl = None
        self.highest_profit = 0
        
        bot_state['current_position'] = self.current_position
        bot_state['entry_price'] = self.entry_price
        bot_state['daily_trades'] += 1
        bot_state['current_option_ltp'] = entry_price
        
        # Save to database
        await save_trade({
            'trade_id': trade_id,
            'entry_time': datetime.now(timezone.utc).isoformat(),
            'option_type': option_type,
            'strike': strike,
            'expiry': expiry,
            'entry_price': self.entry_price,
            'qty': qty,
            'mode': bot_state['mode'],
            'index_name': index_name,
            'created_at': datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"Entered position: {index_name} {option_type} {strike} @ {self.entry_price}")


# Global bot instance
trading_bot = TradingBot()
