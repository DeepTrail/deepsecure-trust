"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api/client";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { Bot, ArrowLeft, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PromptEditor } from "@/components/agents/PromptEditor";
import { useUserRole } from "@/hooks/useUserRole";
import Link from "next/link";

interface AgentInfo {
  agent_id: string;
  name: string;
  delegated_services?: string[];
}

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; agent: AgentInfo };

export default function AgentGoalsPage() {
  const params = useParams<{ id: string }>();
  const agentId = params.id;
  const { isAdmin } = useUserRole();
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [userEmail, setUserEmail] = useState("");

  const fetchData = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const agentData = await apiClient<AgentInfo>(`agents/${agentId}`);
      setState({ kind: "data", agent: agentData });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load agent (${err.status})`
          : "Failed to load agent information";
      setState({ kind: "error", message });
    }
  }, [agentId]);

  useEffect(() => {
    if (agentId) fetchData();
  }, [agentId, fetchData]);

  useEffect(() => {
    apiClient<{ email?: string }>("auth/me")
      .then((u) => setUserEmail(u.email ?? ""))
      .catch(() => {});
  }, []);

  if (state.kind === "loading") return <PageSkeleton variant="detail" />;
  if (state.kind === "error")
    return (
      <ErrorCard
        title="Agent Goals"
        message={state.message}
        retry={fetchData}
      />
    );

  const { agent } = state;
  const delegatedServices = agent.delegated_services ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/dashboard/agents">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Agents
          </Button>
        </Link>
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-muted-foreground" />
          <div>
            <h1 className="text-2xl font-bold">
              {agent.name || agentId}
            </h1>
            <p className="text-xs text-muted-foreground font-mono">{agentId}</p>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Badge variant="default" className="flex items-center gap-1">
            <Target className="h-3 w-3" />
            Goals
          </Badge>
          {isAdmin && (
            <Link href={`/dashboard/agents/${agentId}/config`}>
              <Button variant="outline" size="sm">
                Full Configuration
              </Button>
            </Link>
          )}
        </div>
      </div>

      {delegatedServices.length > 0 && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>Your delegated services:</span>
          <div className="flex flex-wrap gap-1">
            {delegatedServices.map((svc) => (
              <Badge key={svc} variant="secondary" className="text-xs">
                {svc}
              </Badge>
            ))}
          </div>
        </div>
      )}

      <PromptEditor
        agentId={agentId}
        userEmail={userEmail}
        delegatedServices={delegatedServices}
        isAdmin={isAdmin}
      />
    </div>
  );
}
