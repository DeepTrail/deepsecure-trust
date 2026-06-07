"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
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
  AgentLifecycleState,
  AgentSuspendRequest,
  FleetSummary,
} from "@/lib/types/admin";
import { CrossUserMappingTable } from "@/components/agents/CrossUserMappingTable";
import { DelegationsTable } from "@/components/agents/DelegationsTable";
import { SessionsTable } from "@/components/agents/SessionsTable";
import { IdentityStackPanel } from "@/components/agents/IdentityStackPanel";

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; agents: AdminAgent[]; total: number; summary: FleetSummary | null };

const LIFECYCLE_COLORS: Record<string, string> = {
  registered: "bg-slate-500/10 text-slate-600 border-slate-200",
  delegated: "bg-blue-500/10 text-blue-700 border-blue-200",
  authenticated: "bg-amber-500/10 text-amber-700 border-amber-200",
  active: "bg-green-500/10 text-green-700 border-green-200",
  suspended: "bg-red-500/10 text-red-700 border-red-200",
  inactive: "bg-gray-500/10 text-gray-500 border-gray-200",
};

const LIFECYCLE_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All lifecycles" },
  { value: "registered", label: "Registered" },
  { value: "delegated", label: "Delegated" },
  { value: "authenticated", label: "Authenticated" },
  { value: "active", label: "Active" },
];

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
  const router = useRouter();
  const searchParams = useSearchParams();
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [suspendTarget, setSuspendTarget] = useState<AdminAgent | null>(null);
  const [suspendReason, setSuspendReason] = useState("");
  const [suspending, setSuspending] = useState(false);

  const filters = useMemo(
    () => ({
      lifecycle_state: searchParams.get("lifecycle_state") ?? "",
      user_id: searchParams.get("user_id") ?? "",
      service: searchParams.get("service") ?? "",
      q: searchParams.get("q") ?? "",
    }),
    [searchParams]
  );

  const setFilters = useCallback(
    (next: Partial<typeof filters>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries({ ...filters, ...next })) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      const qs = params.toString();
      router.replace(qs ? `?${qs}` : "?", { scroll: false });
    },
    [filters, router, searchParams]
  );

  const clearFilters = useCallback(() => {
    router.replace("?", { scroll: false });
  }, [router]);

  const fetchAgents = useCallback(async () => {
    try {
      const query = new URLSearchParams();
      if (filters.lifecycle_state) query.set("lifecycle_state", filters.lifecycle_state);
      if (filters.user_id) query.set("user_id", filters.user_id);
      if (filters.service) query.set("service", filters.service);
      if (filters.q) query.set("q", filters.q);
      const path = query.toString() ? `admin/agents?${query}` : "admin/agents";
      const data = await apiClient<AdminAgentListResponse>(path);
      setState({
        kind: "data",
        agents: data.agents ?? [],
        total: data.total ?? data.agents?.length ?? 0,
        summary: data.summary ?? null,
      });
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof Error ? err.message : "Failed to load agents",
      });
    }
  }, [filters]);

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

  const { agents, total, summary } = state;
  const hasFilters = Boolean(
    filters.lifecycle_state || filters.user_id || filters.service || filters.q
  );

  const lifecycleLabel = (agent: AdminAgent) =>
    agent.lifecycle_state ?? agent.status;

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

      {/* Filter bar */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Lifecycle</label>
          <select
            className="h-9 rounded-md border bg-background px-3 text-sm"
            value={filters.lifecycle_state}
            onChange={(e) =>
              setFilters({ lifecycle_state: e.target.value as AgentLifecycleState | "" })
            }
          >
            {LIFECYCLE_OPTIONS.map((opt) => (
              <option key={opt.value || "all"} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Delegating user</label>
          <Input
            type="email"
            placeholder="user@company.com"
            value={filters.user_id}
            onChange={(e) => setFilters({ user_id: e.target.value })}
            className="w-52"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Service</label>
          <Input
            type="text"
            placeholder="notion"
            value={filters.service}
            onChange={(e) => setFilters({ service: e.target.value })}
            className="w-36"
          />
        </div>
        <div className="relative space-y-1">
          <label className="text-xs text-muted-foreground">Search</label>
          <Search className="absolute left-3 bottom-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Agent name or ID"
            value={filters.q}
            onChange={(e) => setFilters({ q: e.target.value })}
            className="w-52 pl-9"
          />
        </div>
        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            Clear filters
          </Button>
        )}
      </div>

      {/* Summary bar */}
      <p className="text-sm text-muted-foreground">
        Summary: {summary?.total_agents ?? total} agents |{" "}
        {summary?.delegating_users ?? 0} delegating users |{" "}
        {summary?.active ?? 0} active | {summary?.authenticated ?? 0} auth&apos;d |{" "}
        {summary?.registered ?? 0} reg&apos;d
      </p>

      {/* Agent List */}
      {agents.length === 0 ? (
        <EmptyState
          title="No agents match these filters"
          description={
            hasFilters
              ? "Try clearing filters or adjusting your search"
              : "No agents have been registered yet"
          }
          action={
            hasFilters
              ? { label: "Clear filters", onClick: clearFilters }
              : undefined
          }
        />
      ) : (
        <div className="space-y-2">
          {agents.map((agent) => {
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
                        LIFECYCLE_COLORS[lifecycleLabel(agent)] ??
                          LIFECYCLE_COLORS.inactive
                      )}
                    >
                      {lifecycleLabel(agent)}
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
                      <dl className="grid grid-cols-[auto_1fr_auto_1fr] gap-x-8 gap-y-1.5 text-sm">
                        <dt className="text-muted-foreground">Auth Method</dt>
                        <dd className="text-xs">
                          {agent.public_key
                            ? <><span>Ed25519</span>{" "}<span className="font-mono text-muted-foreground">({truncateKey(agent.public_key)})</span></>
                            : "Workload Identity"}
                        </dd>
                        {agent.platform ? (
                          <>
                            <dt className="text-muted-foreground">Platform</dt>
                            <dd className="text-xs uppercase">{agent.platform}</dd>
                          </>
                        ) : <><dt /><dd /></>}

                        <dt className="text-muted-foreground">Created</dt>
                        <dd>{formatDate(agent.created_at)}</dd>
                        <dt className="text-muted-foreground">Last Active</dt>
                        <dd>{formatDate(agent.last_active_at)}</dd>

                        {agent.selector && (
                          <>
                            <dt className="text-muted-foreground">Service Account</dt>
                            <dd className="col-span-3 font-mono text-xs break-all">{agent.selector}</dd>
                          </>
                        )}
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
