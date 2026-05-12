"use client";

import { useState, useCallback, useEffect } from "react";
import nacl from "tweetnacl";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  KeyRound,
  ShieldCheck,
  AlertTriangle,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

interface ChallengeResponse {
  challenge: string;
  expires_in: number;
}

interface VerifyResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  session_id: string;
}

interface DecodedJwt {
  header: Record<string, unknown>;
  payload: Record<string, unknown>;
}

interface AgentAuthenticatorProps {
  agentId: string;
  delegationId?: string;
  lifecycleState?: string;
  onAuthenticated?: (jwt: string, sessionId: string) => void;
}

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

function decodeBase64(b64: string): Uint8Array {
  const normalized = b64.replace(/-/g, "+").replace(/_/g, "/");
  const padded =
    normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function decodeJwt(token: string): DecodedJwt | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const header = JSON.parse(atob(parts[0].replace(/-/g, "+").replace(/_/g, "/")));
    const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
    return { header, payload };
  } catch {
    return null;
  }
}

type AuthState =
  | { step: "idle" }
  | { step: "input" }
  | { step: "challenging" }
  | { step: "signing" }
  | { step: "verifying" }
  | { step: "authenticated"; jwt: string; sessionId: string; decoded: DecodedJwt }
  | { step: "session-exists"; sessionId: string; expiresAt: string; delegationId?: string }
  | { step: "error"; message: string };

interface SessionInfo {
  session_id: string;
  agent_id: string;
  delegation_id: string;
  is_active: boolean;
  created_at: string;
  expires_at: string;
  last_activity_at?: string;
}

interface SessionListResponse {
  sessions: SessionInfo[];
  total: number;
}

