import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CrossUserMappingTable } from "../CrossUserMappingTable";
import type { DelegatorSummary } from "@/lib/types/admin";

const DELEGATORS: DelegatorSummary[] = [
  {
    email: "alice@acme.com",
    connected_services: [
      { service_id: "notion", display_name: "Notion", status: "connected", scopes_granted: ["read_content", "search"] },
      { service_id: "slack", display_name: "Slack", status: "token_expired", scopes_granted: ["channels:list"] },
    ],
    active_delegation: null,
    delegation_count: 2,
  },
  {
    email: "bob@acme.com",
    connected_services: [
      { service_id: "github", display_name: "GitHub", status: "connected", scopes_granted: ["repo"] },
    ],
    active_delegation: null,
    delegation_count: 1,
  },
];

describe("CrossUserMappingTable", () => {
  it("renders all delegator rows", () => {
    render(<CrossUserMappingTable delegators={DELEGATORS} />);
    expect(screen.getByText("alice@acme.com")).toBeInTheDocument();
    expect(screen.getByText("bob@acme.com")).toBeInTheDocument();
  });

  it("shows service badges for each delegator", () => {
    render(<CrossUserMappingTable delegators={DELEGATORS} />);
    expect(screen.getByText("Notion")).toBeInTheDocument();
    expect(screen.getByText("Slack")).toBeInTheDocument();
    expect(screen.getByText("GitHub")).toBeInTheDocument();
  });

  it("shows delegation count", () => {
    render(<CrossUserMappingTable delegators={DELEGATORS} />);
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("expands a row on click and shows service detail", () => {
    render(<CrossUserMappingTable delegators={DELEGATORS} />);
    fireEvent.click(screen.getByText("alice@acme.com"));
    expect(screen.getByText("read_content")).toBeInTheDocument();
    expect(screen.getByText("search")).toBeInTheDocument();
  });

  it("collapses previous row when another is expanded", () => {
    render(<CrossUserMappingTable delegators={DELEGATORS} />);
    fireEvent.click(screen.getByText("alice@acme.com"));
    expect(screen.getByText("read_content")).toBeInTheDocument();

    fireEvent.click(screen.getByText("bob@acme.com"));
    expect(screen.queryByText("read_content")).not.toBeInTheDocument();
    expect(screen.getByText("repo")).toBeInTheDocument();
  });

  it("shows empty state when no delegators", () => {
    render(<CrossUserMappingTable delegators={[]} />);
    expect(
      screen.getByText(/No delegating users/)
    ).toBeInTheDocument();
  });

  it("shows service status colors via badge classes", () => {
    render(<CrossUserMappingTable delegators={DELEGATORS} />);
    const notionBadge = screen.getByText("Notion");
    expect(notionBadge.className).toContain("text-green-600");
    const slackBadge = screen.getByText("Slack");
    expect(slackBadge.className).toContain("text-amber-600");
  });
});
