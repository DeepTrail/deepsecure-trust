"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api/client";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import { DelegationBuilder } from "@/components/delegation/DelegationBuilder";
import type { Permission } from "@/components/delegation/PermissionChecklist";
import { KeyRound, Plug, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";

interface Agent {
  agent_id: string;
  name: string;
}

interface AvailablePermissionsResponse {
  services: Record<string, {
    connected: boolean;
    service_name: string;
    scopes_granted: string[];
    available_permissions: string[];
    connected_at: string | null;
  }>;
  all_permissions: string[];
  total_services: number;
  total_permissions: number;
}

interface PublicTemplate {
  id: string;
  agent_id: string;
  max_permissions: string[];
  blocked_permissions: string[];
  default_ttl_days: number;
}

function parsePermissionString(permStr: string): Permission | null {
  const parts = permStr.split(":");
  if (parts.length !== 3) return null;
  const [service, scope, action] = parts;
  return { id: permStr, service, scope, action, locked: false };
}

interface DelegationSummary {
  delegation_id: string;
  agent_id: string;
  permissions: string[];
  status?: string;
}

interface PageData {
  agents: Agent[];
  permissions: Permission[];
  totalServices: number;
  templates: PublicTemplate[];
  editDelegation?: DelegationSummary;
}

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; data: PageData };

export default function CreateDelegationPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [allowFreeform, setAllowFreeform] = useState<boolean>(true);
  const router = useRouter();
  const searchParams = useSearchParams();
  const editId = searchParams.get("edit");

  const fetchData = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const [agentsResp, permissionsResp, templatesResp, policyResp, delegationsResp] =
        await Promise.all([
        apiClient<Agent[] | { agents: Agent[] }>("agents/"),
        apiClient<AvailablePermissionsResponse>(
          "users/me/available-permissions",
        ),
        apiClient<{ templates: PublicTemplate[] }>(
          "auth/delegation-templates",
        ).catch(() => ({ templates: [] })),
        apiClient<{ allow_freeform: boolean }>(
          "settings/delegation-policy",
        ).catch(() => ({ allow_freeform: true })),
        editId
          ? apiClient<DelegationSummary[]>("auth/delegations").catch(() => [])
          : Promise.resolve([]),
      ]);

      setAllowFreeform(policyResp.allow_freeform);

      const agents = Array.isArray(agentsResp)
        ? agentsResp
        : (agentsResp.agents ?? []);

      const permissions: Permission[] = (permissionsResp.all_permissions ?? [])
        .map(parsePermissionString)
        .filter((p): p is Permission => p !== null);

      const totalServices = permissionsResp.total_services ?? 0;
      const templates = templatesResp.templates ?? [];
      const delegations = Array.isArray(delegationsResp) ? delegationsResp : [];
      const editDelegation = editId
        ? delegations.find((d) => d.delegation_id === editId)
        : undefined;

      setState({
        kind: "data",
        data: { agents, permissions, totalServices, templates, editDelegation },
      });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load data (${err.status})`
          : "Failed to load data";
      setState({ kind: "error", message });
    }
  }, [editId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreated = () => {
    router.push("/dashboard/delegation");
  };

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error")
    return (
      <ErrorCard title="Create Delegation" message={state.message} retry={fetchData} />
    );

  const { agents, permissions, totalServices, templates, editDelegation } = state.data;
  const isEditMode = !!editDelegation;

  if (agents.length === 0) {
    return (
      <div className="space-y-6">
        <BackLink />
        <h1 className="text-2xl font-bold">Create Delegation</h1>
        <EmptyState
          icon={<KeyRound className="h-12 w-12" />}
          title="No agents available"
          description="Register at least one agent before creating delegations."
        />
      </div>
    );
  }

  if (permissions.length === 0) {
    return (
      <div className="space-y-6">
        <BackLink />
        <h1 className="text-2xl font-bold">Create Delegation</h1>
        <EmptyState
          icon={<Plug className="h-12 w-12" />}
          title="No services connected"
          description="Connect at least one service (Notion, Slack, etc.) from the Services page to see available permissions for delegation."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <BackLink />
      <div>
        <h1 className="text-2xl font-bold">
          {isEditMode ? "Edit Delegation" : "Create Delegation"}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {isEditMode
            ? "Narrow permissions on an existing delegation (widening is not allowed)."
            : "Grant granular permissions to an agent with a time-limited delegation token."}
        </p>
        <div className="flex gap-2 mt-2">
          <Badge variant="outline">
            {totalServices} service{totalServices !== 1 ? "s" : ""} connected
          </Badge>
          <Badge variant="outline">
            {permissions.length} permission{permissions.length !== 1 ? "s" : ""} available
          </Badge>
          {templates.length > 0 && (
            <Badge variant="outline">
              {templates.length} template{templates.length !== 1 ? "s" : ""} available
            </Badge>
          )}
        </div>
      </div>
      <DelegationBuilder
        agents={agents}
        permissions={permissions}
        templates={templates}
        onCreated={handleCreated}
        requireTemplate={!allowFreeform && !isEditMode}
        editMode={isEditMode}
        delegationId={editDelegation?.delegation_id}
        initialAgentId={editDelegation?.agent_id}
        initialPermissions={editDelegation?.permissions}
      />
    </div>
  );
}

function BackLink() {
  return (
    <Button variant="ghost" size="sm" asChild>
      <Link href="/dashboard/delegation">
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Delegations
      </Link>
    </Button>
  );
}
