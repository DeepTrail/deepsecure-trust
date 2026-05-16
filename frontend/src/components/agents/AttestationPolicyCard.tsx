"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ShieldCheck, AlertCircle } from "lucide-react";

interface AttestationPolicy {
  id: string;
  platform: string;
  selector: string;
  agent_name_to_bootstrap: string;
}

interface AttestationPolicyCardProps {
  agentId: string;
  className?: string;
}

const PLATFORM_LABELS: Record<string, string> = {
  gcp_workload_identity: "GCP Workload Identity",
  aws_iam: "AWS IAM",
  kubernetes: "Kubernetes",
  azure_managed_identity: "Azure Managed Identity",
  docker_container: "Docker Container",
};

export function AttestationPolicyCard({
  agentId,
  className,
}: AttestationPolicyCardProps) {
  const [policies, setPolicies] = useState<AttestationPolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchPolicies() {
      try {
        const data = await apiClient<AttestationPolicy[]>(
          "policies/attestation"
        );
        if (!cancelled) {
          setPolicies(
            data.filter((p) => p.agent_name_to_bootstrap === agentId)
          );
        }
      } catch {
        if (!cancelled) {
          setError("Failed to load attestation policies");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchPolicies();
    return () => {
      cancelled = true;
    };
  }, [agentId]);

  if (loading) {
    return (
      <Card className={className}>
        <CardContent className="py-6">
          <p className="text-sm text-muted-foreground text-center">
            Loading attestation policies…
          </p>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={className}>
        <CardContent className="py-6">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-4 w-4" />
            <p className="text-sm">{error}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <ShieldCheck className="h-4 w-4 text-muted-foreground" />
          Attestation Policies
        </CardTitle>
      </CardHeader>
      <CardContent>
        {policies.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No attestation policies configured for this agent. Create one from
            the{" "}
            <a
              href="/dashboard/policies"
              className="underline"
            >
              Policies page
            </a>
            .
          </p>
        ) : (
          <div className="space-y-3">
            {policies.map((policy) => (
              <div
                key={policy.id}
                className="flex items-center justify-between rounded-md border p-3"
              >
                <div className="space-y-1">
                  <Badge variant="secondary" className="text-xs">
                    {PLATFORM_LABELS[policy.platform] ?? policy.platform}
                  </Badge>
                  <p className="text-xs font-mono text-muted-foreground">
                    {policy.selector}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
