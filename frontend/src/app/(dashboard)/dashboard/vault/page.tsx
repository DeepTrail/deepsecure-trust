"use client";

import React, { useEffect, useState, useCallback } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import { useUserRole } from "@/hooks/useUserRole";
import { Lock, Plus, Trash2, Key, Shield, Bot, Server, ChevronDown, ChevronRight, Activity, ExternalLink } from "lucide-react";
import type {
  VaultTokenItem,
  RefreshLogEntry,
  CredentialItem,
  SecretItem,
  EncryptionStatus,
  AgentSessionVaultItem,
  AgentSessionsVaultResponse,
  LinkedAgent,
  AgentLinkageResponse,
} from "@/lib/types/vault";

type Tab = "oauth-tokens" | "secrets" | "split-key-credentials" | "agent-sessions" | "service-credentials";

const TAB_META: { key: Tab; label: string; icon: React.ReactNode; adminOnly?: boolean }[] = [
  { key: "service-credentials", label: "Service Credentials", icon: <Server className="h-4 w-4" />, adminOnly: true },
  { key: "oauth-tokens", label: "OAuth Tokens", icon: <Key className="h-4 w-4" /> },
  { key: "secrets", label: "Secrets", icon: <Lock className="h-4 w-4" /> },
  { key: "split-key-credentials", label: "Split-Key Credentials", icon: <Bot className="h-4 w-4" /> },
  { key: "agent-sessions", label: "Agent Sessions", icon: <Activity className="h-4 w-4" /> },
];

