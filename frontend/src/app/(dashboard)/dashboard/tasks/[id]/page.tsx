"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { LifecycleStepper } from "@/components/tasks/LifecycleStepper";
import { ScopedPermissions } from "@/components/tasks/ScopedPermissions";
import type { Permission } from "@/components/tasks/ScopedPermissions";
import {
  ArrowLeft,
  Clock,
  Key,
  Shield,
  User,
  CheckCircle,
  XCircle,
  Play,
} from "lucide-react";

interface TaskDetail {
  task_id: string;
  name?: string;
  description?: string;
  status: string;
  agent_id?: string;
  delegation_id?: string;
  created_at?: string;
  requested_at?: string;
  delegated_at?: string;
  activated_at?: string;
  completed_at?: string;
  failed_at?: string;
  revoked_at?: string;
  permissions?: Array<{ service: string; scope: string; action: string; attenuated?: boolean }>;
  token_status?: string;
  token_expires_at?: string;
}

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  requested: "secondary",
  delegated: "secondary",
  pending: "secondary",
  active: "default",
  completed: "outline",
  failed: "destructive",
  revoked: "destructive",
};

const TOKEN_STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  active: "default",
  expired: "destructive",
  revoked: "destructive",
};

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; task: TaskDetail };

function formatTimeRemaining(expiresAt: string): string {
  const now = Date.now();
  const expires = new Date(expiresAt).getTime();
  const diff = expires - now;

  if (diff <= 0) return "Expired";

  const hours = Math.floor(diff / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

  if (hours > 24) {
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h remaining`;
  }
  if (hours > 0) return `${hours}h ${minutes}m remaining`;
  return `${minutes}m remaining`;
}

function TokenStatusCard({
  status,
  expiresAt,
}: {
  status?: string;
  expiresAt?: string;
}) {
  if (!status) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Key className="h-4 w-4" />
        <span>No token issued</span>
      </div>
    );
  }

  const variant = TOKEN_STATUS_VARIANTS[status] ?? "secondary";
  const remaining = expiresAt ? formatTimeRemaining(expiresAt) : null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <Key className="h-4 w-4 text-muted-foreground" />
        <Badge variant={variant}>{status}</Badge>
        {remaining && (
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {remaining}
          </span>
        )}
      </div>
    </div>
  );
}

export default function TaskDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [state, setState] = useState<PageState>({ kind: "loading" });

  const taskId = params.id;

  const fetchTask = async () => {
    setState({ kind: "loading" });
    try {
      const task = await apiClient<TaskDetail>(`tasks/${taskId}`);
      setState({ kind: "data", task });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load task (${err.status})`
          : "Failed to load task";
      setState({ kind: "error", message });
    }
  };

  useEffect(() => {
    if (taskId) fetchTask();
  }, [taskId]);

  const [actionError, setActionError] = useState<string | null>(null);

  const handleAction = async (action: string) => {
    if (action === "revoke") {
      if (!window.confirm("Revoke this task?")) return;
    }
    setActionError(null);
    try {
      await apiClient(`tasks/${taskId}/${action}`, { method: "POST" });
      await fetchTask();
    } catch (err) {
      const msg = err instanceof ApiError
        ? `Action "${action}" failed (${err.status})`
        : `Action "${action}" failed`;
      setActionError(msg);
    }
  };

  if (state.kind === "loading") return <PageSkeleton variant="detail" />;
  if (state.kind === "error") {
    return <ErrorCard title="Task Detail" message={state.message} retry={fetchTask} />;
  }

  const { task } = state;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push("/dashboard/tasks")}
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Back to Tasks
        </Button>
      </div>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{task.name || task.task_id}</h1>
          <p className="text-sm text-muted-foreground mt-1">ID: {task.task_id}</p>
        </div>
        <Badge variant={STATUS_VARIANTS[task.status] ?? "secondary"} className="text-sm">
          {task.status}
        </Badge>
      </div>

      {task.description && (
        <p className="text-sm text-muted-foreground">{task.description}</p>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Task Lifecycle</CardTitle>
          <CardDescription>Progress through task lifecycle stages</CardDescription>
        </CardHeader>
        <CardContent>
          <LifecycleStepper
            status={task.status}
            timestamps={{
              pending_at: task.created_at,
              requested_at: task.requested_at ?? task.created_at,
              delegated_at: task.delegated_at,
              activated_at: task.activated_at,
              completed_at: task.completed_at,
              failed_at: task.failed_at,
              revoked_at: task.revoked_at,
            }}
          />
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <Shield className="h-4 w-4" />
              Scoped Permissions
            </CardTitle>
            <CardDescription>
              Permissions granted to this task
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ScopedPermissions permissions={task.permissions ?? []} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <Key className="h-4 w-4" />
              Token Status
            </CardTitle>
            <CardDescription>Task token lifecycle</CardDescription>
          </CardHeader>
          <CardContent>
            <TokenStatusCard
              status={task.token_status}
              expiresAt={task.token_expires_at}
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4 text-sm">
            {task.agent_id && (
              <div>
                <span className="text-muted-foreground flex items-center gap-1">
                  <User className="h-3 w-3" /> Agent
                </span>
                <span className="font-mono text-xs">{task.agent_id}</span>
              </div>
            )}
            {task.delegation_id && (
              <div>
                <span className="text-muted-foreground">Delegation</span>
                <span className="font-mono text-xs block">{task.delegation_id}</span>
              </div>
            )}
            {task.created_at && (
              <div>
                <span className="text-muted-foreground">Created</span>
                <span className="text-xs block">
                  {new Date(task.created_at).toLocaleString()}
                </span>
              </div>
            )}
            {task.completed_at && (
              <div>
                <span className="text-muted-foreground">Completed</span>
                <span className="text-xs block">
                  {new Date(task.completed_at).toLocaleString()}
                </span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Separator />

      <div className="space-y-2">
        <div className="flex gap-2">
          {(task.status === "pending" || task.status === "requested") && (
            <>
              <Button size="sm" onClick={() => handleAction("activate")}>
                <Play className="mr-1 h-3 w-3" /> Activate
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => handleAction("revoke")}
              >
                <XCircle className="mr-1 h-3 w-3" /> Revoke
              </Button>
            </>
          )}
          {task.status === "active" && (
            <>
              <Button size="sm" onClick={() => handleAction("complete")}>
                <CheckCircle className="mr-1 h-3 w-3" /> Complete
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => handleAction("revoke")}
              >
                <XCircle className="mr-1 h-3 w-3" /> Revoke
              </Button>
            </>
          )}
        </div>
        {actionError && (
          <p className="text-sm text-destructive">{actionError}</p>
        )}
      </div>
    </div>
  );
}
