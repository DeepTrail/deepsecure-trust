import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, CheckCircle2, XCircle, Clock, Loader2 } from "lucide-react";

export interface ActivityEvent {
  id: string;
  tool_name: string;
  status: "success" | "error" | "pending";
  timestamp: string;
  details?: string;
}

interface ActivityFeedProps {
  events: ActivityEvent[];
}

function statusIcon(status: ActivityEvent["status"]) {
  switch (status) {
    case "success":
      return <CheckCircle2 className="h-4 w-4 text-green-600" />;
    case "error":
      return <XCircle className="h-4 w-4 text-red-500" />;
    case "pending":
      return <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />;
  }
}

function statusBadgeVariant(
  status: ActivityEvent["status"]
): "default" | "destructive" | "secondary" {
  switch (status) {
    case "success":
      return "default";
    case "error":
      return "destructive";
    case "pending":
      return "secondary";
  }
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
        {events.map((event) => (
          <div
            key={event.id}
            className="flex items-start gap-3 rounded-lg border p-3"
          >
            <div className="mt-0.5">{statusIcon(event.status)}</div>
            <div className="flex-1 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium font-mono">
                  {event.tool_name}
                </span>
                <Badge variant={statusBadgeVariant(event.status)}>
                  {event.status}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                <Clock className="mr-1 inline h-3 w-3" />
                {formatTimestamp(event.timestamp)}
              </p>
              {event.details && (
                <p className="text-xs text-muted-foreground">{event.details}</p>
              )}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
