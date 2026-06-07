"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import { KeyRound, Plus, Shield, Clock, Trash2, Pencil } from "lucide-react";
import { PendingInviteBanner } from "@/components/delegation/PendingInviteBanner";

interface Agent {
  agent_id: string;
  name: string;
}

interface DelegationSummary {
  delegation_id: string;
  agent_id: string;
  permissions: string[];
  expires_in: number;
  created_at: string | null;
  status?: string;
  source?: string;
  template_id?: string | null;
}

function formatTtl(seconds: number): string {
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}

function formatTimeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; delegations: DelegationSummary[]; agents: Agent[] };

export default function DelegationPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });

  const fetchData = async () => {
    setState({ kind: "loading" });
    try {
      const [delegationsResp, agentsResp] = await Promise.all([
        apiClient<DelegationSummary[]>("auth/delegations").catch(() => []),
        apiClient<Agent[] | { agents: Agent[] }>("agents/").catch(() => []),
      ]);

      const delegations = Array.isArray(delegationsResp) ? delegationsResp : [];
      const agents = Array.isArray(agentsResp)
        ? agentsResp
        : ((agentsResp as { agents?: Agent[] }).agents ?? []);

      setState({ kind: "data", delegations, agents });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load delegations (${err.status})`
          : "Failed to load delegations";
      setState({ kind: "error", message });
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error")
    return (
      <ErrorCard title="Delegation" message={state.message} retry={fetchData} />
    );

  const { delegations, agents } = state;
  const agentNameMap = Object.fromEntries(
    agents.map((a) => [a.agent_id, a.name || a.agent_id])
  );
  const pendingInvites = delegations.filter((d) => d.status === "pending");
  const activeDelegations = delegations.filter((d) => d.status !== "pending");

  if (delegations.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Delegation</h1>
          <Button size="sm" asChild>
            <Link href="/dashboard/delegation/create">
              <Plus className="mr-2 h-4 w-4" />
              Create Delegation
            </Link>
          </Button>
        </div>
        <EmptyState
          icon={<KeyRound className="h-12 w-12" />}
          title="No delegations yet"
          description="Create a delegation to grant scoped permissions from your connected services to an agent."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Delegation</h1>
        <Button size="sm" asChild>
          <Link href="/dashboard/delegation/create">
            <Plus className="mr-2 h-4 w-4" />
            Create Delegation
          </Link>
        </Button>
      </div>

      {pendingInvites.map((invite) => (
        <PendingInviteBanner
          key={invite.delegation_id}
          invite={invite}
          agentName={agentNameMap[invite.agent_id]}
          onAccepted={fetchData}
        />
      ))}

      <div className="grid gap-4">
        {activeDelegations.map((d) => {
          const permsByService: Record<string, string[]> = {};
          for (const p of d.permissions ?? []) {
            const parts = p.split(":");
            const svc = parts[0] || "unknown";
            if (!permsByService[svc]) permsByService[svc] = [];
            permsByService[svc].push(parts.slice(1).join(":"));
          }

          const expiresAtMs = d.created_at
            ? new Date(d.created_at).getTime() + d.expires_in * 1000
            : null;
          const isExpired = expiresAtMs ? Date.now() > expiresAtMs : false;
          const ttlLabel = formatTtl(d.expires_in);
          const expiryDate = expiresAtMs ? new Date(expiresAtMs).toLocaleDateString() : null;

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
            <Card key={d.delegation_id} className={isExpired ? "opacity-60" : ""}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-medium">
                  <Shield className="h-4 w-4 text-muted-foreground" />
                  {agentNameMap[d.agent_id] || d.agent_id}
                </CardTitle>
                <div className="flex items-center gap-2">
                  {isExpired ? (
                    <Badge variant="destructive" className="text-xs">
                      Expired · TTL was {ttlLabel}{expiryDate ? ` · ${expiryDate}` : ""}
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="text-xs">
                      <Clock className="mr-1 h-3 w-3" />
                      TTL {ttlLabel}{expiryDate ? ` · Expires ${expiryDate}` : ""}
                    </Badge>
                  )}
                  <Badge variant="default">
                    {(d.permissions ?? []).length} permission{(d.permissions ?? []).length !== 1 ? "s" : ""}
                  </Badge>
                  {!isExpired && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-muted-foreground"
                      asChild
                      title="Edit delegation"
                    >
                      <Link href={`/dashboard/delegation/create?edit=${d.delegation_id}`}>
                        <Pencil className="h-4 w-4" />
                      </Link>
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-destructive"
                    onClick={handleRevoke}
                    title="Revoke delegation"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {Object.entries(permsByService).map(([svc, perms]) => (
                    <Badge key={svc} variant="outline" className="text-xs">
                      {svc}: {perms.join(", ")}
                    </Badge>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  ID: <span className="font-mono">{d.delegation_id}</span>
                  {d.created_at && ` · Created: ${formatTimeAgo(d.created_at)}`}
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
