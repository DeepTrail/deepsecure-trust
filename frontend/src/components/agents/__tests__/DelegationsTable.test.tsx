import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DelegationsTable } from "../DelegationsTable";
import type { DelegationSummary } from "@/lib/types/admin";

const DELEGATIONS: DelegationSummary[] = [
  {
    id: "del-1",
    delegator: "alice@acme.com",
    permissions: ["notion:pages:read", "notion:pages:search", "slack:messages:list"],
    services: ["notion", "slack"],
    created_at: "2026-06-01T00:00:00Z",
    expires_at: "2026-06-08T00:00:00Z",
    is_expired: false,
  },
  {
    id: "del-2",
    delegator: "bob@acme.com",
    permissions: ["github:repos:read"],
    services: ["github"],
    created_at: "2026-05-01T00:00:00Z",
    expires_at: "2026-05-08T00:00:00Z",
    is_expired: true,
  },
];

describe("DelegationsTable", () => {
  it("renders delegation rows with delegator emails", () => {
    render(<DelegationsTable delegations={DELEGATIONS} />);
    expect(screen.getByText("alice@acme.com")).toBeInTheDocument();
    expect(screen.getByText("bob@acme.com")).toBeInTheDocument();
  });

  it("shows permission count and service badges", () => {
    render(<DelegationsTable delegations={DELEGATIONS} />);
    expect(screen.getByText("3 permissions")).toBeInTheDocument();
    expect(screen.getByText("1 permissions")).toBeInTheDocument();
    expect(screen.getByText("Notion")).toBeInTheDocument();
    expect(screen.getByText("Slack")).toBeInTheDocument();
    expect(screen.getByText("GitHub")).toBeInTheDocument();
  });

  it("shows Active/Expired status badges", () => {
    render(<DelegationsTable delegations={DELEGATIONS} />);
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Expired")).toBeInTheDocument();
  });

  it("expands a row to show grouped permissions", () => {
    render(<DelegationsTable delegations={DELEGATIONS} />);
    fireEvent.click(screen.getByText("alice@acme.com"));
    expect(screen.getByText("notion:pages:read")).toBeInTheDocument();
    expect(screen.getByText("notion:pages:search")).toBeInTheDocument();
    expect(screen.getByText("slack:messages:list")).toBeInTheDocument();
  });

  it("collapses previous row when another is expanded", () => {
    render(<DelegationsTable delegations={DELEGATIONS} />);
    fireEvent.click(screen.getByText("alice@acme.com"));
    expect(screen.getByText("notion:pages:read")).toBeInTheDocument();

    fireEvent.click(screen.getByText("bob@acme.com"));
    expect(screen.queryByText("notion:pages:read")).not.toBeInTheDocument();
    expect(screen.getByText("github:repos:read")).toBeInTheDocument();
  });

  it("shows empty state when no delegations", () => {
    render(<DelegationsTable delegations={[]} />);
    expect(screen.getByText("No active delegations")).toBeInTheDocument();
  });
});
