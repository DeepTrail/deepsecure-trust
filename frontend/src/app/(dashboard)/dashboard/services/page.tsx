"use client";

import { useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSkeleton } from "@/components/feedback/page-skeleton";
import { ErrorCard } from "@/components/feedback/error-card";
import { EmptyState } from "@/components/feedback/empty-state";
import { Plug, Link2Off } from "lucide-react";

interface ServicePermission {
  service_id: string;
  service_name: string;
  description?: string;
  connected: boolean;
  scopes?: string[];
}

type PageState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "data"; services: ServicePermission[] };

export default function ServicesPage() {
  const [state, setState] = useState<PageState>({ kind: "loading" });

  const fetchServices = async () => {
    setState({ kind: "loading" });
    try {
      const data = await apiClient<
        ServicePermission[] | { services: Record<string, ServicePermission> }
      >("users/me/available-permissions");
      let services: ServicePermission[];
      if (Array.isArray(data)) {
        services = data;
      } else if (data && typeof data === "object" && "services" in data) {
        services = Object.entries(data.services).map(([id, svc]) => ({
          ...svc,
          service_id: id,
        }));
      } else {
        services = [];
      }
      setState({ kind: "data", services });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Failed to load services (${err.status})`
          : "Failed to load services";
      setState({ kind: "error", message });
    }
  };

  useEffect(() => {
    fetchServices();
  }, []);

  const handleConnect = async (serviceId: string) => {
    try {
      await apiClient("users/me/services/connect", {
        method: "POST",
        body: JSON.stringify({ service_id: serviceId }),
      });
      await fetchServices();
    } catch { /* retry on next fetch */ }
  };

  const handleDisconnect = async (serviceId: string, serviceName: string) => {
    if (!window.confirm(`Disconnect from ${serviceName}? This will revoke access.`)) return;
    try {
      await apiClient(`users/me/services/${serviceId}`, { method: "DELETE" });
      await fetchServices();
    } catch { /* retry on next fetch */ }
  };

  if (state.kind === "loading") return <PageSkeleton />;
  if (state.kind === "error")
    return <ErrorCard title="Services" message={state.message} retry={fetchServices} />;

  const { services } = state;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Service Connections</h1>

      {services.length === 0 ? (
        <EmptyState
          title="No services available"
          description="Service integrations will appear here once configured."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {services.map((svc) => (
            <Card key={svc.service_id}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-medium">
                  <Plug className="h-4 w-4 text-muted-foreground" />
                  {svc.service_name || svc.service_id}
                </CardTitle>
                <Badge variant={svc.connected ? "default" : "secondary"}>
                  {svc.connected ? "Connected" : "Not connected"}
                </Badge>
              </CardHeader>
              <CardContent className="space-y-3">
                {svc.description && (
                  <p className="text-sm text-muted-foreground">{svc.description}</p>
                )}
                {svc.scopes && svc.scopes.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {svc.scopes.map((s) => (
                      <Badge key={s} variant="outline" className="text-xs">{s}</Badge>
                    ))}
                  </div>
                )}
                {svc.connected ? (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDisconnect(svc.service_id, svc.service_name || svc.service_id)}
                  >
                    <Link2Off className="mr-2 h-4 w-4" />
                    Disconnect
                  </Button>
                ) : (
                  <Button size="sm" onClick={() => handleConnect(svc.service_id)}>
                    <Plug className="mr-2 h-4 w-4" />
                    Connect
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
