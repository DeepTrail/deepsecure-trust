"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Terminal, Cloud, Ship, Copy, Check } from "lucide-react";

type RuntimeTab = "env" | "aws" | "k8s";

interface DeployConfigSectionProps {
  agentId: string;
  className?: string;
}

interface TabConfig {
  key: RuntimeTab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
}

const TABS: TabConfig[] = [
  {
    key: "env",
    label: "Environment",
    icon: Terminal,
    description: "Set environment variables for local or CI usage",
  },
  {
    key: "aws",
    label: "AWS",
    icon: Cloud,
    description: "Use IAM role-based identity in AWS Lambda or ECS",
  },
  {
    key: "k8s",
    label: "Kubernetes",
    icon: Ship,
    description: "Mount identity via projected service account token",
  },
];

function envSnippet(agentId: string): string {
  return `export DEEPSECURE_AGENT_ID="${agentId}"
export DEEPSECURE_PRIVATE_KEY="<your-base64-private-key>"
export DEEPSECURE_DEEPTRAIL_CONTROL_URL="https://control.deepsecure.io"`;
}

function awsSnippet(agentId: string): string {
  return `# In your Lambda/ECS task definition, set:
#   DEEPSECURE_AGENT_ID=${agentId}
#   DEEPSECURE_IDENTITY_PROVIDER=aws
#
# The SDK automatically uses the IAM execution role
# to prove agent identity — no static keys needed.

from deepsecure import Client

client = Client()  # auto-detects AWS identity
agent = client.agents.authenticate()`;
}

function k8sSnippet(agentId: string): string {
  return `# 1. Create a Kubernetes Secret with the agent private key:
kubectl create secret generic deepsecure-agent \\
  --from-literal=agent-id="${agentId}" \\
  --from-literal=private-key="<your-base64-private-key>"

# 2. Mount in your Pod spec:
# env:
#   - name: DEEPSECURE_AGENT_ID
#     valueFrom:
#       secretKeyRef:
#         name: deepsecure-agent
#         key: agent-id
#   - name: DEEPSECURE_PRIVATE_KEY
#     valueFrom:
#       secretKeyRef:
#         name: deepsecure-agent
#         key: private-key`;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API may not be available
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

export function DeployConfigSection({
  agentId,
  className,
}: DeployConfigSectionProps) {
  const [activeTab, setActiveTab] = useState<RuntimeTab>("env");

  const snippetMap: Record<RuntimeTab, string> = {
    env: envSnippet(agentId),
    aws: awsSnippet(agentId),
    k8s: k8sSnippet(agentId),
  };

  const activeConfig = TABS.find((t) => t.key === activeTab)!;
  const snippet = snippetMap[activeTab];

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Terminal className="h-4 w-4 text-muted-foreground" />
          Deploy Configuration
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Tab bar */}
        <div className="flex gap-2">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                  activeTab === tab.key
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Description */}
        <p className="text-xs text-muted-foreground">
          {activeConfig.description}
        </p>

        {/* Code block */}
        <div className="relative rounded-lg border bg-muted/50">
          <div className="flex items-center justify-between border-b px-3 py-1.5">
            <Badge variant="secondary" className="text-[10px]">
              {activeConfig.label}
            </Badge>
            <CopyButton text={snippet} />
          </div>
          <pre className="overflow-x-auto p-3 text-xs font-mono leading-relaxed text-foreground">
            {snippet}
          </pre>
        </div>
      </CardContent>
    </Card>
  );
}
