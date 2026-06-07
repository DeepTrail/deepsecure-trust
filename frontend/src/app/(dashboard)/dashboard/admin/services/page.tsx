"use client";

import { useEffect, useState, useCallback } from "react";
import {
  ServerCog,
  Plus,
  ChevronDown,
  ChevronRight,
  Activity,
  Globe,
  Plug,
  RefreshCw,
  Search,
  Loader2,
  Pencil,
  Zap,
  Save,
  X,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton, ErrorCard, EmptyState } from "@/components/feedback";
import { AddServiceModal } from "@/components/admin/AddServiceModal";
import { AvailableToPicker } from "@/components/admin/AvailableToPicker";
import { HealthOAuthCard, type OAuthFormState } from "@/components/admin/HealthOAuthCard";
import type {
  ServiceRegistryEntry,
  ServiceOAuthConfig,
  BackendType,
  ServiceStatus,
  HealthStatus,
  DiscoveredTool,
  ConnectionTestResult,
} from "@/lib/types/admin";

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; services: ServiceRegistryEntry[] };

const STATUS_COLORS: Record<ServiceStatus, string> = {
  active: "bg-green-500/10 text-green-700 border-green-200",
  sandbox: "bg-yellow-500/10 text-yellow-700 border-yellow-200",
  disable: "bg-gray-500/10 text-gray-500 border-gray-200",
};

const HEALTH_COLORS: Record<HealthStatus, string> = {
  up: "text-green-600",
  healthy: "text-green-600",
  down: "text-red-600",
  slow: "text-yellow-600",
  stale: "text-orange-600",
  unknown: "text-gray-400",
};

const HEALTH_LABELS: Record<HealthStatus, string> = {
  up: "Healthy",
  healthy: "Healthy",
  down: "Down",
  slow: "Slow",
  stale: "Stale",
  unknown: "Unknown",
};

function HealthIndicator({ status }: { status: HealthStatus }) {
  return (
    <span className={cn("flex items-center gap-1.5 text-sm font-medium", HEALTH_COLORS[status])}>
      <span
        className={cn(
          "inline-block h-2 w-2 rounded-full",
          (status === "up" || status === "healthy") && "bg-green-500",
          status === "down" && "bg-red-500",
          status === "slow" && "bg-yellow-500",
          status === "unknown" && "bg-gray-400"
        )}
      />
      {HEALTH_LABELS[status]}
    </span>
  );
}

function TypeBadge({ type }: { type: BackendType }) {
  return (
    <Badge variant="outline" className="gap-1 text-xs">
      {type === "rest" ? <Globe className="h-3 w-3" /> : <Plug className="h-3 w-3" />}
      {type === "rest" ? "REST + OAuth" : "MCP Server"}
    </Badge>
  );
}

const STATUS_OPTIONS = ["active", "sandbox", "disable"] as const;

