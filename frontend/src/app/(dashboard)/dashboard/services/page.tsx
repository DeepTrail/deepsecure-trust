"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import {
  Link2Off,
  Mail,
  Calendar,
  HardDrive,
  MessageSquare,
  FileText,
  Loader2,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";

import { Plug } from "lucide-react";
import type { ServiceRegistryEntry } from "@/lib/types/admin";

interface ServiceCatalogEntry {
  service_id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  backend_type: "rest" | "mcp";
}

const ICON_MAP: Record<string, React.ReactNode> = {
  notion: <FileText className="h-6 w-6" />,
  slack: <MessageSquare className="h-6 w-6" />,
  gmail: <Mail className="h-6 w-6" />,
  gcalendar: <Calendar className="h-6 w-6" />,
  gdrive: <HardDrive className="h-6 w-6" />,
};

const FALLBACK_CATALOG: ServiceCatalogEntry[] = [
  {
    service_id: "notion",
    name: "Notion",
    description: "Access workspace pages, databases, and documents",
    icon: <FileText className="h-6 w-6" />,
    backend_type: "rest",
  },
  {
    service_id: "slack",
    name: "Slack",
    description: "Search messages and send notifications",
    icon: <MessageSquare className="h-6 w-6" />,
    backend_type: "rest",
  },
  {
    service_id: "gmail",
    name: "Gmail",
    description: "Read and send emails on your behalf",
    icon: <Mail className="h-6 w-6" />,
    backend_type: "rest",
  },
  {
    service_id: "gcalendar",
    name: "Google Calendar",
    description: "View and manage calendar events",
    icon: <Calendar className="h-6 w-6" />,
    backend_type: "rest",
  },
  {
    service_id: "gdrive",
    name: "Google Drive",
    description: "Access files and folders in Drive",
    icon: <HardDrive className="h-6 w-6" />,
    backend_type: "rest",
  },
];

function registryToEntry(r: ServiceRegistryEntry): ServiceCatalogEntry {
  return {
    service_id: r.service_id,
    name: r.display_name,
    description: r.description ?? "",
    icon: ICON_MAP[r.service_id] ?? <Plug className="h-6 w-6" />,
    backend_type: r.backend_type,
  };
}

interface ConnectedServiceInfo {
  connected: boolean;
  scopes_granted: string[];
  connected_at?: string;
}

type ConnectedMap = Record<string, ConnectedServiceInfo>;

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; catalog: ServiceCatalogEntry[]; connected: ConnectedMap };

export default function ServicesPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <ServicesPageInner />
    </Suspense>
  );
}

