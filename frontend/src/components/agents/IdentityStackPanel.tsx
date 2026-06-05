"use client";

import { useState, useEffect, useCallback } from "react";
import { ChevronDown, ChevronRight, Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api/client";
import { getServiceDisplayName } from "./service-utils";
import type {
  IdentityStackResponse,
  IdentityStackLayer,
  IdentityLayerType,
  UserSessionStackItem,
  DelegationStackItem,
  AgentSessionStackItem,
  TaskTokenStackItem,
} from "@/lib/types/admin";

interface IdentityStackPanelProps {
  agentId: string;
}

const LAYER_STYLES: Record<IdentityLayerType, string> = {
  "User ID-Token": "bg-gray-100 text-gray-600",
  "User Session": "bg-amber-100 text-amber-700",
  Delegation: "bg-blue-100 text-blue-700",
  "Agent Session": "bg-green-100 text-green-700",
  "Task Token": "bg-purple-100 text-purple-700",
};

const EMPTY_MESSAGES: Record<IdentityLayerType, string> = {
  "User ID-Token":
    "User ID-Tokens are issued by the identity provider (Google, Keycloak) and consumed during login. They are not stored by DeepSecure.",
  "User Session": "No active console sessions for delegating users.",
  Delegation: "No delegations.",
  "Agent Session": "No agent sessions. Agent has not authenticated yet.",
  "Task Token":
    "No task tokens. Task tokens are created when agents execute scoped tasks (not yet in production use).",
};

export function IdentityStackPanel({ agentId }: IdentityStackPanelProps) {
  const [data, setData] = useState<IdentityStackResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedLayer, setExpandedLayer] = useState<IdentityLayerType | null>(null);
  const [fetched, setFetched] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiClient.get(`/api/v1/admin/agents/${agentId}/identity-stack`);
      setData(resp.data);
      setFetched(true);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load identity stack";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    if (!fetched) {
      fetchData();
    }
  }, [fetched, fetchData]);

  const toggleLayer = (type: IdentityLayerType) => {
    setExpandedLayer((prev) => (prev === type ? null : type));
  };

  if (loading && !data) {
    return (
      <div className="border-t bg-muted/20 px-4 py-3">
        <h4 className="text-sm font-semibold mb-2">Identity Stack</h4>
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-4 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading identity stack…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border-t bg-muted/20 px-4 py-3">
        <h4 className="text-sm font-semibold mb-2">Identity Stack</h4>
        <div className="flex items-center gap-2 text-sm text-red-600 py-2">
          <AlertCircle className="h-4 w-4" />
          {error}
          <button
            onClick={fetchData}
            className="ml-2 inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
          >
            <RefreshCw className="h-3 w-3" /> Retry
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="border-t bg-muted/20 px-4 py-3">
      <h4 className="text-sm font-semibold mb-2">Identity Stack</h4>
      <div className="rounded-md border bg-white">
        {data.layers.map((layer) => (
          <LayerRow
            key={layer.type}
            layer={layer}
            isExpanded={expandedLayer === layer.type}
            onToggle={() => toggleLayer(layer.type as IdentityLayerType)}
          />
        ))}
      </div>
    </div>
  );
}

