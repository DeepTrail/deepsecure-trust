"use client";

import { Lock, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Permission {
  id: string;
  service: string;
  scope: string;
  action: string;
  locked: false | "role" | "oauth";
  lockReason?: string;
}

export interface PermissionChecklistProps {
  permissions: Permission[];
  selected: string[];
  onToggle: (permissionId: string) => void;
}

function groupBy<T>(items: T[], key: keyof T): Record<string, T[]> {
  return items.reduce(
    (groups, item) => {
      const value = String(item[key]);
      if (!groups[value]) groups[value] = [];
      groups[value].push(item);
      return groups;
    },
    {} as Record<string, T[]>,
  );
}

export function PermissionChecklist({
  permissions,
  selected,
  onToggle,
}: PermissionChecklistProps) {
  const grouped = groupBy(permissions, "service");

  return (
    <div className="space-y-4" role="group" aria-label="Permission checklist">
      {Object.entries(grouped).map(([service, perms]) => (
        <div key={service} className="space-y-2">
          <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            {service}
          </h4>
          <div className="space-y-1">
            {perms.map((perm) => {
              const isLocked = perm.locked !== false;
              const isSelected = selected.includes(perm.id);

              return (
                <label
                  key={perm.id}
                  className={cn(
                    "flex items-center gap-3 rounded-md border px-3 py-2 text-sm transition-colors",
                    isLocked
                      ? "cursor-not-allowed bg-muted/50 opacity-60"
                      : "cursor-pointer hover:bg-accent",
                    isSelected && !isLocked && "border-primary bg-primary/5",
                  )}
                  onClick={isLocked ? (e) => e.preventDefault() : undefined}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    disabled={isLocked}
                    onChange={() => {
                      if (!isLocked) onToggle(perm.id);
                    }}
                    className="h-4 w-4 rounded border-input"
                    aria-label={`${perm.scope}:${perm.action}`}
                  />
                  <span className="flex-1 font-mono text-xs">
                    {perm.scope}:{perm.action}
                  </span>
                  {perm.locked === "role" && (
                    <span className="flex items-center gap-1 text-muted-foreground">
                      <Lock className="h-3.5 w-3.5" data-testid="role-lock-icon" />
                      <span className="text-xs">{perm.lockReason || "Restricted by role"}</span>
                    </span>
                  )}
                  {perm.locked === "oauth" && (
                    <span className="flex items-center gap-1 text-orange-500">
                      <AlertTriangle
                        className="h-3.5 w-3.5"
                        data-testid="oauth-lock-icon"
                      />
                      <span className="text-xs">{perm.lockReason || "Requires OAuth scope"}</span>
                    </span>
                  )}
                </label>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
