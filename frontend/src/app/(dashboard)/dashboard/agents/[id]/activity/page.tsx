"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api/client";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { DelegatedToolsCard, UnavailableToolsDisclosure, type AgentTool } from "@/components/agents/ToolsList";
import { ActivityFeed, type ActivityEvent } from "@/components/agents/ActivityFeed";
import { AgentAuthenticator } from "@/components/agents/AgentAuthenticator";
import {
  LifecycleBadge,
  LifecycleProgressBar,
  AgentIdentityCard,
  SessionHistoryTable,
  type LifecycleState,
} from "@/components/agents";
import { useSSE } from "@/hooks/useSSE";
import {
  Bot,
  ArrowLeft,
  Radio,
  Shield,
  Clock,
  KeyRound,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";

interface ToolsResponse {
  agent_id: string;
  tools: AgentTool[];
}

interface AuditEventsResponse {
  events?: ActivityEvent[];
}

interface AgentInfo {
  agent_id: string;
  name: string;
  status?: string;
  lifecycle_state?: string;
  session_count?: number;
  delegation_count?: number;
  last_authenticated_at?: string;
  last_active_at?: string;
  created_at?: string;
  public_key?: string;
  description?: string;
  platform?: string | null;
  selector?: string | null;
}

interface DelegationSummary {
  delegation_id: string;
  agent_id: string;
  permissions: string[];
  expires_in: number;
  created_at: string | null;
}

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | {
      kind: "data";
      agent: AgentInfo | null;
      delegations: DelegationSummary[];
      tools: AgentTool[];
      events: ActivityEvent[];
    };

function formatTtl(seconds: number): string {
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}

export default function AgentDetailPage() {
  const params = useParams<{ id: string }>();
  const agentId = params.id;
  const [state, setState] = useState<PageState>({ kind: "loading" });

  const { data: liveEvents, connected: sseConnected } = useSSE<ActivityEvent>(
    "/api/events/stream",
    { enabled: !!agentId }
  );

  const fetchData = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const [agentData, delegationsData, toolsData, eventsData] =
        await Promise.all([
          apiClient<AgentInfo>(`agents/${agentId}`).catch(() => null),
          apiClient<DelegationSummary[]>("auth/delegations").catch(() => []),
          apiClient<ToolsResponse>(`agents/${agentId}/tools`).catch(
            () => ({ agent_id: agentId, tools: [] }) as ToolsResponse
          ),
          apiClient<ActivityEvent[] | AuditEventsResponse>(
            `audit/events?agent_id=${agentId}&limit=20`
          ).catch(() => []),
        ]);

      const tools = toolsData.tools ?? [];
      const events = Array.isArray(eventsData)
        ? eventsData
        : (eventsData as AuditEventsResponse).events ?? [];

      const agentDelegations = (
        Array.isArray(delegationsData) ? delegationsData : []
      ).filter((d) => d.agent_id === agentId);

      setState({
        kind: "data",
        agent: agentData,
        delegations: agentDelegations,
        tools,
        events,
      });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load agent data (${err.status})`
          : "Failed to load agent data";
      setState({ kind: "error", message });
    }
  }, [agentId]);

  useEffect(() => {
    if (agentId) fetchData();
  }, [agentId, fetchData]);

  if (state.kind === "loading") return <PageSkeleton variant="detail" />;
  if (state.kind === "error")
    return (
      <ErrorCard
        title="Agent Detail"
        message={state.message}
        retry={fetchData}
      />
    );

  const { agent, delegations, tools, events } = state;

  const agentLiveEvents = liveEvents.filter(
    (e) => (e as unknown as Record<string, unknown>).agent_id === agentId
  );
  const allEvents = [...agentLiveEvents, ...events];

  const latestDelegation = delegations.length > 0 ? delegations[0] : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/dashboard/agents">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
        </Link>
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-muted-foreground" />
          <div>
            <h1 className="text-2xl font-bold">
              {agent?.name || agentId}
            </h1>
            <p className="text-xs text-muted-foreground font-mono">{agentId}</p>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Badge
            variant={sseConnected ? "default" : "secondary"}
            className="flex items-center gap-1"
          >
            <Radio className="h-3 w-3" />
            {sseConnected ? "Live" : "Polling"}
          </Badge>
          {agent && (
            <LifecycleBadge
              state={(agent.lifecycle_state as LifecycleState) ?? "registered"}
            />
          )}
        </div>
      </div>

      {/* Lifecycle Progress */}
      {agent && (
        <LifecycleProgressBar
          state={(agent.lifecycle_state as LifecycleState) ?? "registered"}
        />
      )}

      {/* Delegations for this agent */}
      {delegations.length > 0 ? (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center justify-between text-sm font-medium">
              <span className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-muted-foreground" />
                Delegations ({delegations.length})
              </span>
              <Button size="sm" variant="outline" asChild>
                <Link href="/dashboard/delegation/create">
                  Add Delegation
                </Link>
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {delegations.map((d) => {
                const permsByService: Record<string, string[]> = {};
                for (const p of d.permissions) {
                  const [svc, ...rest] = p.split(":");
                  if (!permsByService[svc]) permsByService[svc] = [];
                  permsByService[svc].push(rest.join(":"));
                }
                const isExpired = d.created_at
                  ? Date.now() > new Date(d.created_at).getTime() + d.expires_in * 1000
                  : false;

                const handleRevoke = async () => {
                  if (!window.confirm("Revoke this delegation? The agent will lose these permissions immediately.")) return;
                  try {
                    await apiClient(`auth/delegations/${d.delegation_id}`, { method: "DELETE" });
                    fetchData();
                  } catch {
                    alert("Failed to revoke delegation");
                  }
                };

                return (
                  <div
                    key={d.delegation_id}
                    className={`rounded-md border p-3 space-y-2 ${isExpired ? "opacity-60" : ""}`}
                  >
                    <div className="flex items-center justify-between">
                      <code className="text-xs font-mono text-muted-foreground">
                        {d.delegation_id}
                      </code>
                      <div className="flex items-center gap-2">
                        {isExpired ? (
                          <Badge variant="destructive" className="text-xs">
                            Expired
                          </Badge>
                        ) : (
                          <Badge variant="secondary" className="text-xs">
                            <Clock className="mr-1 h-3 w-3" />
                            TTL {formatTtl(d.expires_in)}
                          </Badge>
                        )}
                        <Badge variant="default" className="text-xs">
                          {d.permissions.length} permissions
                        </Badge>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 text-muted-foreground hover:text-destructive"
                          onClick={handleRevoke}
                          title="Revoke delegation"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(permsByService).map(([svc, perms]) => (
                        <Badge
                          key={svc}
                          variant="outline"
                          className="text-xs"
                        >
                          {svc} ({perms.length})
                        </Badge>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <KeyRound className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">No delegations assigned</p>
                  <p className="text-xs text-muted-foreground">
                    Create a delegation to grant this agent scoped permissions
                    from your connected services.
                  </p>
                </div>
              </div>
              <Button size="sm" asChild>
                <Link href="/dashboard/delegation/create">
                  Create Delegation
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 4. Delegated Tools */}
      <DelegatedToolsCard tools={tools} />

      {/* 5. Agent Authentication — only for key-based agents */}
      {!agent?.platform && (
        <AgentAuthenticator
          agentId={agentId}
          delegationId={latestDelegation?.delegation_id}
          lifecycleState={agent?.lifecycle_state}
        />
      )}

      {/* 6. Session History */}
      <SessionHistoryTable agentId={agentId} />

      {/* 7. Agent Identity — only for platform agents */}
      {agent?.platform && (
        <AgentIdentityCard
          agentId={agentId}
          platform={agent.platform}
          selector={agent.selector}
        />
      )}

      {/* 8. Activity Feed (full width) */}
      <ActivityFeed events={allEvents} />

      {/* 9. Unavailable Tools (collapsed) */}
      <UnavailableToolsDisclosure tools={tools} />
    </div>
  );
}
