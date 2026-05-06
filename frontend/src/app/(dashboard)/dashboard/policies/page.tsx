"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Shield, Plus, Trash2, Pencil } from "lucide-react";

interface Policy {
  policy_id: string;
  name: string;
  description?: string;
  permissions?: string[];
  agent_ids?: string[];
  created_at?: string;
  updated_at?: string;
}

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; policies: Policy[] };

export default function PoliciesPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const fetchPolicies = async () => {
    setState({ kind: "loading" });
    try {
      const policies = await apiClient<Policy[]>("policies/");
      setState({ kind: "data", policies: policies ?? [] });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load policies (${err.status})`
          : "Failed to load policies";
      setState({ kind: "error", message });
    }
  };

  useEffect(() => {
    fetchPolicies();
  }, []);

  const handleDelete = async (policyId: string) => {
    if (!window.confirm("Are you sure you want to delete this policy?")) return;
    try {
      await apiClient(`policies/${policyId}`, { method: "DELETE" });
      await fetchPolicies();
    } catch {
      // Will surface on next fetch
    }
  };

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error")
    return <ErrorCard title="Policies" message={state.message} retry={fetchPolicies} />;

  const { policies } = state;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Policies</h1>
        <Button size="sm" onClick={() => setCreating(!creating)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Policy
        </Button>
      </div>

      {creating && (
        <PolicyCreateForm onDone={() => { setCreating(false); fetchPolicies(); }} />
      )}

      {policies.length === 0 && !creating ? (
        <EmptyState
          title="No policies defined"
          description="Create policies to manage agent permissions and access control."
        />
      ) : (
        <div className="grid gap-4">
          {policies.map((policy) =>
            editingId === policy.policy_id ? (
              <PolicyEditForm
                key={policy.policy_id}
                policy={policy}
                onDone={() => { setEditingId(null); fetchPolicies(); }}
                onCancel={() => setEditingId(null)}
              />
            ) : (
              <Card key={policy.policy_id}>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="flex items-center gap-2 text-sm font-medium">
                    <Shield className="h-4 w-4 text-muted-foreground" />
                    {policy.name}
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setEditingId(policy.policy_id)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(policy.policy_id)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {policy.description && (
                    <p className="text-sm text-muted-foreground mb-2">{policy.description}</p>
                  )}
                  {policy.permissions && policy.permissions.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-2">
                      {policy.permissions.map((p) => (
                        <Badge key={p} variant="outline" className="text-xs">
                          {p}
                        </Badge>
                      ))}
                    </div>
                  )}
                  {policy.agent_ids && policy.agent_ids.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      Agents: {policy.agent_ids.join(", ")}
                    </p>
                  )}
                </CardContent>
              </Card>
            )
          )}
        </div>
      )}
    </div>
  );
}

function PolicyCreateForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [permissions, setPermissions] = useState("");
  const [agentIds, setAgentIds] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setError(null);

    const permList = permissions
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const agentList = agentIds
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    try {
      await apiClient("policies/", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || undefined,
          permissions: permList,
          agent_ids: agentList.length > 0 ? agentList : undefined,
        }),
      });
      onDone();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Failed to create policy (${err.status}).`);
      } else {
        setError("Failed to create policy. Please try again.");
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
              <label htmlFor="policy-name" className="text-sm font-medium">Name</label>
              <input
                id="policy-name"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="my-policy"
                required
              />
            </div>
            <div className="flex-1 space-y-1">
              <label htmlFor="policy-desc" className="text-sm font-medium">Description</label>
              <input
                id="policy-desc"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Policy description"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label htmlFor="policy-perms" className="text-sm font-medium">
              Permissions <span className="text-muted-foreground">(comma-separated)</span>
            </label>
            <input
              id="policy-perms"
              className="w-full rounded-md border px-3 py-2 text-sm font-mono"
              value={permissions}
              onChange={(e) => setPermissions(e.target.value)}
              placeholder="service:scope:action, service:scope:action"
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="policy-agents" className="text-sm font-medium">
              Agent IDs <span className="text-muted-foreground">(optional, comma-separated)</span>
            </label>
            <input
              id="policy-agents"
              className="w-full rounded-md border px-3 py-2 text-sm font-mono"
              value={agentIds}
              onChange={(e) => setAgentIds(e.target.value)}
              placeholder="agent-1, agent-2"
            />
          </div>
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
          <div className="flex gap-2">
            <Button type="submit" disabled={submitting || !name.trim()}>
              {submitting ? "Creating..." : "Create"}
            </Button>
            <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function PolicyEditForm({
  policy,
  onDone,
  onCancel,
}: {
  policy: Policy;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(policy.name);
  const [description, setDescription] = useState(policy.description ?? "");
  const [permissions, setPermissions] = useState(
    (policy.permissions ?? []).join(", ")
  );
  const [agentIds, setAgentIds] = useState(
    (policy.agent_ids ?? []).join(", ")
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setError(null);

    const permList = permissions
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const agentList = agentIds
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    try {
      await apiClient(`policies/${policy.policy_id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || undefined,
          permissions: permList,
          agent_ids: agentList.length > 0 ? agentList : undefined,
        }),
      });
      onDone();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Failed to update policy (${err.status}).`);
      } else {
        setError("Failed to update policy. Please try again.");
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
              <label htmlFor="edit-policy-name" className="text-sm font-medium">Name</label>
              <input
                id="edit-policy-name"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="my-policy"
                required
              />
            </div>
            <div className="flex-1 space-y-1">
              <label htmlFor="edit-policy-desc" className="text-sm font-medium">Description</label>
              <input
                id="edit-policy-desc"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Policy description"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label htmlFor="edit-policy-perms" className="text-sm font-medium">
              Permissions <span className="text-muted-foreground">(comma-separated)</span>
            </label>
            <input
              id="edit-policy-perms"
              className="w-full rounded-md border px-3 py-2 text-sm font-mono"
              value={permissions}
              onChange={(e) => setPermissions(e.target.value)}
              placeholder="service:scope:action, service:scope:action"
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="edit-policy-agents" className="text-sm font-medium">
              Agent IDs <span className="text-muted-foreground">(optional, comma-separated)</span>
            </label>
            <input
              id="edit-policy-agents"
              className="w-full rounded-md border px-3 py-2 text-sm font-mono"
              value={agentIds}
              onChange={(e) => setAgentIds(e.target.value)}
              placeholder="agent-1, agent-2"
            />
          </div>
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
          <div className="flex gap-2">
            <Button type="submit" disabled={submitting || !name.trim()}>
              {submitting ? "Saving..." : "Save"}
            </Button>
            <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
