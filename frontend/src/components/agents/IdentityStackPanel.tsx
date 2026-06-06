"use client";

import { useState, useEffect, useCallback, Fragment } from "react";
import { ChevronDown, ChevronRight, Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api/client";
import { getServiceDisplayName } from "./service-utils";
import { PermissionGroups } from "./DelegationsTable";
import type {
  IdentityStackResponse,
  IdentityStackLayer,
  IdentityLayerType,
  UserIdTokenStackItem,
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
    "No delegating users for this agent. ID tokens are not stored; groups appear here from login claims and organization directory when delegators exist.",
  "User Session": "No active console sessions for delegating users.",
  Delegation: "No delegations.",
  "Agent Session": "No agent sessions. Agent has not authenticated yet.",
  "Task Token":
    "No task tokens. Task tokens are created when agents execute scoped tasks (not yet in production use).",
};

function truncateId(id: string, length = 12): string {
  return id.length > length ? `${id.slice(0, length)}…` : id;
}

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
      const data = await apiClient<IdentityStackResponse>(
        `admin/agents/${agentId}/identity-stack`
      );
      setData(data);
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

  if (layer.items.length === 0) {
    return (
      <div className="text-xs text-muted-foreground bg-muted/10 rounded-md px-3 py-2">
        {EMPTY_MESSAGES[type]}
      </div>
    );
  }

  switch (type) {
    case "User ID-Token":
      return <UserIdTokenTable items={layer.items as unknown as UserIdTokenStackItem[]} />;
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

function UserIdTokenTable({ items }: { items: UserIdTokenStackItem[] }) {
  return (
    <div>
      <p className="text-[10px] text-muted-foreground mb-2">
        ID tokens are consumed at login and not stored. Groups reflect cached IdP claims and org directory membership.
      </p>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b text-muted-foreground">
            <th className="text-left py-1 font-medium">User</th>
            <th className="text-left py-1 font-medium">IdP</th>
            <th className="text-left py-1 font-medium">Groups</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-b last:border-b-0">
              <td className="py-1">{item.user}</td>
              <td className="py-1">{item.idp ?? "—"}</td>
              <td className="py-1">
                {item.groups.length > 0 ? (
                  <div className="flex gap-1 flex-wrap">
                    {item.groups.map((g) => (
                      <Badge key={g} variant="outline" className="text-[10px] px-1.5 py-0">
                        {g}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function UserSessionTable({ items }: { items: UserSessionStackItem[] }) {
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="border-b text-muted-foreground">
          <th className="text-left py-1 font-medium">Session ID</th>
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
            <td className="py-1 font-mono text-[10px]">{truncateId(item.session_id ?? item.id)}</td>
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
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  return (
    <div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b text-muted-foreground">
            <th className="w-6 py-1" />
            <th className="text-left py-1 font-medium">Delegation ID</th>
            <th className="text-left py-1 font-medium">Delegator</th>
            <th className="text-left py-1 font-medium">Permissions</th>
            <th className="text-left py-1 font-medium">Expires</th>
            <th className="text-left py-1 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const isOpen = expandedRow === item.id;
            const permissions = item.permissions ?? [];
            return (
              <Fragment key={item.id}>
                <tr
                  className="border-b cursor-pointer hover:bg-muted/20 transition-colors"
                  onClick={() => setExpandedRow(isOpen ? null : item.id)}
                >
                  <td className="py-1 pr-1">
                    {isOpen ? (
                      <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                    )}
                  </td>
                  <td className="py-1 font-mono text-[10px]">{truncateId(item.id)}</td>
                  <td className="py-1">{item.delegator}</td>
                  <td className="py-1">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-muted-foreground">
                        {item.permissions_count} permissions
                      </span>
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
                {isOpen && permissions.length > 0 && (
                  <tr>
                    <td colSpan={6} className="bg-muted/10 px-4 py-2">
                      <PermissionGroups permissions={permissions} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
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
            <th className="text-left py-1 font-medium">Delegation ID</th>
            <th className="text-left py-1 font-medium">Created</th>
            <th className="text-left py-1 font-medium">Expires</th>
            <th className="text-left py-1 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-b last:border-b-0">
              <td className="py-1 font-mono text-[10px]">{truncateId(item.session_id)}</td>
              <td className="py-1">{item.delegator}</td>
              <td className="py-1 font-mono text-[10px]">{truncateId(item.delegation_id)}</td>
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
            <td className="py-1 font-mono text-[10px]">{truncateId(item.id)}</td>
            <td className="py-1 font-mono text-[10px]">
              {item.agent_session_id ? truncateId(item.agent_session_id) : "—"}
            </td>
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
