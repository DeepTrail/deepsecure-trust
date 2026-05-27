"use client";

import { useCallback, useEffect, useState } from "react";
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

export default function DashboardPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [showOnboarding, setShowOnboarding] = useState(false);
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
              {data.recentEvents.map((event) => {
                const isDenied = event.event_type === "permission_denied";
                const toolDisplay = isDenied
                  ? event.attempted_tool ?? event.event_type
                  : event.tool ?? event.event_type;

                return (
                  <div
                    key={event.id}
                    className="flex items-center justify-between text-sm"
                  >
                    <div className="flex items-center gap-2">
                      {event.success === false || isDenied ? (
                        <XCircle className="h-3.5 w-3.5 text-red-500 shrink-0" />
                      ) : (
                        <CheckCircle2 className="h-3.5 w-3.5 text-green-600 shrink-0" />
                      )}
                      <span className="font-mono text-xs truncate max-w-[200px]">
                        {toolDisplay}
                      </span>
                      {event.agent_id && (
                        <span className="text-xs text-muted-foreground">
                          {resolve(event.agent_id)}
                        </span>
                      )}
                    </div>
                    <span className="text-muted-foreground text-xs shrink-0">
                      {new Date(event.timestamp).toLocaleString()}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
