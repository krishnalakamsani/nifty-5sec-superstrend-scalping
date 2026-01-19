import React, { useContext, useState } from "react";
import { AppContext } from "@/App";
import { Play, Square, XCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

const ControlsPanel = () => {
  const { botStatus, position, startBot, stopBot, squareOff, setMode } =
    useContext(AppContext);
  const [loading, setLoading] = useState({
    start: false,
    stop: false,
    squareoff: false,
  });

  const handleStart = async () => {
    setLoading((prev) => ({ ...prev, start: true }));
    await startBot();
    setLoading((prev) => ({ ...prev, start: false }));
  };

  const handleStop = async () => {
    setLoading((prev) => ({ ...prev, stop: true }));
    await stopBot();
    setLoading((prev) => ({ ...prev, stop: false }));
  };

  const handleSquareOff = async () => {
    setLoading((prev) => ({ ...prev, squareoff: true }));
    await squareOff();
    setLoading((prev) => ({ ...prev, squareoff: false }));
  };

  const handleModeChange = async (checked) => {
    await setMode(checked ? "live" : "paper");
  };

  const canChangeMode = !position?.has_position;

  return (
    <div className="terminal-card" data-testid="controls-panel">
      <div className="terminal-card-header">
        <h2 className="text-sm font-semibold text-gray-900 font-[Manrope]">
          Controls
        </h2>
      </div>

      <div className="p-4 space-y-4">
        {/* Start/Stop Buttons */}
        <div className="grid grid-cols-2 gap-2">
          <Button
            onClick={handleStart}
            disabled={botStatus.is_running || loading.start}
            className="w-full h-10 bg-emerald-600 hover:bg-emerald-700 text-white rounded-sm btn-active"
            data-testid="start-bot-btn"
          >
            {loading.start ? (
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Play className="w-4 h-4 mr-2" />
            )}
            Start
          </Button>

          <Button
            onClick={handleStop}
            disabled={!botStatus.is_running || loading.stop}
            variant="outline"
            className="w-full h-10 rounded-sm btn-active border-gray-300"
            data-testid="stop-bot-btn"
          >
            {loading.stop ? (
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Square className="w-4 h-4 mr-2" />
            )}
            Stop
          </Button>
        </div>

        {/* Square Off Button */}
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              disabled={!position?.has_position || loading.squareoff}
              variant="destructive"
              className="w-full h-10 rounded-sm btn-active"
              data-testid="squareoff-btn"
            >
              {loading.squareoff ? (
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <XCircle className="w-4 h-4 mr-2" />
              )}
              Square Off Now
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Confirm Square Off</AlertDialogTitle>
              <AlertDialogDescription>
                This will immediately close your current position at market
                price. Are you sure you want to proceed?
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleSquareOff}
                className="bg-red-600 hover:bg-red-700"
              >
                Square Off
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Mode Toggle */}
        <div className="flex items-center justify-between p-3 bg-gray-50 rounded-sm border border-gray-100">
          <div>
            <Label htmlFor="mode-toggle" className="text-sm font-medium">
              Trading Mode
            </Label>
            <p className="text-xs text-gray-500">
              {canChangeMode
                ? "Switch between paper and live"
                : "Close position to change"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`text-xs font-medium ${
                botStatus.mode === "paper" ? "text-blue-600" : "text-gray-400"
              }`}
            >
              Paper
            </span>
            <Switch
              id="mode-toggle"
              checked={botStatus.mode === "live"}
              onCheckedChange={handleModeChange}
              disabled={!canChangeMode}
              data-testid="mode-toggle"
            />
            <span
              className={`text-xs font-medium ${
                botStatus.mode === "live" ? "text-amber-600" : "text-gray-400"
              }`}
            >
              Live
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ControlsPanel;
