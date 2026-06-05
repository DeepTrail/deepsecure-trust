"use client";

import { useEffect, useState } from "react";
import { Loader2, Ban } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/utils";

interface PermissionPickerProps {
  selected: string[];
  onChange: (perms: string[]) => void;
  maxPermissions?: string[];
  blockedPermissions?: string[];
  variant?: "allow" | "block";
}

interface AvailablePermissionsResponse {
  all_permissions: string[];
}

function groupPermissions(permissions: string[]): Record<string, string[]> {
  const groups: Record<string, string[]> = {};
  for (const perm of permissions) {
    const service = perm.split(":")[0] || "other";
    if (!groups[service]) groups[service] = [];
    groups[service].push(perm);
  }
  return groups;
}

export function PermissionPicker({
  selected,
  onChange,
  maxPermissions,
  blockedPermissions,
  variant = "allow",
}: PermissionPickerProps) {
  const [allPermissions, setAllPermissions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (maxPermissions) {
      setAllPermissions(maxPermissions);
      setLoading(false);
      return;
    }

    let cancelled = false;
    async function load() {
      try {
        const resp = await apiClient<AvailablePermissionsResponse>(
          "users/me/available-permissions"
        );
        if (!cancelled) setAllPermissions(resp.all_permissions ?? []);
      } catch {
        if (!cancelled) setError("Failed to load permissions");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [maxPermissions]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading permissions...
      </div>
    );
  }

  if (error) {
    return <p className="text-sm text-destructive">{error}</p>;
  }

  if (allPermissions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No permissions available. Connect a service first.
      </p>
    );
  }

  const blockedSet = new Set(blockedPermissions ?? []);
  const grouped = groupPermissions(allPermissions);

  function togglePerm(perm: string) {
    if (blockedSet.has(perm)) return;
    if (selected.includes(perm)) {
      onChange(selected.filter((p) => p !== perm));
    } else {
      onChange([...selected, perm]);
    }
  }

  function toggleAll(service: string, perms: string[]) {
    const available = perms.filter((p) => !blockedSet.has(p));
    const allSelected = available.every((p) => selected.includes(p));
    if (allSelected) {
      onChange(selected.filter((p) => !available.includes(p)));
    } else {
      const newSelected = new Set([...selected, ...available]);
      onChange(Array.from(newSelected));
    }
  }

  const isBlock = variant === "block";

  return (
    <div className="space-y-4" role="group" aria-label="Permission picker">
      {Object.entries(grouped).map(([service, perms]) => {
        const available = perms.filter((p) => !blockedSet.has(p));
        const selectedCount = available.filter((p) => selected.includes(p)).length;
        const allSelected = available.length > 0 && selectedCount === available.length;

        return (
          <div key={service} className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                {service}
                <span className="ml-1.5 font-normal normal-case">
                  ({perms.length})
                </span>
              </h4>
              {available.length > 1 && (
                <button
                  type="button"
                  className="text-xs text-primary hover:underline"
                  onClick={() => toggleAll(service, perms)}
                >
                  {allSelected ? "Deselect all" : "Select all"}
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {perms.map((perm) => {
                const isBlocked = blockedSet.has(perm);
                const isSelected = selected.includes(perm);
                const label = perm.split(":").slice(1).join(":");

                return (
                  <button
                    key={perm}
                    type="button"
                    disabled={isBlocked}
                    onClick={() => togglePerm(perm)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                      isBlocked && "cursor-not-allowed opacity-50 line-through",
                      !isBlocked && !isSelected && "hover:border-foreground hover:text-foreground text-muted-foreground",
                      !isBlocked && isSelected && !isBlock && "border-primary bg-primary/10 text-primary",
                      !isBlocked && isSelected && isBlock && "border-destructive bg-destructive/10 text-destructive",
                    )}
                  >
                    {isBlocked && <Ban className="h-3 w-3" />}
                    {label || perm}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
