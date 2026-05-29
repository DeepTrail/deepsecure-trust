"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import type {
  AuditEvent,
  AuditEventsResponse,
  AuditSummary,
  AvailablePermissionsResponse,
} from "@/lib/types/audit";
import dynamic from "next/dynamic";

const DelegationChainFlow = dynamic(
  () => import("@/components/charts/DelegationChainFlow"),
  { ssr: false }
);
import { useAgentNames } from "@/hooks/useAgentNames";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import {
  BarChart3,
  Activity,
  ShieldAlert,
  Link2,
  TrendingUp,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  MinusCircle,
} from "lucide-react";

interface Delegation {
  delegation_id: string;
  agent_id: string;
  permissions: string[];
}

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | {
      kind: "data";
      summary: AuditSummary;
      denials: AuditEvent[];
      delegations: Delegation[];
      connectedServices: AvailablePermissionsResponse;
      userEmail: string;
    };

export default function AnalyticsPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const { resolve } = useAgentNames();

  const fetchData = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const [summaryData, denialsData, delegationsData, servicesData, profileData] =
        await Promise.all([
          apiClient<AuditSummary>("audit/summary"),
          apiClient<AuditEventsResponse>(
            "audit/events?event_type=permission_denied&limit=500"
          ),
          apiClient<Delegation[]>("auth/delegations").catch(() => []),
          apiClient<AvailablePermissionsResponse>(
            "users/me/available-permissions"
          ).catch(
            () =>
              ({
                services: {},
                all_permissions: [],
                total_services: 0,
                total_permissions: 0,
              }) as AvailablePermissionsResponse
          ),
          apiClient<{ email?: string; user_id?: string }>("users/me").catch(
            () => ({ email: undefined, user_id: undefined })
          ),
        ]);

      setState({
        kind: "data",
        summary: summaryData,
        denials: denialsData.events ?? [],
        delegations: Array.isArray(delegationsData) ? delegationsData : [],
        connectedServices: servicesData,
        userEmail:
          profileData.email ?? profileData.user_id ?? "Unknown User",
      });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load analytics (${err.status})`
          : "Failed to load analytics data";
      setState({ kind: "error", message });
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error")
    return (
      <ErrorCard
        title="Analytics"
        message={state.message}
        retry={fetchData}
      />
    );

  const { summary, denials, delegations, connectedServices, userEmail } = state;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Tool Call Analytics</h1>

      {/* Section 1: Metrics Cards */}
      <MetricsCards summary={summary} denialCount={denials.length} />

      {/* Section 2: Volume by Backend */}
      <VolumeByBackend summary={summary} />

      {/* Section 3: Top Tools */}
      <TopToolsTable summary={summary} />

      {/* Section 4: Denial Analysis */}
      <DenialAnalysis denials={denials} summary={summary} resolve={resolve} />

      {/* Section 5: Agent Permission Utilization */}
      <DelegationChainViz
        delegations={delegations}
        summary={summary}
        resolve={resolve}
      />

      {/* Section 6: Delegation Chain Visualization */}
      <DelegationChainFlow
        userEmail={userEmail}
        connectedServices={connectedServices}
        delegations={delegations}
        summary={summary}
        resolve={resolve}
      />
    </div>
  );
}

function MetricsCards({
  summary,
  denialCount,
}: {
  summary: AuditSummary;
  denialCount: number;
}) {
  const toolCount = Object.keys(summary.by_tool).length;
  const agentCount = Object.keys(summary.by_agent).length;
  const denialRate =
    summary.total_events > 0
      ? ((denialCount / summary.total_events) * 100).toFixed(1)
      : "0";

  const cards = [
    {
      label: "Total Events",
      value: summary.total_events.toLocaleString(),
      icon: Activity,
    },
    { label: "Unique Tools", value: toolCount, icon: BarChart3 },
    { label: "Active Agents", value: agentCount, icon: TrendingUp },
    {
      label: "Denial Rate",
      value: `${denialRate}%`,
      icon: ShieldAlert,
      alert: Number(denialRate) > 10,
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-4">
      {cards.map((c) => (
        <Card key={c.label}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{c.label}</CardTitle>
            <c.icon
              className={`h-4 w-4 ${
                "alert" in c && c.alert
                  ? "text-amber-500"
                  : "text-muted-foreground"
              }`}
            />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{c.value}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function VolumeByBackend({ summary }: { summary: AuditSummary }) {
  const data = useMemo(() => {
    const byBackend = new Map<string, number>();
    for (const [tool, count] of Object.entries(summary.by_tool)) {
      const backend = tool.split(".")[0];
      byBackend.set(backend, (byBackend.get(backend) ?? 0) + count);
    }
    const total = Array.from(byBackend.values()).reduce((a, b) => a + b, 0);
    return Array.from(byBackend.entries())
      .map(([name, count]) => ({
        name,
        count,
        percent: total > 0 ? Math.round((count / total) * 100) : 0,
      }))
      .sort((a, b) => b.count - a.count);
  }, [summary]);

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <BarChart3 className="h-4 w-4" />
            Volume by Backend
          </CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState title="No data" description="No tool calls recorded yet." />
        </CardContent>
      </Card>
    );
  }

  const maxCount = Math.max(...data.map((d) => d.count));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <BarChart3 className="h-4 w-4" />
          Volume by Backend
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {data.map((d) => (
          <div key={d.name} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">{d.name}</span>
              <span className="text-muted-foreground">
                {d.count.toLocaleString()} ({d.percent}%)
              </span>
            </div>
            <div className="h-2 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${(d.count / maxCount) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function TopToolsTable({ summary }: { summary: AuditSummary }) {
  const tools = useMemo(
    () =>
      Object.entries(summary.by_tool)
        .map(([tool, count]) => ({ tool, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 10),
    [summary]
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <TrendingUp className="h-4 w-4" />
          Top Tools
        </CardTitle>
      </CardHeader>
      <CardContent>
        {tools.length === 0 ? (
          <EmptyState title="No tools" description="No tool calls recorded yet." />
        ) : (
          <div className="space-y-2">
            {tools.map((t, i) => (
              <div
                key={t.tool}
                className="flex items-center justify-between text-sm"
              >
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground w-6 text-right">
                    {i + 1}.
                  </span>
                  <span className="font-mono text-xs">{t.tool}</span>
                </div>
                <Badge variant="secondary">{t.count.toLocaleString()}</Badge>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function DenialAnalysis({
  denials,
  summary,
  resolve,
}: {
  denials: AuditEvent[];
  summary: AuditSummary;
  resolve: (id: string) => string;
}) {
  const analysis = useMemo(() => {
    const byPermission = new Map<
      string,
      { count: number; agents: Set<string> }
    >();
    for (const event of denials) {
      const perm = event.required_permission ?? "unknown";
      const entry = byPermission.get(perm) ?? {
        count: 0,
        agents: new Set<string>(),
      };
      entry.count++;
      if (event.agent_id) entry.agents.add(event.agent_id);
      byPermission.set(perm, entry);
    }
    return Array.from(byPermission.entries())
      .map(([perm, { count, agents }]) => ({
        perm,
        count,
        agentCount: agents.size,
        agents: Array.from(agents),
      }))
      .sort((a, b) => b.count - a.count);
  }, [denials]);

  const totalDenials = denials.length;
  const denialRate =
    summary.total_events > 0
      ? ((totalDenials / summary.total_events) * 100).toFixed(1)
      : "0";

  const writeCount = analysis
    .filter(
      (a) =>
        a.perm.includes(":write") ||
        a.perm.includes(":create") ||
        a.perm.includes(":send")
    )
    .reduce((sum, a) => sum + a.count, 0);
  const writePercent =
    totalDenials > 0 ? Math.round((writeCount / totalDenials) * 100) : 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <ShieldAlert className="h-4 w-4" />
          Permission Denial Analysis
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Total Denials:</span>{" "}
            <span className="font-bold">{totalDenials}</span>
          </div>
          <div>
            <span className="text-muted-foreground">Denial Rate:</span>{" "}
            <span className="font-bold">{denialRate}%</span>
          </div>
        </div>

        {analysis.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No permission denials recorded.
          </p>
        ) : (
          <div className="space-y-3">
            {analysis.map(({ perm, count, agentCount, agents }) => (
              <div key={perm} className="rounded-md border p-3 space-y-1">
                <div className="flex items-center justify-between">
                  <code className="text-xs font-mono">{perm}</code>
                  <Badge variant="destructive">{count} denials</Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  {agentCount} agent{agentCount !== 1 ? "s" : ""}:{" "}
                  {agents.map((a) => resolve(a)).join(", ")}
                </p>
              </div>
            ))}
          </div>
        )}

        {writePercent > 50 && (
          <div className="rounded-md bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 p-3 text-sm text-amber-800 dark:text-amber-200">
            <strong>Insight:</strong> {writePercent}% of denials are write
            operations not delegated. Consider updating delegations.
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function DelegationChainViz({
  delegations,
  summary,
  resolve,
}: {
  delegations: Delegation[];
  summary: AuditSummary;
  resolve: (id: string) => string;
}) {
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  const chains = useMemo(() => {
    return delegations.map((d) => {
      const permissions = d.permissions.map((perm) => {
        const parts = perm.split(":");
        const service = parts[0];
        const toolPrefix = `${service}.`;
        const usageCount = Object.entries(summary.by_tool)
          .filter(([tool]) => tool.startsWith(toolPrefix))
          .reduce((sum, [, count]) => sum + count, 0);
        return {
          permission: perm,
          service,
          usageCount,
          used: usageCount > 0,
        };
      });

      const usedCount = permissions.filter((p) => p.used).length;
      const utilizationPercent =
        permissions.length > 0
          ? Math.round((usedCount / permissions.length) * 100)
          : 0;

      return {
        delegationId: d.delegation_id,
        agentId: d.agent_id,
        agentName: resolve(d.agent_id),
        permissions,
        usedCount,
        totalCount: permissions.length,
        utilizationPercent,
      };
    });
  }, [delegations, summary, resolve]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Link2 className="h-4 w-4" />
          Agent Permission Utilization
        </CardTitle>
      </CardHeader>
      <CardContent>
        {chains.length === 0 ? (
          <EmptyState
            title="No delegations"
            description="Create delegations to see permission utilization analysis."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" role="table">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">Agent</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">Agent ID</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">Permissions</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground min-w-[200px]">Utilization</th>
                  <th className="w-8 px-2 py-2.5"></th>
                </tr>
              </thead>
              <tbody>
                {chains.map((chain) => {
                  const isExpanded = expandedAgent === chain.delegationId;
                  return (
                    <React.Fragment key={chain.delegationId}>
                      <tr
                        className="border-b cursor-pointer hover:bg-muted/30 transition-colors"
                        onClick={() =>
                          setExpandedAgent(isExpanded ? null : chain.delegationId)
                        }
                      >
                        <td className="px-3 py-2.5 font-medium">{chain.agentName}</td>
                        <td className="px-3 py-2.5 text-xs text-muted-foreground font-mono">{chain.agentId}</td>
                        <td className="px-3 py-2.5 text-xs text-muted-foreground">
                          {chain.usedCount} / {chain.totalCount} used
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all ${
                                  chain.utilizationPercent > 75
                                    ? "bg-green-500"
                                    : chain.utilizationPercent > 25
                                      ? "bg-amber-500"
                                      : "bg-red-500"
                                }`}
                                style={{ width: `${chain.utilizationPercent}%` }}
                              />
                            </div>
                            <span className="text-xs font-medium tabular-nums w-10 text-right">
                              {chain.utilizationPercent}%
                            </span>
                          </div>
                        </td>
                        <td className="px-2 py-2.5">
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          )}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr>
                          <td colSpan={5} className="p-0">
                            <div className="border-t border-dashed bg-muted/20">
                              <table className="w-full text-xs">
                                <thead>
                                  <tr className="border-b">
                                    <th className="px-6 py-2 text-left font-medium text-muted-foreground">Permission</th>
                                    <th className="px-3 py-2 text-left font-medium text-muted-foreground">Service</th>
                                    <th className="px-3 py-2 text-left font-medium text-muted-foreground">Status</th>
                                    <th className="px-3 py-2 text-right font-medium text-muted-foreground">Tool Calls</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {chain.permissions.map((p) => (
                                    <tr key={p.permission} className="border-b last:border-b-0">
                                      <td className="px-6 py-1.5 font-mono">{p.permission}</td>
                                      <td className="px-3 py-1.5 text-muted-foreground">{p.service}</td>
                                      <td className="px-3 py-1.5">
                                        {p.used ? (
                                          <span className="inline-flex items-center gap-1 text-green-700 dark:text-green-400">
                                            <CheckCircle2 className="h-3 w-3" /> Active
                                          </span>
                                        ) : (
                                          <span className="inline-flex items-center gap-1 text-muted-foreground">
                                            <MinusCircle className="h-3 w-3" /> Unused
                                          </span>
                                        )}
                                      </td>
                                      <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">
                                        {p.usageCount > 0 ? p.usageCount.toLocaleString() : "—"}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
