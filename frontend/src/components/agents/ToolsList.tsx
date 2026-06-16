"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  ShieldCheck,
  ChevronRight,
  ChevronDown,
  Wrench,
  EyeOff,
} from "lucide-react";

export interface AgentTool {
  name: string;
  backend: string;
  permission: string;
  available: boolean;
  reason?: string;
}

function groupByService(tools: AgentTool[]): Record<string, AgentTool[]> {
  const groups: Record<string, AgentTool[]> = {};
  for (const t of tools) {
    if (!groups[t.backend]) groups[t.backend] = [];
    groups[t.backend].push(t);
  }
  return groups;
}

function toolDisplayName(name: string): string {
  const dot = name.indexOf(".");
  return dot >= 0 ? name.slice(dot + 1) : name;
}

// ---------------------------------------------------------------------------
// DelegatedToolsCard
// ---------------------------------------------------------------------------

interface DelegatedToolsCardProps {
  tools: AgentTool[];
  className?: string;
}

export function DelegatedToolsCard({ tools, className }: DelegatedToolsCardProps) {
  const [open, setOpen] = useState(false);
  const delegated = tools.filter((t) => t.available);

  if (delegated.length === 0) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <ShieldCheck className="h-4 w-4" />
            Delegated Tools &amp; Permissions (0)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <Wrench className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">No tools delegated yet</p>
              <p className="text-xs text-muted-foreground">
                Only active (non-expired) delegations grant tool access. If all delegations have expired, create a new one to restore access.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const grouped = groupByService(delegated);
  const serviceCount = Object.keys(grouped).length;

  return (
    <Card className={`border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/20 ${className ?? ""}`}>
      <CardHeader className="pb-3">
        <button
          type="button"
          className="flex w-full items-center justify-between"
          onClick={() => setOpen(!open)}
        >
          <CardTitle className="flex items-center gap-2 text-sm font-medium text-green-700 dark:text-green-400 cursor-pointer hover:opacity-80 transition-opacity">
            {open ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            <ShieldCheck className="h-4 w-4" />
            Delegated Tools &amp; Permissions ({delegated.length})
          </CardTitle>
          <span className="text-xs font-normal text-muted-foreground">
            {serviceCount} {serviceCount === 1 ? "service" : "services"}
          </span>
        </button>
      </CardHeader>

      {/* Preview when collapsed */}
      {!open && (
        <CardContent className="pt-0 pb-3">
          <p className="text-xs text-muted-foreground">
            {Object.keys(grouped).join(", ")}
          </p>
        </CardContent>
      )}

      {open && (
        <CardContent className="space-y-4">
          {Object.entries(grouped).map(([service, serviceTools]) => (
            <div key={service} className="space-y-1.5">
              <p className="text-xs font-semibold uppercase tracking-wide text-green-700/70 dark:text-green-400/70">
                {service}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {serviceTools.map((t) => (
                  <Badge
                    key={t.name}
                    variant="outline"
                    className="border-green-300 text-green-700 dark:border-green-800 dark:text-green-400"
                    title={t.permission}
                  >
                    <CheckCircle2 className="mr-1 h-3 w-3" />
                    {toolDisplayName(t.name)}
                  </Badge>
                ))}
              </div>
              <div className="flex flex-wrap gap-1">
                {serviceTools.map((t) => (
                  <span
                    key={`perm-${t.permission}`}
                    className="text-[10px] font-mono text-green-600/60 dark:text-green-500/50"
                  >
                    {t.permission}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// UnavailableToolsDisclosure
// ---------------------------------------------------------------------------

interface UnavailableToolsDisclosureProps {
  tools: AgentTool[];
  className?: string;
}

export function UnavailableToolsDisclosure({ tools, className }: UnavailableToolsDisclosureProps) {
  const [open, setOpen] = useState(false);
  const unavailable = tools.filter((t) => !t.available);

  if (unavailable.length === 0) return null;

  const grouped = groupByService(unavailable);
  const serviceCount = Object.keys(grouped).length;

  return (
    <div className={className}>
      <button
        type="button"
        className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
        onClick={() => setOpen(!open)}
      >
        {open ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
        <EyeOff className="h-3.5 w-3.5" />
        Show {unavailable.length} unavailable tools from {serviceCount}{" "}
        {serviceCount === 1 ? "service" : "services"}
      </button>

      {open && (
        <Card className="mt-2 border-muted">
          <CardContent className="space-y-3 pt-4">
            {Object.entries(grouped).map(([service, serviceTools]) => (
              <div key={service} className="space-y-1.5">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {service} ({serviceTools.length})
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {serviceTools.map((t) => (
                    <Badge
                      key={t.name}
                      variant="secondary"
                      className="text-xs font-mono"
                    >
                      {toolDisplayName(t.name)}
                    </Badge>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Legacy ToolsList (backward compat)
// ---------------------------------------------------------------------------

interface ToolsListProps {
  tools: AgentTool[];
}

export function ToolsList({ tools }: ToolsListProps) {
  return (
    <div className="space-y-4">
      <DelegatedToolsCard tools={tools} />
      <UnavailableToolsDisclosure tools={tools} />
    </div>
  );
}
