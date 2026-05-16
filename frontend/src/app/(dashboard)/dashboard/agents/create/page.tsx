"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Bot, Info } from "lucide-react";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { AgentTypeSelector, IdentityMethodSelector, PrivateKeyModal } from "@/components/agents";
import type { AgentType, IdentityMethod } from "@/components/agents";

interface AgentCreateResponse {
  agent_id: string;
  name: string;
  public_key?: string | null;
  private_key?: string;
  private_key_warning?: string;
  platform?: string | null;
  selector?: string | null;
}

const PLATFORM_LABELS: Record<Exclude<IdentityMethod, "key">, string> = {
  gcp: "GCP Workload Identity",
  aws: "AWS IAM",
  k8s: "Kubernetes Service Account",
};

export default function AgentCreatePage() {
  const router = useRouter();

  const [agentType, setAgentType] = useState<AgentType>("own");
  const [identityMethod, setIdentityMethod] = useState<IdentityMethod>("key");
  const [agentId, setAgentId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [publicKey, setPublicKey] = useState("");
  const [selector, setSelector] = useState("");
  const [k8sNamespace, setK8sNamespace] = useState("");
  const [k8sSaName, setK8sSaName] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isPlatformBased = identityMethod !== "key";

  const [keypairResult, setKeypairResult] = useState<{
    agentId: string;
    publicKey: string;
    privateKey: string;
  } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    setSubmitting(true);
    setError(null);

    try {
      const body: Record<string, string> = {
        name: name.trim() || "Untitled Agent",
      };
      if (description.trim()) body.description = description.trim();

      if (identityMethod === "key") {
        if (agentId.trim()) body.agent_id = agentId.trim();
        if (publicKey.trim()) body.public_key = publicKey.trim();
      } else {
        const platformMap: Record<string, string> = {
          gcp: "gcp_workload_identity",
          aws: "aws_iam",
          k8s: "kubernetes",
        };
        body.platform = platformMap[identityMethod];
        if (identityMethod === "k8s") {
          body.selector = `namespace=${k8sNamespace.trim()},service_account=${k8sSaName.trim()}`;
        } else {
          body.selector = selector.trim();
        }
      }

      const result = await apiClient<AgentCreateResponse>("agents/", {
        method: "POST",
        body: JSON.stringify(body),
      });

      if (identityMethod !== "key") {
        router.push(`/dashboard/delegation/create?agent_id=${result.agent_id}`);
      } else if (result.private_key) {
        setKeypairResult({
          agentId: result.agent_id,
          publicKey: result.public_key ?? "",
          privateKey: result.private_key,
        });
      } else {
        router.push("/dashboard/agents");
      }
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          if (identityMethod !== "key") {
            setError("An agent is already registered with this platform identity. Each selector must be unique.");
          } else {
            setError("An agent with this ID or public key already exists.");
          }
        } else if (err.status === 422) {
          const detail = (err.body as { detail?: string })?.detail;
          setError(detail || "Invalid input. Please check your values and try again.");
        } else {
          setError(`Failed to create agent (${err.status}). Please try again.`);
        }
      } else {
        setError("Failed to create agent. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleModalDismiss = () => {
    setKeypairResult(null);
    router.push("/dashboard/agents");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.push("/dashboard/agents")} aria-label="Back to agents">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">Register Agent</h1>
          <p className="text-sm text-muted-foreground">
            Set up a new AI agent with identity and credentials
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Bot className="h-4 w-4" />
            Agent Details
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label className="text-sm font-medium">Agent Type</label>
              <AgentTypeSelector value={agentType} onChange={setAgentType} />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Identity Method</label>
              <IdentityMethodSelector value={identityMethod} onChange={setIdentityMethod} />
            </div>

            <Separator />

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1">
                <label htmlFor="create-agent-name" className="text-sm font-medium">
                  Name <span className="text-destructive">*</span>
                </label>
                <input
                  id="create-agent-name"
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Sales Agent for Lead Gen"
                  required
                />
                <p className="text-xs text-muted-foreground">
                  Human-readable name for this agent.
                </p>
              </div>
              <div className="space-y-1">
                <label htmlFor="create-agent-description" className="text-sm font-medium">
                  Description
                </label>
                <input
                  id="create-agent-description"
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Helps with lead gen and follow up"
                />
              </div>
            </div>

            {identityMethod === "gcp" && (
              <div className="space-y-1">
                <label htmlFor="create-agent-gcp-sa" className="text-sm font-medium">
                  GCP Service Account Email <span className="text-destructive">*</span>
                </label>
                <input
                  id="create-agent-gcp-sa"
                  className="w-full rounded-md border px-3 py-2 text-sm font-mono"
                  value={selector}
                  onChange={(e) => setSelector(e.target.value)}
                  placeholder="my-agent@my-project.iam.gserviceaccount.com"
                />
                <p className="text-xs text-muted-foreground">
                  The GCP service account that this agent will authenticate as.
                </p>
              </div>
            )}

            {identityMethod === "aws" && (
              <div className="space-y-1">
                <label htmlFor="create-agent-aws-role" className="text-sm font-medium">
                  AWS IAM Role ARN <span className="text-destructive">*</span>
                </label>
                <input
                  id="create-agent-aws-role"
                  className="w-full rounded-md border px-3 py-2 text-sm font-mono"
                  value={selector}
                  onChange={(e) => setSelector(e.target.value)}
                  placeholder="arn:aws:iam::123456789012:role/my-agent-role"
                />
                <p className="text-xs text-muted-foreground">
                  The IAM role ARN that this agent will assume for authentication.
                </p>
              </div>
            )}

            {identityMethod === "k8s" && (
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <label htmlFor="create-agent-k8s-ns" className="text-sm font-medium">
                    Namespace <span className="text-destructive">*</span>
                  </label>
                  <input
                    id="create-agent-k8s-ns"
                    className="w-full rounded-md border px-3 py-2 text-sm font-mono"
                    value={k8sNamespace}
                    onChange={(e) => setK8sNamespace(e.target.value)}
                    placeholder="default"
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor="create-agent-k8s-sa" className="text-sm font-medium">
                    Service Account Name <span className="text-destructive">*</span>
                  </label>
                  <input
                    id="create-agent-k8s-sa"
                    className="w-full rounded-md border px-3 py-2 text-sm font-mono"
                    value={k8sSaName}
                    onChange={(e) => setK8sSaName(e.target.value)}
                    placeholder="my-agent-sa"
                  />
                </div>
              </div>
            )}

            <div className="rounded-md border bg-muted/30 p-3">
              <div className="flex items-start gap-2">
                <Info className="mt-0.5 h-4 w-4 text-muted-foreground shrink-0" />
                <div className="text-xs text-muted-foreground space-y-1">
                  <p>
                    <strong>Agent ID</strong> will be auto-generated by the server (e.g., <code className="text-[11px]">agent-e694edcb-...</code>).
                  </p>
                  {isPlatformBased ? (
                    <p>
                      This agent will authenticate using <strong>{PLATFORM_LABELS[identityMethod as Exclude<IdentityMethod, "key">]}</strong>. No keys or environment variables needed — identity is verified via the platform&apos;s native token.
                    </p>
                  ) : (
                    <p>
                      <strong>Ed25519 keypair</strong> will be generated server-side. The private key will be shown <strong>once</strong> after creation — save it securely.
                    </p>
                  )}
                </div>
              </div>
            </div>

            {!isPlatformBased && (
              <>
                <button
                  type="button"
                  className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                >
                  {showAdvanced ? "Hide advanced options" : "Show advanced options"}
                </button>

                {showAdvanced && (
                  <div className="space-y-4 rounded-md border p-4">
                    <div className="space-y-1">
                      <label htmlFor="create-agent-id" className="text-sm font-medium">
                        Agent ID{" "}
                        <span className="text-muted-foreground font-normal">(optional)</span>
                      </label>
                      <input
                        id="create-agent-id"
                        className="w-full rounded-md border px-3 py-2 text-sm font-mono"
                        value={agentId}
                        onChange={(e) => setAgentId(e.target.value)}
                        placeholder="my-sales-bot"
                      />
                      <p className="text-xs text-muted-foreground">
                        Custom identifier. If left empty, the server generates a UUID-based ID.
                        Cannot be changed after creation.
                      </p>
                    </div>

                    <Separator />

                    <div className="space-y-1">
                      <label htmlFor="create-agent-pubkey" className="text-sm font-medium">
                        Public Key{" "}
                        <span className="text-muted-foreground font-normal">(optional, Base64 Ed25519)</span>
                      </label>
                      <textarea
                        id="create-agent-pubkey"
                        className="w-full rounded-md border px-3 py-2 text-sm font-mono"
                        value={publicKey}
                        onChange={(e) => setPublicKey(e.target.value)}
                        placeholder="Base64-encoded 32-byte Ed25519 public key"
                        rows={2}
                      />
                      <p className="text-xs text-muted-foreground">
                        {agentType === "own"
                          ? "For production agents: generate the keypair in your infrastructure so the private key never leaves your systems. Provide only the public key here."
                          : "For vendor agents, leave empty — the server will generate the keypair for you to share with the vendor."}
                      </p>
                    </div>
                  </div>
                )}
              </>
            )}

            {error && (
              <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3">
                <p className="text-sm text-destructive">{error}</p>
              </div>
            )}

            <div className="flex gap-3">
              <Button type="submit" disabled={submitting}>
                {submitting ? "Creating..." : "Register Agent"}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => router.push("/dashboard/agents")}
              >
                Cancel
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {keypairResult && (
        <PrivateKeyModal
          agentId={keypairResult.agentId}
          publicKey={keypairResult.publicKey}
          privateKey={keypairResult.privateKey}
          onDismiss={handleModalDismiss}
        />
      )}
    </div>
  );
}
