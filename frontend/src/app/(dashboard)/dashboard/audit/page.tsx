"use client";

import React, { useEffect, useState, useCallback } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import type { AuditEvent, AuditEventsResponse, AuditEventType } from "@/lib/types/audit";
import { useAgentNames } from "@/hooks/useAgentNames";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import {
  ScrollText,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  XCircle,
} from "lucide-react";

interface AuditFilters {
  event_type: string;
  agent_id: string;
  tool: string;
  on_behalf_of: string;
  from_date: string;
  to_date: string;
}

const EVENT_TYPES: AuditEventType[] = [
  "mcp_tool_call",
  "permission_denied",
  "agent_auth",
  "delegation_created",
  "service_connected",
  "sso_login",
];

const EMPTY_FILTERS: AuditFilters = {
  event_type: "",
  agent_id: "",
  tool: "",
  on_behalf_of: "",
  from_date: "",
  to_date: "",
};

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; events: AuditEvent[]; total: number };

function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function EventDetailPanel({ event }: { event: AuditEvent }) {
  return (
    <div className="pl-8 py-2 border-t border-dashed text-sm text-muted-foreground space-y-1">
      {event.organization_id && (
        <div>
          <span className="font-medium">Organization:</span>{" "}
          {event.organization_id}
        </div>
      )}
      {event.arguments && (
        <div>
          <span className="font-medium">Arguments:</span>{" "}
          {JSON.stringify(event.arguments)}
        </div>
      )}
      {event.result_summary && (
        <div>
          <span className="font-medium">Result:</span> {event.result_summary}
        </div>
      )}
      {event.reason && (
        <div>
          <span className="font-medium">Reason:</span> {event.reason}
        </div>
      )}
      {event.delegation_id && (
        <div>
          <span className="font-medium">Delegation:</span>{" "}
          {event.delegation_id}
        </div>
      )}
      <div>
        <span className="font-medium">Session:</span>{" "}
        {event.agent_session_id ?? "—"} |{" "}
        <span className="font-medium">MCP:</span>{" "}
        {event.mcp_session_id ?? "—"}
      </div>
    </div>
  );
}

