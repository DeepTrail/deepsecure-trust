"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Bot, Shield, ScrollText, Activity } from "lucide-react";

interface AuditEvent {
  id: string;
  event_type: string;
  timestamp: string;
  agent_id?: string;
}

interface DashboardData {
  agentCount: number;
  policyCount: number;
  recentEvents: AuditEvent[];
}

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; data: DashboardData };

export default function DashboardPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });

  const fetchData = async () => {
    setState({ kind: "loading" });
    try {
      const [rawAgents, rawPolicies, events] = await Promise.all([
        apiClient<unknown[] | { agents: unknown[]; total?: number }>("agents/").catch(() => []),
        apiClient<unknown[]>("policies/").catch(() => []),
        apiClient<AuditEvent[] | { events: AuditEvent[] }>(
          "audit/events?limit=10"
        ).catch(() => [] as AuditEvent[]),
      ]);

      const agentCount = Array.isArray(rawAgents)
        ? rawAgents.length
        : (rawAgents as { total?: number }).total ?? (rawAgents as { agents: unknown[] }).agents?.length ?? 0;
      const policyCount = Array.isArray(rawPolicies) ? rawPolicies.length : 0;
      const rawEvents = Array.isArray(events)
        ? events
        : (events as { events: AuditEvent[] }).events ?? [];

      setState({
        kind: "data",
        data: { agentCount, policyCount, recentEvents: rawEvents.slice(0, 10) },
      });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load dashboard (${err.status})`
          : "Failed to load dashboard data";
      setState({ kind: "error", message });
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error")
    return (
      <ErrorCard title="Dashboard" message={state.message} retry={fetchData} />
    );

  const { data } = state;

  const metrics = [
    { label: "Agents", value: data.agentCount, icon: Bot },
    { label: "Policies", value: data.policyCount, icon: Shield },
    { label: "Activity", value: data.recentEvents.length, icon: ScrollText },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Overview</h1>

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
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Activity className="h-4 w-4" />
            Recent Activity
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.recentEvents.length === 0 ? (
            <EmptyState
              title="No recent activity"
              description="Activity will appear here as agents perform actions."
            />
          ) : (
            <div className="space-y-3">
              {data.recentEvents.map((event) => (
                <div
                  key={event.id}
                  className="flex items-center justify-between text-sm"
                >
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">{event.event_type}</Badge>
                    {event.agent_id && (
                      <span className="text-xs text-muted-foreground">
                        {event.agent_id}
                      </span>
                    )}
                  </div>
                  <span className="text-muted-foreground text-xs">
                    {new Date(event.timestamp).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
