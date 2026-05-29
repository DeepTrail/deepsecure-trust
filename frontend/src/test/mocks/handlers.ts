import { http, HttpResponse } from "msw";
import type { AuditEvent, AuditSummary } from "@/lib/types/audit";

const mockAuditEvents: AuditEvent[] = [
  {
    id: "evt-001",
    timestamp: "2026-05-26T16:00:00Z",
    event_type: "mcp_tool_call",
    agent_id: "agent-sdr-001",
    on_behalf_of: "sarah@acme.com",
    organization_id: null,
    tool: "notion.search_pages",
    success: true,
    arguments: { query: "meeting notes" },
    result_summary: "Found 5 results",
    reason: null,
    attempted_tool: null,
    required_permission: null,
    duration_ms: 473,
    session_id: "sess-001",
    agent_session_id: "asess-001",
    mcp_session_id: "mcpsess-001",
    delegation_id: "del-001",
    extra_data: null,
  },
  {
    id: "evt-002",
    timestamp: "2026-05-26T15:55:00Z",
    event_type: "permission_denied",
    agent_id: "agent-sdr-001",
    on_behalf_of: "sarah@acme.com",
    organization_id: null,
    tool: null,
    success: false,
    arguments: null,
    result_summary: null,
    reason: "Permission not delegated",
    attempted_tool: "slack.post_message",
    required_permission: "slack:messages:send",
    duration_ms: null,
    session_id: "sess-001",
    agent_session_id: "asess-001",
    mcp_session_id: "mcpsess-001",
    delegation_id: "del-001",
    extra_data: null,
  },
  {
    id: "evt-003",
    timestamp: "2026-05-26T15:50:00Z",
    event_type: "mcp_tool_call",
    agent_id: "agent-researcher-002",
    on_behalf_of: "sarah@acme.com",
    organization_id: null,
    tool: "notion.read_page",
    success: true,
    arguments: { page_id: "abc-123" },
    result_summary: "Page content retrieved",
    reason: null,
    attempted_tool: null,
    required_permission: null,
    duration_ms: 231,
    session_id: "sess-002",
    agent_session_id: "asess-002",
    mcp_session_id: "mcpsess-002",
    delegation_id: "del-002",
    extra_data: null,
  },
];

const mockSummary: AuditSummary = {
  total_events: 150,
  by_event_type: { mcp_tool_call: 145, permission_denied: 5 },
  by_tool: {
    "notion.search_pages": 50,
    "notion.read_page": 30,
    "slack.post_message": 20,
    "slack.list_channels": 15,
    "gmail.send_email": 10,
    "gmail.read_inbox": 8,
  },
  by_agent: { "agent-sdr-001": 100, "agent-researcher-002": 50 },
  time_range: {
    start: "2026-05-20T00:00:00Z",
    end: "2026-05-26T23:59:59Z",
  },
};

export const handlers = [
  http.get("/api/proxy/agents/", () => {
    return HttpResponse.json({
      agents: [
        { agent_id: "agent-sdr-001", name: "SDR Agent" },
        { agent_id: "agent-researcher-002", name: "Research Agent" },
      ],
    });
  }),

  http.get("/api/proxy/agents", () => {
    return HttpResponse.json({
      agents: [
        { agent_id: "agent-sdr-001", name: "SDR Agent" },
        { agent_id: "agent-researcher-002", name: "Research Agent" },
      ],
    });
  }),

  http.get("/api/proxy/audit/events", ({ request }) => {
    const url = new URL(request.url);
    const eventType = url.searchParams.get("event_type");
    let events = mockAuditEvents;
    if (eventType) {
      events = events.filter((e) => e.event_type === eventType);
    }
    return HttpResponse.json({
      events,
      total: events.length,
      limit: 100,
      offset: 0,
    });
  }),

  http.get("/api/proxy/audit/summary", () => {
    return HttpResponse.json(mockSummary);
  }),

  http.get("/api/proxy/auth/delegations", () => {
    return HttpResponse.json([
      {
        id: "del-001",
        agent_id: "agent-sdr-001",
        permissions: [
          "notion:pages:search",
          "notion:pages:read",
          "slack:messages:send",
        ],
      },
    ]);
  }),
];
