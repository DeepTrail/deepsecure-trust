import type { AuditEvent } from "@/lib/types/audit";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, CheckCircle2, XCircle, Clock } from "lucide-react";

interface ActivityFeedProps {
  events: AuditEvent[];
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

export function ActivityFeed({ events }: ActivityFeedProps) {
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

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Activity className="h-4 w-4 text-muted-foreground" />
          Recent Activity ({events.length})
        </CardTitle>
      </CardHeader>
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
      </CardContent>
    </Card>
  );
}
