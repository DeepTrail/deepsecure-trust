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

interface LifecycleProgressBarProps {
  state: LifecycleState;
  className?: string;
}

interface Step {
  key: LifecycleState;
  label: string;
  icon: LucideIcon;
}

const STEPS: Step[] = [
  { key: "registered", label: "Registered", icon: UserPlus },
  { key: "delegated", label: "Delegated", icon: Shield },
  { key: "authenticated", label: "Authenticated", icon: KeyRound },
  { key: "active", label: "Active", icon: Zap },
];

const STATE_ORDER: Record<LifecycleState, number> = {
  registered: 0,
  delegated: 1,
  authenticated: 2,
  active: 3,
};

export function LifecycleProgressBar({
  state,
  className,
}: LifecycleProgressBarProps) {
  const currentIdx = STATE_ORDER[state] ?? 0;

  return (
    <div className={cn("w-full", className)}>
      <div className="flex items-center justify-between">
        {STEPS.map((step, idx) => {
          const Icon = step.icon;
          const reached = idx <= currentIdx;
          const isCurrent = idx === currentIdx;

          return (
            <div key={step.key} className="flex flex-1 items-center">
              {/* Step circle */}
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-full border-2 transition-colors",
                    reached
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-muted-foreground/30 bg-background text-muted-foreground/50",
                    isCurrent && "ring-2 ring-primary/30 ring-offset-2 ring-offset-background"
                  )}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <span
                  className={cn(
                    "text-[10px] font-medium leading-tight text-center whitespace-nowrap",
                    reached ? "text-foreground" : "text-muted-foreground/50"
                  )}
                >
                  {step.label}
                </span>
              </div>

              {/* Connector line (not after the last step) */}
              {idx < STEPS.length - 1 && (
                <div
                  className={cn(
                    "mx-1 h-0.5 flex-1 rounded-full transition-colors",
                    idx < currentIdx ? "bg-primary" : "bg-muted-foreground/20"
                  )}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
