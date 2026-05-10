import { Badge } from "@/components/ui/badge";
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

interface LifecycleBadgeProps {
  state: LifecycleState;
  className?: string;
}

const CONFIG: Record<
  LifecycleState,
  { label: string; icon: LucideIcon; variant: "secondary" | "outline" | "default"; colorClass: string }
> = {
  registered: {
    label: "Registered",
    icon: UserPlus,
    variant: "secondary",
    colorClass: "text-muted-foreground",
  },
  delegated: {
    label: "Delegated",
    icon: Shield,
    variant: "outline",
    colorClass: "text-blue-600 dark:text-blue-400",
  },
  authenticated: {
    label: "Authenticated",
    icon: KeyRound,
    variant: "outline",
    colorClass: "text-amber-600 dark:text-amber-400",
  },
  active: {
    label: "Active",
    icon: Zap,
    variant: "default",
    colorClass: "text-green-600 dark:text-green-400",
  },
};

export function LifecycleBadge({ state, className }: LifecycleBadgeProps) {
  const cfg = CONFIG[state] ?? CONFIG.registered;
  const Icon = cfg.icon;

  return (
    <Badge
      variant={cfg.variant}
      className={cn("flex items-center gap-1", className)}
    >
      <Icon className={cn("h-3 w-3", cfg.colorClass)} />
      {cfg.label}
    </Badge>
  );
}