function LayerRow({
  layer,
  isExpanded,
  onToggle,
}: {
  layer: IdentityStackLayer;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const Chevron = isExpanded ? ChevronDown : ChevronRight;
  const badgeClass = LAYER_STYLES[layer.type as IdentityLayerType] ?? "bg-gray-100 text-gray-600";

  return (
    <div className="border-b last:border-b-0">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted/30 transition-colors"
      >
        <Chevron className="h-4 w-4 shrink-0 text-muted-foreground" />
        <Badge variant="outline" className={cn("text-xs px-2 py-0.5", badgeClass)}>
          {layer.type}
        </Badge>
        <span className="ml-auto text-xs text-muted-foreground">
          {layer.count} total · <span className={layer.active > 0 ? "text-green-600" : ""}>{layer.active} active</span>
        </span>
      </button>

      {isExpanded && (
        <div className="px-3 pb-3">
          <LayerContent layer={layer} />
        </div>
      )}
    </div>
  );
}

function LayerContent({ layer }: { layer: IdentityStackLayer }) {
  const type = layer.type as IdentityLayerType;

  if (type === "User ID-Token" || layer.items.length === 0) {
    return (
      <div className="text-xs text-muted-foreground bg-muted/10 rounded-md px-3 py-2">
        {EMPTY_MESSAGES[type]}
      </div>
    );
  }

  switch (type) {
    case "User Session":
      return <UserSessionTable items={layer.items as unknown as UserSessionStackItem[]} />;
    case "Delegation":
      return <DelegationTable items={layer.items as unknown as DelegationStackItem[]} count={layer.count} />;
    case "Agent Session":
      return <AgentSessionTable items={layer.items as unknown as AgentSessionStackItem[]} count={layer.count} />;
    case "Task Token":
      return <TaskTokenTable items={layer.items as unknown as TaskTokenStackItem[]} />;
    default:
      return null;
  }
}

function UserSessionTable({ items }: { items: UserSessionStackItem[] }) {
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="border-b text-muted-foreground">
          <th className="text-left py-1 font-medium">User</th>
          <th className="text-left py-1 font-medium">IdP</th>
          <th className="text-left py-1 font-medium">Created</th>
          <th className="text-left py-1 font-medium">Expires</th>
          <th className="text-left py-1 font-medium">Status</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id} className="border-b last:border-b-0">
            <td className="py-1">{item.user}</td>
            <td className="py-1">{item.idp ?? "—"}</td>
            <td className="py-1">{item.created_at ? new Date(item.created_at).toLocaleString() : "—"}</td>
            <td className="py-1">{item.expires_at ? new Date(item.expires_at).toLocaleString() : "—"}</td>
            <td className="py-1">
              <StatusBadge status={item.status} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DelegationTable({ items, count }: { items: DelegationStackItem[]; count: number }) {
  return (
    <div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b text-muted-foreground">
            <th className="text-left py-1 font-medium">Delegator</th>
            <th className="text-left py-1 font-medium">Permissions</th>
            <th className="text-left py-1 font-medium">Services</th>
            <th className="text-left py-1 font-medium">Expires</th>
            <th className="text-left py-1 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-b last:border-b-0">
              <td className="py-1">{item.delegator}</td>
              <td className="py-1">{item.permissions_count}</td>
              <td className="py-1">
                <div className="flex gap-1 flex-wrap">
                  {item.services.map((s) => (
                    <Badge key={s} variant="outline" className="text-[10px] px-1.5 py-0">
                      {getServiceDisplayName(s)}
                    </Badge>
                  ))}
                </div>
              </td>
              <td className="py-1">{item.expires_at ? new Date(item.expires_at).toLocaleDateString() : "—"}</td>
              <td className="py-1">
                <StatusBadge status={item.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {count > items.length && (
        <div className="text-xs text-muted-foreground mt-1">
          Showing {items.length} of {count}
        </div>
      )}
    </div>
  );
}

function AgentSessionTable({ items, count }: { items: AgentSessionStackItem[]; count: number }) {
  return (
    <div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b text-muted-foreground">
            <th className="text-left py-1 font-medium">Session ID</th>
            <th className="text-left py-1 font-medium">Delegator</th>
            <th className="text-left py-1 font-medium">Delegation</th>
            <th className="text-left py-1 font-medium">Created</th>
            <th className="text-left py-1 font-medium">Expires</th>
            <th className="text-left py-1 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-b last:border-b-0">
              <td className="py-1 font-mono text-[10px]">{item.session_id.slice(0, 12)}…</td>
              <td className="py-1">{item.delegator}</td>
              <td className="py-1 font-mono text-[10px]">{item.delegation_id.slice(0, 12)}…</td>
              <td className="py-1">{item.created_at ? new Date(item.created_at).toLocaleString() : "—"}</td>
              <td className="py-1">{item.expires_at ? new Date(item.expires_at).toLocaleString() : "—"}</td>
              <td className="py-1">
                <StatusBadge status={item.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {count > items.length && (
        <div className="text-xs text-muted-foreground mt-1">
          Showing {items.length} of {count}
        </div>
      )}
    </div>
  );
}

function TaskTokenTable({ items }: { items: TaskTokenStackItem[] }) {
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="border-b text-muted-foreground">
          <th className="text-left py-1 font-medium">Task ID</th>
          <th className="text-left py-1 font-medium">Session</th>
          <th className="text-left py-1 font-medium">Permissions</th>
          <th className="text-left py-1 font-medium">Status</th>
          <th className="text-left py-1 font-medium">Created</th>
          <th className="text-left py-1 font-medium">Deadline</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id} className="border-b last:border-b-0">
            <td className="py-1 font-mono text-[10px]">{item.id.slice(0, 12)}…</td>
            <td className="py-1 font-mono text-[10px]">{item.agent_session_id ? item.agent_session_id.slice(0, 12) + "…" : "—"}</td>
            <td className="py-1">{item.scoped_permissions_count}</td>
            <td className="py-1">
              <StatusBadge status={item.task_status} />
            </td>
            <td className="py-1">{item.created_at ? new Date(item.created_at).toLocaleString() : "—"}</td>
            <td className="py-1">{item.expires_at ? new Date(item.expires_at).toLocaleString() : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function StatusBadge({ status }: { status: string }) {
  const isActive = status === "active";
  return (
    <Badge
      variant="outline"
      className={cn(
        "text-[10px] px-1.5 py-0",
        isActive ? "text-green-600 border-green-200 bg-green-50" : "text-gray-500 border-gray-200 bg-gray-50"
      )}
    >
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </Badge>
  );
}
