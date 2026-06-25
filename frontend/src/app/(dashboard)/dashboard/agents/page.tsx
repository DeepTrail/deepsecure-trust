"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import { LifecycleBadge, type LifecycleState } from "@/components/agents";
import { LifecycleTimeline } from "@/components/agents/LifecycleTimeline";
import { useUserRole } from "@/hooks/useUserRole";
import { Bot, Plus, Trash2, Settings2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface Agent {
  agent_id: string;
  name: string;
  status?: string;
  lifecycle_state?: string;
  created_at?: string;
  public_key?: string;
}

interface MyAgent {
  agent_id: string;
  name: string;
  lifecycle_state: string;
  delegated_services: string[];
  my_prompt_count: number;
}

type Tab = "my-agents" | "all-agents";

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; agents: Agent[] }
  | { kind: "my-data"; agents: MyAgent[] };

export default function AgentsPage() {
  const { isAdmin, isLoading: roleLoading } = useUserRole();
  const [activeTab, setActiveTab] = useState<Tab>("my-agents");
  const [state, setState] = useState<PageState>({ kind: "loading" });

  useEffect(() => {
    if (!roleLoading) {
      setActiveTab(isAdmin ? "all-agents" : "my-agents");
    }
  }, [isAdmin, roleLoading]);

  const fetchAllAgents = useCallback(async () => {
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
  }, []);

  const fetchMyAgents = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const data = await apiClient<{ agents: MyAgent[]; total: number }>(
        "agents/my-agents"
      );
      setState({ kind: "my-data", agents: data.agents ?? [] });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load your agents (${err.status})`
          : "Failed to load your agents";
      setState({ kind: "error", message });
    }
  }, []);

  useEffect(() => {
    if (roleLoading) return;
    if (activeTab === "all-agents") {
      fetchAllAgents();
    } else {
      fetchMyAgents();
    }
  }, [activeTab, roleLoading, fetchAllAgents, fetchMyAgents]);

  const handleDelete = async (agentId: string) => {
    if (!window.confirm("Are you sure you want to delete this agent?")) return;
    try {
      await apiClient(`agents/${agentId}`, { method: "DELETE" });
      await fetchAllAgents();
    } catch {
      // Will surface on next fetch
    }
  };

  if (roleLoading || state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error") {
    const retry = activeTab === "all-agents" ? fetchAllAgents : fetchMyAgents;
    return <ErrorCard title="Agents" message={state.message} retry={retry} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Agents</h1>
        {isAdmin && (
          <Button size="sm" asChild>
            <Link href="/dashboard/agents/create">
              <Plus className="mr-2 h-4 w-4" />
              Register Agent
            </Link>
          </Button>
        )}
      </div>

      {/* Tab bar — only show when admin has both views */}
      {isAdmin && (
        <div className="flex gap-1 rounded-lg bg-muted p-1">
          <button
            onClick={() => setActiveTab("all-agents")}
            className={cn(
              "flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              activeTab === "all-agents"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            All Agents
          </button>
          <button
            onClick={() => setActiveTab("my-agents")}
            className={cn(
              "flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              activeTab === "my-agents"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            My Agents
          </button>
        </div>
      )}

      {/* All Agents view */}
      {activeTab === "all-agents" && state.kind === "data" && (
        <>
          {state.agents.length === 0 ? (
            <EmptyState
              title="No agents registered"
              description="Register your first AI agent to get started with identity management."
            />
          ) : (
            <div className="grid gap-4">
              {state.agents.map((agent) => (
                <Card
                  key={agent.agent_id}
                  className="transition-colors hover:bg-muted/50"
                >
                  <Link
                    href={`/dashboard/agents/${agent.agent_id}/activity`}
                    className="block"
                  >
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="flex items-center gap-2 text-sm font-medium">
                        <Bot className="h-4 w-4 text-muted-foreground" />
                        {agent.name || agent.agent_id}
                      </CardTitle>
                      <LifecycleBadge
                        state={
                          (agent.lifecycle_state as LifecycleState) ??
                          "registered"
                        }
                      />
                    </CardHeader>
                    <CardContent>
                      <p className="text-xs text-muted-foreground">
                        ID: <span className="font-mono">{agent.agent_id}</span>
                        {agent.created_at &&
                          ` · Created: ${new Date(agent.created_at).toLocaleDateString()}`}
                      </p>
                      <LifecycleTimeline
                        state={
                          (agent.lifecycle_state as LifecycleState) ??
                          "registered"
                        }
                        className="mt-3"
                      />
                    </CardContent>
                  </Link>
                  <div className="flex justify-end px-6 pb-4">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.preventDefault();
                        handleDelete(agent.agent_id);
                      }}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {/* My Agents view */}
      {activeTab === "my-agents" && state.kind === "my-data" && (
        <>
          {state.agents.length === 0 ? (
            <EmptyState
              title="No agents delegated to you"
              description="Ask your admin to create a delegation for you to start managing agent goals."
            />
          ) : (
            <div className="grid gap-4">
              {state.agents.map((agent) => (
                <Card
                  key={agent.agent_id}
                  className="transition-colors hover:bg-muted/50"
                >
                  <Link
                    href={`/dashboard/agents/${agent.agent_id}/goals`}
                    className="block"
                  >
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="flex items-center gap-2 text-sm font-medium">
                        <Bot className="h-4 w-4 text-muted-foreground" />
                        {agent.name}
                      </CardTitle>
                      <LifecycleBadge
                        state={
                          (agent.lifecycle_state as LifecycleState) ??
                          "registered"
                        }
                      />
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        {agent.delegated_services.length > 0 && (
                          <span>
                            Services:{" "}
                            {agent.delegated_services.join(", ")}
                          </span>
                        )}
                        {agent.my_prompt_count > 0 && (
                          <span>
                            · {agent.my_prompt_count} prompt
                            {agent.my_prompt_count !== 1 ? "s" : ""}
                          </span>
                        )}
                      </div>
                    </CardContent>
                  </Link>
                  <div className="flex justify-end px-6 pb-4">
                    <Button variant="outline" size="sm" asChild>
                      <Link
                        href={`/dashboard/agents/${agent.agent_id}/goals`}
                      >
                        <Settings2 className="mr-2 h-4 w-4" />
                        Configure Goals
                      </Link>
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
