"use client";

import { Bot, Building2 } from "lucide-react";
import { cn } from "@/lib/utils";

export type AgentType = "own" | "vendor";

interface AgentTypeSelectorProps {
  value: AgentType;
  onChange: (type: AgentType) => void;
}

const AGENT_TYPES: {
  type: AgentType;
  label: string;
  description: string;
  icon: typeof Bot;
}[] = [
  {
    type: "own",
    label: "Own Agent",
    description: "An agent you build and control that needs its own identity and credentials.",
    icon: Bot,
  },
  {
    type: "vendor",
    label: "Vendor Agent",
    description: "A third-party agent that uses your credentials to access services on your behalf.",
    icon: Building2,
  },
];

export function AgentTypeSelector({ value, onChange }: AgentTypeSelectorProps) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Agent type">
      {AGENT_TYPES.map(({ type, label, description, icon: Icon }) => {
        const selected = value === type;
        return (
          <button
            key={type}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(type)}
            className={cn(
              "flex flex-col items-start gap-2 rounded-lg border-2 p-4 text-left transition-colors",
              selected
                ? "border-primary bg-primary/5"
                : "border-border hover:border-muted-foreground/30"
            )}
          >
            <div className="flex items-center gap-2">
              <Icon className={cn("h-5 w-5", selected ? "text-primary" : "text-muted-foreground")} />
              <span className={cn("text-sm font-semibold", selected ? "text-primary" : "text-foreground")}>
                {label}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{description}</p>
          </button>
        );
      })}
    </div>
  );
}
