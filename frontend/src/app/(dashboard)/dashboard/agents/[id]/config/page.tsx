"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api/client";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import {
  Bot,
  ArrowLeft,
  Save,
  Plus,
  Trash2,
  Settings,
  MessageSquare,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";

interface TaggedPrompt {
  services: string;
  prompt: string;
}

interface AgentConfig {
  prompts_per_delegation: number;
  max_rounds: number;
  interval_seconds: number;
  tagged_prompts: TaggedPrompt[];
}

interface AgentInfo {
  agent_id: string;
  name: string;
}

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; agent: AgentInfo | null; config: AgentConfig };

export default function AgentConfigPage() {
  const params = useParams<{ id: string }>();
  const agentId = params.id;
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [draft, setDraft] = useState<AgentConfig | null>(null);

  const fetchData = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const [agentData, configData] = await Promise.all([
        apiClient<AgentInfo>(`agents/${agentId}`).catch(() => null),
        apiClient<AgentConfig>(`agents/${agentId}/config`),
      ]);
      setState({ kind: "data", agent: agentData, config: configData });
      setDraft(structuredClone(configData));
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load config (${err.status})`
          : "Failed to load agent configuration";
      setState({ kind: "error", message });
    }
  }, [agentId]);

  useEffect(() => {
    if (agentId) fetchData();
  }, [agentId, fetchData]);

  const handleSave = async () => {
    if (!draft) return;
    setSaving(true);
    setSaveMessage(null);
    try {
      const updated = await apiClient<AgentConfig>(
        `agents/${agentId}/config`,
        {
          method: "PUT",
          body: JSON.stringify(draft),
        }
      );
      setState((prev) =>
        prev.kind === "data" ? { ...prev, config: updated } : prev
      );
      setDraft(structuredClone(updated));
      setSaveMessage("Configuration saved successfully.");
      setTimeout(() => setSaveMessage(null), 3000);
    } catch (err) {
      setSaveMessage(
        err instanceof ApiError
          ? `Save failed (${err.status})`
          : "Save failed"
      );
    } finally {
      setSaving(false);
    }
  };

  if (state.kind === "loading") return <PageSkeleton variant="detail" />;
  if (state.kind === "error")
    return (
      <ErrorCard
        title="Agent Configuration"
        message={state.message}
        retry={fetchData}
      />
    );

  const { agent } = state;
  const config = draft!;

  const isDirty =
    JSON.stringify(draft) !== JSON.stringify(state.config);

  const updateField = <K extends keyof AgentConfig>(
    key: K,
    value: AgentConfig[K]
  ) => {
    setDraft((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const updatePrompt = (index: number, field: keyof TaggedPrompt, value: string) => {
    setDraft((prev) => {
      if (!prev) return prev;
      const updated = [...prev.tagged_prompts];
      updated[index] = { ...updated[index], [field]: value };
      return { ...prev, tagged_prompts: updated };
    });
  };

  const addPrompt = () => {
    setDraft((prev) =>
      prev
        ? {
            ...prev,
            tagged_prompts: [
              ...prev.tagged_prompts,
              { services: "", prompt: "" },
            ],
          }
        : prev
    );
  };

  const removePrompt = (index: number) => {
    setDraft((prev) =>
      prev
        ? {
            ...prev,
            tagged_prompts: prev.tagged_prompts.filter((_, i) => i !== index),
          }
        : prev
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/dashboard/agents/${agentId}/activity`}>
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Activity
          </Button>
        </Link>
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-muted-foreground" />
          <div>
            <h1 className="text-2xl font-bold">
              {agent?.name || agentId}
            </h1>
            <p className="text-xs text-muted-foreground font-mono">{agentId}</p>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Badge variant="default" className="flex items-center gap-1">
            <Settings className="h-3 w-3" />
            Configuration
          </Badge>
        </div>
      </div>

      {/* Save Banner */}
      {(isDirty || saveMessage) && (
        <div className="flex items-center gap-3 rounded-md border px-4 py-3 bg-muted/50">
          {saveMessage ? (
            <p className={`text-sm ${saveMessage.includes("failed") ? "text-destructive" : "text-green-600 dark:text-green-400"}`}>
              {saveMessage}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              You have unsaved changes.
            </p>
          )}
          <div className="ml-auto">
            <Button size="sm" onClick={handleSave} disabled={saving || !isDirty}>
              <Save className="mr-2 h-4 w-4" />
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </div>
      )}

      {/* Card 1: Operational Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Settings className="h-4 w-4 text-muted-foreground" />
            Operational Settings
          </CardTitle>
          <CardDescription>
            Controls how many prompts the agent runs per delegation, how many
            execution rounds per job, and the sleep interval between rounds.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="ppd">Prompts per Delegation</Label>
              <Input
                id="ppd"
                type="number"
                min={1}
                max={50}
                value={config.prompts_per_delegation}
                onChange={(e) =>
                  updateField(
                    "prompts_per_delegation",
                    parseInt(e.target.value, 10) || 1
                  )
                }
              />
              <p className="text-xs text-muted-foreground">
                Max prompts executed per delegation per round (1–50).
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rounds">Max Rounds</Label>
              <Input
                id="rounds"
                type="number"
                min={1}
                max={20}
                value={config.max_rounds}
                onChange={(e) =>
                  updateField(
                    "max_rounds",
                    parseInt(e.target.value, 10) || 1
                  )
                }
              />
              <p className="text-xs text-muted-foreground">
                Execution rounds per Cloud Run Job invocation (1–20).
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="interval">Interval (seconds)</Label>
              <Input
                id="interval"
                type="number"
                min={10}
                max={3600}
                value={config.interval_seconds}
                onChange={(e) =>
                  updateField(
                    "interval_seconds",
                    parseInt(e.target.value, 10) || 60
                  )
                }
              />
              <p className="text-xs text-muted-foreground">
                Sleep between rounds in seconds (10–3600).
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Card 2: Tagged Prompts */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between text-base">
            <span className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-muted-foreground" />
              Tagged Prompts ({config.tagged_prompts.length})
            </span>
            <Button size="sm" variant="outline" onClick={addPrompt}>
              <Plus className="mr-2 h-4 w-4" />
              Add Prompt
            </Button>
          </CardTitle>
          <CardDescription>
            Each prompt is tagged with the service(s) it requires. The agent
            matches prompts to delegated permissions at runtime — only prompts
            whose services are all covered by the active delegation will execute.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {config.tagged_prompts.length === 0 ? (
            <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
              No prompts configured. The agent will exit cleanly without executing anything.
            </div>
          ) : (
            <div className="space-y-4">
              {config.tagged_prompts.map((tp, idx) => (
                <div
                  key={idx}
                  className="rounded-md border p-4 space-y-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 space-y-2">
                      <Label htmlFor={`services-${idx}`}>
                        Services
                      </Label>
                      <div className="flex items-center gap-2">
                        <Input
                          id={`services-${idx}`}
                          value={tp.services}
                          onChange={(e) =>
                            updatePrompt(idx, "services", e.target.value)
                          }
                          placeholder="e.g. notion or slack,notion,gmail"
                          className="max-w-sm"
                        />
                        <div className="flex flex-wrap gap-1">
                          {tp.services
                            .split(",")
                            .map((s) => s.trim())
                            .filter(Boolean)
                            .map((svc) => (
                              <Badge
                                key={svc}
                                variant="secondary"
                                className="text-xs"
                              >
                                {svc}
                              </Badge>
                            ))}
                        </div>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="mt-6 text-muted-foreground hover:text-destructive"
                      onClick={() => removePrompt(idx)}
                      title="Remove prompt"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`prompt-${idx}`}>Prompt</Label>
                    <textarea
                      id={`prompt-${idx}`}
                      value={tp.prompt}
                      onChange={(e) =>
                        updatePrompt(idx, "prompt", e.target.value)
                      }
                      rows={3}
                      placeholder="Enter the LLM prompt text..."
                      className="w-full min-w-0 rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs transition-[color,box-shadow] outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30 resize-y"
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
