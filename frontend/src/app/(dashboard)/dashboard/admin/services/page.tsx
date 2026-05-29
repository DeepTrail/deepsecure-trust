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
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton, ErrorCard, EmptyState } from "@/components/feedback";
import { AddServiceModal } from "@/components/admin/AddServiceModal";
import type {
  ServiceRegistryEntry,
  BackendType,
  ServiceStatus,
  HealthStatus,
  DiscoveredTool,
} from "@/lib/types/admin";

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; services: ServiceRegistryEntry[] };

const STATUS_COLORS: Record<ServiceStatus, string> = {
  active: "bg-green-500/10 text-green-700 border-green-200",
  sandbox: "bg-yellow-500/10 text-yellow-700 border-yellow-200",
  review: "bg-blue-500/10 text-blue-700 border-blue-200",
  disabled: "bg-gray-500/10 text-gray-500 border-gray-200",
};

const HEALTH_COLORS: Record<HealthStatus, string> = {
  up: "text-green-600",
  down: "text-red-600",
  slow: "text-yellow-600",
  unknown: "text-gray-400",
};

const HEALTH_LABELS: Record<HealthStatus, string> = {
  up: "Healthy",
  down: "Down",
  slow: "Slow",
  unknown: "Unknown",
};

function HealthIndicator({ status }: { status: HealthStatus }) {
  return (
    <span className={cn("flex items-center gap-1.5 text-sm font-medium", HEALTH_COLORS[status])}>
      <span
        className={cn(
          "inline-block h-2 w-2 rounded-full",
          status === "up" && "bg-green-500",
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

function ExpandedPanel({ service }: { service: ServiceRegistryEntry }) {
  const isMcp = service.backend_type === "mcp";
  return (
    <div className="border-t bg-muted/20 px-6 py-4">
      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-3">
          <h4 className="text-sm font-semibold">Connection Details</h4>
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Endpoint</dt>
              <dd className="font-mono text-xs">{service.endpoint_url}</dd>
            </div>
            {isMcp && (
              <>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Transport</dt>
                  <dd>{service.transport}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Auth Method</dt>
                  <dd>{service.mcp_auth_method}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Protocol Version</dt>
                  <dd>{service.mcp_protocol_version}</dd>
                </div>
              </>
            )}
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Data Classification</dt>
              <dd className="capitalize">{service.data_classification}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Available To</dt>
              <dd>{service.available_to_roles.join(", ")}</dd>
            </div>
          </dl>
        </div>

        <div className="space-y-3">
          <h4 className="text-sm font-semibold">Health & Monitoring</h4>
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Latency</dt>
              <dd>
                {service.health_latency_ms != null ? `${service.health_latency_ms}ms` : "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Errors (24h)</dt>
              <dd>{service.health_error_count_24h}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Last Checked</dt>
              <dd>
                {service.health_last_checked_at
                  ? new Date(service.health_last_checked_at).toLocaleString()
                  : "Never"}
              </dd>
            </div>
          </dl>

          {isMcp && service.discovered_tools && service.discovered_tools.length > 0 && (
            <div className="mt-4">
              <h4 className="mb-2 text-sm font-semibold">
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
                <p className="mt-1 text-xs text-muted-foreground">
                  Last discovered:{" "}
                  {new Date(service.tools_last_discovered_at).toLocaleString()}
                </p>
              )}
            </div>
          )}
        </div>
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
      const data = await apiClient<{ services: ServiceRegistryEntry[] }>(
        "admin/services"
      );
      setState({ kind: "data", services: data.services ?? [] });
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
            {services.filter((s) => s.health_status === "up").length}
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

                {isExpanded && <ExpandedPanel service={service} />}
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
