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

  const handleToggleAll = (service: string, perms: Permission[]) => {
    const unlocked = perms.filter((p) => p.locked === false);
    const allSelected = unlocked.every((p) => selected.includes(p.id));
    for (const p of unlocked) {
      const isSelected = selected.includes(p.id);
      if (allSelected && isSelected) onToggle(p.id);
      if (!allSelected && !isSelected) onToggle(p.id);
    }
  };

  return (
    <div className="space-y-5" role="group" aria-label="Permission checklist">
      {Object.entries(grouped).map(([service, perms]) => {
        const unlocked = perms.filter((p) => p.locked === false);
        const selectedCount = unlocked.filter((p) => selected.includes(p.id)).length;
        const allSelected = unlocked.length > 0 && selectedCount === unlocked.length;

        return (
          <div key={service} className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                {service}
                <span className="ml-1.5 text-xs font-normal normal-case">
                  ({perms.length} permission{perms.length !== 1 ? "s" : ""})
                </span>
              </h4>
              {unlocked.length > 1 && (
                <button
                  type="button"
                  className="text-xs text-primary hover:underline"
                  onClick={() => handleToggleAll(service, perms)}
                >
                  {allSelected ? "Deselect all" : "Select all"}
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {perms.map((perm) => {
                const isLocked = perm.locked !== false;
                const isSelected = selected.includes(perm.id);

                return (
                  <label
                    key={perm.id}
                    className={cn(
                      "inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors",
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
                      className="h-3.5 w-3.5 rounded border-input"
                      aria-label={`${perm.scope}:${perm.action}`}
                    />
                    <span className="font-mono text-xs whitespace-nowrap">
                      {perm.scope}:{perm.action}
                    </span>
                    {perm.locked === "role" && (
                      <span title={perm.lockReason || "Restricted by role"}>
                        <Lock
                          className="h-3 w-3 text-muted-foreground"
                          data-testid="role-lock-icon"
                        />
                      </span>
                    )}
                    {perm.locked === "oauth" && (
                      <span title={perm.lockReason || "Requires OAuth scope"}>
                        <AlertTriangle
                          className="h-3 w-3 text-orange-500"
                          data-testid="oauth-lock-icon"
                        />
                      </span>
                    )}
                  </label>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
