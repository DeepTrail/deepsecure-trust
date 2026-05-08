"use client";

import { useState } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { CheckCircle2, Send } from "lucide-react";
import {
  PermissionChecklist,
  type Permission,
} from "./PermissionChecklist";

interface Agent {
  agent_id: string;
  name: string;
}

interface DelegationBuilderProps {
  agents: Agent[];
  permissions: Permission[];
  onCreated?: () => void;
}

interface DelegationResult {
  delegation_id: string;
}

const TTL_OPTIONS = [
  { label: "15 minutes", value: 900 },
  { label: "1 hour", value: 3600 },
  { label: "8 hours", value: 28800 },
  { label: "24 hours", value: 86400 },
  { label: "7 days", value: 604800 },
];

export function DelegationBuilder({
  agents,
  permissions,
  onCreated,
}: DelegationBuilderProps) {
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [ttl, setTtl] = useState<number>(3600);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DelegationResult | null>(null);

  const handleTogglePermission = (permissionId: string) => {
    setSelectedPermissions((prev) =>
      prev.includes(permissionId)
        ? prev.filter((id) => id !== permissionId)
        : [...prev, permissionId],
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAgent || selectedPermissions.length === 0) return;

    setSubmitting(true);
    setError(null);

    try {
      const permissionStrings = selectedPermissions.map((id) => {
        const perm = permissions.find((p) => p.id === id);
        return perm ? `${perm.service}:${perm.scope}:${perm.action}` : id;
      });

      const data = await apiClient<DelegationResult>("auth/delegate", {
        method: "POST",
        body: JSON.stringify({
          agent_id: selectedAgent,
          permissions: permissionStrings,
          constraints: { expires_in_hours: ttl / 3600 },
        }),
      });
      setResult(data);
      onCreated?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Failed to create delegation (${err.status})`);
      } else {
        setError("Failed to create delegation. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    setResult(null);
    setSelectedAgent("");
    setSelectedPermissions([]);
    setTtl(3600);
    setError(null);
  };

  if (result) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-4 py-8">
          <CheckCircle2 className="h-12 w-12 text-green-500" />
          <h3 className="text-lg font-semibold">Delegation Created</h3>
          <p className="text-sm text-muted-foreground">
            Delegation ID:{" "}
            <span className="font-mono" data-testid="delegation-id">
              {result.delegation_id}
            </span>
          </p>
          <Button variant="outline" onClick={handleReset}>
            Create Another
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Select Agent</CardTitle>
        </CardHeader>
        <CardContent>
          <select
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            aria-label="Select agent"
            required
          >
            <option value="">Choose an agent...</option>
            {agents.map((agent) => (
              <option key={agent.agent_id} value={agent.agent_id}>
                {agent.name || agent.agent_id}
              </option>
            ))}
          </select>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Permissions
            {selectedPermissions.length > 0 && (
              <Badge variant="secondary" className="ml-2">
                {selectedPermissions.length} selected
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <PermissionChecklist
            permissions={permissions}
            selected={selectedPermissions}
            onToggle={handleTogglePermission}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Time-to-Live (TTL)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {TTL_OPTIONS.map((option) => (
              <Button
                key={option.value}
                type="button"
                variant={ttl === option.value ? "default" : "outline"}
                size="sm"
                onClick={() => setTtl(option.value)}
              >
                {option.label}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="flex items-center gap-3">
          <p className="text-sm text-destructive flex-1">{error}</p>
          <Button type="button" variant="outline" size="sm" onClick={() => { setError(null); handleSubmit(new Event("submit") as unknown as React.FormEvent); }}>
            Retry
          </Button>
        </div>
      )}

      <Separator />

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {selectedAgent
            ? `Delegating ${selectedPermissions.length} permission(s) to ${selectedAgent}`
            : "Select an agent and permissions to create a delegation"}
        </p>
        <Button
          type="submit"
          disabled={
            submitting || !selectedAgent || selectedPermissions.length === 0
          }
        >
          <Send className="mr-2 h-4 w-4" />
          {submitting ? "Creating..." : "Create Delegation"}
        </Button>
      </div>
    </form>
  );
}