export default function AuditPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [filters, setFilters] = useState<AuditFilters>(EMPTY_FILTERS);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;
  const { resolve } = useAgentNames();

  const buildQueryString = useCallback(
    (f: AuditFilters): string => {
      const params = new URLSearchParams();
      if (f.event_type) params.set("event_type", f.event_type);
      if (f.agent_id) params.set("agent_id", f.agent_id);
      if (f.tool) params.set("tool", f.tool);
      if (f.on_behalf_of) params.set("on_behalf_of", f.on_behalf_of);
      if (f.from_date) params.set("from_date", f.from_date);
      if (f.to_date) params.set("to_date", f.to_date);
      params.set("limit", String(PAGE_SIZE));
      params.set("offset", String(page * PAGE_SIZE));
      const qs = params.toString();
      return qs ? `?${qs}` : "";
    },
    [page]
  );

  const fetchEvents = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const qs = buildQueryString(filters);
      const data = await apiClient<AuditEventsResponse>(
        `audit/events${qs}`
      );
      const events = data.events ?? [];
      setState({ kind: "data", events, total: data.total ?? events.length });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load audit events (${err.status})`
          : "Failed to load audit events";
      setState({ kind: "error", message });
    }
  }, [filters, buildQueryString]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const updateFilter = (key: keyof AuditFilters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(0);
  };

  const clearFilters = () => {
    setFilters(EMPTY_FILTERS);
    setPage(0);
  };

  const hasActiveFilters = Object.values(filters).some(Boolean);

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error")
    return (
      <ErrorCard
        title="Audit Trail"
        message={state.message}
        retry={fetchEvents}
      />
    );

  const { events } = state;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Audit Trail</h1>
        <Button variant="ghost" size="sm" onClick={fetchEvents}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Filter Bar */}
      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
            <div className="space-y-1">
              <label
                htmlFor="filter-event-type"
                className="text-xs font-medium text-muted-foreground"
              >
                Event Type
              </label>
              <select
                id="filter-event-type"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={filters.event_type}
                onChange={(e) => updateFilter("event_type", e.target.value)}
              >
                <option value="">All types</option>
                {EVENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label
                htmlFor="filter-agent"
                className="text-xs font-medium text-muted-foreground"
              >
                Agent ID
              </label>
              <input
                id="filter-agent"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={filters.agent_id}
                onChange={(e) => updateFilter("agent_id", e.target.value)}
                placeholder="Filter by agent..."
              />
            </div>
            <div className="space-y-1">
              <label
                htmlFor="filter-tool"
                className="text-xs font-medium text-muted-foreground"
              >
                Tool
              </label>
              <input
                id="filter-tool"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={filters.tool}
                onChange={(e) => updateFilter("tool", e.target.value)}
                placeholder="e.g. notion.search_pages"
              />
            </div>
            <div className="space-y-1">
              <label
                htmlFor="filter-user"
                className="text-xs font-medium text-muted-foreground"
              >
                User
              </label>
              <input
                id="filter-user"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={filters.on_behalf_of}
                onChange={(e) => updateFilter("on_behalf_of", e.target.value)}
                placeholder="e.g. sarah@acme.com"
              />
            </div>
            <div className="space-y-1">
              <label
                htmlFor="filter-from"
                className="text-xs font-medium text-muted-foreground"
              >
                From Date
              </label>
              <input
                id="filter-from"
                type="date"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={filters.from_date}
                onChange={(e) => updateFilter("from_date", e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label
                htmlFor="filter-to"
                className="text-xs font-medium text-muted-foreground"
              >
                To Date
              </label>
              <input
                id="filter-to"
                type="date"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={filters.to_date}
                onChange={(e) => updateFilter("to_date", e.target.value)}
              />
            </div>
          </div>
          {hasActiveFilters && (
            <div className="mt-3 flex justify-end">
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                Clear filters
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Event Table */}
      {events.length === 0 ? (
        <EmptyState
          title="No audit events"
          description={
            hasActiveFilters
              ? "No events match the current filters. Try adjusting your criteria."
              : "Audit events will appear here as agents perform actions."
          }
        />
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" role="table">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">Agent</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">On Behalf Of</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">Tool Call</th>
                  <th className="w-20 px-3 py-2.5 text-right text-xs font-medium text-muted-foreground">Duration</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">Timestamp</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">Event Type</th>
                  <th className="w-10 px-3 py-2.5 text-center text-xs font-medium text-muted-foreground">Status</th>
                  <th className="w-8 px-2 py-2.5"></th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => {
                  const isDenied = event.event_type === "permission_denied";
                  const toolDisplay = isDenied
                    ? event.attempted_tool ?? "—"
                    : event.tool ?? "—";
                  const isExpanded = expandedId === event.id;

                  return (
                    <React.Fragment key={event.id}>
                      <tr
                        className={`border-b cursor-pointer hover:bg-muted/30 transition-colors ${
                          isDenied || event.success === false
                            ? "bg-red-50 dark:bg-red-950/20"
                            : ""
                        }`}
                        onClick={() =>
                          setExpandedId(isExpanded ? null : event.id)
                        }
                      >
                        <td className="px-3 py-2.5 text-xs font-medium">
                          {event.agent_id ? resolve(event.agent_id) : "—"}
                        </td>
                        <td className="px-3 py-2.5 text-xs truncate max-w-[200px]">
                          {isDenied
                            ? <span className="text-red-600 font-medium">DENIED: {event.required_permission ?? "unknown"}</span>
                            : event.on_behalf_of ?? "—"}
                        </td>
                        <td className="px-3 py-2.5 font-mono text-xs font-medium truncate max-w-[200px]">
                          {toolDisplay}
                        </td>
                        <td className="px-3 py-2.5 text-xs text-muted-foreground tabular-nums text-right">
                          {formatDuration(event.duration_ms)}
                        </td>
                        <td className="px-3 py-2.5 text-xs text-muted-foreground tabular-nums whitespace-nowrap">
                          {new Date(event.timestamp).toLocaleString()}
                        </td>
                        <td className="px-3 py-2.5">
                          <Badge variant="outline" className="text-[10px] whitespace-nowrap">
                            {event.event_type}
                          </Badge>
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          {event.success === false || isDenied ? (
                            <XCircle className="h-4 w-4 text-red-500 inline-block" />
                          ) : (
                            <CheckCircle2 className="h-4 w-4 text-green-600 inline-block" />
                          )}
                        </td>
                        <td className="px-2 py-2.5">
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          )}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr>
                          <td colSpan={8} className="p-0">
                            <EventDetailPanel event={event} />
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-4 py-3 border-t">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page + 1}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={events.length < PAGE_SIZE}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
