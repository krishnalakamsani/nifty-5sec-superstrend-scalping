import React, { useContext, useState } from "react";
import { AppContext } from "@/App";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Key, Settings, ShieldCheck, Eye, EyeOff, Save } from "lucide-react";

const SettingsPanel = ({ onClose }) => {
  const { config, updateConfig } = useContext(AppContext);

  // API Credentials
  const [accessToken, setAccessToken] = useState("");
  const [clientId, setClientId] = useState("");
  const [showToken, setShowToken] = useState(false);

  // Risk Parameters
  const [orderQty, setOrderQty] = useState(config.order_qty);
  const [maxTrades, setMaxTrades] = useState(config.max_trades_per_day);
  const [maxLoss, setMaxLoss] = useState(config.daily_max_loss);
  const [trailStart, setTrailStart] = useState(config.trail_start_profit);
  const [trailStep, setTrailStep] = useState(config.trail_step);
  const [trailDistance, setTrailDistance] = useState(config.trailing_sl_distance);

  const [saving, setSaving] = useState(false);

  const handleSaveCredentials = async () => {
    if (!accessToken || !clientId) {
      return;
    }
    setSaving(true);
    await updateConfig({
      dhan_access_token: accessToken,
      dhan_client_id: clientId,
    });
    setAccessToken("");
    setClientId("");
    setSaving(false);
  };

  const handleSaveRiskParams = async () => {
    setSaving(true);
    await updateConfig({
      order_qty: orderQty,
      max_trades_per_day: maxTrades,
      daily_max_loss: maxLoss,
      trail_start_profit: trailStart,
      trail_step: trailStep,
      trailing_sl_distance: trailDistance,
    });
    setSaving(false);
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[500px]" data-testid="settings-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-[Manrope]">
            <Settings className="w-5 h-5" />
            Settings
          </DialogTitle>
          <DialogDescription>
            Configure API credentials and risk parameters
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="credentials" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="credentials" className="text-xs">
              <Key className="w-3 h-3 mr-1" />
              API Credentials
            </TabsTrigger>
            <TabsTrigger value="risk" className="text-xs">
              <ShieldCheck className="w-3 h-3 mr-1" />
              Risk Parameters
            </TabsTrigger>
          </TabsList>

          {/* API Credentials Tab */}
          <TabsContent value="credentials" className="space-y-4 mt-4">
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-sm text-xs text-amber-800">
              <strong>Note:</strong> Dhan access token expires daily. Update it
              here each morning before trading.
            </div>

            <div className="space-y-3">
              <div>
                <Label htmlFor="client-id">Client ID</Label>
                <Input
                  id="client-id"
                  placeholder="Enter your Dhan Client ID"
                  value={clientId}
                  onChange={(e) => setClientId(e.target.value)}
                  className="mt-1 rounded-sm"
                  data-testid="client-id-input"
                />
              </div>

              <div>
                <Label htmlFor="access-token">Access Token</Label>
                <div className="relative mt-1">
                  <Input
                    id="access-token"
                    type={showToken ? "text" : "password"}
                    placeholder="Enter your Dhan Access Token"
                    value={accessToken}
                    onChange={(e) => setAccessToken(e.target.value)}
                    className="pr-10 rounded-sm"
                    data-testid="access-token-input"
                  />
                  <button
                    type="button"
                    onClick={() => setShowToken(!showToken)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showToken ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2">
                <span
                  className={`text-xs ${
                    config.has_credentials
                      ? "text-emerald-600"
                      : "text-amber-600"
                  }`}
                >
                  {config.has_credentials
                    ? "✓ Credentials configured"
                    : "⚠ No credentials set"}
                </span>
                <Button
                  onClick={handleSaveCredentials}
                  disabled={saving || !accessToken || !clientId}
                  size="sm"
                  className="rounded-sm btn-active"
                  data-testid="save-credentials-btn"
                >
                  <Save className="w-3 h-3 mr-1" />
                  {saving ? "Saving..." : "Save Credentials"}
                </Button>
              </div>
            </div>

            <div className="text-xs text-gray-500 pt-2 border-t border-gray-100">
              Get your credentials from{" "}
              <a
                href="https://web.dhan.co"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                web.dhan.co
              </a>{" "}
              → My Profile → DhanHQ Trading APIs
            </div>
          </TabsContent>

          {/* Risk Parameters Tab */}
          <TabsContent value="risk" className="space-y-4 mt-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="order-qty">Order Quantity</Label>
                <Input
                  id="order-qty"
                  type="number"
                  value={orderQty}
                  onChange={(e) => setOrderQty(parseInt(e.target.value))}
                  className="mt-1 rounded-sm"
                  data-testid="order-qty-input"
                />
                <p className="text-xs text-gray-500 mt-1">1 lot = 50 qty</p>
              </div>

              <div>
                <Label htmlFor="max-trades">Max Trades/Day</Label>
                <Input
                  id="max-trades"
                  type="number"
                  value={maxTrades}
                  onChange={(e) => setMaxTrades(parseInt(e.target.value))}
                  className="mt-1 rounded-sm"
                  data-testid="max-trades-input"
                />
              </div>

              <div>
                <Label htmlFor="max-loss">Daily Max Loss (₹)</Label>
                <Input
                  id="max-loss"
                  type="number"
                  value={maxLoss}
                  onChange={(e) => setMaxLoss(parseFloat(e.target.value))}
                  className="mt-1 rounded-sm"
                  data-testid="max-loss-input"
                />
              </div>

              <div>
                <Label htmlFor="trail-start">Trail Start Profit</Label>
                <Input
                  id="trail-start"
                  type="number"
                  value={trailStart}
                  onChange={(e) => setTrailStart(parseFloat(e.target.value))}
                  className="mt-1 rounded-sm"
                  data-testid="trail-start-input"
                />
                <p className="text-xs text-gray-500 mt-1">Points</p>
              </div>

              <div>
                <Label htmlFor="trail-step">Trail Step</Label>
                <Input
                  id="trail-step"
                  type="number"
                  value={trailStep}
                  onChange={(e) => setTrailStep(parseFloat(e.target.value))}
                  className="mt-1 rounded-sm"
                  data-testid="trail-step-input"
                />
                <p className="text-xs text-gray-500 mt-1">Points</p>
              </div>

              <div>
                <Label htmlFor="trail-distance">Trailing SL Distance</Label>
                <Input
                  id="trail-distance"
                  type="number"
                  value={trailDistance}
                  onChange={(e) => setTrailDistance(parseFloat(e.target.value))}
                  className="mt-1 rounded-sm"
                  data-testid="trail-distance-input"
                />
                <p className="text-xs text-gray-500 mt-1">Points</p>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button
                onClick={handleSaveRiskParams}
                disabled={saving}
                size="sm"
                className="rounded-sm btn-active"
                data-testid="save-risk-params-btn"
              >
                <Save className="w-3 h-3 mr-1" />
                {saving ? "Saving..." : "Save Parameters"}
              </Button>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
};

export default SettingsPanel;
