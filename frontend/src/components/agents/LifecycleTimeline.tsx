import { cn } from "@/lib/utils";
import {
  UserPlus,
  Shield,
  KeyRound,
  Zap,
  type LucideIcon,
} from "lucide-react";

export type LifecycleState =
  | "registered"
  | "delegated"
  | "authenticated"
  | "active";

interface LifecycleTimelineProps {
  state: LifecycleState;
  className?: string;
}

interface Step {
  key: LifecycleState;
  label: string;
  shortLabel: string;
  icon: LucideIcon;
}

const STEPS: Step[] = [
  { key: "registered", label: "Registered", shortLabel: "Reg", icon: UserPlus },
  { key: "delegated", label: "Delegated", shortLabel: "Del", icon: Shield },
  { key: "authenticated", label: "Authenticated", shortLabel: "Auth", icon: KeyRound },
  { key: "active", label: "Active", shortLabel: "Active", icon: Zap },
];

const STATE_ORDER: Record<LifecycleState, number> = {
  registered: 0,
  delegated: 1,
  authenticated: 2,
  active: 3,
};

const NEXT_ACTION: Record<LifecycleState, string> = {
  registered: "Next: Create a delegation to grant permissions",
  delegated: "Next: Authenticate agent with Ed25519 key",
  authenticated: "Next: Agent makes an API call to become active",
  active: "Agent is fully operational",
};

export function LifecycleTimeline({
  state,
  className,
}: LifecycleTimelineProps) {
  const currentIdx = STATE_ORDER[state] ?? 0;

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-center gap-0.5">
        {STEPS.map((step, idx) => {
          const Icon = step.icon;
          const reached = idx <= currentIdx;
          const isCurrent = idx === currentIdx;
          const isNext = idx === currentIdx + 1;

          return (
            <div key={step.key} className="flex flex-1 items-center">
              <div
                className="flex flex-col items-center gap-0.5"
                title={step.label}
              >
                <div
                  className={cn(
                    "flex h-5 w-5 items-center justify-center rounded-full transition-colors",
                    reached
                      ? "bg-primary text-primary-foreground"
                      : isNext
                        ? "border border-dashed border-primary/50 bg-background text-primary/50"
                        : "border border-muted-foreground/20 bg-background text-muted-foreground/30",
                    isCurrent && "ring-1 ring-primary/30 ring-offset-1 ring-offset-background"
                  )}
                >
                  <Icon className="h-2.5 w-2.5" />
                </div>
                <span
                  className={cn(
                    "text-[8px] font-medium leading-none",
                    reached ? "text-foreground" : isNext ? "text-primary/60" : "text-muted-foreground/40"
                  )}
                >
                  {step.shortLabel}
                </span>
              </div>

              {idx < STEPS.length - 1 && (
                <div
                  className={cn(
                    "mx-0.5 h-px flex-1 rounded-full transition-colors",
                    idx < currentIdx ? "bg-primary" : "bg-muted-foreground/15"
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

      <p className="text-[10px] leading-tight text-muted-foreground">
        {NEXT_ACTION[state]}
      </p>
    </div>
  );
}
