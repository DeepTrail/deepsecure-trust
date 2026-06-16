"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import {
  History,
  Globe,
  Clock,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
} from "lucide-react";

export interface AgentSession {
  session_id: string;
  agent_id: string;
  delegation_id: string;
  is_active: boolean;
  source_ip: string | null;
  created_at: string;
  expires_at: string;
  last_activity_at: string | null;
  created_via: string | null;
  llm_provider: string | null;
}

interface SessionsResponse {
  sessions: AgentSession[];
  total: number;
  limit?: number | null;
  offset?: number | null;
}

interface SessionHistoryTableProps {
  agentId: string;
  className?: string;
}

const PAGE_SIZE = 10;

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
  const [sectionOpen, setSectionOpen] = useState(false);
  const [page, setPage] = useState(0);
  const [activeOnly, setActiveOnly] = useState(true);

  const fetchSessions = useCallback(
    async (pageNum: number, activeFilter: boolean) => {
      setLoading(true);
      setError(null);
      try {
        const offset = pageNum * PAGE_SIZE;
        const activeParam = activeFilter ? "&active_only=true" : "";
        const data = await apiClient<SessionsResponse | AgentSession[]>(
          `agents/${agentId}/sessions?limit=${PAGE_SIZE}&offset=${offset}${activeParam}`
        );

        if (Array.isArray(data)) {
          setSessions(data);
          setTotal(data.length);
        } else {
          setSessions(data.sessions ?? []);
          setTotal(data.total ?? 0);
        }
      } catch {
        setError("Failed to load sessions");
      } finally {
        setLoading(false);
      }
    },
    [agentId]
  );

  useEffect(() => {
    setPage(0);
    fetchSessions(0, activeOnly);
  }, [fetchSessions, activeOnly]);

  useEffect(() => {
    if (page > 0) fetchSessions(page, activeOnly);
  }, [page, fetchSessions, activeOnly]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const preview = sessions[0];

  const handlePrev = () => setPage((p) => Math.max(0, p - 1));
  const handleNext = () => setPage((p) => Math.min(totalPages - 1, p + 1));

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex w-full items-center justify-between">
          <button
            type="button"
            className="flex items-center gap-2"
            onClick={() => setSectionOpen(!sectionOpen)}
          >
            <CardTitle className="flex items-center gap-2 text-sm font-medium cursor-pointer hover:opacity-80 transition-opacity">
              {sectionOpen ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
              <History className="h-4 w-4 text-muted-foreground" />
              Session History
            </CardTitle>
            {!loading && !error && (
              <Badge variant="secondary" className="text-xs">
                {total} {activeOnly ? "active" : "total"}
              </Badge>
            )}
          </button>
          {sectionOpen && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-[10px] px-2"
              onClick={(e) => {
                e.stopPropagation();
                setActiveOnly(!activeOnly);
              }}
            >
              {activeOnly ? "Show All" : "Active Only"}
            </Button>
          )}
        </div>
      </CardHeader>

      {/* "Most recent" preview when collapsed */}
      {!sectionOpen && !loading && preview && (
        <CardContent className="pt-0 pb-3">
          <p className="text-xs text-muted-foreground">
            Most recent: {preview.session_id.slice(0, 16)}…
            {preview.last_activity_at
              ? ` · ${new Date(preview.last_activity_at).toLocaleString()}`
              : ` · ${formatTimestamp(preview.created_at)}`}
            {preview.is_active ? " · Active" : " · Expired"}
          </p>
        </CardContent>
      )}

      {sectionOpen && (
        <CardContent>
          {loading && (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-16 w-full rounded-lg" />
              ))}
            </div>
          )}

          {error && (
            <p className="py-4 text-center text-sm text-destructive">
              {error}
            </p>
          )}

          {!loading && !error && sessions.length === 0 && (
            <div className="py-8 text-center text-sm text-muted-foreground">
              <History className="mx-auto mb-2 h-8 w-8" />
              No sessions recorded yet.
            </div>
          )}

          {!loading && !error && sessions.length > 0 && (
            <>
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
                          <Badge
                            variant="default"
                            className="text-[10px] bg-green-600"
                          >
                            Valid
                          </Badge>
                        )}
                        {!s.is_active && (
                          <Badge variant="secondary" className="text-[10px]">
                            Expired
                          </Badge>
                        )}
                        {s.created_via && (
                          <Badge variant="outline" className="text-[10px]">
                            {s.created_via.replace(/_/g, " ")}
                          </Badge>
                        )}
                        {s.llm_provider && (
                          <Badge variant="outline" className="text-[10px] border-blue-300 text-blue-700">
                            {s.llm_provider}
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

              {/* Pagination controls */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between pt-4 border-t mt-4">
                  <p className="text-xs text-muted-foreground">
                    Showing {page * PAGE_SIZE + 1}–
                    {Math.min((page + 1) * PAGE_SIZE, total)} of {total}
                  </p>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handlePrev}
                      disabled={page === 0}
                      className="h-7 px-2"
                    >
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </Button>
                    <span className="text-xs text-muted-foreground px-2">
                      {page + 1} / {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleNext}
                      disabled={page >= totalPages - 1}
                      className="h-7 px-2"
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      )}
    </Card>
  );
}
