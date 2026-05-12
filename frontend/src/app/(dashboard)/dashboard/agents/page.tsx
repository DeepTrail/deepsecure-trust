"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import { LifecycleBadge, type LifecycleState } from "@/components/agents";
import { LifecycleTimeline } from "@/components/agents/LifecycleTimeline";
import { Bot, Plus, Trash2 } from "lucide-react";

interface Agent {
  agent_id: string;
  name: string;
  status?: string;
  lifecycle_state?: string;
  created_at?: string;
  public_key?: string;
}

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; agents: Agent[] };

export default function AgentsPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });

  const fetchAgents = async () => {
    setState({ kind: "loading" });
    try {
      const data = await apiClient<Agent[] | { agents: Agent[] }>("agents/");
      const agents = Array.isArray(data) ? data : (data.agents ?? []);
      setState({ kind: "data", agents });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load agents (${err.status})`
          : "Failed to load agents";
      setState({ kind: "error", message });
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const handleDelete = async (agentId: string) => {
    if (!window.confirm("Are you sure you want to delete this agent?")) return;
    try {
      await apiClient(`agents/${agentId}`, { method: "DELETE" });
      await fetchAgents();
    } catch {
      // Will surface on next fetch
    }
  };

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error")
    return <ErrorCard title="Agents" message={state.message} retry={fetchAgents} />;

  const { agents } = state;

  if (agents.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Agents</h1>
          <Button size="sm" asChild>
            <Link href="/dashboard/agents/create">
              <Plus className="mr-2 h-4 w-4" />
              Register Agent
            </Link>
          </Button>
        </div>
        <EmptyState
          title="No agents registered"
          description="Register your first AI agent to get started with identity management."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Agents</h1>
        <Button size="sm" asChild>
          <Link href="/dashboard/agents/create">
            <Plus className="mr-2 h-4 w-4" />
            Register Agent
          </Link>
        </Button>
      </div>

      <div className="grid gap-4">
        {agents.map((agent) => (
          <Card key={agent.agent_id} className="transition-colors hover:bg-muted/50">
            <Link href={`/dashboard/agents/${agent.agent_id}/activity`} className="block">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-medium">
                  <Bot className="h-4 w-4 text-muted-foreground" />
                  {agent.name || agent.agent_id}
                </CardTitle>
                <LifecycleBadge
                  state={(agent.lifecycle_state as LifecycleState) ?? "registered"}
                />
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  ID: <span className="font-mono">{agent.agent_id}</span>
                  {agent.created_at && ` · Created: ${new Date(agent.created_at).toLocaleDateString()}`}
                </p>
                <LifecycleTimeline
                  state={(agent.lifecycle_state as LifecycleState) ?? "registered"}
                  className="mt-3"
                />
              </CardContent>
            </Link>
            <div className="flex justify-end px-6 pb-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => { e.preventDefault(); handleDelete(agent.agent_id); }}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

