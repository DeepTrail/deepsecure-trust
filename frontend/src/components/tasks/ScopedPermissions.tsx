"use client";

import { cn } from "@/lib/utils";
import { Shield, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export interface Permission {
  service: string;
  scope: string;
  action: string;
  attenuated?: boolean;
}

export interface ScopedPermissionsProps {
  permissions: Permission[];
  className?: string;
}

export function ScopedPermissions({
  permissions,
  className,
}: ScopedPermissionsProps) {
  if (permissions.length === 0) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 py-4 text-sm text-muted-foreground",
          className
        )}
      >
        <Shield className="h-4 w-4" />
        <span>No permissions assigned to this task.</span>
      </div>
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      <div className="rounded-lg border">
        <table className="w-full text-sm" role="table">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                Service
              </th>
              <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                Scope
              </th>
              <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                Action
              </th>
              <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                Source
              </th>
            </tr>
          </thead>
          <tbody>
            {permissions.map((perm, idx) => (
              <tr
                key={`${perm.service}-${perm.scope}-${perm.action}-${idx}`}
                className={cn(
                  "border-b last:border-0",
                  perm.attenuated && "bg-amber-50/50 dark:bg-amber-950/10"
                )}
              >
                <td className="px-4 py-2 font-mono text-xs">{perm.service}</td>
                <td className="px-4 py-2 font-mono text-xs">{perm.scope}</td>
                <td className="px-4 py-2 font-mono text-xs">{perm.action}</td>
                <td className="px-4 py-2">
                  {perm.attenuated ? (
                    <Badge variant="outline" className="text-[10px] gap-1">
                      <Shield className="h-3 w-3" />
                      Attenuated
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="text-[10px] gap-1">
                      <ShieldCheck className="h-3 w-3" />
                      Delegation
                    </Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
