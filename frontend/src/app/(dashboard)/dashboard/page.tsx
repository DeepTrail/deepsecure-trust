"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiClient, ApiError } from "@/lib/api/client";
import type { AuditEvent, AuditEventsResponse } from "@/lib/types/audit";
import { useAgentNames } from "@/hooks/useAgentNames";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import {
  Bot,
  Shield,
  ScrollText,
  Activity,
  Sparkles,
  CheckCircle2,
  XCircle,
  ArrowRight,
  Clock,
  ShieldAlert,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { checkOnboardingStatus } from "@/lib/auth/onboarding";

interface DashboardData {
  agentCount: number;
  policyCount: number;
  recentEvents: AuditEvent[];
}

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; data: DashboardData };

function EventDetailPanel({ event }: { event: AuditEvent }) {
  return (
    <div className="pl-8 py-2 border-t border-dashed text-sm text-muted-foreground space-y-1">
      {event.organization_id && (
        <div>
          <span className="font-medium">Organization:</span>{" "}
          {event.organization_id}
        </div>
      )}
      {event.arguments && (
        <div>
          <span className="font-medium">Arguments:</span>{" "}
          {JSON.stringify(event.arguments)}
        </div>
      )}
      {event.result_summary && (
        <div>
          <span className="font-medium">Result:</span> {event.result_summary}
        </div>
      )}
      {event.reason && (
        <div>
          <span className="font-medium">Reason:</span> {event.reason}
        </div>
      )}
      {event.delegation_id && (
        <div>
          <span className="font-medium">Delegation:</span>{" "}
          {event.delegation_id}
        </div>
      )}
      <div>
        <span className="font-medium">Session:</span>{" "}
        {event.agent_session_id ?? "—"} |{" "}
        <span className="font-medium">MCP:</span>{" "}
        {event.mcp_session_id ?? "—"}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const { resolve } = useAgentNames();

  useEffect(() => {
    checkOnboardingStatus()
      .then((dest) => setShowOnboarding(dest === "onboarding"))
      .catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const [rawAgents, rawPolicies, eventsData] = await Promise.all([
        apiClient<unknown[] | { agents: unknown[]; total?: number }>("agents/").catch(() => []),
        apiClient<unknown[]>("policies/").catch(() => []),
        apiClient<AuditEventsResponse>(
          "audit/events?limit=10"
        ).catch(() => ({ events: [], total: 0, limit: 10, offset: 0 })),
      ]);

      const agentCount = Array.isArray(rawAgents)
        ? rawAgents.length
        : (rawAgents as { total?: number }).total ?? (rawAgents as { agents: unknown[] }).agents?.length ?? 0;
      const policyCount = Array.isArray(rawPolicies) ? rawPolicies.length : 0;
      const recentEvents = (eventsData as AuditEventsResponse).events ?? [];

      setState({
        kind: "data",
        data: { agentCount, policyCount, recentEvents: recentEvents.slice(0, 10) },
      });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load dashboard (${err.status})`
          : "Failed to load dashboard data";
      setState({ kind: "error", message });
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        fetchData();
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, [fetchData]);

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error")
    return (
      <ErrorCard title="Dashboard" message={state.message} retry={fetchData} />
    );

  const { data } = state;

  const deniedCount = data.recentEvents.filter(
    (e) => e.event_type === "permission_denied" || e.success === false
  ).length;
  const durationsMs = data.recentEvents
    .map((e) => e.duration_ms)
    .filter((d): d is number => d !== null && d > 0);
  const avgDuration =
    durationsMs.length > 0
      ? Math.round(durationsMs.reduce((a, b) => a + b, 0) / durationsMs.length)
      : null;

  function formatDuration(ms: number | null): string {
    if (ms === null) return "—";
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  const metrics = [
    { label: "Agents", value: data.agentCount, icon: Bot },
    { label: "Policies", value: data.policyCount, icon: Shield },
    { label: "Activity", value: data.recentEvents.length, icon: ScrollText },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Overview</h1>

      {showOnboarding && (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="flex items-center justify-between py-4">
            <div className="flex items-center gap-3">
              <Sparkles className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium">Complete your setup</p>
                <p className="text-sm text-muted-foreground">
                  Walk through the onboarding wizard to configure agents and delegations.
                </p>
              </div>
            </div>
            <Button size="sm" asChild>
              <Link href="/onboarding">Start Onboarding</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {metrics.map((m) => (
          <Card key={m.label}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{m.label}</CardTitle>
              <m.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{m.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <Activity className="h-4 w-4" />
            Recent Activity
          </CardTitle>
          <Link
            href="/dashboard/audit"
            className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
          >
            View all in Audit Trail
            <ArrowRight className="h-3 w-3" />
          </Link>
        </CardHeader>
        <CardContent>
          {data.recentEvents.length === 0 ? (
            <EmptyState
              title="No recent activity"
              description="Activity will appear here as agents perform actions."
            />
          ) : (
            <div className="space-y-4">
              {/* Health Summary Banner */}
              <div className="flex items-center gap-3 rounded-md border bg-muted/40 px-3 py-2">
                <Badge variant="secondary" className="text-xs">
                  {data.recentEvents.length} events
                </Badge>
                <Badge
                  variant={deniedCount > 0 ? "destructive" : "secondary"}
                  className="text-xs flex items-center gap-1"
                >
                  {deniedCount > 0 && <ShieldAlert className="h-3 w-3" />}
                  {deniedCount} denied
                </Badge>
                {avgDuration !== null && (
                  <Badge variant="outline" className="text-xs flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    avg {formatDuration(avgDuration)}
                  </Badge>
                )}
              </div>

              {/* Event Table */}
              <div className="overflow-x-auto -mx-6">
                <table className="w-full text-sm" role="table">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Agent</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">On Behalf Of</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Tool Call</th>
                      <th className="w-20 px-3 py-2 text-right text-xs font-medium text-muted-foreground">Duration</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Timestamp</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Event Type</th>
                      <th className="w-10 px-3 py-2 text-center text-xs font-medium text-muted-foreground">Status</th>
                      <th className="w-8 px-2 py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recentEvents.map((event) => {
                      const isDenied =
                        event.event_type === "permission_denied" ||
                        event.success === false;
                      const toolDisplay = isDenied
                        ? event.attempted_tool ?? event.tool ?? event.event_type
                        : event.tool ?? event.event_type;
                      const isExpanded = expandedId === event.id;

                      return (
                        <React.Fragment key={event.id}>
                          <tr
                            className={`border-b cursor-pointer hover:bg-muted/30 transition-colors ${
                              isDenied
                                ? "bg-red-50 dark:bg-red-950/20"
                                : ""
                            }`}
                            onClick={() =>
                              setExpandedId(isExpanded ? null : event.id)
                            }
                          >
                            <td className="px-3 py-2 text-xs font-medium">
                              {event.agent_id ? resolve(event.agent_id) : "—"}
                            </td>
                            <td className="px-3 py-2 text-xs truncate max-w-[180px]">
                              {isDenied && event.required_permission
                                ? <span className="text-red-600 font-medium">DENIED: {event.required_permission}</span>
                                : event.on_behalf_of ?? "—"}
                            </td>
                            <td className="px-3 py-2 font-mono text-xs font-medium truncate max-w-[180px]">
                              {toolDisplay}
                            </td>
                            <td className="px-3 py-2 text-xs text-muted-foreground tabular-nums text-right">
                              {formatDuration(event.duration_ms)}
                            </td>
                            <td className="px-3 py-2 text-xs text-muted-foreground tabular-nums whitespace-nowrap">
                              {new Date(event.timestamp).toLocaleString()}
                            </td>
                            <td className="px-3 py-2">
                              <Badge variant="outline" className="text-[10px] whitespace-nowrap py-0">
                                {event.event_type}
                              </Badge>
                            </td>
                            <td className="px-3 py-2 text-center">
                              {isDenied ? (
                                <XCircle className="h-3.5 w-3.5 text-red-500 inline-block" />
                              ) : (
                                <CheckCircle2 className="h-3.5 w-3.5 text-green-600 inline-block" />
                              )}
                            </td>
                            <td className="px-2 py-2">
                              {isExpanded ? (
                                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                              ) : (
                                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                              )}
                            </td>
                          </tr>
                          {isExpanded && (
                            <tr>
                              <td colSpan={8} className="p-0">
                                <EventDetailPanel event={event} />
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
