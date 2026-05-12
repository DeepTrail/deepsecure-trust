"use client";

import { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { History, Globe, Clock, CheckCircle2, XCircle } from "lucide-react";

export interface AgentSession {
  session_id: string;
  agent_id: string;
  delegation_id: string;
  is_active: boolean;
  source_ip: string | null;
  created_at: string;
  expires_at: string;
  last_activity_at: string | null;
}

interface SessionsResponse {
  sessions: AgentSession[];
  total: number;
}

interface SessionHistoryTableProps {
  agentId: string;
  className?: string;
}

function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function relativeTime(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  } catch {
    return iso;
  }
}

export function SessionHistoryTable({
  agentId,
  className,
}: SessionHistoryTableProps) {
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchSessions() {
      setLoading(true);
      setError(null);
      try {
        const data = await apiClient<SessionsResponse | AgentSession[]>(
          `agents/${agentId}/sessions`
        );

        if (cancelled) return;

        if (Array.isArray(data)) {
          setSessions(data);
          setTotal(data.length);
        } else {
          setSessions(data.sessions ?? []);
          setTotal(data.total ?? 0);
        }
      } catch {
        if (!cancelled) setError("Failed to load sessions");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchSessions();
    return () => {
      cancelled = true;
    };
  }, [agentId]);

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between text-sm font-medium">
          <span className="flex items-center gap-2">
            <History className="h-4 w-4 text-muted-foreground" />
            Session History
          </span>
          {!loading && !error && (
            <Badge variant="secondary" className="text-xs">
              {total} total
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-16 w-full rounded-lg" />
            ))}
          </div>
        )}

        {error && (
          <p className="py-4 text-center text-sm text-destructive">{error}</p>
        )}

        {!loading && !error && sessions.length === 0 && (
          <div className="py-8 text-center text-sm text-muted-foreground">
            <History className="mx-auto mb-2 h-8 w-8" />
            No sessions recorded yet.
          </div>
        )}

        {!loading && !error && sessions.length > 0 && (
          <div className="space-y-2">
            {sessions.map((s) => (
              <div
                key={s.session_id}
                className={cn(
                  "flex items-start justify-between rounded-lg border p-3",
                  s.is_active && "border-primary/30 bg-primary/5"
                )}
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    {s.is_active ? (
                      <CheckCircle2 className="h-4 w-4 text-green-600" />
                    ) : (
                      <XCircle className="h-4 w-4 text-muted-foreground" />
                    )}
                    <code className="text-xs font-mono text-muted-foreground">
                      {s.session_id.slice(0, 12)}...
                    </code>
                    {s.is_active && (
                      <Badge variant="default" className="text-[10px] bg-green-600">
                        Valid
                      </Badge>
                    )}
                    {!s.is_active && (
                      <Badge variant="secondary" className="text-[10px]">
                        Expired
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatTimestamp(s.created_at)}
                    </span>
                    {s.source_ip && (
                      <span className="flex items-center gap-1">
                        <Globe className="h-3 w-3" />
                        {s.source_ip}
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-[10px] text-muted-foreground">
                    {relativeTime(s.created_at)}
                  </span>
                  {s.expires_at && (
                    <p className="text-[10px] text-muted-foreground">
                      Expires: {formatTimestamp(s.expires_at)}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
