# NiftyAlgo Terminal - Automated Options Trading Bot

A full-stack automated options trading bot for Nifty Index using Dhan Trading API with a real-time dashboard.

## Features

### Trading Strategy
- **Timeframe**: 5-second candles
- **Indicator**: SuperTrend(7, 4) on Nifty Index spot
- **Entry**: BUY ATM PUT on RED signal, BUY ATM CALL on GREEN signal
- **Exit**: SuperTrend reversal or Trailing Stop Loss
- **ATM Selection**: Nifty spot rounded to nearest 50

### Risk Management
- Order quantity: 1 lot (50 qty)
- Max trades/day: 5
- Daily max loss: ₹2000
- No new trades after 3:20 PM IST
- Force square-off at 3:25 PM IST
- Trailing SL with configurable parameters

### Dashboard Features
- Live bot status (Running/Stopped)
- Market status (Open/Closed)
- Paper/Live trading modes
- Real-time Nifty spot tracking with chart
- SuperTrend signal display
- Live position panel with unrealized P&L
- Trailing SL tracking
- Trade history table
- Daily summary (P&L, trades, drawdown)
- Live log viewer with filtering
- Settings panel for API credentials & risk parameters

## Tech Stack

- **Backend**: Python FastAPI
- **Frontend**: React + Tailwind CSS
- **Database**: SQLite
- **Real-time**: WebSocket
- **Charts**: Recharts
- **UI Components**: shadcn/ui

## Setup Instructions

### Prerequisites
- Python 3.8+
- Node.js 16+
- Dhan Trading Account with API access

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your settings

# Run server
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
yarn install

# Create .env file
cp .env.example .env
# Edit .env with your backend URL

# Run development server
yarn start
```

### EC2 Ubuntu Deployment

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python
sudo apt install python3 python3-pip python3-venv -y

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs -y

# Clone repository
git clone <your-repo-url>
cd niftyalgo-terminal

# Setup backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup frontend
cd ../frontend
npm install
npm run build

# Run with PM2 (recommended)
npm install -g pm2
pm2 start server:app --name backend --interpreter python3
pm2 serve build 3000 --name frontend --spa
pm2 save
pm2 startup
```

## API Endpoints

### Status & Market Data
- `GET /api/status` - Bot status
- `GET /api/market/nifty` - Nifty LTP & SuperTrend
- `GET /api/position` - Current position
- `GET /api/trades` - Trade history
- `GET /api/summary` - Daily summary
- `GET /api/logs` - Bot logs
- `GET /api/config` - Current configuration

### Bot Control
- `POST /api/bot/start` - Start trading bot
- `POST /api/bot/stop` - Stop trading bot
- `POST /api/bot/squareoff` - Force square off

### Configuration
- `POST /api/config/update` - Update settings
- `POST /api/config/mode?mode=paper|live` - Switch mode

### WebSocket
- `WS /ws` - Real-time updates

## Configuration

### Environment Variables

**Backend (.env)**
```
MONGO_URL=mongodb://localhost:27017  # Not used, SQLite is default
DB_NAME=trading_db
CORS_ORIGINS=*
```

**Frontend (.env)**
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

### Risk Parameters (via Settings UI)
- `order_qty`: Order quantity (default: 50)
- `max_trades_per_day`: Max trades allowed (default: 5)
- `daily_max_loss`: Stop trading if loss exceeds (default: 2000)
- `trail_start_profit`: Activate trailing at this profit (default: 10)
- `trail_step`: Trail step size (default: 5)
- `trailing_sl_distance`: Distance from peak (default: 10)

## Dhan API Setup

1. Login to [web.dhan.co](https://web.dhan.co)
2. Go to My Profile → DhanHQ Trading APIs
3. Generate Access Token
4. Copy Client ID and Access Token
5. Enter in Settings panel in the dashboard

**Note**: Access token expires daily. Update it each morning before market opens.

## Important Notes

- **Paper Mode**: Simulates trades without real orders
- **Live Mode**: Places real orders with your Dhan account
- **Market Hours**: Trading only during 9:15 AM - 3:30 PM IST
- **Weekdays Only**: No trading on weekends

## Disclaimer

This is for educational purposes only. Trading in derivatives involves substantial risk of loss. Past performance is not indicative of future results. Use at your own risk.

## License

MIT License
