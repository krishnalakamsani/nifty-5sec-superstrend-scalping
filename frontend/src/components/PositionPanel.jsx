import React, { useContext } from "react";
import { AppContext } from "../App";
import { TrendingUp, TrendingDown, Target, AlertTriangle } from "lucide-react";

const PositionPanel = () => {
  const { position, config } = useContext(AppContext);

  const hasPosition = position?.has_position;
  const unrealizedPnl = position?.unrealized_pnl || 0;
  const isProfitable = unrealizedPnl >= 0;

  return (
    <div className="terminal-card flex-1" data-testid="position-panel">
      <div className="terminal-card-header">
        <h2 className="text-sm font-semibold text-gray-900 font-[Manrope]">
          Live Position
        </h2>
        {hasPosition && (
          <span
            className={`status-badge ${
              position.option_type === "CE"
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : "bg-red-50 text-red-700 border-red-200"
            }`}
          >
            {position.option_type === "CE" ? (
              <TrendingUp className="w-3 h-3" />
            ) : (
              <TrendingDown className="w-3 h-3" />
            )}
            {position.option_type}
          </span>
        )}
      </div>

      <div className="p-4">
        {hasPosition ? (
          <div className="space-y-4">
            {/* Strike & Expiry */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="label-text">Strike</p>
                <p className="value-text" data-testid="position-strike">
                  {position.strike}
                </p>
              </div>
              <div>
                <p className="label-text">Expiry</p>
                <p className="value-text text-base" data-testid="position-expiry">
                  {position.expiry}
                </p>
              </div>
            </div>

            {/* Entry & Current LTP */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="label-text">Entry Price</p>
                <p className="value-text" data-testid="position-entry-price">
                  ₹{position.entry_price?.toFixed(2)}
                </p>
              </div>
              <div>
                <p className="label-text">Current LTP</p>
                <p
                  className={`value-text ${
                    isProfitable ? "value-positive" : "value-negative"
                  }`}
                  data-testid="position-current-ltp"
                >
                  ₹{position.current_ltp?.toFixed(2)}
                </p>
              </div>
            </div>

            {/* Unrealized PnL */}
            <div className="bg-gray-50 rounded-sm p-3 border border-gray-100">
              <p className="label-text mb-1">Unrealized P&L</p>
              <p
                className={`text-2xl font-bold font-mono tracking-tight ${
                  isProfitable ? "value-positive" : "value-negative"
                }`}
                data-testid="unrealized-pnl"
              >
                {isProfitable ? "+" : ""}₹{unrealizedPnl.toFixed(2)}
              </p>
            </div>

            {/* Trailing SL */}
            <div className="flex items-center gap-2">
              <Target className="w-4 h-4 text-gray-400" />
              <div className="flex-1">
                <p className="label-text">Trailing SL</p>
                <p
                  className="value-text text-base"
                  data-testid="trailing-sl"
                >
                  {position.trailing_sl
                    ? `₹${position.trailing_sl.toFixed(2)}`
                    : "Not Active"}
                </p>
              </div>
            </div>

            {/* Quantity */}
            <div className="text-xs text-gray-500 font-mono">
              Qty: {config.order_qty} | Lot: 1
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-gray-400">
            <AlertTriangle className="w-8 h-8 mb-2" />
            <p className="text-sm font-medium">No Open Position</p>
            <p className="text-xs">Waiting for signal...</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default PositionPanel;
