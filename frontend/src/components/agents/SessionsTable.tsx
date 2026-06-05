"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api/client";
import type {
  SessionSummary,
  SessionEventSummary,
  SessionEventsResponse,
} from "@/lib/types/admin";

interface SessionsTableProps {
  sessions: SessionSummary[];
  agentId: string;
}

export function SessionsTable({ sessions, agentId }: SessionsTableProps) {
  const [sectionOpen, setSectionOpen] = useState(false);
  const [expandedSessionRow, setExpandedSessionRow] = useState<string | null>(null);
  const [sessionEvents, setSessionEvents] = useState<
    Record<string, SessionEventSummary[]>
  >({});
  const [loadingSession, setLoadingSession] = useState<string | null>(null);

  const loadSessionEvents = async (sessionId: string) => {
    if (sessionEvents[sessionId]) return;
    setLoadingSession(sessionId);
    try {
      const data = await apiClient<SessionEventsResponse>(
        `admin/agents/${agentId}/sessions/${sessionId}/events`
      );
      setSessionEvents((prev) => ({ ...prev, [sessionId]: data.events }));
    } catch {
      setSessionEvents((prev) => ({ ...prev, [sessionId]: [] }));
    } finally {
      setLoadingSession(null);
    }
  };

  const handleToggleSession = (sessionId: string) => {
    if (expandedSessionRow === sessionId) {
      setExpandedSessionRow(null);
    } else {
      setExpandedSessionRow(sessionId);
      loadSessionEvents(sessionId);
    }
  };

  const preview = sessions[0];

  return (
    <div className="space-y-2">
      <button
        className="flex items-center gap-2 text-sm font-semibold hover:opacity-80 transition-opacity"
        onClick={() => setSectionOpen(!sectionOpen)}
      >
        {sectionOpen ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
        Sessions ({sessions.length})
      </button>

      {!sectionOpen && preview && (
        <p className="ml-6 text-xs text-muted-foreground">
          Most recent: {preview.session_id.slice(0, 16)}…
          {preview.delegator ? ` · ${preview.delegator}` : ""}
          {preview.last_activity_at
            ? ` · ${new Date(preview.last_activity_at).toLocaleString()}`
            : ""}
        </p>
      )}

      {sectionOpen && (
        <>
          {sessions.length === 0 ? (
            <p className="text-sm text-muted-foreground ml-6">
              No sessions recorded
            </p>
          ) : (
            <div className="overflow-x-auto rounded border">
              <table className="w-full text-xs">
                <thead className="bg-muted/50 border-b">
                  <tr>
                    <th className="w-8 px-3 py-2" />
                    <th className="px-3 py-2 text-left font-medium">Session ID</th>
                    <th className="px-3 py-2 text-left font-medium">Delegator</th>
                    <th className="px-3 py-2 text-left font-medium">Created</th>
                    <th className="px-3 py-2 text-left font-medium">Last Activity</th>
                    <th className="px-3 py-2 text-left font-medium">Tool Calls</th>
                    <th className="px-3 py-2 text-left font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {sessions.map((s) => {
                    const isOpen = expandedSessionRow === s.session_id;
                    return (
                      <SessionRow
                        key={s.session_id}
                        session={s}
                        isOpen={isOpen}
                        onToggle={() => handleToggleSession(s.session_id)}
                        events={sessionEvents[s.session_id]}
                        loading={loadingSession === s.session_id}
                      />
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function SessionRow({
  session,
  isOpen,
  onToggle,
  events,
  loading,
}: {
  session: SessionSummary;
  isOpen: boolean;
  onToggle: () => void;
  events?: SessionEventSummary[];
  loading: boolean;
}) {
  return (
    <>
      <tr
        className="cursor-pointer hover:bg-muted/30 transition-colors"
        onClick={onToggle}
      >
        <td className="px-3 py-2">
          {isOpen ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </td>
        <td className="px-3 py-2 font-mono text-muted-foreground">
          {session.session_id.length > 16
            ? `${session.session_id.slice(0, 16)}…`
            : session.session_id}
        </td>
        <td className="px-3 py-2 text-muted-foreground">
          {session.delegator ?? "—"}
        </td>
        <td className="px-3 py-2 text-muted-foreground">
          {session.created_at
            ? new Date(session.created_at).toLocaleString()
            : "—"}
        </td>
        <td className="px-3 py-2 text-muted-foreground">
          {session.last_activity_at
            ? new Date(session.last_activity_at).toLocaleString()
            : "—"}
        </td>
        <td className="px-3 py-2 text-muted-foreground">
          {session.tool_calls}
        </td>
        <td className="px-3 py-2">
          <Badge
            variant="outline"
            className={cn(
              "text-xs",
              session.status === "active"
                ? "text-green-700 border-green-200"
                : "text-gray-500 border-gray-200"
            )}
          >
            {session.status}
          </Badge>
        </td>
      </tr>
      {isOpen && (
        <tr>
          <td colSpan={7} className="bg-muted/10 px-6 py-3">
            {loading ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Loading tool calls…
              </div>
            ) : events && events.length > 0 ? (
              <div className="space-y-1.5">
                {events.map((evt) => (
                  <div
                    key={evt.id}
                    className="flex items-center gap-2 text-xs"
                  >
                    {evt.success ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
                    ) : (
                      <XCircle className="h-3.5 w-3.5 text-red-500 shrink-0" />
                    )}
                    <span className="font-mono font-medium">
                      {evt.tool ?? evt.event_type}
                    </span>
                    <span className="text-muted-foreground">
                      {new Date(evt.timestamp).toLocaleString()}
                    </span>
                    {evt.result_summary && (
                      <span className="text-muted-foreground truncate max-w-[200px]">
                        — {evt.result_summary}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                No tool calls for this session
              </p>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