function ServicesPageInner() {
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [connecting, setConnecting] = useState<string | null>(null);
  const [successService, setSuccessService] = useState<string | null>(null);
  const searchParams = useSearchParams();
  const router = useRouter();

  const fetchConnectedServices = useCallback(async () => {
    try {
      const [permData, registryData] = await Promise.allSettled([
        apiClient<{ services?: Record<string, ConnectedServiceInfo> }>(
          "users/me/available-permissions"
        ),
        apiClient<{ services: ServiceRegistryEntry[] }>("admin/services").catch(
          () => null
        ),
      ]);

      const connected: ConnectedMap = {};
      if (permData.status === "fulfilled" && permData.value?.services) {
        for (const [id, svc] of Object.entries(permData.value.services)) {
          connected[id] = svc;
        }
      }

      let catalog: ServiceCatalogEntry[];
      if (
        registryData.status === "fulfilled" &&
        registryData.value &&
        typeof registryData.value === "object" &&
        "services" in (registryData.value as Record<string, unknown>)
      ) {
        const reg = registryData.value as { services: ServiceRegistryEntry[] };
        const fromDB = reg.services
          .filter((s: ServiceRegistryEntry) => s.status === "active")
          .map(registryToEntry);
        const dbIds = new Set(fromDB.map((e: ServiceCatalogEntry) => e.service_id));
        const fallbackOnly = FALLBACK_CATALOG.filter(
          (f) => !dbIds.has(f.service_id)
        );
        catalog = [...fromDB, ...fallbackOnly];
      } else {
        catalog = FALLBACK_CATALOG;
      }

      setState({ kind: "ready", catalog, connected });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load services (${err.status})`
          : "Failed to load services";
      setState({ kind: "error", message });
    }
  }, []);

  useEffect(() => {
    const status = searchParams.get("status");
    const serviceId = searchParams.get("service_id");

    if (status === "connected" && serviceId) {
      setSuccessService(serviceId);
      router.replace("/dashboard/services", { scroll: false });
      const timer = setTimeout(() => setSuccessService(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [searchParams, router]);

  useEffect(() => {
    fetchConnectedServices();
  }, [fetchConnectedServices]);

  const handleConnect = async (serviceId: string) => {
    setConnecting(serviceId);
    try {
      const redirectUrl = `${window.location.origin}/dashboard/services`;
      const data = await apiClient<{ authorization_url: string; state: string }>(
        `oauth/${serviceId}/authorize?redirect=false&post_connect_redirect=${encodeURIComponent(redirectUrl)}`
      );

      if (data.authorization_url) {
        window.location.href = data.authorization_url;
        return;
      }
    } catch (err) {
      const detail =
        err instanceof ApiError && err.body && typeof err.body === "object" && "detail" in err.body
          ? String((err.body as Record<string, unknown>).detail)
          : "Failed to start OAuth flow";
      alert(`Connection failed: ${detail}`);
    }
    setConnecting(null);
  };

  const handleDisconnect = async (serviceId: string, serviceName: string) => {
    if (!window.confirm(`Disconnect from ${serviceName}? This will revoke access.`)) return;
    try {
      await apiClient(`users/me/services/${serviceId}`, { method: "DELETE" });
      await fetchConnectedServices();
    } catch {
      alert("Failed to disconnect service. Please try again.");
    }
  };

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error")
    return (
      <ErrorCard
        title="Services"
        message={state.message}
        retry={fetchConnectedServices}
      />
    );

  const { catalog, connected } = state;

  const restServices = catalog.filter((s) => s.backend_type === "rest");
  const mcpServices = catalog.filter((s) => s.backend_type === "mcp");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Service Connections</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Connect the services your AI agents can access. DeepSecure handles
          OAuth flows and securely stores credentials.
        </p>
      </div>

      {successService && (
        <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800 dark:border-green-900 dark:bg-green-950 dark:text-green-200">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>
            <strong>
              {catalog.find((s) => s.service_id === successService)?.name ?? successService}
            </strong>{" "}
            connected successfully.
          </span>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {restServices.map((svc) => {
          const info = connected[svc.service_id];
          const isConnected = info?.connected === true;
          const isConnecting = connecting === svc.service_id;

          return (
            <Card key={svc.service_id} className="flex flex-col">
              <CardHeader className="flex flex-row items-start gap-3 space-y-0 pb-2">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border bg-muted/50">
                  {svc.icon}
                </div>
                <div className="flex-1 space-y-1">
                  <CardTitle className="text-base font-semibold">
                    {svc.name}
                  </CardTitle>
                  <Badge
                    variant={isConnected ? "default" : "secondary"}
                    className="text-xs"
                  >
                    {isConnected ? "Connected" : "Not Connected"}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col justify-between space-y-4">
                <p className="text-sm text-muted-foreground">
                  {svc.description}
                </p>

                {isConnected && info?.scopes_granted && info.scopes_granted.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {info.scopes_granted.slice(0, 3).map((s) => (
                      <Badge key={s} variant="outline" className="text-xs">
                        {s}
                      </Badge>
                    ))}
                    {info.scopes_granted.length > 3 && (
                      <Badge variant="outline" className="text-xs">
                        +{info.scopes_granted.length - 3} more
                      </Badge>
                    )}
                  </div>
                )}

                {isConnected ? (
                  <Button
                    variant="destructive"
                    size="sm"
                    className="w-full"
                    onClick={() => handleDisconnect(svc.service_id, svc.name)}
                  >
                    <Link2Off className="mr-2 h-4 w-4" />
                    Disconnect
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    className="w-full"
                    onClick={() => handleConnect(svc.service_id)}
                    disabled={isConnecting}
                  >
                    {isConnecting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Redirecting&hellip;
                      </>
                    ) : (
                      <>
                        <ExternalLink className="mr-2 h-4 w-4" />
                        Connect
                      </>
                    )}
                  </Button>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {mcpServices.length > 0 && (
        <>
          <div>
            <h2 className="text-lg font-semibold">MCP Services</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              These services are managed by your admin via MCP protocol and are
              available to your agents automatically.
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {mcpServices.map((svc) => (
              <Card key={svc.service_id} className="flex flex-col">
                <CardHeader className="flex flex-row items-start gap-3 space-y-0 pb-2">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border bg-muted/50">
                    {svc.icon}
                  </div>
                  <div className="flex-1 space-y-1">
                    <CardTitle className="text-base font-semibold">
                      {svc.name}
                    </CardTitle>
                    <Badge variant="outline" className="text-xs">
                      Available
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col justify-between space-y-4">
                  <p className="text-sm text-muted-foreground">
                    {svc.description}
                  </p>
                  <Badge variant="secondary" className="w-fit text-xs">
                    <Plug className="mr-1 h-3 w-3" />
                    MCP Protocol
                  </Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
