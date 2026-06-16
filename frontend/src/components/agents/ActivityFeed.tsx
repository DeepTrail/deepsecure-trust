"use client";

import { useState, useCallback } from "react";
import type { AuditEvent } from "@/lib/types/audit";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  ChevronDown,
  ChevronRight,
  Loader2,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";

const PAGE_SIZE = 10;

interface ActivityFeedProps {
  events: AuditEvent[];
  agentId?: string;
  totalFromServer?: number;
}

function statusIcon(event: AuditEvent) {
  if (event.success === false || event.event_type === "permission_denied") {
    return <XCircle className="h-4 w-4 text-red-500" />;
  }
  return <CheckCircle2 className="h-4 w-4 text-green-600" />;
}

function statusBadgeVariant(
  event: AuditEvent
): "default" | "destructive" | "secondary" {
  if (event.success === false || event.event_type === "permission_denied") {
    return "destructive";
  }
  return "default";
}

function statusLabel(event: AuditEvent): string {
  if (event.event_type === "permission_denied") return "denied";
  if (event.success === false) return "error";
  if (event.success === true) return "success";
  return "unknown";
}

function formatTimestamp(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

interface AuditQueryResponse {
  events: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
}

export function ActivityFeed({
  events: initialEvents,
  agentId,
  totalFromServer,
}: ActivityFeedProps) {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<AuditEvent[]>(initialEvents);
  const [hasMore, setHasMore] = useState(
    totalFromServer != null
      ? initialEvents.length < totalFromServer
      : initialEvents.length >= PAGE_SIZE
  );
  const [loadingMore, setLoadingMore] = useState(false);

  const displayCount = events.length;
  const totalCount = totalFromServer ?? displayCount;

  const loadMore = useCallback(async () => {
    if (!agentId || loadingMore) return;
    setLoadingMore(true);
    try {
      const offset = events.length;
      const data = await apiClient<AuditQueryResponse | AuditEvent[]>(
        `audit/events?agent_id=${agentId}&limit=${PAGE_SIZE}&offset=${offset}`
      );

      let newEvents: AuditEvent[];
      if (Array.isArray(data)) {
        newEvents = data;
        setHasMore(newEvents.length >= PAGE_SIZE);
      } else {
        newEvents = data.events ?? [];
        setHasMore(offset + newEvents.length < data.total);
      }

      setEvents((prev) => {
        const existingIds = new Set(prev.map((e) => e.id));
        const deduped = newEvents.filter((e) => !existingIds.has(e.id));
        return [...prev, ...deduped];
      });
    } catch {
      // silently fail — user can retry
    } finally {
      setLoadingMore(false);
    }
  }, [agentId, events.length, loadingMore]);

  if (events.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          <Activity className="mx-auto mb-2 h-8 w-8" />
          No recent activity for this agent.
        </CardContent>
      </Card>
    );
  }

  const preview = events[0];

  return (
    <Card>
      <CardHeader>
        <button
          type="button"
          className="flex w-full items-center justify-between"
          onClick={() => setOpen(!open)}
        >
          <CardTitle className="flex items-center gap-2 text-sm font-medium cursor-pointer hover:opacity-80 transition-opacity">
            {open ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
            <Activity className="h-4 w-4 text-muted-foreground" />
            Recent Activity
          </CardTitle>
          <Badge variant="secondary" className="text-xs">
            {totalCount} total
          </Badge>
        </button>
      </CardHeader>

      {/* Preview when collapsed */}
      {!open && preview && (
        <CardContent className="pt-0 pb-3">
          <p className="text-xs text-muted-foreground">
            Latest: {preview.tool ?? preview.event_type} ·{" "}
            {formatTimestamp(preview.timestamp)} ·{" "}
            {preview.success === false ? "error" : "success"}
          </p>
        </CardContent>
      )}

      {open && (
        <CardContent className="space-y-3">
          {events.map((event) => {
            const toolDisplay =
              event.event_type === "permission_denied"
                ? event.attempted_tool ?? "—"
                : event.tool ?? event.event_type;

            return (
              <div
                key={event.id}
                className="flex items-start gap-3 rounded-lg border p-3"
              >
                <div className="mt-0.5">{statusIcon(event)}</div>
                <div className="flex-1 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium font-mono">
                      {toolDisplay}
                    </span>
                    <Badge variant={statusBadgeVariant(event)}>
                      {statusLabel(event)}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    <Clock className="mr-1 inline h-3 w-3" />
                    {formatTimestamp(event.timestamp)}
                  </p>
                  {event.result_summary && (
                    <p className="text-xs text-muted-foreground">
                      {event.result_summary}
                    </p>
                  )}
                </div>
              </div>
            );
          })}

          {/* Load More */}
          {hasMore && agentId && (
            <div className="flex justify-center pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={loadMore}
                disabled={loadingMore}
                className="text-xs"
              >
                {loadingMore ? (
                  <>
                    <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                    Loading…
                  </>
                ) : (
                  `Load More (showing ${displayCount} of ${totalCount})`
                )}
              </Button>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