export function AgentAuthenticator({
  agentId,
  delegationId,
  lifecycleState,
  onAuthenticated,
}: AgentAuthenticatorProps) {
  const [state, setState] = useState<AuthState>({ step: "idle" });
  const [privateKeyInput, setPrivateKeyInput] = useState("");
  const [copied, setCopied] = useState(false);
  const [showRawJwt, setShowRawJwt] = useState(false);

  useEffect(() => {
    if (
      lifecycleState === "authenticated" ||
      lifecycleState === "active"
    ) {
      apiClient<SessionListResponse>(
        `agents/${agentId}/sessions?active_only=true`
      )
        .then((data) => {
          const latest = data.sessions?.[0];
          if (latest) {
            setState({
              step: "session-exists",
              sessionId: latest.session_id,
              expiresAt: latest.expires_at,
              delegationId: latest.delegation_id || undefined,
            });
          }
        })
        .catch(() => {});
    }
  }, [agentId, lifecycleState]);

  const handleAuthenticate = useCallback(async () => {
    const trimmed = privateKeyInput.trim();
    if (!trimmed) {
      setState({ step: "error", message: "Please enter the agent's private key." });
      return;
    }

    let seedBytes: Uint8Array;
    try {
      if (/^[0-9a-fA-F]+$/.test(trimmed) && trimmed.length === 64) {
        seedBytes = new Uint8Array(
          trimmed.match(/.{2}/g)!.map((h) => parseInt(h, 16))
        );
      } else {
        seedBytes = decodeBase64(trimmed);
      }
      if (seedBytes.length !== 32) {
        setState({
          step: "error",
          message: `Invalid key length: expected 32 bytes, got ${seedBytes.length}. Provide the 32-byte Ed25519 private key (seed).`,
        });
        return;
      }
    } catch {
      setState({
        step: "error",
        message: "Could not decode private key. Provide base64 or hex-encoded 32-byte Ed25519 seed.",
      });
      return;
    }

    try {
      // Step 1: Request challenge
      setState({ step: "challenging" });
      const challengeResp = await apiClient<ChallengeResponse>(
        "auth/agent/challenge",
        {
          method: "POST",
          body: JSON.stringify({ agent_id: agentId }),
        }
      );

      // Step 2: Sign challenge with private key
      setState({ step: "signing" });
      const keypair = nacl.sign.keyPair.fromSeed(seedBytes);
      const challengeBytes = new TextEncoder().encode(challengeResp.challenge);
      const signatureBytes = nacl.sign.detached(challengeBytes, keypair.secretKey);
      const signatureB64url = base64UrlEncode(signatureBytes);

      // Step 3: Verify and get Agent JWT
      setState({ step: "verifying" });
      const verifyBody: Record<string, string> = {
        agent_id: agentId,
        challenge: challengeResp.challenge,
        signature: signatureB64url,
      };
      if (delegationId) {
        verifyBody.delegation_id = delegationId;
      }

      const verifyResp = await apiClient<VerifyResponse>(
        "auth/agent/verify",
        {
          method: "POST",
          body: JSON.stringify(verifyBody),
        }
      );

      const decoded = decodeJwt(verifyResp.access_token);
      if (!decoded) {
        setState({ step: "error", message: "Authentication succeeded but JWT could not be decoded." });
        return;
      }

      setState({
        step: "authenticated",
        jwt: verifyResp.access_token,
        sessionId: verifyResp.session_id,
        decoded,
      });

      onAuthenticated?.(verifyResp.access_token, verifyResp.session_id);
    } catch (err) {
      if (err instanceof ApiError) {
        const detail =
          (err.body as { detail?: { message?: string } | string })?.detail;
        const msg =
          typeof detail === "string"
            ? detail
            : typeof detail === "object" && detail?.message
              ? detail.message
              : `Authentication failed (${err.status})`;
        setState({ step: "error", message: msg });
      } else {
        setState({ step: "error", message: "Authentication failed. Check the private key and try again." });
      }
    }
  }, [agentId, delegationId, privateKeyInput, onAuthenticated]);

  const handleCopyJwt = useCallback(() => {
    if (state.step !== "authenticated") return;
    navigator.clipboard.writeText(state.jwt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [state]);

  const isProcessing = ["challenging", "signing", "verifying"].includes(state.step);
  const stepLabel =
    state.step === "challenging"
      ? "Requesting challenge..."
      : state.step === "signing"
        ? "Signing with private key..."
        : state.step === "verifying"
          ? "Verifying signature..."
          : "";

  if (state.step === "session-exists") {
    return (
      <Card className="border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/20">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm font-medium text-green-700 dark:text-green-400">
            <ShieldCheck className="h-4 w-4" />
            Agent Authenticated
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Agent ID</span>
              <code className="font-mono text-xs">{agentId}</code>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Session ID</span>
              <code className="font-mono text-xs">{state.sessionId}</code>
            </div>
            {state.delegationId && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Delegation</span>
                <code className="font-mono text-xs">
                  {state.delegationId.slice(0, 24)}...
                </code>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-muted-foreground">Expires</span>
              <span className="text-xs">
                {new Date(state.expiresAt).toLocaleString()}
              </span>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            This agent has an active session. Re-authenticate to obtain a fresh JWT with current permissions.
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setState({ step: "input" });
              setPrivateKeyInput("");
            }}
          >
            Re-authenticate
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (state.step === "authenticated") {
    const { decoded, sessionId, jwt } = state;
    const permissions = (decoded.payload.delegated_permissions as string[]) || [];
    const permsByService: Record<string, string[]> = {};
    for (const p of permissions) {
      const [svc, ...rest] = p.split(":");
      if (!permsByService[svc]) permsByService[svc] = [];
      permsByService[svc].push(rest.join(":"));
    }

    return (
      <Card className="border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/20">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm font-medium text-green-700 dark:text-green-400">
            <ShieldCheck className="h-4 w-4" />
            Agent Authenticated
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Agent ID</span>
              <code className="font-mono text-xs">{decoded.payload.sub as string}</code>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Session ID</span>
              <code className="font-mono text-xs">{sessionId}</code>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Owner</span>
              <code className="font-mono text-xs">
                {decoded.payload.owner === "no-delegation"
                  ? "No delegation — create one to assign an owner"
                  : (decoded.payload.owner as string)}
              </code>
            </div>
            {typeof decoded.payload.delegation_id === "string" && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Delegation</span>
                <code className="font-mono text-xs">
                  {decoded.payload.delegation_id.slice(0, 20)}...
                </code>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-muted-foreground">Expires</span>
              <span className="text-xs">
                {decoded.payload.exp
                  ? new Date((decoded.payload.exp as number) * 1000).toLocaleString()
                  : "N/A"}
              </span>
            </div>
          </div>

          {permissions.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">
                Delegated Permissions ({permissions.length})
              </p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(permsByService).map(([svc, perms]) => (
                  <Badge key={svc} variant="outline" className="text-xs">
                    {svc}: {perms.join(", ")}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-1">
            <button
              type="button"
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              onClick={() => setShowRawJwt(!showRawJwt)}
            >
              {showRawJwt ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              Raw Agent Session JWT
            </button>
            {showRawJwt && (
              <div className="relative">
                <pre className="overflow-x-auto rounded-md bg-muted p-3 text-[11px] font-mono leading-relaxed">
                  {jwt}
                </pre>
                <Button
                  variant="ghost"
                  size="sm"
                  className="absolute right-1 top-1 h-6 w-6 p-0"
                  onClick={handleCopyJwt}
                >
                  {copied ? (
                    <Check className="h-3 w-3 text-green-600" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                </Button>
              </div>
            )}
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setState({ step: "input" });
              setPrivateKeyInput("");
            }}
          >
            Re-authenticate
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <KeyRound className="h-4 w-4 text-muted-foreground" />
          Agent Authentication
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {state.step === "idle" && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Authenticate this agent using Ed25519 challenge-response to obtain an Agent Session JWT
              with delegated permissions.
            </p>
            <Button size="sm" onClick={() => setState({ step: "input" })}>
              <KeyRound className="mr-2 h-4 w-4" />
              Authenticate Agent
            </Button>
          </div>
        )}

        {(state.step === "input" || state.step === "error" || isProcessing) && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Paste the Ed25519 private key that was generated during agent registration.
              This key is used locally to sign a challenge -- it is never sent to the server.
            </p>
            <div className="space-y-1">
              <label htmlFor="agent-private-key" className="text-xs font-medium">
                Private Key (Base64 or Hex)
              </label>
              <textarea
                id="agent-private-key"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono"
                rows={2}
                placeholder="Paste base64 or hex-encoded 32-byte Ed25519 private key (seed)"
                value={privateKeyInput}
                onChange={(e) => setPrivateKeyInput(e.target.value)}
                disabled={isProcessing}
              />
              <p className="text-[11px] text-muted-foreground">
                The private key stays in your browser and is used only to sign the challenge nonce.
              </p>
            </div>

            {state.step === "error" && (
              <div className="flex items-start gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                <p className="text-sm text-destructive">{state.message}</p>
              </div>
            )}

            {isProcessing && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                {stepLabel}
              </div>
            )}

            <div className="flex gap-2">
              <Button
                size="sm"
                disabled={isProcessing || !privateKeyInput.trim()}
                onClick={handleAuthenticate}
              >
                {isProcessing ? "Authenticating..." : "Sign & Verify"}
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={isProcessing}
                onClick={() => {
                  setState({ step: "idle" });
                  setPrivateKeyInput("");
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
