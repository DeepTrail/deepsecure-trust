"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Bot, Plus, Trash2 } from "lucide-react";

interface Agent {
  agent_id: string;
  name: string;
  status?: string;
  created_at?: string;
  public_key?: string;
}

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; agents: Agent[] };

function statusBadgeVariant(status?: string): "default" | "destructive" | "secondary" {
  switch (status) {
    case "active":
      return "default";
    case "suspended":
    case "revoked":
      return "destructive";
    default:
      return "secondary";
  }
}

export default function AgentsPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [creating, setCreating] = useState(false);

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

  if (agents.length === 0 && !creating) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Agents</h1>
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Register Agent
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
        <Button size="sm" onClick={() => setCreating(!creating)}>
          <Plus className="mr-2 h-4 w-4" />
          Register Agent
        </Button>
      </div>

      {creating && <AgentCreateForm onDone={() => { setCreating(false); fetchAgents(); }} />}

      <div className="grid gap-4">
        {agents.map((agent) => (
          <Card key={agent.agent_id}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="flex items-center gap-2 text-sm font-medium">
                <Bot className="h-4 w-4 text-muted-foreground" />
                {agent.name || agent.agent_id}
              </CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant={statusBadgeVariant(agent.status)}>
                  {agent.status || "registered"}
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDelete(agent.agent_id)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">
                ID: <span className="font-mono">{agent.agent_id}</span>
                {agent.created_at && ` · Created: ${new Date(agent.created_at).toLocaleDateString()}`}
              </p>
              {agent.public_key && (
                <p className="text-xs text-muted-foreground mt-1">
                  Key: <span className="font-mono">{agent.public_key.slice(0, 16)}...</span>
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function AgentCreateForm({ onDone }: { onDone: () => void }) {
  const [agentId, setAgentId] = useState("");
  const [name, setName] = useState("");
  const [publicKey, setPublicKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!agentId.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const body: Record<string, string> = {
        agent_id: agentId.trim(),
        name: name.trim() || agentId.trim(),
      };
      if (publicKey.trim()) {
        body.public_key = publicKey.trim();
      }
      await apiClient("agents/", {
        method: "POST",
        body: JSON.stringify(body),
      });
      onDone();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("An agent with this ID already exists.");
      } else {
        setError("Failed to create agent. Please try again.");
      }
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardContent className="pt-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex items-end gap-4">
            <div className="flex-1 space-y-1">
              <label htmlFor="agent-id" className="text-sm font-medium">Agent ID</label>
              <input
                id="agent-id"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={agentId}
                onChange={(e) => setAgentId(e.target.value)}
                placeholder="my-agent"
                required
              />
            </div>
            <div className="flex-1 space-y-1">
              <label htmlFor="agent-name" className="text-sm font-medium">Name</label>
              <input
                id="agent-name"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My Agent"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label htmlFor="agent-pubkey" className="text-sm font-medium">
              Public Key <span className="text-muted-foreground">(optional, Base64 Ed25519)</span>
            </label>
            <textarea
              id="agent-pubkey"
              className="w-full rounded-md border px-3 py-2 text-sm font-mono"
              value={publicKey}
              onChange={(e) => setPublicKey(e.target.value)}
              placeholder="Base64-encoded Ed25519 public key"
              rows={2}
            />
          </div>
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
          <div className="flex gap-2">
            <Button type="submit" disabled={submitting || !agentId.trim()}>
              {submitting ? "Creating..." : "Create"}
            </Button>
            <Button type="button" variant="ghost" onClick={onDone}>
              Cancel
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
