"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  HeartPulse,
  RefreshCw,
  AlertTriangle,
  ShieldOff,
  Lock,
  Activity,
  Globe,
  Plug,
  CheckCircle2,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import type {
  HealthAggregation,
  BackendHealthEntry,
  EmergencyActionRequest,
  EmergencyActionResponse,
} from "@/lib/types/admin";

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; health: HealthAggregation };

type EmergencyAction = "suspend-all" | "disable-delegations" | "lockdown";

interface EmergencyDialogState {
  open: boolean;
  action: EmergencyAction | null;
  reason: string;
  submitting: boolean;
  result: EmergencyActionResponse | null;
  error: string | null;
}

const EMERGENCY_ACTIONS: Record<
  EmergencyAction,
  { label: string; description: string; icon: typeof AlertTriangle; endpoint: string }
> = {
  "suspend-all": {
    label: "Suspend All Agents",
    description:
      "Immediately suspend all active agents. They will lose access to all services until manually reactivated.",
    icon: AlertTriangle,
    endpoint: "admin/emergency/suspend-all",
  },
  "disable-delegations": {
    label: "Disable All Delegations",
    description:
      "Revoke every active delegation across all agents and users. New delegations can still be created afterwards.",
    icon: ShieldOff,
    endpoint: "admin/emergency/disable-delegations",
  },
  lockdown: {
    label: "Full Lockdown",
    description:
      "Suspend all agents AND revoke all delegations. This is the nuclear option — use only in a confirmed breach.",
    icon: Lock,
    endpoint: "admin/emergency/lockdown",
  },
};

const HEALTH_DOT: Record<string, string> = {
  up: "bg-green-500",
  down: "bg-red-500",
  slow: "bg-yellow-500",
  unknown: "bg-gray-400",
};

const HEALTH_LABEL: Record<string, string> = {
  up: "Healthy",
  down: "Down",
  slow: "Slow",
  unknown: "Unknown",
};

