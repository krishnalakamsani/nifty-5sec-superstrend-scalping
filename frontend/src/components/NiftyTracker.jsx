import React, { useContext, useEffect, useState, useRef } from "react";
import { AppContext } from "@/App";
import { TrendingUp, TrendingDown, Activity } from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

const NiftyTracker = () => {
  const { niftyData } = useContext(AppContext);
  const [priceHistory, setPriceHistory] = useState([]);
  const [flashClass, setFlashClass] = useState("");
  const prevLtpRef = useRef(niftyData.ltp);

  // Update price history for chart
  useEffect(() => {
    if (niftyData.ltp > 0) {
      setPriceHistory((prev) => {
        const newEntry = {
          time: new Date().toLocaleTimeString("en-IN", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          }),
          price: niftyData.ltp,
          supertrend: niftyData.supertrend_value,
        };

        const updated = [...prev, newEntry].slice(-60); // Keep last 60 data points
        return updated;
      });

      // Flash effect on price change
      if (niftyData.ltp !== prevLtpRef.current) {
        setFlashClass(
          niftyData.ltp > prevLtpRef.current ? "flash-green" : "flash-red"
        );
        setTimeout(() => setFlashClass(""), 300);
        prevLtpRef.current = niftyData.ltp;
      }
    }
  }, [niftyData.ltp, niftyData.supertrend_value]);

  const isGreen = niftyData.supertrend_signal === "GREEN";
  const signalColor = isGreen ? "#059669" : "#DC2626";

  return (
    <div className="terminal-card" data-testid="nifty-tracker">
      <div className="terminal-card-header">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-600" />
          <h2 className="text-sm font-semibold text-gray-900 font-[Manrope]">
            NIFTY 50 Index
          </h2>
        </div>
        <div
          className={`status-badge ${
            isGreen ? "status-running" : "status-error"
          }`}
          data-testid="supertrend-signal"
        >
          {isGreen ? (
            <TrendingUp className="w-3 h-3" />
          ) : (
            <TrendingDown className="w-3 h-3" />
          )}
          SuperTrend: {niftyData.supertrend_signal || "N/A"}
        </div>
      </div>

      <div className="p-4">
        {/* Price Display */}
        <div className="flex items-baseline gap-4 mb-4">
          <div className={`rounded-sm p-2 ${flashClass}`}>
            <p className="label-text">NIFTY LTP</p>
            <p
              className="text-3xl font-bold font-mono tracking-tight text-gray-900"
              data-testid="nifty-ltp"
            >
              {niftyData.ltp > 0 ? niftyData.ltp.toLocaleString("en-IN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              }) : "—"}
            </p>
          </div>

          <div>
            <p className="label-text">SuperTrend Value</p>
            <p
              className="text-lg font-mono tracking-tight"
              style={{ color: signalColor }}
              data-testid="supertrend-value"
            >
              {niftyData.supertrend_value > 0
                ? niftyData.supertrend_value.toLocaleString("en-IN", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })
                : "—"}
            </p>
          </div>

          <div className="ml-auto text-right">
            <p className="label-text">Last Update</p>
            <p className="text-sm font-mono text-gray-600">
              {new Date().toLocaleTimeString("en-IN")}
            </p>
          </div>
        </div>

        {/* Price Chart */}
        <div className="h-48 bg-gray-50 border border-gray-100 rounded-sm">
          {priceHistory.length > 2 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={priceHistory}
                margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563EB" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="time"
                  tick={{ fontSize: 10, fill: "#9CA3AF" }}
                  axisLine={false}
                  tickLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fontSize: 10, fill: "#9CA3AF" }}
                  axisLine={false}
                  tickLine={false}
                  width={60}
                  tickFormatter={(value) => value.toFixed(0)}
                />
                {niftyData.supertrend_value > 0 && (
                  <ReferenceLine
                    y={niftyData.supertrend_value}
                    stroke={signalColor}
                    strokeDasharray="3 3"
                    strokeWidth={1}
                  />
                )}
                <Area
                  type="monotone"
                  dataKey="price"
                  stroke="#2563EB"
                  strokeWidth={2}
                  fill="url(#priceGradient)"
                  dot={false}
                  animationDuration={0}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-gray-400 text-sm">
              Waiting for market data...
            </div>
          )}
        </div>

        {/* Info Bar */}
        <div className="mt-3 flex items-center justify-between text-xs text-gray-500 font-mono">
          <span>Timeframe: 5 seconds</span>
          <span>SuperTrend(7, 4)</span>
          <span>{priceHistory.length} candles</span>
        </div>
      </div>
    </div>
  );
};

export default NiftyTracker;
