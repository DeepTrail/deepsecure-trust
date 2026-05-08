"use client";

import { useEffect, useState, useCallback } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import { ScrollText, RefreshCw, ChevronRight, X } from "lucide-react";

interface AttributionLink {
  actor_type: "user" | "agent";
  actor_id: string;
  action: string;
  timestamp: string;
}

interface AuditEvent {
  id: string;
  event_type: string;
  token_layer: "user" | "agent" | "delegation" | "gateway";
  agent_id: string | null;
  user_id: string | null;
  timestamp: string;
  details: Record<string, unknown>;
  attribution_chain?: AttributionLink[];
}

interface AuditFilters {
  event_type: string;
  agent_id: string;
  token_layer: string;
  from_date: string;
  to_date: string;
}

const LAYER_COLORS: Record<string, string> = {
  user: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  agent: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  delegation:
    "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  gateway:
    "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
};

const EVENT_TYPES = [
  "mcp_tool_call",
  "permission_denied",
  "agent_auth",
  "delegation_created",
  "service_connected",
  "sso_login",
];

const TOKEN_LAYERS = ["user", "agent", "delegation", "gateway"];

const EMPTY_FILTERS: AuditFilters = {
  event_type: "",
  agent_id: "",
  token_layer: "",
  from_date: "",
  to_date: "",
};

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; events: AuditEvent[] };

export default function AuditPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [filters, setFilters] = useState<AuditFilters>(EMPTY_FILTERS);
  const [selectedEvent, setSelectedEvent] = useState<AuditEvent | null>(null);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;

  const buildQueryString = useCallback((f: AuditFilters): string => {
    const params = new URLSearchParams();
    if (f.event_type) params.set("event_type", f.event_type);
    if (f.agent_id) params.set("agent_id", f.agent_id);
    if (f.token_layer) params.set("token_layer", f.token_layer);
    if (f.from_date) params.set("from_date", f.from_date);
    if (f.to_date) params.set("to_date", f.to_date);
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(page * PAGE_SIZE));
    const qs = params.toString();
    return qs ? `?${qs}` : "";
  }, [page]);

  const fetchEvents = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const qs = buildQueryString(filters);
      const data = await apiClient<AuditEvent[] | { events: AuditEvent[] }>(
        `audit/events${qs}`
      );
      const events = Array.isArray(data) ? data : data.events ?? [];
      setState({ kind: "data", events });
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
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
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
                htmlFor="filter-layer"
                className="text-xs font-medium text-muted-foreground"
              >
                Token Layer
              </label>
              <select
                id="filter-layer"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={filters.token_layer}
                onChange={(e) => updateFilter("token_layer", e.target.value)}
              >
                <option value="">All layers</option>
                {TOKEN_LAYERS.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
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

      <div className="flex gap-6">
        {/* Event list */}
        <div className="flex-1 space-y-3">
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
            <>
              {events.map((event) => (
                <Card
                  key={event.id}
                  className={`cursor-pointer transition-colors hover:bg-muted/50 ${
                    selectedEvent?.id === event.id ? "ring-2 ring-primary" : ""
                  }`}
                  onClick={() => setSelectedEvent(event)}
                >
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="flex items-center gap-2 text-sm font-medium">
                      <ScrollText className="h-4 w-4 text-muted-foreground" />
                      {event.event_type}
                    </CardTitle>
                    <div className="flex gap-2 items-center">
                      <Badge
                        className={
                          LAYER_COLORS[event.token_layer] ?? ""
                        }
                      >
                        {event.token_layer}
                      </Badge>
                      <Badge variant="outline">{event.event_type}</Badge>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <span>
                        {new Date(event.timestamp).toLocaleString()}
                      </span>
                      {event.agent_id && (
                        <span>Agent: {event.agent_id}</span>
                      )}
                      {event.user_id && (
                        <span>User: {event.user_id}</span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}

              {/* Pagination */}
              <div className="flex items-center justify-between pt-2">
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
            </>
          )}
        </div>

        {/* Detail Panel */}
        {selectedEvent && (
          <div className="w-96 shrink-0">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <CardTitle className="text-base">Event Details</CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedEvent(null)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Header */}
                <div>
                  <h3 className="font-medium">{selectedEvent.event_type}</h3>
                  <p className="text-sm text-muted-foreground">
                    {new Date(selectedEvent.timestamp).toLocaleString()}
                  </p>
                </div>

                <Separator />

                {/* Metadata */}
                <div className="space-y-2">
                  <h4 className="text-sm font-medium">Metadata</h4>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">
                        Token Layer
                      </span>
                      <Badge
                        className={
                          LAYER_COLORS[selectedEvent.token_layer] ?? ""
                        }
                      >
                        {selectedEvent.token_layer}
                      </Badge>
                    </div>
                    {selectedEvent.agent_id && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">
                          Agent ID
                        </span>
                        <span className="font-mono text-xs">
                          {selectedEvent.agent_id}
                        </span>
                      </div>
                    )}
                    {selectedEvent.user_id && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">
                          User ID
                        </span>
                        <span className="font-mono text-xs">
                          {selectedEvent.user_id}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                <Separator />

                {/* Details */}
                {selectedEvent.details &&
                  Object.keys(selectedEvent.details).length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-medium">Details</h4>
                      <div className="space-y-1 text-sm">
                        {Object.entries(selectedEvent.details).map(
                          ([key, value]) => (
                            <div key={key} className="flex justify-between">
                              <span className="text-muted-foreground">
                                {key}
                              </span>
                              <span className="font-mono text-xs max-w-[200px] truncate">
                                {typeof value === "string"
                                  ? value
                                  : JSON.stringify(value)}
                              </span>
                            </div>
                          )
                        )}
                      </div>
                    </div>
                  )}

                {/* Attribution Chain */}
                {selectedEvent.attribution_chain &&
                  selectedEvent.attribution_chain.length > 0 && (
                    <>
                      <Separator />
                      <div className="space-y-2">
                        <h4 className="text-sm font-medium">
                          Attribution Chain
                        </h4>
                        <ol className="space-y-2">
                          {selectedEvent.attribution_chain.map(
                            (link, index) => (
                              <li
                                key={index}
                                className="flex items-start gap-2 text-sm"
                              >
                                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
                                  {index + 1}
                                </span>
                                <div>
                                  <div className="flex items-center gap-1">
                                    <Badge
                                      variant={
                                        link.actor_type === "user"
                                          ? "secondary"
                                          : "default"
                                      }
                                      className="text-xs"
                                    >
                                      {link.actor_type}
                                    </Badge>
                                    <span className="font-mono text-xs">
                                      {link.actor_id}
                                    </span>
                                  </div>
                                  <p className="text-xs text-muted-foreground">
                                    {link.action} —{" "}
                                    {new Date(
                                      link.timestamp
                                    ).toLocaleTimeString()}
                                  </p>
                                </div>
                              </li>
                            )
                          )}
                        </ol>
                      </div>
                    </>
                  )}
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
