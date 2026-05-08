"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import { ListTodo, Plus, Play, CheckCircle, XCircle, ChevronRight } from "lucide-react";

interface Task {
  task_id: string;
  name?: string;
  description?: string;
  status: string;
  agent_id?: string;
  created_at?: string;
}

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  pending: "secondary",
  active: "default",
  completed: "outline",
  revoked: "destructive",
};

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; tasks: Task[] };

export default function TasksPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [creating, setCreating] = useState(false);

  const fetchTasks = async () => {
    setState({ kind: "loading" });
    try {
      const data = await apiClient<Task[] | { tasks: Task[] }>("tasks/");
      const tasks = Array.isArray(data) ? data : (data.tasks ?? []);
      setState({ kind: "data", tasks });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load tasks (${err.status})`
          : "Failed to load tasks";
      setState({ kind: "error", message });
    }
  };

  useEffect(() => {
    fetchTasks();
  }, []);

  const handleAction = async (taskId: string, action: string) => {
    if (action === "revoke") {
      if (!window.confirm("Revoke this task?")) return;
    }
    try {
      await apiClient(`tasks/${taskId}/${action}`, { method: "POST" });
      await fetchTasks();
    } catch { /* retry on next fetch */ }
  };

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error")
    return <ErrorCard title="Tasks" message={state.message} retry={fetchTasks} />;

  const { tasks } = state;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Tasks</h1>
        <Button size="sm" onClick={() => setCreating(!creating)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Task
        </Button>
      </div>

      {creating && (
        <TaskCreateForm onDone={() => { setCreating(false); fetchTasks(); }} />
      )}

      {tasks.length === 0 && !creating ? (
        <EmptyState
          title="No tasks"
          description="Create tasks to assign scoped work to agents."
        />
      ) : (
        <div className="grid gap-4">
          {tasks.map((task) => (
            <Card key={task.task_id}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-medium">
                  <ListTodo className="h-4 w-4 text-muted-foreground" />
                  <Link
                    href={`/dashboard/tasks/${task.task_id}`}
                    className="hover:underline"
                  >
                    {task.name || task.task_id}
                  </Link>
                </CardTitle>
                <div className="flex items-center gap-2">
                  <Badge variant={STATUS_VARIANTS[task.status] ?? "secondary"}>
                    {task.status}
                  </Badge>
                  <Link href={`/dashboard/tasks/${task.task_id}`}>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </Link>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {task.description && (
                  <p className="text-sm text-muted-foreground">{task.description}</p>
                )}
                <div className="text-xs text-muted-foreground">
                  ID: {task.task_id}
                  {task.agent_id && ` · Agent: ${task.agent_id}`}
                </div>
                <div className="flex gap-2">
                  {task.status === "pending" && (
                    <>
                      <Button size="sm" variant="outline" onClick={() => handleAction(task.task_id, "activate")}>
                        <Play className="mr-1 h-3 w-3" /> Activate
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleAction(task.task_id, "revoke")}>
                        <XCircle className="mr-1 h-3 w-3" /> Revoke
                      </Button>
                    </>
                  )}
                  {task.status === "active" && (
                    <>
                      <Button size="sm" variant="outline" onClick={() => handleAction(task.task_id, "complete")}>
                        <CheckCircle className="mr-1 h-3 w-3" /> Complete
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleAction(task.task_id, "revoke")}>
                        <XCircle className="mr-1 h-3 w-3" /> Revoke
                      </Button>
                    </>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function TaskCreateForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [agentId, setAgentId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !agentId.trim()) return;
    setSubmitting(true);
    try {
      await apiClient("tasks/", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || undefined,
          agent_id: agentId.trim(),
        }),
      });
      onDone();
    } catch {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardContent className="pt-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex items-end gap-4">
            <div className="flex-1 space-y-1">
              <label htmlFor="task-name" className="text-sm font-medium">Task Name</label>
              <input
                id="task-name"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Process invoices"
                required
              />
            </div>
            <div className="flex-1 space-y-1">
              <label htmlFor="task-agent" className="text-sm font-medium">Agent ID</label>
              <input
                id="task-agent"
                className="w-full rounded-md border px-3 py-2 text-sm"
                value={agentId}
                onChange={(e) => setAgentId(e.target.value)}
                placeholder="my-agent"
                required
              />
            </div>
            <Button type="submit" disabled={submitting || !name.trim() || !agentId.trim()}>
              {submitting ? "Creating..." : "Create"}
            </Button>
            <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
          </div>
          <div className="space-y-1">
            <label htmlFor="task-description" className="text-sm font-medium">Description</label>
            <textarea
              id="task-description"
              className="w-full rounded-md border px-3 py-2 text-sm"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional task description"
              rows={2}
            />
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
