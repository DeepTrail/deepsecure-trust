"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CheckCircle2, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface SlotEntry {
  name: string;
  sa_email: string;
  available: boolean;
  claimed_by?: string | null;
}

interface WizardState {
  platform: string;
  selector: string;
  name: string;
  description: string;
  prompts_per_delegation: number;
  max_rounds: number;
  interval_seconds: number;
  tagged_prompts: { services: string; prompt: string }[];
  max_permissions: string;
  default_ttl_days: number;
  available_to_roles: string;
}

const TOTAL_STEPS = 6;

function StepIndicator({
  current,
  total,
}: {
  current: number;
  total: number;
}) {
  return (
    <div className="flex items-center gap-2">
      {Array.from({ length: total }, (_, i) => (
        <div key={i} className="flex items-center gap-1">
          <div
            className={cn(
              "h-2.5 w-2.5 rounded-full transition-colors",
              i < current
                ? "bg-primary"
                : i === current
                  ? "bg-primary ring-2 ring-primary/30"
                  : "bg-muted"
            )}
          />
          {i < total - 1 && (
            <div
              className={cn(
                "h-0.5 w-6",
                i < current ? "bg-primary" : "bg-muted"
              )}
            />
          )}
        </div>
      ))}
    </div>
  );
}

const STEP_LABELS = [
  "Identity",
  "Agent Details",
  "Configuration",
  "Prompts",
  "Delegation Template",
  "Review & Create",
];

