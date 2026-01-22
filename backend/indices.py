# Index configurations for trading
# Each index has different security ID, lot size, strike interval, etc.

INDICES = {
    "NIFTY": {
        "name": "NIFTY 50",
        "security_id": 13,
        "exchange_segment": "IDX_I",
        "lot_size": 50,
        "strike_interval": 50,  # Round to nearest 50
        "expiry_day": 1,  # Tuesday (0=Monday, 1=Tuesday, etc.)
        "trading_symbol": "NIFTY",
    },
    "BANKNIFTY": {
        "name": "BANK NIFTY",
        "security_id": 25,
        "exchange_segment": "IDX_I",
        "lot_size": 15,
        "strike_interval": 100,  # Round to nearest 100
        "expiry_day": 2,  # Wednesday
        "trading_symbol": "BANKNIFTY",
    },
    "SENSEX": {
        "name": "SENSEX",
        "security_id": 51,
        "exchange_segment": "BSE_INDEX",
        "lot_size": 10,
        "strike_interval": 100,  # Round to nearest 100
        "expiry_day": 4,  # Friday
        "trading_symbol": "SENSEX",
    },
    "FINNIFTY": {
        "name": "FINNIFTY",
        "security_id": 27,
        "exchange_segment": "IDX_I",
        "lot_size": 25,
        "strike_interval": 50,
        "expiry_day": 1,  # Tuesday
        "trading_symbol": "FINNIFTY",
    },
    "MIDCPNIFTY": {
        "name": "MIDCAP NIFTY",
        "security_id": 442,
        "exchange_segment": "IDX_I",
        "lot_size": 50,
        "strike_interval": 25,
        "expiry_day": 0,  # Monday
        "trading_symbol": "MIDCPNIFTY",
    }
}

def get_index_config(index_name: str) -> dict:
    """Get configuration for an index"""
    return INDICES.get(index_name.upper(), INDICES["NIFTY"])

def get_available_indices() -> list:
    """Get list of available indices"""
    return list(INDICES.keys())

def round_to_strike(price: float, index_name: str) -> int:
    """Round price to nearest strike for the given index"""
    config = get_index_config(index_name)
    interval = config["strike_interval"]
    return round(price / interval) * interval
