"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  BackendType,
  McpAuthMethod,
  McpTransport,
  DataClassification,
  ConnectionTestResult,
} from "@/lib/types/admin";

interface AddServiceModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function AddServiceModal({ open, onOpenChange, onCreated }: AddServiceModalProps) {
  const [backendType, setBackendType] = useState<BackendType>("rest");
  const [serviceId, setServiceId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [endpointUrl, setEndpointUrl] = useState("");
  const [transport, setTransport] = useState<McpTransport>("streamable-http");
  const [authMethod, setAuthMethod] = useState<McpAuthMethod>("none");
  const [authHeader, setAuthHeader] = useState("Authorization");
  const [authValue, setAuthValue] = useState("");
  const [dataClassification, setDataClassification] = useState<DataClassification>("internal");
  const [submitting, setSubmitting] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isMcp = backendType === "mcp";

  function resetForm() {
    setServiceId("");
    setDisplayName("");
    setDescription("");
    setEndpointUrl("");
    setTransport("streamable-http");
    setAuthMethod("none");
    setAuthHeader("Authorization");
    setAuthValue("");
    setDataClassification("internal");
    setTestResult(null);
    setError(null);
  }

  async function handleTestConnection() {
    if (!serviceId) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await apiClient<ConnectionTestResult>(
        `admin/services/${encodeURIComponent(serviceId)}/test`,
        { method: "POST" }
      );
      setTestResult(result);
    } catch (err) {
      setTestResult({
        status: "error",
        message: err instanceof Error ? err.message : "Connection test failed",
        latency_ms: null,
      });
    } finally {
      setTesting(false);
    }
  }

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        service_id: serviceId,
        display_name: displayName,
        description: description || undefined,
        backend_type: backendType,
        endpoint_url: endpointUrl,
        data_classification: dataClassification,
      };
      if (isMcp) {
        body.transport = transport;
        body.mcp_auth_method = authMethod;
        if (authMethod !== "none") {
          body.mcp_auth_header = authHeader;
          body.mcp_auth_value = authValue;
        }
      }
      await apiClient("admin/services", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      resetForm();
      onOpenChange(false);
      onCreated();
    } catch (err) {
      if (err instanceof ApiError) {
        const body = err.body as Record<string, string> | undefined;
        setError(body?.detail ?? err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to create service");
      }
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = serviceId && displayName && endpointUrl && !submitting;

  return (
    <Dialog
      open={open}
      onOpenChange={(v: boolean) => {
        if (!v) resetForm();
        onOpenChange(v);
      }}
    >
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Service</DialogTitle>
          <DialogDescription>
            Register a new backend service or MCP server in the catalog.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          {/* Backend Type Selector */}
          <div className="grid gap-2">
            <Label>Backend Type</Label>
            <div className="flex rounded-md border">
              {(["rest", "mcp"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setBackendType(t)}
                  className={`flex-1 px-3 py-2 text-sm font-medium transition-colors ${
                    backendType === t
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {t === "rest" ? "REST + OAuth" : "MCP Server"}
                </button>
              ))}
            </div>
          </div>

          {/* Common Fields */}
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="service-id">Service ID</Label>
              <Input
                id="service-id"
                placeholder="e.g. jira-mcp"
                value={serviceId}
                onChange={(e) => setServiceId(e.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="display-name">Display Name</Label>
              <Input
                id="display-name"
                placeholder="e.g. Jira"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="endpoint">Endpoint URL</Label>
            <Input
              id="endpoint"
              placeholder={isMcp ? "https://jira.example.com/mcp" : "https://api.jira.com/v3"}
              value={endpointUrl}
              onChange={(e) => setEndpointUrl(e.target.value)}
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="description">Description (optional)</Label>
            <Input
              id="description"
              placeholder="Brief description of this service"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="grid gap-1.5">
            <Label>Data Classification</Label>
            <Select
              value={dataClassification}
              onValueChange={(v) => setDataClassification(v as DataClassification)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="internal">Internal</SelectItem>
                <SelectItem value="confidential">Confidential</SelectItem>
                <SelectItem value="restricted">Restricted</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* MCP-specific fields */}
          {isMcp && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-1.5">
                  <Label>Transport</Label>
                  <Select
                    value={transport}
                    onValueChange={(v) => setTransport(v as McpTransport)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="streamable-http">Streamable HTTP</SelectItem>
                      <SelectItem value="sse">SSE</SelectItem>
                      <SelectItem value="rest">REST</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <Label>Auth Method</Label>
                  <Select
                    value={authMethod}
                    onValueChange={(v) => setAuthMethod(v as McpAuthMethod)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None</SelectItem>
                      <SelectItem value="api-key">API Key</SelectItem>
                      <SelectItem value="bearer-token">Bearer Token</SelectItem>
                      <SelectItem value="oauth">OAuth</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {authMethod !== "none" && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="grid gap-1.5">
                    <Label htmlFor="auth-header">Auth Header</Label>
                    <Input
                      id="auth-header"
                      value={authHeader}
                      onChange={(e) => setAuthHeader(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="auth-value">Auth Value</Label>
                    <Input
                      id="auth-value"
                      type="password"
                      placeholder="API key or token"
                      value={authValue}
                      onChange={(e) => setAuthValue(e.target.value)}
                    />
                  </div>
                </div>
              )}
            </>
          )}

          {/* Test Result */}
          {testResult && (
            <div
              className={`rounded-md border p-3 text-sm ${
                testResult.status === "success"
                  ? "border-green-200 bg-green-50 text-green-800"
                  : "border-red-200 bg-red-50 text-red-800"
              }`}
            >
              <p className="font-medium">
                {testResult.status === "success" ? "Connection successful" : "Connection failed"}
              </p>
              <p className="text-xs">{testResult.message}</p>
              {testResult.latency_ms != null && (
                <p className="text-xs">Latency: {testResult.latency_ms}ms</p>
              )}
            </div>
          )}

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="outline"
            onClick={handleTestConnection}
            disabled={!serviceId || !endpointUrl || testing}
          >
            {testing && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
            Test Connection
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            {submitting && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
            Add Service
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
