"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { DelegationSummary } from "@/lib/types/admin";
import {
  getServiceDisplayName,
  groupPermissionsByService,
} from "./service-utils";

interface DelegationsTableProps {
  delegations: DelegationSummary[];
}

export function DelegationsTable({ delegations }: DelegationsTableProps) {
  const [expandedDelegationRow, setExpandedDelegationRow] = useState<string | null>(null);

  if (delegations.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No active delegations</p>
    );
  }

  return (
    <div className="overflow-x-auto rounded border">
      <table className="w-full text-xs">
        <thead className="bg-muted/50 border-b">
          <tr>
            <th className="w-8 px-3 py-2" />
            <th className="px-3 py-2 text-left font-medium">Delegator</th>
            <th className="px-3 py-2 text-left font-medium">Permissions</th>
            <th className="px-3 py-2 text-left font-medium">Created</th>
            <th className="px-3 py-2 text-left font-medium">Expires</th>
            <th className="px-3 py-2 text-left font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {delegations.map((d) => {
            const isOpen = expandedDelegationRow === d.id;
            return (
              <DelegationRow
                key={d.id}
                delegation={d}
                isOpen={isOpen}
                onToggle={() =>
                  setExpandedDelegationRow(isOpen ? null : d.id)
                }
              />
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function DelegationRow({
  delegation,
  isOpen,
  onToggle,
}: {
  delegation: DelegationSummary;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        className="cursor-pointer hover:bg-muted/30 transition-colors"
        onClick={onToggle}
      >
        <td className="px-3 py-2">
          {isOpen ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </td>
        <td className="px-3 py-2 text-muted-foreground">
          {delegation.delegator}
        </td>
        <td className="px-3 py-2">
          <div className="flex items-center gap-1.5">
            <span className="text-muted-foreground">
              {delegation.permissions.length} permissions
            </span>
            {delegation.services.map((svc) => (
              <Badge
                key={svc}
                variant="outline"
                className="text-[10px]"
              >
                {getServiceDisplayName(svc)}
              </Badge>
            ))}
          </div>
        </td>
        <td className="px-3 py-2 text-muted-foreground">
          {delegation.created_at
            ? new Date(delegation.created_at).toLocaleDateString()
            : "—"}
        </td>
        <td className="px-3 py-2 text-muted-foreground">
          {delegation.expires_at
            ? new Date(delegation.expires_at).toLocaleDateString()
            : "—"}
        </td>
        <td className="px-3 py-2">
          <Badge
            variant={delegation.is_expired ? "destructive" : "outline"}
            className={cn(
              "text-xs",
              !delegation.is_expired && "text-green-700 border-green-200"
            )}
          >
            {delegation.is_expired ? "Expired" : "Active"}
          </Badge>
        </td>
      </tr>
      {isOpen && (
        <tr>
          <td colSpan={6} className="bg-muted/10 px-6 py-3">
            <PermissionGroups permissions={delegation.permissions} />
          </td>
        </tr>
      )}
    </>
  );
}

function PermissionGroups({ permissions }: { permissions: string[] }) {
  const groups = groupPermissionsByService(permissions);
  const entries = Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="space-y-2">
      {entries.map(([service, perms]) => (
        <div key={service} className="text-xs">
          <span className="font-medium">
            {getServiceDisplayName(service)}
          </span>
          <div className="mt-1 flex flex-wrap gap-1">
            {perms.map((p) => (
              <Badge key={p} variant="secondary" className="text-[10px] font-normal font-mono">
                {p}
              </Badge>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