function ExpandedPanel({
  service,
  onUpdated,
}: {
  service: ServiceRegistryEntry;
  onUpdated: () => void;
}) {
  const isMcp = service.backend_type === "mcp";
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);
  const [editing, setEditing] = useState(false);
  const isServiceEveryone =
    (service.available_to_roles ?? []).includes("all") &&
    (service.available_to_groups ?? []).length === 0 &&
    (service.available_to_users ?? []).length === 0;
  const [editEveryone, setEditEveryone] = useState(isServiceEveryone);
  const [editGroups, setEditGroups] = useState<string[]>(service.available_to_groups ?? []);
  const [editUsers, setEditUsers] = useState<string[]>(service.available_to_users ?? []);
  const [editStatus, setEditStatus] = useState<string>(service.status);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const isRest = service.backend_type === "rest";
  const [oauthConfig, setOauthConfig] = useState<ServiceOAuthConfig | null>(null);
  const [oauthLoading, setOauthLoading] = useState(false);
  const [oauthEditing, setOauthEditing] = useState(false);
  const [oaClientId, setOaClientId] = useState("");
  const [oaClientSecret, setOaClientSecret] = useState("");
  const [oaAuthUrl, setOaAuthUrl] = useState("");
  const [oaTokenUrl, setOaTokenUrl] = useState("");
  const [oaScopes, setOaScopes] = useState("");
  const [oauthSaving, setOauthSaving] = useState(false);
  const [oauthError, setOauthError] = useState<string | null>(null);

  useEffect(() => {
    if (!isRest) return;
    setOauthLoading(true);
    apiClient<ServiceOAuthConfig>(
      `admin/services/${encodeURIComponent(service.service_id)}/oauth`
    )
      .then((cfg) => {
        setOauthConfig(cfg);
        setOaClientId(cfg.client_id);
        setOaAuthUrl(cfg.auth_url ?? "");
        setOaTokenUrl(cfg.token_url ?? "");
        setOaScopes(cfg.scopes?.join(", ") ?? "");
      })
      .catch(() => setOauthConfig(null))
      .finally(() => setOauthLoading(false));
  }, [isRest, service.service_id]);

  function handleOAuthFormChange(field: keyof OAuthFormState, value: string) {
    if (field === "clientId") setOaClientId(value);
    else if (field === "clientSecret") setOaClientSecret(value);
    else if (field === "authUrl") setOaAuthUrl(value);
    else if (field === "tokenUrl") setOaTokenUrl(value);
    else if (field === "scopes") setOaScopes(value);
  }

  function handleOAuthEditStart() {
    if (oauthConfig?.source === "env") {
      if (
        !confirm(
          "This service uses centralized credentials from environment configuration. Saving per-service credentials will override them. Continue?"
        )
      ) {
        return;
      }
    }
    setOauthEditing(true);
  }

  function handleOAuthEditCancel() {
    setOauthEditing(false);
    setOauthError(null);
    if (oauthConfig) {
      setOaClientId(oauthConfig.client_id);
      setOaAuthUrl(oauthConfig.auth_url ?? "");
      setOaTokenUrl(oauthConfig.token_url ?? "");
      setOaScopes(oauthConfig.scopes?.join(", ") ?? "");
    }
    setOaClientSecret("");
  }

  async function handleOauthSave() {
    setOauthSaving(true);
    setOauthError(null);
    try {
      const body: Record<string, unknown> = {
        client_id: oaClientId,
        client_secret: oaClientSecret,
      };
      if (oaAuthUrl) body.auth_url = oaAuthUrl;
      if (oaTokenUrl) body.token_url = oaTokenUrl;
      if (oaScopes) body.scopes = oaScopes.split(",").map((s) => s.trim()).filter(Boolean);
      const cfg = await apiClient<ServiceOAuthConfig>(
        `admin/services/${encodeURIComponent(service.service_id)}/oauth`,
        { method: "PUT", body: JSON.stringify(body) }
      );
      setOauthConfig(cfg);
      setOaClientId(cfg.client_id);
      setOaClientSecret("");
      setOaAuthUrl(cfg.auth_url ?? "");
      setOaTokenUrl(cfg.token_url ?? "");
      setOaScopes(cfg.scopes?.join(", ") ?? "");
      setOauthEditing(false);
    } catch (err) {
      setOauthError(err instanceof Error ? err.message : "Failed to save credentials");
    } finally {
      setOauthSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await apiClient<ConnectionTestResult>(
        `admin/services/${encodeURIComponent(service.service_id)}/test`,
        { method: "POST" }
      );
      setTestResult(result);
    } catch (err) {
      setTestResult({
        status: "error",
        message: err instanceof Error ? err.message : "Connection test failed",
        latency_ms: null,
      });
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setSaveError(null);
    try {
      await apiClient(
        `admin/services/${encodeURIComponent(service.service_id)}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            available_to_roles: editEveryone ? ["all"] : [],
            available_to_groups: editEveryone ? [] : editGroups,
            available_to_users: editEveryone ? [] : editUsers,
            status: editStatus,
          }),
        }
      );
      setEditing(false);
      onUpdated();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  function renderAvailableToBadges() {
    if (isServiceEveryone) {
      return <Badge variant="secondary" className="text-xs">Everyone</Badge>;
    }
    const roles = (service.available_to_roles ?? []).filter((r) => r !== "all");
    return (
      <div className="flex flex-wrap gap-1">
        {roles.map((r) => (
          <Badge key={r} variant="outline" className="text-xs capitalize">
            {r}
          </Badge>
        ))}
        {(service.available_to_groups ?? []).map((g) => (
          <Badge key={g} variant="outline" className="text-xs">
            {g}
          </Badge>
        ))}
        {(service.available_to_users ?? []).map((u) => (
          <Badge key={u} variant="outline" className="text-xs">
            {u}
          </Badge>
        ))}
      </div>
    );
  }

  const healthOAuthCardProps = {
    health: {
      latencyMs: service.health_latency_ms,
      errorCount24h: service.health_error_count_24h,
      lastCheckedAt: service.health_last_checked_at,
      status: service.health_status,
    },
    showOAuth: isRest,
    oauthConfig,
    oauthLoading,
    oauthEditing,
    oauthForm: {
      clientId: oaClientId,
      clientSecret: oaClientSecret,
      authUrl: oaAuthUrl,
      tokenUrl: oaTokenUrl,
      scopes: oaScopes,
    },
    oauthSaving,
    oauthError,
    onOAuthEditStart: handleOAuthEditStart,
    onOAuthEditCancel: handleOAuthEditCancel,
    onOAuthSave: handleOauthSave,
    onOAuthFormChange: handleOAuthFormChange,
    testResult,
  };

  function renderMcpTools() {
    if (!isMcp || !service.discovered_tools?.length) return null;
    return (
      <div className="space-y-2">
        <h4 className="text-sm font-semibold">
          Discovered Tools ({service.discovered_tools.length})
        </h4>
        <div className="flex flex-wrap gap-1">
          {service.discovered_tools.map((tool: DiscoveredTool) => (
            <Badge key={tool.name} variant="secondary" className="text-xs">
              {tool.name}
            </Badge>
          ))}
        </div>
        {service.tools_last_discovered_at && (
          <p className="text-xs text-muted-foreground">
            Last discovered: {new Date(service.tools_last_discovered_at).toLocaleString()}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="border-t bg-muted/20 px-6 py-4">
      {editing ? (
        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-3">
            <h4 className="text-sm font-semibold">Connection Details</h4>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-muted-foreground mb-1">Endpoint</dt>
                <dd className="font-mono text-xs break-all">{service.endpoint_url}</dd>
              </div>
              {isMcp && (
                <>
                  <div>
                    <dt className="text-muted-foreground mb-1">Transport</dt>
                    <dd>{service.transport}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground mb-1">Auth Method</dt>
                    <dd>{service.mcp_auth_method}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground mb-1">Protocol Version</dt>
                    <dd>{service.mcp_protocol_version}</dd>
                  </div>
                </>
              )}
              <div>
                <dt className="text-muted-foreground mb-1">Data Classification</dt>
                <dd className="capitalize">{service.data_classification}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground mb-1.5">Available To</dt>
                <dd>
                  <AvailableToPicker
                    everyone={editEveryone}
                    onEveryoneChange={setEditEveryone}
                    selectedGroups={editGroups}
                    selectedUsers={editUsers}
                    onGroupsChange={setEditGroups}
                    onUsersChange={setEditUsers}
                  />
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground mb-1.5">Status</dt>
                <dd>
                  <div className="flex gap-1">
                    {STATUS_OPTIONS.map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => setEditStatus(s)}
                        className={cn(
                          "rounded-full border px-2 py-0.5 text-xs font-medium capitalize transition-colors",
                          editStatus === s
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-border text-muted-foreground hover:border-foreground"
                        )}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </dd>
              </div>
            </dl>
          </div>

          <div className="space-y-4">
            <HealthOAuthCard mode="edit" {...healthOAuthCardProps} />
            {saveError && <p className="text-sm text-red-600">{saveError}</p>}
            {renderMcpTools()}
          </div>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="space-y-3">
            <h4 className="text-sm font-semibold">Details</h4>
            <dl className="grid grid-cols-[auto_1fr_auto_1fr] gap-x-8 gap-y-2 text-sm">
              <dt className="text-muted-foreground">Endpoint</dt>
              <dd className="font-mono text-xs break-all">{service.endpoint_url}</dd>
              <dt className="text-muted-foreground">Classification</dt>
              <dd className="capitalize">{service.data_classification}</dd>

              <dt className="text-muted-foreground">Available to</dt>
              <dd>{renderAvailableToBadges()}</dd>
              <dt className="text-muted-foreground">Status</dt>
              <dd>
                <Badge
                  variant="outline"
                  className={cn("text-xs capitalize", STATUS_COLORS[service.status])}
                >
                  {service.status}
                </Badge>
              </dd>

              {isMcp ? (
                <>
                  <dt className="text-muted-foreground">Transport</dt>
                  <dd className="text-xs">{service.transport}</dd>
                  <dt className="text-muted-foreground">Auth method</dt>
                  <dd className="text-xs">{service.mcp_auth_method ?? "—"}</dd>
                  <dt className="text-muted-foreground">Protocol</dt>
                  <dd className="col-span-3 text-xs">{service.mcp_protocol_version ?? "—"}</dd>
                </>
              ) : (
                <>
                  <dt className="text-muted-foreground">Type</dt>
                  <dd className="text-xs">REST + OAuth</dd>
                  <dt className="text-muted-foreground">Health</dt>
                  <dd>
                    <HealthIndicator status={service.health_status} />
                  </dd>
                </>
              )}
            </dl>
          </div>

          <HealthOAuthCard mode="view" {...healthOAuthCardProps} />
          {renderMcpTools()}
        </div>
      )}

      {/* Action Buttons */}
      <div className="mt-4 flex items-center gap-2 border-t pt-3">
        <Button variant="outline" size="sm" onClick={handleTest} disabled={testing}>
          {testing ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
          ) : (
            <Zap className="mr-1.5 h-3.5 w-3.5" />
          )}
          Test Connection
        </Button>

        {editing ? (
          <>
            <Button size="sm" onClick={handleSave} disabled={saving}>
              {saving ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <Save className="mr-1.5 h-3.5 w-3.5" />
              )}
              Save Changes
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setEditing(false);
                setEditEveryone(isServiceEveryone);
                setEditGroups(service.available_to_groups ?? []);
                setEditUsers(service.available_to_users ?? []);
                setEditStatus(service.status);
                setSaveError(null);
              }}
            >
              <X className="mr-1.5 h-3.5 w-3.5" />
              Cancel
            </Button>
          </>
        ) : (
          <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
            <Pencil className="mr-1.5 h-3.5 w-3.5" />
            Edit
          </Button>
        )}
      </div>
    </div>
  );
}

export default function AdminServiceCatalogPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | BackendType>("all");
  const [search, setSearch] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);

  const fetchServices = useCallback(async () => {
    try {
      const raw = await apiClient<ServiceRegistryEntry[]>("admin/services");
      const services = Array.isArray(raw) ? raw : [];
      setState({ kind: "data", services });
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof Error ? err.message : "Failed to load services",
      });
    }
  }, []);

  useEffect(() => {
    fetchServices();
  }, [fetchServices]);

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error") {
    return <ErrorCard title="Service Catalog" message={state.message} retry={fetchServices} />;
  }

  const { services } = state;

  const filtered = services.filter((s) => {
    if (filter !== "all" && s.backend_type !== filter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        s.service_id.toLowerCase().includes(q) ||
        s.display_name.toLowerCase().includes(q) ||
        (s.description ?? "").toLowerCase().includes(q)
      );
    }
    return true;
  });

  const counts = {
    all: services.length,
    rest: services.filter((s) => s.backend_type === "rest").length,
    mcp: services.filter((s) => s.backend_type === "mcp").length,
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <ServerCog className="h-6 w-6" />
            Service Catalog
          </h1>
          <p className="text-muted-foreground">
            Manage backend services, MCP servers, and OAuth integrations
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchServices}>
            <RefreshCw className="mr-1.5 h-4 w-4" />
            Refresh
          </Button>
          <Button size="sm" onClick={() => setShowAddModal(true)}>
            <Plus className="mr-1.5 h-4 w-4" />
            Add Service
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Total Services</p>
          <p className="text-2xl font-bold">{counts.all}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">REST + OAuth</p>
          <p className="text-2xl font-bold">{counts.rest}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">MCP Servers</p>
          <p className="text-2xl font-bold">{counts.mcp}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Healthy</p>
          <p className="text-2xl font-bold text-green-600">
            {services.filter((s) => s.health_status === "up" || s.health_status === "healthy").length}
          </p>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search services..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-9 w-full rounded-md border bg-background pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div className="flex rounded-md border">
          {(["all", "rest", "mcp"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "px-3 py-1.5 text-xs font-medium transition-colors",
                filter === f
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {f === "all" ? "All" : f === "rest" ? "REST" : "MCP"} ({counts[f]})
            </button>
          ))}
        </div>
      </div>

      {/* Service List */}
      {filtered.length === 0 ? (
        <EmptyState
          title="No services found"
          description={search ? "Try a different search term" : "Add your first service to get started"}
        />
      ) : (
        <div className="space-y-2">
          {filtered.map((service) => {
            const isExpanded = expandedId === service.service_id;
            return (
              <Card key={service.service_id} className="overflow-hidden">
                <button
                  onClick={() => setExpandedId(isExpanded ? null : service.service_id)}
                  className="flex w-full items-center gap-4 px-6 py-4 text-left hover:bg-muted/30 transition-colors"
                >
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                  )}

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{service.display_name}</span>
                      <span className="text-xs text-muted-foreground">
                        ({service.service_id})
                      </span>
                    </div>
                    {service.description && (
                      <p className="truncate text-sm text-muted-foreground">
                        {service.description}
                      </p>
                    )}
                  </div>

                  <TypeBadge type={service.backend_type} />

                  <Badge
                    variant="outline"
                    className={cn("text-xs capitalize", STATUS_COLORS[service.status])}
                  >
                    {service.status}
                  </Badge>

                  <HealthIndicator status={service.health_status} />

                  {service.health_latency_ms != null && (
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Activity className="h-3 w-3" />
                      {service.health_latency_ms}ms
                    </span>
                  )}
                </button>

                {isExpanded && <ExpandedPanel service={service} onUpdated={fetchServices} />}
              </Card>
            );
          })}
        </div>
      )}

      <AddServiceModal
        open={showAddModal}
        onOpenChange={setShowAddModal}
        onCreated={fetchServices}
      />
    </div>
  );
}
