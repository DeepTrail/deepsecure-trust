"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { DelegatorSummary } from "@/lib/types/admin";
import { getServiceDisplayName, getServiceStatusColor } from "./service-utils";

interface CrossUserMappingTableProps {
  delegators: DelegatorSummary[];
}

export function CrossUserMappingTable({ delegators }: CrossUserMappingTableProps) {
  const [expandedUserRow, setExpandedUserRow] = useState<string | null>(null);

  if (delegators.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No delegating users — no users have delegated permissions to this agent.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded border">
      <table className="w-full text-xs">
        <thead className="bg-muted/50 border-b">
          <tr>
            <th className="w-8 px-3 py-2" />
            <th className="px-3 py-2 text-left font-medium">User</th>
            <th className="px-3 py-2 text-left font-medium">Services</th>
            <th className="px-3 py-2 text-left font-medium">Delegations</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {delegators.map((d) => {
            const isOpen = expandedUserRow === d.email;
            return (
              <UserRow
                key={d.email}
                delegator={d}
                isOpen={isOpen}
                onToggle={() => setExpandedUserRow(isOpen ? null : d.email)}
              />
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function UserRow({
  delegator,
  isOpen,
  onToggle,
}: {
  delegator: DelegatorSummary;
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
        <td className="px-3 py-2 text-muted-foreground">{delegator.email}</td>
        <td className="px-3 py-2">
          <div className="flex flex-wrap gap-1">
            {delegator.connected_services.length > 0 ? (
              delegator.connected_services.map((svc) => (
                <Badge
                  key={svc.service_id}
                  variant="outline"
                  className={`text-[10px] ${getServiceStatusColor(svc.status)}`}
                >
                  {getServiceDisplayName(svc.service_id)}
                </Badge>
              ))
            ) : (
              <span className="text-muted-foreground">—</span>
            )}
          </div>
        </td>
        <td className="px-3 py-2 text-muted-foreground">
          {delegator.delegation_count}
        </td>
      </tr>
      {isOpen && (
        <tr>
          <td colSpan={4} className="bg-muted/10 px-6 py-3">
            <ServiceDetailGrid services={delegator.connected_services} />
          </td>
        </tr>
      )}
    </>
  );
}

function ServiceDetailGrid({
  services,
}: {
  services: DelegatorSummary["connected_services"];
}) {
  if (services.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No connected services for this user.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {services.map((svc) => (
        <div key={svc.service_id} className="flex items-start gap-3 text-xs">
          <div className="flex items-center gap-1.5 min-w-[120px]">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                svc.status === "connected"
                  ? "bg-green-500"
                  : svc.status === "token_expired"
                    ? "bg-amber-500"
                    : "bg-gray-400"
              }`}
            />
            <span className="font-medium">
              {getServiceDisplayName(svc.service_id)}
            </span>
          </div>
          <div className="flex flex-wrap gap-1">
            {svc.scopes_granted.map((scope) => (
              <Badge
                key={scope}
                variant="secondary"
                className="text-[10px] font-normal"
              >
                {scope}
              </Badge>
            ))}
            {svc.scopes_granted.length === 0 && (
              <span className="text-muted-foreground">No scopes</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
