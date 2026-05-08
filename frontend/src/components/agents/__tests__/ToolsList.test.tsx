import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ToolsList, type AgentTool } from "../ToolsList";

const TOOLS: AgentTool[] = [
  {
    name: "notion.search_pages",
    backend: "notion",
    permission: "notion:pages:read",
    available: true,
  },
  {
    name: "notion.create_page",
    backend: "notion",
    permission: "notion:pages:create",
    available: false,
    reason: "Not in delegation",
  },
  {
    name: "slack.post_message",
    backend: "slack",
    permission: "slack:messages:write",
    available: true,
  },
];

describe("ToolsList", () => {
  it("renders all tools with their names", () => {
    render(<ToolsList tools={TOOLS} />);

    expect(screen.getByText("notion.search_pages")).toBeInTheDocument();
    expect(screen.getByText("notion.create_page")).toBeInTheDocument();
    expect(screen.getByText("slack.post_message")).toBeInTheDocument();
  });

  it("shows tool count in header", () => {
    render(<ToolsList tools={TOOLS} />);

    expect(screen.getByText(`Tools (${TOOLS.length})`)).toBeInTheDocument();
  });

  it("displays permission for each tool", () => {
    render(<ToolsList tools={TOOLS} />);

    expect(screen.getByText("notion:pages:read")).toBeInTheDocument();
    expect(screen.getByText("notion:pages:create")).toBeInTheDocument();
    expect(screen.getByText("slack:messages:write")).toBeInTheDocument();
  });

  it("displays backend badge for each tool", () => {
    render(<ToolsList tools={TOOLS} />);

    const notionBadges = screen.getAllByText("notion");
    expect(notionBadges).toHaveLength(2);
    expect(screen.getByText("slack")).toBeInTheDocument();
  });

  it("shows green checkmark icon for available tools", () => {
    render(<ToolsList tools={[TOOLS[0]]} />);

    const icon = document.querySelector(".lucide-circle-check");
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveClass("text-green-600");
  });

  it("shows red X icon for unavailable tools", () => {
    render(<ToolsList tools={[TOOLS[1]]} />);

    const icon = document.querySelector(".lucide-circle-x");
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveClass("text-red-500");
  });

  it("shows reason text for unavailable tools", () => {
    render(<ToolsList tools={TOOLS} />);

    expect(screen.getByText("Not in delegation")).toBeInTheDocument();
  });

  it("does not show reason for available tools", () => {
    render(<ToolsList tools={[TOOLS[0]]} />);

    expect(screen.queryByText("Not in delegation")).not.toBeInTheDocument();
  });

  it("renders empty state when no tools provided", () => {
    render(<ToolsList tools={[]} />);

    expect(
      screen.getByText("No tools configured for this agent.")
    ).toBeInTheDocument();
  });

  it("does not render header when tools list is empty", () => {
    render(<ToolsList tools={[]} />);

    expect(screen.queryByText(/^Tools \(/)).not.toBeInTheDocument();
  });
});
