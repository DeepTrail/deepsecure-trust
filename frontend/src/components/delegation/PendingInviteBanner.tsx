"use client";

import { useState } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Info } from "lucide-react";
import Link from "next/link";

export interface PendingInvite {
  delegation_id: string;
  agent_id: string;
  template_id?: string | null;
}

interface PendingInviteBannerProps {
  invite: PendingInvite;
  agentName?: string;
  permissionCount?: number;
  onAccepted?: () => void;
  onDismiss?: () => void;
}

export function PendingInviteBanner({
  invite,
  agentName,
  permissionCount,
  onAccepted,
  onDismiss,
}: PendingInviteBannerProps) {
  const [accepting, setAccepting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const handleAccept = async () => {
    setAccepting(true);
    setError(null);
    try {
      await apiClient(`delegations/${invite.delegation_id}/accept`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      onAccepted?.();
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setError("Connect required services before accepting this invite.");
      } else {
        setError("Failed to accept invite. Please try again.");
      }
    } finally {
      setAccepting(false);
    }
  };

  const handleDismiss = () => {
    setDismissed(true);
    onDismiss?.();
  };

  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50/80 px-4 py-3 dark:border-blue-900 dark:bg-blue-950/40">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-2">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-blue-600" />
          <div>
            <p className="text-sm font-medium">
              You have a pending delegation invite for {agentName || invite.agent_id}
            </p>
            {permissionCount !== undefined && (
              <p className="text-xs text-muted-foreground">
                Permissions: {permissionCount} (template ceiling)
              </p>
            )}
            {error && <p className="text-xs text-destructive mt-1">{error}</p>}
          </div>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button variant="outline" size="sm" asChild>
            <Link href="/dashboard/delegation">Review</Link>
          </Button>
          <Button size="sm" onClick={handleAccept} disabled={accepting}>
            {accepting ? "Accepting..." : "Accept"}
          </Button>
          <Button variant="ghost" size="sm" onClick={handleDismiss}>
            Dismiss
          </Button>
        </div>
      </div>
    </div>
  );
}