export default function VaultPage() {
  const { isAdmin, isLoading: roleLoading } = useUserRole();
  const [tab, setTab] = useState<Tab | null>(null);
  const [encryptionStatus, setEncryptionStatus] = useState<EncryptionStatus | null>(null);

  useEffect(() => {
    apiClient<EncryptionStatus>("vault/encryption-status").then(setEncryptionStatus).catch(() => {});
  }, []);

  useEffect(() => {
    if (!roleLoading && tab === null) {
      setTab(isAdmin ? "service-credentials" : "oauth-tokens");
    }
  }, [roleLoading, isAdmin, tab]);

  if (roleLoading || tab === null) return <PageSkeleton />;

  const visibleTabs = TAB_META.filter((t) => !t.adminOnly || isAdmin);

  function encBadgeFor(category: keyof EncryptionStatus) {
    if (!encryptionStatus) return null;
    const val = encryptionStatus[category];
    const isKms = val === "gcp-kms" || val === "kms";
    return (
      <Badge variant="outline" className={isKms ? "border-green-500 text-green-700" : "border-amber-500 text-amber-700"}>
        {val === "gcp-kms" ? "KMS" : val === "kms" ? "KMS" : val === "fernet" ? "Fernet" : val === "shamir_split_key" ? "Shamir" : val}
      </Badge>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">Vault</h1>
          <Shield className="h-5 w-5 text-muted-foreground" />
        </div>
      </div>

      <div className="flex gap-1 border-b">
        {visibleTabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground/40"
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {tab === "oauth-tokens" && <OAuthTokensTab encBadge={encBadgeFor("vault_tokens")} />}
      {tab === "secrets" && <SecretsTab encBadge={encBadgeFor("secrets")} />}
      {tab === "split-key-credentials" && <SplitKeyCredentialsTab />}
      {tab === "agent-sessions" && <AgentSessionsTab />}
      {tab === "service-credentials" && isAdmin && <ServiceCredentialsTab encBadge={encBadgeFor("service_credentials")} />}
    </div>
  );
}

// ─── OAuth Tokens Tab ────────────────────────────────────────────────────────

function OAuthTokensTab({ encBadge }: { encBadge: React.ReactNode }) {
  const [tokens, setTokens] = useState<VaultTokenItem[]>([]);
  const [linkage, setLinkage] = useState<Record<string, LinkedAgent[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedRef, setExpandedRef] = useState<string | null>(null);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    try {
      const [tokenData, linkageData] = await Promise.allSettled([
        apiClient<{ tokens: VaultTokenItem[] }>("vault/user-tokens"),
        apiClient<AgentLinkageResponse>("vault/user-tokens/agent-linkage"),
      ]);
      setTokens(tokenData.status === "fulfilled" ? tokenData.value.tokens ?? [] : []);
      setLinkage(linkageData.status === "fulfilled" ? linkageData.value.linkage ?? {} : {});
      if (tokenData.status === "rejected") {
        const err = tokenData.reason;
        throw err;
      }
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? `Error ${err.status}` : "Failed to load tokens");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch_(); }, [fetch_]);

  if (loading) return <PageSkeleton />;
  if (error) return <ErrorCard title="OAuth Tokens" message={error} retry={fetch_} />;

  const colCount = 9;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold">Your OAuth Tokens</h2>
        {encBadge}
      </div>
      {tokens.length === 0 ? (
        <EmptyState title="No OAuth tokens" description="Connect services to see your stored tokens here." />
      ) : (
        <div className="rounded-md border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="w-8 px-2 py-3" />
                <th className="px-4 py-3 text-left font-medium">Service</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Scopes</th>
                <th className="px-4 py-3 text-left font-medium">Used by</th>
                <th className="px-4 py-3 text-left font-medium">Connected</th>
                <th className="px-4 py-3 text-left font-medium">Expires</th>
                <th className="px-4 py-3 text-left font-medium">Last Refreshed</th>
                <th className="px-4 py-3 text-left font-medium">Last Used</th>
              </tr>
            </thead>
            <tbody>
              {tokens.map((t) => {
                const isExpanded = expandedRef === t.token_ref;
                const hasLog = t.refresh_log && t.refresh_log.length > 0;
                return (
                  <React.Fragment key={t.token_ref}>
                    <tr
                      className={`border-b last:border-b-0 ${hasLog ? "cursor-pointer hover:bg-muted/30" : ""}`}
                      onClick={() => hasLog && setExpandedRef(isExpanded ? null : t.token_ref)}
                    >
                      <td className="w-8 px-2 py-3 text-muted-foreground">
                        {hasLog ? (
                          isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />
                        ) : null}
                      </td>
                      <td className="px-4 py-3 font-medium capitalize">{t.service_id}</td>
                      <td className="px-4 py-3">
                        <StatusBadge status={t.status} />
                      </td>
                      <td className="px-4 py-3">
                        {t.scopes_granted?.length ? (
                          <div className="flex flex-wrap gap-1">
                            {t.scopes_granted.slice(0, 3).map((s) => (
                              <Badge key={s} variant="secondary" className="text-[10px]">{s}</Badge>
                            ))}
                            {t.scopes_granted.length > 3 && (
                              <Badge variant="outline" className="text-[10px]">+{t.scopes_granted.length - 3}</Badge>
                            )}
                          </div>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <AgentBadges agents={linkage[t.service_id] ?? []} />
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{fmtDate(t.created_at)}</td>
                      <td className="px-4 py-3 text-muted-foreground">{fmtDate(t.expires_at)}</td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {t.last_refreshed_at ? (
                          <span title={`Refreshed ${t.refresh_count} time${t.refresh_count !== 1 ? "s" : ""}`}>
                            {fmtRelative(t.last_refreshed_at)}
                          </span>
                        ) : (
                          <span className="text-muted-foreground/50">Never</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{fmtDate(t.last_used_at)}</td>
                    </tr>
                    {isExpanded && hasLog && (
                      <tr>
                        <td colSpan={colCount} className="px-6 py-3 bg-muted/20">
                          <RefreshHistory log={t.refresh_log} />
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
    </div>
  );
}

function RefreshHistory({ log }: { log: RefreshLogEntry[] }) {
  const reversed = [...log].reverse();
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium text-muted-foreground mb-2">
        Refresh History (last {log.length} event{log.length !== 1 ? "s" : ""})
      </p>
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="text-left text-muted-foreground border-b">
            <th className="py-1 pr-4 font-medium">Timestamp</th>
            <th className="py-1 pr-4 font-medium">Status</th>
            <th className="py-1 pr-4 font-medium">Latency</th>
            <th className="py-1 font-medium">Details</th>
          </tr>
        </thead>
        <tbody>
          {reversed.map((entry, i) => (
            <tr key={i} className="border-b border-dashed last:border-0">
              <td className="py-1 pr-4 text-muted-foreground whitespace-nowrap">
                {fmtRelative(entry.timestamp)}
              </td>
              <td className="py-1 pr-4">
                <span className={
                  entry.status === "success"
                    ? "text-green-600 font-medium"
                    : "text-red-600 font-medium"
                }>
                  {entry.status === "success" ? "✓ success" : "✗ failure"}
                </span>
              </td>
              <td className="py-1 pr-4 text-muted-foreground tabular-nums">
                {entry.latency_ms != null ? `${entry.latency_ms}ms` : "—"}
              </td>
              <td className="py-1 text-muted-foreground">
                {entry.status === "success"
                  ? entry.new_expires_in
                    ? `new TTL: ${Math.round(entry.new_expires_in / 60)}min`
                    : "refreshed"
                  : entry.error
                    ? <span className="text-red-500">{entry.error}</span>
                    : "unknown error"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Secrets Tab ─────────────────────────────────────────────────────────────

function SecretsTab({ encBadge }: { encBadge: React.ReactNode }) {
  const [secrets, setSecrets] = useState<SecretItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient<SecretItem[] | { secrets: SecretItem[] }>("vault/secrets");
      const list = Array.isArray(data) ? data : data.secrets ?? [];
      setSecrets(list);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? `Error ${err.status}` : "Failed to load secrets");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch_(); }, [fetch_]);

  const handleDelete = async (name: string) => {
    if (!window.confirm(`Delete secret '${name}'? This cannot be undone.`)) return;
    try {
      await apiClient(`vault/secrets/${name}`, { method: "DELETE" });
      await fetch_();
    } catch { /* retry on next fetch */ }
  };

  if (loading) return <PageSkeleton />;
  if (error) return <ErrorCard title="Secrets" message={error} retry={fetch_} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">Stored Secrets</h2>
          {encBadge}
        </div>
        <Button size="sm" onClick={() => setCreating(!creating)}>
          <Plus className="mr-2 h-4 w-4" />
          Store Secret
        </Button>
      </div>

      {creating && (
        <SecretCreateForm onDone={() => { setCreating(false); fetch_(); }} />
      )}

      {secrets.length === 0 && !creating ? (
        <EmptyState title="No secrets stored" description="Store API keys and credentials securely for your agents." />
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
                {secret.service && <Badge variant="outline">{secret.service}</Badge>}
                {secret.created_at && <span>Created: {new Date(secret.created_at).toLocaleDateString()}</span>}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Split-Key Credentials Tab (renamed from Agent Credentials) ──────────────

function SplitKeyCredentialsTab() {
  const [credentials, setCredentials] = useState<CredentialItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient<{ credentials: CredentialItem[] }>("vault/user-credentials");
      setCredentials(data.credentials ?? []);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? `Error ${err.status}` : "Failed to load credentials");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch_(); }, [fetch_]);

  if (loading) return <PageSkeleton />;
  if (error) return <ErrorCard title="Split-Key Credentials" message={error} retry={fetch_} />;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Split-Key Credentials</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Ed25519 agents only. GCP/AWS workload-identity agents use Agent Sessions.
        </p>
      </div>
      {credentials.length === 0 ? (
        <EmptyState
          title="No split-key credentials"
          description="Split-key credentials appear here when Ed25519 agents are issued ephemeral keys. GCP/AWS workload-identity agents use the Agent Sessions tab instead."
        />
      ) : (
        <div className="rounded-md border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-3 text-left font-medium">Agent</th>
                <th className="px-4 py-3 text-left font-medium">Credential ID</th>
                <th className="px-4 py-3 text-left font-medium">Scope</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Issued</th>
                <th className="px-4 py-3 text-left font-medium">Expires</th>
              </tr>
            </thead>
            <tbody>
              {credentials.map((c) => (
                <tr key={c.credential_id} className="border-b last:border-b-0">
                  <td className="px-4 py-3 font-medium font-mono text-xs">{c.agent_id}</td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    {c.credential_id.length > 16
                      ? `${c.credential_id.slice(0, 8)}...${c.credential_id.slice(-8)}`
                      : c.credential_id}
                  </td>
                  <td className="px-4 py-3">{c.scope ?? <span className="text-muted-foreground">—</span>}</td>
                  <td className="px-4 py-3"><StatusBadge status={c.status} /></td>
                  <td className="px-4 py-3 text-muted-foreground">{fmtDate(c.issued_at)}</td>
                  <td className="px-4 py-3 text-muted-foreground">{fmtDate(c.expires_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Agent Sessions Tab ─────────────────────────────────────────────────────

function AgentSessionsTab() {
  const [sessions, setSessions] = useState<AgentSessionVaultItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient<AgentSessionsVaultResponse>("vault/agent-sessions");
      setSessions(data.sessions ?? []);
      setTotal(data.total ?? 0);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? `Error ${err.status}` : "Failed to load agent sessions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch_(); }, [fetch_]);

  if (loading) return <PageSkeleton />;
  if (error) return <ErrorCard title="Agent Sessions" message={error} retry={fetch_} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Agent Sessions</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Active sessions for agents you have delegated permissions to.
          </p>
        </div>
        <a
          href="/dashboard/admin/agents"
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          View in Fleet
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>
      {sessions.length === 0 ? (
        <EmptyState
          title="No agent sessions"
          description="Sessions appear here when agents you have delegated to create active sessions. Delegate permissions to an agent to get started."
        />
      ) : (
        <>
          <div className="rounded-md border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-4 py-3 text-left font-medium">Agent</th>
                  <th className="px-4 py-3 text-left font-medium">Status</th>
                  <th className="px-4 py-3 text-left font-medium">Permissions</th>
                  <th className="px-4 py-3 text-left font-medium">Created</th>
                  <th className="px-4 py-3 text-left font-medium">Expires</th>
                  <th className="px-4 py-3 text-left font-medium">Last Activity</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.session_id} className="border-b last:border-b-0">
                    <td className="px-4 py-3">
                      <div className="flex flex-col">
                        <span className="font-medium">{s.agent_name}</span>
                        <span className="text-xs text-muted-foreground font-mono">{s.agent_id}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={s.status} /></td>
                    <td className="px-4 py-3">
                      <Badge variant="secondary">{s.permissions_count} scope{s.permissions_count !== 1 ? "s" : ""}</Badge>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{fmtDate(s.created_at)}</td>
                    <td className="px-4 py-3 text-muted-foreground">{fmtDate(s.expires_at)}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {s.last_activity_at ? fmtRelative(s.last_activity_at) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {total > sessions.length && (
            <p className="text-sm text-muted-foreground text-center">
              Showing {sessions.length} of {total} sessions
            </p>
          )}
        </>
      )}
    </div>
  );
}

// ─── Service Credentials Tab (admin only) ────────────────────────────────────

interface AdminService {
  service_id: string;
  display_name: string;
  backend_type: string;
  status: string;
  mcp_auth_method?: string;
  mcp_auth_configured?: boolean;
  updated_at?: string;
}

function ServiceCredentialsTab({ encBadge }: { encBadge: React.ReactNode }) {
  const [services, setServices] = useState<AdminService[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient<AdminService[]>("admin/services");
      setServices(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? `Error ${err.status}` : "Failed to load services");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch_(); }, [fetch_]);

  if (loading) return <PageSkeleton />;
  if (error) return <ErrorCard title="Service Credentials" message={error} retry={fetch_} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold">Service Credentials</h2>
        {encBadge}
        <span className="text-xs text-muted-foreground ml-2">
          Manage credentials via the Service Catalog page
        </span>
      </div>
      {services.length === 0 ? (
        <EmptyState title="No services configured" description="Add services in the Service Catalog." />
      ) : (
        <div className="rounded-md border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-3 text-left font-medium">Service</th>
                <th className="px-4 py-3 text-left font-medium">Type</th>
                <th className="px-4 py-3 text-left font-medium">Auth Method</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {services.map((s) => (
                <tr key={s.service_id} className="border-b last:border-b-0">
                  <td className="px-4 py-3 font-medium">{s.display_name}</td>
                  <td className="px-4 py-3">
                    <Badge variant="outline">{s.backend_type.toUpperCase()}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    {s.backend_type === "rest" || s.backend_type === "oauth" ? (
                      <span className="text-muted-foreground">OAuth</span>
                    ) : s.mcp_auth_method && s.mcp_auth_method !== "none" ? (
                      <div className="flex items-center gap-1">
                        <span className="capitalize">{s.mcp_auth_method.replace(/_/g, " ")}</span>
                        {s.mcp_auth_configured && <Badge variant="secondary" className="text-[10px]">Configured</Badge>}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">None</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={s.status === "active" ? "default" : "secondary"}>
                      {s.status}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Shared components ───────────────────────────────────────────────────────

function AgentBadges({ agents }: { agents: LinkedAgent[] }) {
  if (agents.length === 0) {
    return <span className="text-muted-foreground">—</span>;
  }
  const shown = agents.slice(0, 2);
  const overflow = agents.length - shown.length;
  return (
    <div className="flex flex-wrap gap-1">
      {shown.map((a) => (
        <Badge key={a.agent_id} variant="secondary" className="text-[10px]">
          {a.agent_name}
        </Badge>
      ))}
      {overflow > 0 && (
        <Badge variant="outline" className="text-[10px]" title={agents.map(a => a.agent_name).join(", ")}>
          +{overflow}
        </Badge>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    active: "bg-green-100 text-green-800 border-green-300",
    valid: "bg-green-100 text-green-800 border-green-300",
    expiring_soon: "bg-amber-100 text-amber-800 border-amber-300",
    expired: "bg-red-100 text-red-800 border-red-300",
    revoked: "bg-red-100 text-red-800 border-red-300",
  };
  const display = status.replace(/_/g, " ");
  return (
    <Badge variant="outline" className={`capitalize ${colors[status] ?? ""}`}>
      {display}
    </Badge>
  );
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function fmtRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
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
