"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Lock, Plus, Trash2 } from "lucide-react";

interface Secret {
  name: string;
  service?: string;
  created_at?: string;
  updated_at?: string;
}

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; secrets: Secret[] };

export default function VaultPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [creating, setCreating] = useState(false);

  const fetchSecrets = async () => {
    setState({ kind: "loading" });
    try {
      const data = await apiClient<Secret[] | { secrets: Secret[] }>("vault/secrets");
      const secrets = Array.isArray(data) ? data : data.secrets ?? [];
      setState({ kind: "data", secrets });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.status === 401
            ? "Vault access requires agent-level authentication. Secrets are managed through the CLI/SDK."
            : `Failed to load vault (${err.status})`
          : "Failed to load vault";
      setState({ kind: "error", message });
    }
  };

  useEffect(() => {
    fetchSecrets();
  }, []);

  const handleDelete = async (name: string) => {
    if (!window.confirm(`Delete secret '${name}'? This cannot be undone.`)) return;
    try {
      await apiClient(`vault/secrets/${name}`, { method: "DELETE" });
      await fetchSecrets();
    } catch { /* retry on next fetch */ }
  };

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error")
    return <ErrorCard title="Vault" message={state.message} retry={fetchSecrets} />;

  const { secrets } = state;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Vault</h1>
        <Button size="sm" onClick={() => setCreating(!creating)}>
          <Plus className="mr-2 h-4 w-4" />
          Store Secret
        </Button>
      </div>

      {creating && (
        <SecretCreateForm onDone={() => { setCreating(false); fetchSecrets(); }} />
      )}

      {secrets.length === 0 && !creating ? (
        <EmptyState
          title="No secrets stored"
          description="Store API keys and credentials securely for your agents."
        />
      ) : (
        <div className="grid gap-4">
          {secrets.map((secret) => (
            <Card key={secret.name}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-medium">
                  <Lock className="h-4 w-4 text-muted-foreground" />
                  <span className="font-mono">{secret.name}</span>
                </CardTitle>
                <Button variant="ghost" size="sm" onClick={() => handleDelete(secret.name)}>
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </CardHeader>
              <CardContent className="flex items-center gap-3 text-xs text-muted-foreground">
                {secret.service && (
                  <Badge variant="outline">{secret.service}</Badge>
                )}
                {secret.created_at && (
                  <span>Created: {new Date(secret.created_at).toLocaleDateString()}</span>
                )}
                {secret.updated_at && (
                  <span>Updated: {new Date(secret.updated_at).toLocaleDateString()}</span>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function SecretCreateForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const [service, setService] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !value.trim()) return;
    setSubmitting(true);
    try {
      await apiClient("vault/store", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          value: value.trim(),
          service: service.trim() || undefined,
        }),
      });
      onDone();
    } catch {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardContent className="pt-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex gap-4">
            <div className="flex-1 space-y-1">
              <label htmlFor="secret-name" className="text-sm font-medium">Name</label>
              <input
                id="secret-name"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="NOTION_API_KEY"
                required
              />
            </div>
            <div className="flex-1 space-y-1">
              <label htmlFor="secret-service" className="text-sm font-medium">Service</label>
              <input
                id="secret-service"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={service}
                onChange={(e) => setService(e.target.value)}
                placeholder="notion (optional)"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label htmlFor="secret-value" className="text-sm font-medium">Value</label>
            <input
              id="secret-value"
              type="password"
              className="w-full rounded-md border px-3 py-2 text-sm"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>
          <div className="flex gap-2">
            <Button type="submit" disabled={submitting || !name.trim() || !value.trim()}>
              {submitting ? "Storing..." : "Store"}
            </Button>
            <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
