"use client";

import { cn } from "@/lib/utils";
import { CheckCircle, Circle, Clock, XCircle, ArrowRight } from "lucide-react";

const LIFECYCLE_STEPS = [
  "pending",
  "requested",
  "delegated",
  "active",
  "completed",
] as const;

type LifecycleStep = (typeof LIFECYCLE_STEPS)[number];

const TERMINAL_STATES = ["failed", "revoked"] as const;
type TerminalState = (typeof TERMINAL_STATES)[number];

type TaskStatus = LifecycleStep | TerminalState;

interface StepTimestamps {
  pending_at?: string;
  requested_at?: string;
  delegated_at?: string;
  activated_at?: string;
  completed_at?: string;
  failed_at?: string;
  revoked_at?: string;
}

export interface LifecycleStepperProps {
  status: string;
  timestamps?: StepTimestamps;
  className?: string;
}

function getStepIndex(status: TaskStatus): number {
  const idx = (LIFECYCLE_STEPS as readonly string[]).indexOf(status);
  return idx === -1 ? -1 : idx;
}

function isTerminal(status: string): status is TerminalState {
  return (TERMINAL_STATES as readonly string[]).includes(status);
}

function formatTimestamp(iso?: string): string | null {
  if (!iso) return null;
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return null;
  }
}

const TIMESTAMP_KEYS: Record<string, keyof StepTimestamps> = {
  pending: "pending_at",
  requested: "requested_at",
  delegated: "delegated_at",
  active: "activated_at",
  completed: "completed_at",
  failed: "failed_at",
  revoked: "revoked_at",
};

function StepIcon({
  step,
  state,
}: {
  step: string;
  state: "completed" | "current" | "future" | "failed";
}) {
  const iconClass = "h-5 w-5";
  switch (state) {
    case "completed":
      return <CheckCircle className={cn(iconClass, "text-green-500")} />;
    case "current":
      return <Clock className={cn(iconClass, "text-blue-500 animate-pulse")} />;
    case "failed":
      return <XCircle className={cn(iconClass, "text-red-500")} />;
    case "future":
    default:
      return <Circle className={cn(iconClass, "text-muted-foreground/40")} />;
  }
}

function getStepState(
  stepIndex: number,
  currentIndex: number,
  isTerminalStatus: boolean,
  status: string
): "completed" | "current" | "future" | "failed" {
  if (isTerminalStatus && stepIndex === currentIndex) return "failed";
  if (stepIndex < currentIndex) return "completed";
  if (stepIndex === currentIndex) return "current";
  return "future";
}

export function LifecycleStepper({
  status,
  timestamps = {},
  className,
}: LifecycleStepperProps) {
  const normalizedStatus = status.toLowerCase();
  const terminal = isTerminal(normalizedStatus);
  const currentIndex = terminal
    ? LIFECYCLE_STEPS.length - 1
    : getStepIndex(normalizedStatus as LifecycleStep);

  const effectiveIndex = currentIndex === -1 ? 0 : currentIndex;

  const steps = terminal
    ? [...LIFECYCLE_STEPS.slice(0, -1), normalizedStatus]
    : [...LIFECYCLE_STEPS];

  return (
    <div
      className={cn("flex items-start gap-0", className)}
      role="list"
      aria-label="Task lifecycle"
    >
      {steps.map((step, idx) => {
        const state = getStepState(idx, effectiveIndex, terminal, normalizedStatus);
        const tsKey = TIMESTAMP_KEYS[step];
        const ts = tsKey ? formatTimestamp(timestamps[tsKey]) : null;
        const isLast = idx === steps.length - 1;

        return (
          <div key={step} className="flex items-start" role="listitem">
            <div className="flex flex-col items-center gap-1 min-w-[80px]">
              <StepIcon step={step} state={state} />
              <span
                className={cn(
                  "text-xs font-medium capitalize",
                  state === "completed" && "text-green-600",
                  state === "current" && "text-blue-600",
                  state === "failed" && "text-red-600",
                  state === "future" && "text-muted-foreground/50"
                )}
              >
                {step}
              </span>
              {ts && (
                <span className="text-[10px] text-muted-foreground">{ts}</span>
              )}
            </div>
            {!isLast && (
              <div className="flex items-center pt-2.5 px-1">
                <div
                  className={cn(
                    "h-[2px] w-6",
                    idx < effectiveIndex ? "bg-green-400" : "bg-muted-foreground/20"
                  )}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
