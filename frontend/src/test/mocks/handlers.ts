import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/proxy/agents", () => {
    return HttpResponse.json({ agents: [] });
  }),

  http.get("/api/proxy/audit/events", () => {
    return HttpResponse.json({ events: [], total: 0 });
  }),
];
