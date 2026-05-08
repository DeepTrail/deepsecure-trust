"use client";

import { useState, useCallback } from "react";
import { AlertTriangle, Check, Copy, Download, Key } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface PrivateKeyModalProps {
  agentId: string;
  publicKey: string;
  privateKey: string;
  onDismiss: () => void;
}

export function PrivateKeyModal({ agentId, publicKey, privateKey, onDismiss }: PrivateKeyModalProps) {
  const [confirmed, setConfirmed] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(privateKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = privateKey;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [privateKey]);

  const handleDownload = useCallback(() => {
    const content = [
      `# DeepSecure Agent Private Key`,
      `# Agent ID: ${agentId}`,
      `# WARNING: Keep this file secure. Do not commit to version control.`,
      ``,
      `AGENT_ID=${agentId}`,
      `PUBLIC_KEY=${publicKey}`,
      `PRIVATE_KEY=${privateKey}`,
    ].join("\n");

    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${agentId}-keypair.env`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [agentId, publicKey, privateKey]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true" aria-label="Private key">
      <Card className="w-full max-w-lg mx-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Key className="h-5 w-5 text-primary" />
            Agent Keypair Generated
          </CardTitle>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="rounded-md border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
              <p className="text-sm text-amber-800 dark:text-amber-200">
                This private key will not be shown again.
                {" "}Store it securely before closing this dialog.
              </p>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Agent ID</label>
            <p className="font-mono text-sm">{agentId}</p>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Public Key</label>
            <p className="break-all rounded-md bg-muted p-2 font-mono text-xs" title={publicKey}>
              {publicKey.length > 24
                ? `${publicKey.slice(0, 12)}...${publicKey.slice(-12)}`
                : publicKey}
            </p>
          </div>

          <Separator />

          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">Private Key</label>
            <div className="relative">
              <pre className="break-all rounded-md bg-muted p-2 pr-20 font-mono text-xs whitespace-pre-wrap" data-testid="private-key-display">
                {privateKey}
              </pre>
              <div className="absolute right-2 top-2 flex gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={handleCopy}
                  aria-label="Copy private key"
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-green-600" /> : <Copy className="h-3.5 w-3.5" />}
                </Button>
              </div>
            </div>
            <div className="flex gap-2">
              <Button type="button" variant="outline" size="sm" onClick={handleCopy}>
                <Copy className="mr-2 h-3.5 w-3.5" />
                {copied ? "Copied!" : "Copy to clipboard"}
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={handleDownload}>
                <Download className="mr-2 h-3.5 w-3.5" />
                Download as file
              </Button>
            </div>
          </div>
        </CardContent>

        <CardFooter className="flex flex-col items-start gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300"
              data-testid="confirm-checkbox"
            />
            <span className="text-sm">I have saved my private key</span>
          </label>
          <Button
            type="button"
            onClick={onDismiss}
            disabled={!confirmed}
            className="w-full"
          >
            Close
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
