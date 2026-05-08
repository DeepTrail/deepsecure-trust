"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Bot, Info } from "lucide-react";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { AgentTypeSelector, PrivateKeyModal } from "@/components/agents";
import type { AgentType } from "@/components/agents";

interface AgentCreateResponse {
  agent_id: string;
  name: string;
  public_key: string;
  private_key?: string;
  private_key_warning?: string;
}

export default function AgentCreatePage() {
  const router = useRouter();

  const [agentType, setAgentType] = useState<AgentType>("own");
  const [agentId, setAgentId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [publicKey, setPublicKey] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      if (agentId.trim()) {
        body.agent_id = agentId.trim();
      }
      if (description.trim()) {
        body.description = description.trim();
      }
      if (publicKey.trim()) {
        body.public_key = publicKey.trim();
      }

      const result = await apiClient<AgentCreateResponse>("agents/", {
        method: "POST",
        body: JSON.stringify(body),
      });

      if (result.private_key) {
        setKeypairResult({
          agentId: result.agent_id,
          publicKey: result.public_key,
          privateKey: result.private_key,
        });
      } else {
        router.push("/dashboard/agents");
      }
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setError("An agent with this ID or public key already exists.");
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

            <div className="rounded-md border bg-muted/30 p-3">
              <div className="flex items-start gap-2">
                <Info className="mt-0.5 h-4 w-4 text-muted-foreground shrink-0" />
                <div className="text-xs text-muted-foreground space-y-1">
                  <p>
                    <strong>Agent ID</strong> will be auto-generated by the server (e.g., <code className="text-[11px]">agent-e694edcb-...</code>).
                  </p>
                  <p>
                    <strong>Ed25519 keypair</strong> will be generated server-side. The private key will be shown <strong>once</strong> after creation — save it securely.
                  </p>
                </div>
              </div>
            </div>

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
