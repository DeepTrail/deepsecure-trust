"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { KeyRound, Cloud, Box, Copy, Check, CheckCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface AgentIdentityCardProps {
  agentId: string;
  platform?: string | null;
  selector?: string | null;
  className?: string;
}

const PLATFORM_CONFIG: Record<
  string,
  { label: string; icon: LucideIcon }
> = {
  gcp_workload_identity: { label: "GCP Workload Identity", icon: Cloud },
  aws_iam: { label: "AWS IAM", icon: Cloud },
  kubernetes: { label: "Kubernetes", icon: Box },
};

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API may not be available in all contexts
    }
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={handleCopy}
      className="h-7 px-2 text-xs"
    >
      {copied ? (
        <Check className="mr-1 h-3 w-3 text-green-600" />
      ) : (
        <Copy className="mr-1 h-3 w-3" />
      )}
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}

function KeyBasedCard({ agentId, className }: { agentId: string; className?: string }) {
  return (
    <Card className={cn("bg-gray-50 dark:bg-gray-800/50", className)}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <KeyRound className="h-4 w-4 text-muted-foreground" />
          Identity Method
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Method:</span>
          <span className="font-medium">Cryptographic Key (Ed25519)</span>
        </div>

        <div className="rounded-lg border bg-muted/50">
          <div className="space-y-0 divide-y">
            <div className="flex items-center justify-between px-3 py-2">
              <code className="text-xs font-mono">
                <span className="text-muted-foreground">DEEPSECURE_AGENT_ID</span>
                {" = "}
                <span className="text-foreground">{agentId}</span>
              </code>
              <CopyButton text={agentId} />
            </div>
            <div className="flex items-center justify-between px-3 py-2">
              <code className="text-xs font-mono">
                <span className="text-muted-foreground">DEEPSECURE_PRIVATE_KEY</span>
                {" = "}
                <span className="italic text-muted-foreground/70">&lt;set during creation&gt;</span>
              </code>
            </div>
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          Set these environment variables in your agent&apos;s runtime.
        </p>
      </CardContent>
    </Card>
  );
}

function PlatformBasedCard({
  platform,
  selector,
  className,
}: {
  platform: string;
  selector?: string | null;
  className?: string;
}) {
  const config = PLATFORM_CONFIG[platform] ?? {
    label: platform,
    icon: Cloud,
  };
  const Icon = config.icon;

  return (
    <Card className={cn("bg-gray-50 dark:bg-gray-800/50", className)}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Icon className="h-4 w-4 text-muted-foreground" />
          Identity Method
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 text-sm">
          <div className="flex items-baseline gap-2">
            <span className="text-muted-foreground">Method:</span>
            <span className="font-medium">{config.label}</span>
          </div>
          {selector && (
            <div className="flex items-baseline gap-2">
              <span className="shrink-0 text-muted-foreground">Selector:</span>
              <code className="break-all text-xs font-mono">{selector}</code>
            </div>
          )}
        </div>

        <div className="flex items-start gap-2 rounded-md border border-green-200 bg-green-50/50 p-3 dark:border-green-900 dark:bg-green-950/20">
          <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-green-600 dark:text-green-400" />
          <div className="text-sm">
            <p className="font-medium text-green-700 dark:text-green-400">
              No keys or environment variables needed.
            </p>
            <p className="text-xs text-green-600/80 dark:text-green-400/70">
              Your agent authenticates automatically via its platform identity.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function AgentIdentityCard({
  agentId,
  platform,
  selector,
  className,
}: AgentIdentityCardProps) {
  if (platform) {
    return (
      <PlatformBasedCard
        platform={platform}
        selector={selector}
        className={className}
      />
    );
  }

  return <KeyBasedCard agentId={agentId} className={className} />;
}