export function ProvisionWizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [slots, setSlots] = useState<SlotEntry[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [state, setState] = useState<WizardState>({
    platform: "gcp_workload_identity",
    selector: "",
    name: "",
    description: "",
    prompts_per_delegation: 10,
    max_rounds: 3,
    interval_seconds: 60,
    tagged_prompts: [],
    max_permissions: "",
    default_ttl_days: 7,
    available_to_roles: "all",
  });

  useEffect(() => {
    async function fetchSlots() {
      try {
        const data = await apiClient<{ slots: SlotEntry[] }>(
          "admin/agent-slots"
        );
        setSlots(data.slots ?? []);
      } catch {
        // Non-fatal — user can enter custom selector
      } finally {
        setSlotsLoading(false);
      }
    }
    fetchSlots();
  }, []);

  const availableSlots = slots.filter((s) => s.available);

  const update = (patch: Partial<WizardState>) =>
    setState((prev) => ({ ...prev, ...patch }));

  const canNext = (): boolean => {
    switch (step) {
      case 0:
        return state.selector.length > 0;
      case 1:
        return state.name.trim().length > 0;
      case 2:
        return true;
      case 3:
        return true;
      case 4:
        return state.max_permissions.trim().length > 0;
      case 5:
        return true;
      default:
        return false;
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const permissions = state.max_permissions
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean);

      const body = {
        agent: {
          name: state.name,
          description: state.description || undefined,
          platform: state.platform,
          selector: state.selector,
        },
        config: {
          prompts_per_delegation: state.prompts_per_delegation,
          max_rounds: state.max_rounds,
          interval_seconds: state.interval_seconds,
          tagged_prompts: state.tagged_prompts,
        },
        delegation_template: {
          max_permissions: permissions,
          default_ttl_days: state.default_ttl_days,
          available_to_roles: state.available_to_roles
            .split(",")
            .map((r) => r.trim())
            .filter(Boolean),
        },
      };

      const result = await apiClient<{
        agent: { agent_id: string };
        scheduler_resumed: boolean;
        warning?: string;
      }>("admin/agents/provision", {
        method: "POST",
        body: JSON.stringify(body),
      });

      if (result.warning) {
        setError(result.warning);
      }

      router.push(
        `/dashboard/agents/${result.agent.agent_id}/activity`
      );
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Provisioning failed. Please try again."
      );
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Step indicator */}
      <div className="flex items-center justify-between">
        <StepIndicator current={step} total={TOTAL_STEPS} />
        <span className="text-sm text-muted-foreground">
          Step {step + 1}: {STEP_LABELS[step]}
        </span>
      </div>

      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/30 dark:text-red-200">
          {error}
        </div>
      )}

      {/* Step 1: Identity */}
      {step === 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Select Agent Identity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Platform</Label>
              <Select
                value={state.platform}
                onValueChange={(v) => update({ platform: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gcp_workload_identity">
                    GCP Workload Identity
                  </SelectItem>
                  <SelectItem value="aws_iam">AWS IAM</SelectItem>
                  <SelectItem value="kubernetes">Kubernetes</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {state.platform === "gcp_workload_identity" && (
              <div className="space-y-2">
                <Label>Identity Slot</Label>
                {slotsLoading ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading identity slots...
                  </div>
                ) : availableSlots.length > 0 ? (
                  <Select
                    value={state.selector}
                    onValueChange={(v) => update({ selector: v })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select a pre-provisioned slot" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableSlots.map((slot) => (
                        <SelectItem
                          key={slot.sa_email}
                          value={slot.sa_email}
                        >
                          {slot.name} ({slot.sa_email})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <p className="text-sm text-amber-700 dark:text-amber-300">
                    All identity slots are claimed. Enter a custom SA
                    email below.
                  </p>
                )}
                <Input
                  placeholder="Or enter custom SA email"
                  value={state.selector}
                  onChange={(e) => update({ selector: e.target.value })}
                />
              </div>
            )}

            {state.platform !== "gcp_workload_identity" && (
              <div className="space-y-2">
                <Label>Selector / ARN / Service Account</Label>
                <Input
                  placeholder="Enter identity selector"
                  value={state.selector}
                  onChange={(e) => update({ selector: e.target.value })}
                />
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Step 2: Agent Details */}
      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Agent Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Name *</Label>
              <Input
                placeholder="e.g., Sales Research Agent"
                value={state.name}
                onChange={(e) => update({ name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <textarea
                className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 resize-y"
                placeholder="What does this agent do?"
                value={state.description}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => update({ description: e.target.value })}
                rows={3}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Configuration */}
      {step === 2 && (
        <Card>
          <CardHeader>
            <CardTitle>Operational Settings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label>Prompts per Delegation</Label>
                <Input
                  type="number"
                  min={1}
                  max={50}
                  value={state.prompts_per_delegation}
                  onChange={(e) =>
                    update({
                      prompts_per_delegation: parseInt(e.target.value) || 10,
                    })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Max Rounds</Label>
                <Input
                  type="number"
                  min={1}
                  max={20}
                  value={state.max_rounds}
                  onChange={(e) =>
                    update({ max_rounds: parseInt(e.target.value) || 3 })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Interval (seconds)</Label>
                <Input
                  type="number"
                  min={10}
                  max={3600}
                  value={state.interval_seconds}
                  onChange={(e) =>
                    update({
                      interval_seconds: parseInt(e.target.value) || 60,
                    })
                  }
                />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 4: Initial Prompts */}
      {step === 3 && (
        <Card>
          <CardHeader>
            <CardTitle>Initial Prompts (Optional)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {state.tagged_prompts.map((tp, i) => (
              <div key={i} className="flex items-start gap-2 rounded-md border p-3">
                <div className="flex-1 space-y-1">
                  <div className="flex flex-wrap gap-1">
                    {tp.services.split(",").map((s) => (
                      <Badge key={s} variant="outline" className="text-xs">
                        {s.trim()}
                      </Badge>
                    ))}
                  </div>
                  <p className="text-sm">{tp.prompt}</p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    update({
                      tagged_prompts: state.tagged_prompts.filter(
                        (_, j) => j !== i
                      ),
                    })
                  }
                >
                  ×
                </Button>
              </div>
            ))}
            <PromptAdder
              onAdd={(services, prompt) =>
                update({
                  tagged_prompts: [
                    ...state.tagged_prompts,
                    { services, prompt },
                  ],
                })
              }
            />
          </CardContent>
        </Card>
      )}

      {/* Step 5: Delegation Template */}
      {step === 4 && (
        <Card>
          <CardHeader>
            <CardTitle>Delegation Template</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Max Permissions *</Label>
              <textarea
                className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 resize-y"
                placeholder="notion:pages:read, notion:pages:search, slack:messages:send"
                value={state.max_permissions}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                  update({ max_permissions: e.target.value })
                }
                rows={3}
              />
              <p className="text-xs text-muted-foreground">
                Comma-separated list of permission scopes
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Default TTL (days)</Label>
                <Input
                  type="number"
                  min={1}
                  max={365}
                  value={state.default_ttl_days}
                  onChange={(e) =>
                    update({
                      default_ttl_days: parseInt(e.target.value) || 7,
                    })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Available to Roles</Label>
                <Input
                  placeholder="all"
                  value={state.available_to_roles}
                  onChange={(e) =>
                    update({ available_to_roles: e.target.value })
                  }
                />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 6: Review */}
      {step === 5 && (
        <Card>
          <CardHeader>
            <CardTitle>Review & Create</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg bg-muted p-4 space-y-3">
              <ReviewRow label="Platform" value={state.platform} />
              <ReviewRow label="Selector" value={state.selector} />
              <ReviewRow label="Name" value={state.name} />
              {state.description && (
                <ReviewRow label="Description" value={state.description} />
              )}
              <ReviewRow
                label="Config"
                value={`${state.prompts_per_delegation} prompts/delegation, ${state.max_rounds} rounds, ${state.interval_seconds}s interval`}
              />
              <ReviewRow
                label="Prompts"
                value={`${state.tagged_prompts.length} initial prompt(s)`}
              />
              <ReviewRow
                label="Permissions"
                value={state.max_permissions}
              />
              <ReviewRow
                label="TTL"
                value={`${state.default_ttl_days} days`}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Navigation */}
      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => setStep((s) => s - 1)}
          disabled={step === 0}
        >
          Back
        </Button>
        {step < TOTAL_STEPS - 1 ? (
          <Button
            onClick={() => setStep((s) => s + 1)}
            disabled={!canNext()}
          >
            Next: {STEP_LABELS[step + 1]}
          </Button>
        ) : (
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <CheckCircle2 className="mr-2 h-4 w-4" />
                Create Agent
              </>
            )}
          </Button>
        )}
      </div>
    </div>
  );
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="max-w-[60%] truncate font-medium">{value}</span>
    </div>
  );
}

function PromptAdder({
  onAdd,
}: {
  onAdd: (services: string, prompt: string) => void;
}) {
  const [services, setServices] = useState("");
  const [prompt, setPrompt] = useState("");

  return (
    <div className="space-y-2 rounded-md border border-dashed p-3">
      <Input
        placeholder="Services (e.g., notion,slack)"
        value={services}
        onChange={(e) => setServices(e.target.value)}
      />
      <textarea
        className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 resize-y"
        placeholder="What should the agent do?"
        value={prompt}
        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setPrompt(e.target.value)}
        rows={2}
      />
      <Button
        size="sm"
        variant="outline"
        disabled={!services.trim() || !prompt.trim()}
        onClick={() => {
          onAdd(services.trim(), prompt.trim());
          setServices("");
          setPrompt("");
        }}
      >
        + Add Prompt
      </Button>
    </div>
  );
}
