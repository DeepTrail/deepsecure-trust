"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Users,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Search,
  ShieldAlert,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { PageSkeleton, ErrorCard, EmptyState } from "@/components/feedback";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type {
  AdminAgent,
  AdminAgentListResponse,
  AgentSuspendRequest,
} from "@/lib/types/admin";
import { CrossUserMappingTable } from "@/components/agents/CrossUserMappingTable";
import { DelegationsTable } from "@/components/agents/DelegationsTable";
import { SessionsTable } from "@/components/agents/SessionsTable";
import { IdentityStackPanel } from "@/components/agents/IdentityStackPanel";

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; agents: AdminAgent[] };

const STATUS_COLORS: Record<AdminAgent["status"], string> = {
  active: "bg-green-500/10 text-green-700 border-green-200",
  suspended: "bg-red-500/10 text-red-700 border-red-200",
  inactive: "bg-gray-500/10 text-gray-500 border-gray-200",
};

function formatDate(iso: string | null): string {
  if (!iso) return "Never";
  return new Date(iso).toLocaleString();
}

function truncateKey(key: string | null): string {
  if (!key) return "Workload Identity";
  if (key.length <= 20) return key;
  return `${key.slice(0, 10)}...${key.slice(-6)}`;
}

export default function AdminAgentFleetPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [suspendTarget, setSuspendTarget] = useState<AdminAgent | null>(null);
  const [suspendReason, setSuspendReason] = useState("");
  const [suspending, setSuspending] = useState(false);

  const fetchAgents = useCallback(async () => {
    try {
      const data = await apiClient<AdminAgentListResponse>("admin/agents");
      setState({ kind: "data", agents: data.agents ?? [] });
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof Error ? err.message : "Failed to load agents",
      });
    }
  }, []);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  const handleSuspend = async () => {
    if (!suspendTarget || !suspendReason.trim()) return;
    setSuspending(true);
    try {
      await apiClient<{ message: string }>(
        `admin/agents/${suspendTarget.agent_id}/suspend`,
        {
          method: "POST",
          body: JSON.stringify({ reason: suspendReason.trim() } satisfies AgentSuspendRequest),
        }
      );
      setSuspendTarget(null);
      setSuspendReason("");
      await fetchAgents();
    } catch {
      // keep dialog open on failure so user can retry
    } finally {
      setSuspending(false);
    }
  };

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error") {
    return <ErrorCard title="Agent Fleet" message={state.message} retry={fetchAgents} />;
  }

  const { agents } = state;

  const filtered = agents.filter((a) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      a.agent_id.toLowerCase().includes(q) ||
      a.name.toLowerCase().includes(q)
    );
  });

  const totalDelegations = agents.reduce((sum, a) => sum + a.delegation_count, 0);
  const activeCount = agents.filter((a) => a.status === "active").length;
  const suspendedCount = agents.filter((a) => a.status === "suspended").length;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <Users className="h-6 w-6" />
            Agent Fleet
          </h1>
          <p className="text-muted-foreground">
            Monitor and manage all registered AI agents
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchAgents}>
          <RefreshCw className="mr-1.5 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Total Agents</p>
          <p className="text-2xl font-bold">{agents.length}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Active</p>
          <p className="text-2xl font-bold text-green-600">{activeCount}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Suspended</p>
          <p className="text-2xl font-bold text-red-600">{suspendedCount}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Total Delegations</p>
          <p className="text-2xl font-bold">{totalDelegations}</p>
        </Card>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Search agents by name or ID..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Agent List */}
      {filtered.length === 0 ? (
        <EmptyState
          title="No agents found"
          description={
            search
              ? "Try a different search term"
              : "No agents have been registered yet"
          }
        />
      ) : (
        <div className="space-y-2">
          {filtered.map((agent) => {
            const isExpanded = expandedId === agent.agent_id;
            return (
              <Card key={agent.agent_id} className="overflow-hidden">
                <div className="flex items-center gap-4 px-6 py-4">
                  <button
                    onClick={() =>
                      setExpandedId(isExpanded ? null : agent.agent_id)
                    }
                    className="flex flex-1 items-center gap-4 text-left hover:opacity-80 transition-opacity"
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                    )}

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{agent.name}</span>
                        <span className="text-xs text-muted-foreground">
                          ({agent.agent_id})
                        </span>
                      </div>
                    </div>

                    <Badge
                      variant="outline"
                      className={cn(
                        "text-xs capitalize",
                        STATUS_COLORS[agent.status]
                      )}
                    >
                      {agent.status}
                    </Badge>

                    <span className="text-sm text-muted-foreground whitespace-nowrap">
                      {agent.delegation_count} delegation{agent.delegation_count !== 1 ? "s" : ""}
                    </span>

                    <span className="text-sm text-muted-foreground whitespace-nowrap">
                      {agent.active_sessions} session{agent.active_sessions !== 1 ? "s" : ""}
                    </span>

                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      {agent.last_active_at
                        ? `Active ${new Date(agent.last_active_at).toLocaleDateString()}`
                        : "Never active"}
                    </span>
                  </button>

                  {agent.status === "active" && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="shrink-0 text-red-600 hover:text-red-700 hover:border-red-300"
                      onClick={() => setSuspendTarget(agent)}
                    >
                      <ShieldAlert className="mr-1.5 h-3.5 w-3.5" />
                      Suspend
                    </Button>
                  )}
                </div>

                {isExpanded && (
                  <div className="border-t bg-muted/20 px-6 py-4 space-y-5">
                    {/* Details */}
                    <div className="space-y-3">
                      <h4 className="text-sm font-semibold">Details</h4>
                      <dl className="space-y-1 text-sm max-w-md">
                        <div className="flex justify-between">
                          <dt className="text-muted-foreground">Auth</dt>
                          <dd className={agent.public_key ? "font-mono text-xs" : "text-xs"}>
                            {truncateKey(agent.public_key)}
                          </dd>
                        </div>
                        {agent.platform && (
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">Platform</dt>
                            <dd className="text-xs uppercase">{agent.platform}</dd>
                          </div>
                        )}
                        {agent.selector && (
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">Selector</dt>
                            <dd className="font-mono text-xs">{agent.selector}</dd>
                          </div>
                        )}
                        <div className="flex justify-between">
                          <dt className="text-muted-foreground">Auth Method</dt>
                          <dd className="text-xs capitalize">{agent.auth_method.replace("_", " ")}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-muted-foreground">Created</dt>
                          <dd>{formatDate(agent.created_at)}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-muted-foreground">Last Active</dt>
                          <dd>{formatDate(agent.last_active_at)}</dd>
                        </div>
                      </dl>
                    </div>

                    {/* Cross-User Mapping */}
                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold">
                        Cross-User Mapping ({agent.delegators?.length ?? 0})
                      </h4>
                      <CrossUserMappingTable delegators={agent.delegators ?? []} />
                    </div>

                    {/* Delegations */}
                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold">
                        Delegations ({agent.delegation_count})
                      </h4>
                      <DelegationsTable delegations={agent.delegations} />
                    </div>

                    {/* Sessions */}
                    <SessionsTable sessions={agent.sessions} agentId={agent.agent_id} />

                    {/* Identity Stack */}
                    <IdentityStackPanel agentId={agent.agent_id} />
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* Suspend Confirmation Dialog */}
      <Dialog
        open={suspendTarget !== null}
        onOpenChange={(open: boolean) => {
          if (!open) {
            setSuspendTarget(null);
            setSuspendReason("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Suspend Agent</DialogTitle>
            <DialogDescription>
              This will immediately suspend{" "}
              <span className="font-medium text-foreground">
                {suspendTarget?.name}
              </span>{" "}
              ({suspendTarget?.agent_id}). The agent will not be able to
              authenticate or execute actions until reactivated.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <label htmlFor="suspend-reason" className="text-sm font-medium">
              Reason for suspension
            </label>
            <Input
              id="suspend-reason"
              placeholder="e.g., Suspicious activity detected"
              value={suspendReason}
              onChange={(e) => setSuspendReason(e.target.value)}
            />
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setSuspendTarget(null);
                setSuspendReason("");
              }}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={!suspendReason.trim() || suspending}
              onClick={handleSuspend}
            >
              {suspending ? "Suspending..." : "Suspend Agent"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
