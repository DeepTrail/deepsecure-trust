import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ActivityFeed } from "../ActivityFeed";
import type { AuditEvent } from "@/lib/types/audit";

function makeEvent(overrides: Partial<AuditEvent> = {}): AuditEvent {
  return {
    id: "evt-1",
    timestamp: "2026-05-06T12:00:00Z",
    event_type: "mcp_tool_call",
    agent_id: "agent-001",
    on_behalf_of: "sarah@acme.com",
    organization_id: null,
    tool: "notion.search_pages",
    success: true,
    arguments: null,
    result_summary: null,
    reason: null,
    attempted_tool: null,
    required_permission: null,
    duration_ms: null,
    session_id: null,
    agent_session_id: null,
    mcp_session_id: null,
    delegation_id: null,
    extra_data: null,
    ...overrides,
  };
}

const EVENTS: AuditEvent[] = [
  makeEvent({
    id: "evt-1",
    tool: "notion.search_pages",
    success: true,
    result_summary: "Found 3 pages",
  }),
  makeEvent({
    id: "evt-2",
    tool: "slack.post_message",
    success: false,
    result_summary: "Rate limited",
    timestamp: "2026-05-06T11:55:00Z",
  }),
  makeEvent({
    id: "evt-3",
    event_type: "permission_denied",
    tool: null,
    success: false,
    attempted_tool: "notion.create_page",
    required_permission: "notion:pages:create",
    timestamp: "2026-05-06T12:01:00Z",
  }),
];

describe("ActivityFeed", () => {
  it("renders all events with tool names", () => {
    render(<ActivityFeed events={EVENTS} />);

    expect(screen.getByText("notion.search_pages")).toBeInTheDocument();
    expect(screen.getByText("slack.post_message")).toBeInTheDocument();
    expect(screen.getByText("notion.create_page")).toBeInTheDocument();
  });

  it("shows event count in header", () => {
    render(<ActivityFeed events={EVENTS} />);

    expect(
      screen.getByText(`Recent Activity (${EVENTS.length})`)
    ).toBeInTheDocument();
  });

  it("displays status badges", () => {
    render(<ActivityFeed events={EVENTS} />);

    expect(screen.getByText("success")).toBeInTheDocument();
    expect(screen.getByText("error")).toBeInTheDocument();
    expect(screen.getByText("denied")).toBeInTheDocument();
  });

  it("shows green checkmark for success events", () => {
    render(<ActivityFeed events={[EVENTS[0]]} />);

    const icon = document.querySelector(".lucide-circle-check");
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveClass("text-green-600");
  });

  it("shows red X for error events", () => {
    render(<ActivityFeed events={[EVENTS[1]]} />);

    const icon = document.querySelector(".lucide-circle-x");
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveClass("text-red-500");
  });

  it("shows red X for denied events", () => {
    render(<ActivityFeed events={[EVENTS[2]]} />);

    const icon = document.querySelector(".lucide-circle-x");
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveClass("text-red-500");
  });

  it("renders result_summary when provided", () => {
    render(<ActivityFeed events={EVENTS} />);

    expect(screen.getByText("Found 3 pages")).toBeInTheDocument();
    expect(screen.getByText("Rate limited")).toBeInTheDocument();
  });

  it("does not render result_summary when absent", () => {
    render(<ActivityFeed events={[EVENTS[2]]} />);

    expect(screen.queryByText("Found 3 pages")).not.toBeInTheDocument();
  });

  it("renders empty state when no events provided", () => {
    render(<ActivityFeed events={[]} />);

    expect(
      screen.getByText("No recent activity for this agent.")
    ).toBeInTheDocument();
  });

  it("does not render header when events list is empty", () => {
    render(<ActivityFeed events={[]} />);

    expect(screen.queryByText(/^Recent Activity \(/)).not.toBeInTheDocument();
  });

  it("formats timestamps in a readable format", () => {
    render(<ActivityFeed events={[EVENTS[0]]} />);

    const timeElements = document.querySelectorAll(".lucide-clock");
    expect(timeElements.length).toBeGreaterThan(0);
  });

  it("uses attempted_tool for denied events", () => {
    render(<ActivityFeed events={[EVENTS[2]]} />);
    expect(screen.getByText("notion.create_page")).toBeInTheDocument();
  });
});
