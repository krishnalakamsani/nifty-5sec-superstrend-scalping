import React, { useState, useEffect, useRef, useCallback } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";
import { Toaster } from "./components/ui/sonner";
import { toast } from "sonner";
import Dashboard from "./pages/Dashboard";
import "./App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// WebSocket URL
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://');

// Create context for shared state
export const AppContext = React.createContext();

function App() {
  const [botStatus, setBotStatus] = useState({
    is_running: false,
    mode: "live",
    market_status: "closed",
    connection_status: "disconnected",
    daily_max_loss_triggered: false
  });
  const [niftyData, setNiftyData] = useState({
    ltp: 0,
    supertrend_signal: null,
    supertrend_value: 0
  });
  const [position, setPosition] = useState(null);
  const [trades, setTrades] = useState([]);
  const [summary, setSummary] = useState({
    total_trades: 0,
    total_pnl: 0,
    max_drawdown: 0,
    daily_stop_triggered: false
  });
  const [logs, setLogs] = useState([]);
  const [config, setConfig] = useState({
    order_qty: 50,
    max_trades_per_day: 5,
    daily_max_loss: 2000,
    trail_start_profit: 10,
    trail_step: 5,
    trailing_sl_distance: 10,
    has_credentials: false,
    mode: "live"
  });
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  // Fetch initial data
  const fetchData = useCallback(async () => {
    try {
      const [statusRes, niftyRes, positionRes, tradesRes, summaryRes, logsRes, configRes] = await Promise.all([
        axios.get(`${API}/status`),
        axios.get(`${API}/market/nifty`),
        axios.get(`${API}/position`),
        axios.get(`${API}/trades?limit=50`),
        axios.get(`${API}/summary`),
        axios.get(`${API}/logs?limit=100`),
        axios.get(`${API}/config`)
      ]);

      setBotStatus(statusRes.data);
      setNiftyData(niftyRes.data);
      setPosition(positionRes.data);
      setTrades(tradesRes.data);
      setSummary(summaryRes.data);
      setLogs(logsRes.data);
      setConfig(configRes.data);
    } catch (error) {
      console.error("Error fetching data:", error);
    }
  }, []);

  // WebSocket connection
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(`${WS_URL}/ws`);

    ws.onopen = () => {
      setWsConnected(true);
      console.log("WebSocket connected");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "state_update") {
          const update = data.data;
          setNiftyData({
            ltp: update.nifty_ltp,
            supertrend_signal: update.supertrend_signal,
            supertrend_value: update.supertrend_value
          });
          setBotStatus(prev => ({
            ...prev,
            is_running: update.is_running,
            mode: update.mode
          }));
          setSummary(prev => ({
            ...prev,
            total_trades: update.daily_trades,
            total_pnl: update.daily_pnl
          }));
          if (update.position) {
            setPosition({
              has_position: true,
              ...update.position,
              entry_price: update.entry_price,
              current_ltp: update.current_option_ltp,
              trailing_sl: update.trailing_sl,
              unrealized_pnl: (update.current_option_ltp - update.entry_price) * config.order_qty
            });
          } else {
            setPosition({ has_position: false });
          }
        }
      } catch (e) {
        console.error("WebSocket message parse error:", e);
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
      console.log("WebSocket disconnected");
      // Reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    wsRef.current = ws;
  }, [config.order_qty]);

  useEffect(() => {
    fetchData();
    connectWebSocket();

    // Polling fallback for non-WebSocket updates
    const pollInterval = setInterval(fetchData, 5000);

    return () => {
      clearInterval(pollInterval);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [fetchData, connectWebSocket]);

  // Bot control functions
  const startBot = async () => {
    try {
      const res = await axios.post(`${API}/bot/start`);
      toast.success(res.data.message);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to start bot");
    }
  };

  const stopBot = async () => {
    try {
      const res = await axios.post(`${API}/bot/stop`);
      toast.success(res.data.message);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to stop bot");
    }
  };

  const squareOff = async () => {
    try {
      const res = await axios.post(`${API}/bot/squareoff`);
      toast.success(res.data.message);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to square off");
    }
  };

  const updateConfig = async (newConfig) => {
    try {
      await axios.post(`${API}/config/update`, newConfig);
      toast.success("Configuration updated");
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to update config");
    }
  };

  const setMode = async (mode) => {
    try {
      await axios.post(`${API}/config/mode?mode=${mode}`);
      toast.success(`Mode changed to ${mode}`);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to change mode");
    }
  };

  const refreshLogs = async () => {
    try {
      const res = await axios.get(`${API}/logs?limit=100`);
      setLogs(res.data);
    } catch (error) {
      console.error("Failed to refresh logs:", error);
    }
  };

  const contextValue = {
    botStatus,
    niftyData,
    position,
    trades,
    summary,
    logs,
    config,
    wsConnected,
    startBot,
    stopBot,
    squareOff,
    updateConfig,
    setMode,
    refreshLogs,
    fetchData
  };

  return (
    <AppContext.Provider value={contextValue}>
      <div className="min-h-screen bg-white">
        <Toaster position="top-right" richColors />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Dashboard />} />
          </Routes>
        </BrowserRouter>
      </div>
    </AppContext.Provider>
  );
}

export default App;