export default function AdminHealthPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [dialog, setDialog] = useState<EmergencyDialogState>({
    open: false,
    action: null,
    reason: "",
    submitting: false,
    result: null,
    error: null,
  });
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await apiClient<HealthAggregation>("admin/health");
      setState({ kind: "data", health: data });
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof Error ? err.message : "Failed to load health data",
      });
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    intervalRef.current = setInterval(fetchHealth, 30_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchHealth]);

  function openEmergencyDialog(action: EmergencyAction) {
    setDialog({
      open: true,
      action,
      reason: "",
      submitting: false,
      result: null,
      error: null,
    });
  }

  function closeDialog() {
    setDialog((prev) => ({ ...prev, open: false }));
  }

  async function executeEmergency() {
    if (!dialog.action || !dialog.reason.trim()) return;
    const config = EMERGENCY_ACTIONS[dialog.action];
    setDialog((prev) => ({ ...prev, submitting: true, error: null }));

    try {
      const body: EmergencyActionRequest = { reason: dialog.reason.trim() };
      const result = await apiClient<EmergencyActionResponse>(config.endpoint, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setDialog((prev) => ({ ...prev, submitting: false, result }));
      fetchHealth();
    } catch (err) {
      setDialog((prev) => ({
        ...prev,
        submitting: false,
        error: err instanceof Error ? err.message : "Action failed",
      }));
    }
  }

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error") {
    return <ErrorCard title="Health Dashboard" message={state.message} retry={fetchHealth} />;
  }

  const { health } = state;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <HeartPulse className="h-6 w-6" />
            Health Dashboard
          </h1>
          <p className="text-muted-foreground">
            Real-time service health monitoring and emergency controls
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchHealth}>
          <RefreshCw className="mr-1.5 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Total Services</p>
          <p className="text-2xl font-bold">{health.total_services}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Healthy</p>
          <p className="text-2xl font-bold text-green-600">{health.services_up}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Unhealthy</p>
          <p className="text-2xl font-bold text-red-600">{health.services_down}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Avg Latency</p>
          <p className="text-2xl font-bold">
            {health.avg_latency_ms != null ? `${Math.round(health.avg_latency_ms)}ms` : "—"}
          </p>
        </Card>
      </div>

      {/* Backend Status Table */}
      <Card>
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">Backend Status</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-6 py-3 text-left font-medium text-muted-foreground">Service</th>
                <th className="px-6 py-3 text-left font-medium text-muted-foreground">Type</th>
                <th className="px-6 py-3 text-left font-medium text-muted-foreground">Health</th>
                <th className="px-6 py-3 text-right font-medium text-muted-foreground">Latency</th>
                <th className="px-6 py-3 text-right font-medium text-muted-foreground">Errors (24h)</th>
                <th className="px-6 py-3 text-right font-medium text-muted-foreground">Last Checked</th>
              </tr>
            </thead>
            <tbody>
              {health.backends.map((backend: BackendHealthEntry) => (
                <tr key={backend.service_id} className="border-b last:border-0 hover:bg-muted/30 transition-colors">
                  <td className="px-6 py-3">
                    <div>
                      <span className="font-medium">{backend.display_name}</span>
                      <span className="ml-1.5 text-xs text-muted-foreground">
                        ({backend.service_id})
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-3">
                    <Badge variant="outline" className="gap-1 text-xs">
                      {backend.backend_type === "rest" ? (
                        <Globe className="h-3 w-3" />
                      ) : (
                        <Plug className="h-3 w-3" />
                      )}
                      {backend.backend_type === "rest" ? "REST" : "MCP"}
                    </Badge>
                  </td>
                  <td className="px-6 py-3">
                    <span className="flex items-center gap-1.5">
                      <span
                        className={cn(
                          "inline-block h-2 w-2 rounded-full",
                          HEALTH_DOT[backend.health_status] ?? HEALTH_DOT.unknown
                        )}
                      />
                      <span className="text-sm">{HEALTH_LABEL[backend.health_status] ?? "Unknown"}</span>
                    </span>
                  </td>
                  <td className="px-6 py-3 text-right">
                    {backend.latency_ms != null ? (
                      <span className="flex items-center justify-end gap-1 text-muted-foreground">
                        <Activity className="h-3 w-3" />
                        {backend.latency_ms}ms
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-6 py-3 text-right">
                    <span
                      className={cn(
                        backend.error_count_24h > 0 ? "text-red-600 font-medium" : "text-muted-foreground"
                      )}
                    >
                      {backend.error_count_24h}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-right text-muted-foreground">
                    {backend.last_checked_at
                      ? new Date(backend.last_checked_at).toLocaleString()
                      : "Never"}
                  </td>
                </tr>
              ))}
              {health.backends.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-muted-foreground">
                    No backends registered
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Emergency Controls */}
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 dark:border-red-900/50 dark:bg-red-950/20">
        <div className="mb-4">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-red-800 dark:text-red-300">
            <AlertTriangle className="h-5 w-5" />
            Emergency Controls
          </h2>
          <p className="text-sm text-red-700/80 dark:text-red-400/80">
            These actions take effect immediately and cannot be automatically undone.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          {(Object.entries(EMERGENCY_ACTIONS) as [EmergencyAction, (typeof EMERGENCY_ACTIONS)[EmergencyAction]][]).map(
            ([key, config]) => {
              const Icon = config.icon;
              return (
                <Button
                  key={key}
                  variant="outline"
                  className="h-auto flex-col items-start gap-1 border-red-300 px-4 py-3 text-left text-red-800 hover:bg-red-100 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950/40"
                  onClick={() => openEmergencyDialog(key)}
                >
                  <span className="flex items-center gap-2 font-semibold">
                    <Icon className="h-4 w-4" />
                    {config.label}
                  </span>
                  <span className="text-xs font-normal text-red-700/70 dark:text-red-400/70">
                    {config.description.split(".")[0]}
                  </span>
                </Button>
              );
            }
          )}
        </div>
      </div>

      {/* Emergency Action Dialog */}
      <Dialog open={dialog.open} onOpenChange={(open: boolean) => !open && closeDialog()}>
        <DialogContent>
          {dialog.action && !dialog.result && (
            <>
              <DialogHeader>
                <DialogTitle className="text-red-700">
                  Confirm: {EMERGENCY_ACTIONS[dialog.action].label}
                </DialogTitle>
                <DialogDescription>
                  {EMERGENCY_ACTIONS[dialog.action].description}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-2 py-2">
                <label htmlFor="emergency-reason" className="text-sm font-medium">
                  Reason (required)
                </label>
                <Input
                  id="emergency-reason"
                  placeholder="e.g. Suspected credential leak in production"
                  value={dialog.reason}
                  onChange={(e) => setDialog((prev) => ({ ...prev, reason: e.target.value }))}
                  disabled={dialog.submitting}
                />
                {dialog.error && (
                  <p className="text-sm text-destructive">{dialog.error}</p>
                )}
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={closeDialog} disabled={dialog.submitting}>
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={executeEmergency}
                  disabled={!dialog.reason.trim() || dialog.submitting}
                >
                  {dialog.submitting ? "Executing…" : "Confirm"}
                </Button>
              </DialogFooter>
            </>
          )}

          {dialog.result && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-green-700">
                  <CheckCircle2 className="h-5 w-5" />
                  Action Executed
                </DialogTitle>
                <DialogDescription>
                  The emergency action completed successfully.
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-2 rounded-md border bg-muted/50 p-4 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Action</span>
                  <span className="font-medium">{dialog.result.action}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Agents Affected</span>
                  <span className="font-medium">{dialog.result.agents_affected}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Delegations Revoked</span>
                  <span className="font-medium">{dialog.result.delegations_revoked}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Executed By</span>
                  <span className="font-medium">{dialog.result.executed_by}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Timestamp</span>
                  <span className="font-medium">
                    {new Date(dialog.result.timestamp).toLocaleString()}
                  </span>
                </div>
              </div>

              <DialogFooter>
                <Button onClick={closeDialog}>Close</Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
