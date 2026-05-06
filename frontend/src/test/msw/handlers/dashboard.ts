import { http, HttpResponse } from "msw";

const mockAgents = [
  { id: "agent-1", agent_id: "agent-alpha", name: "Alpha Agent", status: "active", public_key: "abc123" },
  { id: "agent-2", agent_id: "agent-beta", name: "Beta Agent", status: "registered", public_key: null },
];

const mockPolicies = [
  { id: "policy-1", name: "Default Policy", description: "Allow read access", permissions: ["read"], agent_ids: ["agent-alpha"] },
  { id: "policy-2", name: "Admin Policy", description: "Full access", permissions: ["read", "write"], agent_ids: [] },
];

const mockServices = [
  { name: "notion", display_name: "Notion", connected: true, permissions: [{ scope: "pages:read" }] },
  { name: "slack", display_name: "Slack", connected: false, permissions: [{ scope: "messages:read" }] },
];

const mockAuditEvents = [
  {
    id: "evt-1",
    event_type: "mcp_tool_call",
    timestamp: "2026-01-15T09:00:00Z",
    agent_id: "agent-alpha",
    user_id: "user-1",
    token_layer: "agent",
    details: { tool: "notion.search" },
    attribution_chain: [
      { actor: "user-1", action: "delegate", layer: "user" },
      { actor: "agent-alpha", action: "tool_call", layer: "agent" },
    ],
  },
  {
    id: "evt-2",
    event_type: "agent_auth",
    timestamp: "2026-01-15T10:00:00Z",
    agent_id: "agent-beta",
    token_layer: "delegation",
    details: {},
    attribution_chain: [],
  },
];

const mockSecrets = [
  { id: "secret-1", name: "NOTION_TOKEN", service: "notion", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-10T00:00:00Z" },
  { id: "secret-2", name: "SLACK_TOKEN", service: "slack", created_at: "2026-01-02T00:00:00Z" },
];

const mockTasks = [
  { id: "task-1", name: "Sync Notion", agent_id: "agent-alpha", status: "active", description: "Sync pages daily" },
  { id: "task-2", name: "Post Summary", agent_id: "agent-beta", status: "pending", description: "Post weekly summary" },
];

export const dashboardHandlers = [
  http.get("/api/proxy/agents", () => HttpResponse.json(mockAgents)),
  http.post("/api/proxy/agents/", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: "new-agent", ...body }, { status: 201 });
  }),
  http.delete("/api/proxy/agents/:id", () => HttpResponse.json({ ok: true })),

  http.get("/api/proxy/policies", () => HttpResponse.json(mockPolicies)),
  http.post("/api/proxy/policies/", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: "new-policy", ...body }, { status: 201 });
  }),
  http.put("/api/proxy/policies/:id", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(body);
  }),
  http.delete("/api/proxy/policies/:id", () => HttpResponse.json({ ok: true })),

  http.get("/api/proxy/services/available", () => HttpResponse.json(mockServices)),
  http.post("/api/proxy/oauth/:service/connect", () => HttpResponse.json({ redirect_url: "/oauth/callback" })),
  http.post("/api/proxy/oauth/:service/disconnect", () => HttpResponse.json({ ok: true })),

  http.get("/api/proxy/audit/events", ({ request }) => {
    const url = new URL(request.url);
    const eventType = url.searchParams.get("event_type");
    let events = mockAuditEvents;
    if (eventType) events = events.filter((e) => e.event_type === eventType);
    return HttpResponse.json(events);
  }),

  http.get("/api/proxy/vault/secrets", () => HttpResponse.json(mockSecrets)),
  http.post("/api/proxy/vault/secrets", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: "new-secret", ...body }, { status: 201 });
  }),
  http.delete("/api/proxy/vault/secrets/:id", () => HttpResponse.json({ ok: true })),

  http.get("/api/proxy/tasks", () => HttpResponse.json(mockTasks)),
  http.post("/api/proxy/tasks/", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: "new-task", ...body }, { status: 201 });
  }),
  http.post("/api/proxy/tasks/:id/activate", () => HttpResponse.json({ status: "active" })),
  http.post("/api/proxy/tasks/:id/complete", () => HttpResponse.json({ status: "completed" })),
  http.post("/api/proxy/tasks/:id/revoke", () => HttpResponse.json({ status: "revoked" })),
];

export const dashboardErrorHandlers = [
  http.get("/api/proxy/agents", () => HttpResponse.json({ detail: "Internal error" }, { status: 500 })),
  http.get("/api/proxy/policies", () => HttpResponse.json({ detail: "Internal error" }, { status: 500 })),
  http.get("/api/proxy/services/available", () => HttpResponse.json({ detail: "Internal error" }, { status: 500 })),
  http.get("/api/proxy/audit/events", () => HttpResponse.json({ detail: "Internal error" }, { status: 500 })),
  http.get("/api/proxy/vault/secrets", () => HttpResponse.json({ detail: "Internal error" }, { status: 500 })),
  http.get("/api/proxy/tasks", () => HttpResponse.json({ detail: "Internal error" }, { status: 500 })),
];

export const dashboardEmptyHandlers = [
  http.get("/api/proxy/agents", () => HttpResponse.json([])),
  http.get("/api/proxy/policies", () => HttpResponse.json([])),
  http.get("/api/proxy/services/available", () => HttpResponse.json([])),
  http.get("/api/proxy/audit/events", () => HttpResponse.json([])),
  http.get("/api/proxy/vault/secrets", () => HttpResponse.json([])),
  http.get("/api/proxy/tasks", () => HttpResponse.json([])),
];
