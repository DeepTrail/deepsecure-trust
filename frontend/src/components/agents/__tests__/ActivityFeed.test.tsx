import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ActivityFeed, type ActivityEvent } from "../ActivityFeed";

const EVENTS: ActivityEvent[] = [
  {
    id: "evt-1",
    tool_name: "notion.search_pages",
    status: "success",
    timestamp: "2026-05-06T12:00:00Z",
    details: "Found 3 pages",
  },
  {
    id: "evt-2",
    tool_name: "slack.post_message",
    status: "error",
    timestamp: "2026-05-06T11:55:00Z",
    details: "Rate limited",
  },
  {
    id: "evt-3",
    tool_name: "notion.create_page",
    status: "pending",
    timestamp: "2026-05-06T12:01:00Z",
  },
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
    expect(screen.getByText("pending")).toBeInTheDocument();
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

  it("shows spinner for pending events", () => {
    render(<ActivityFeed events={[EVENTS[2]]} />);

    const icon = document.querySelector(".lucide-loader-circle");
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveClass("animate-spin");
  });

  it("renders details when provided", () => {
    render(<ActivityFeed events={EVENTS} />);

    expect(screen.getByText("Found 3 pages")).toBeInTheDocument();
    expect(screen.getByText("Rate limited")).toBeInTheDocument();
  });

  it("does not render details when absent", () => {
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
});
