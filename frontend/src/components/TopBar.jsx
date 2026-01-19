import React, { useContext } from "react";
import { AppContext } from "@/App";
import { Settings, Wifi, WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";

const TopBar = ({ onSettingsClick }) => {
  const { botStatus, wsConnected } = useContext(AppContext);

  return (
    <header className="bg-white/80 backdrop-blur-md border-b border-gray-200 px-4 lg:px-6 py-3">
      <div className="flex items-center justify-between">
        {/* Logo & Title */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-sm flex items-center justify-center">
            <span className="text-white font-bold text-sm font-mono">NA</span>
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-900 tracking-tight font-[Manrope]">
              NiftyAlgo Terminal
            </h1>
            <p className="text-[10px] uppercase tracking-wider text-gray-500 font-bold">
              Automated Options Trading
            </p>
          </div>
        </div>

        {/* Status Badges */}
        <div className="flex items-center gap-3">
          {/* Bot Status */}
          <div
            className={`status-badge ${
              botStatus.is_running ? "status-running" : "status-stopped"
            }`}
            data-testid="bot-status-badge"
          >
            <span
              className={`w-2 h-2 rounded-full ${
                botStatus.is_running
                  ? "bg-emerald-500 pulse-dot"
                  : "bg-gray-400"
              }`}
            />
            {botStatus.is_running ? "Running" : "Stopped"}
          </div>

          {/* Market Status */}
          <div
            className={`status-badge ${
              botStatus.market_status === "open"
                ? "status-running"
                : "status-stopped"
            }`}
            data-testid="market-status-badge"
          >
            {botStatus.market_status === "open" ? "Market Open" : "Market Closed"}
          </div>

          {/* Mode Badge */}
          <div
            className={`status-badge ${
              botStatus.mode === "live"
                ? "bg-amber-50 text-amber-700 border-amber-200"
                : "bg-blue-50 text-blue-700 border-blue-200"
            }`}
            data-testid="mode-badge"
          >
            {botStatus.mode === "live" ? "LIVE" : "PAPER"}
          </div>

          {/* WebSocket Status */}
          <div
            className={`status-badge ${
              wsConnected ? "status-running" : "status-error"
            }`}
            data-testid="ws-status-badge"
          >
            {wsConnected ? (
              <Wifi className="w-3 h-3" />
            ) : (
              <WifiOff className="w-3 h-3" />
            )}
            {wsConnected ? "Connected" : "Disconnected"}
          </div>

          {/* Settings Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={onSettingsClick}
            className="h-8 px-3 rounded-sm btn-active"
            data-testid="settings-btn"
          >
            <Settings className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </header>
  );
};

export default TopBar;
