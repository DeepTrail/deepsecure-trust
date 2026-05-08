import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DelegationBuilder } from "../DelegationBuilder";
import { apiClient, ApiError } from "@/lib/api/client";
import type { Permission } from "../PermissionChecklist";

vi.mock("@/lib/api/client", () => ({
  apiClient: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    statusText: string;
    body?: unknown;
    constructor(status: number, statusText: string, body?: unknown) {
      super(`API error: ${status} ${statusText}`);
      this.name = "ApiError";
      this.status = status;
      this.statusText = statusText;
      this.body = body;
    }
  },
}));

const mockApiClient = vi.mocked(apiClient);

const AGENTS = [
  { agent_id: "agent-1", name: "Alpha Agent" },
  { agent_id: "agent-2", name: "Beta Agent" },
];

const PERMISSIONS: Permission[] = [
  { id: "p1", service: "notion", scope: "pages", action: "read", locked: false },
  { id: "p2", service: "notion", scope: "pages", action: "write", locked: "role", lockReason: "Admin only" },
  { id: "p3", service: "github", scope: "repos", action: "read", locked: false },
  { id: "p4", service: "github", scope: "repos", action: "push", locked: "oauth", lockReason: "Needs scope" },
];

describe("DelegationBuilder", () => {
  beforeEach(() => {
    mockApiClient.mockReset();
  });

  it("renders agent selection dropdown", () => {
    render(<DelegationBuilder agents={AGENTS} permissions={PERMISSIONS} />);

    const select = screen.getByLabelText("Select agent");
    expect(select).toBeInTheDocument();
    expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    expect(screen.getByText("Beta Agent")).toBeInTheDocument();
  });

  it("renders permission checklist", () => {
    render(<DelegationBuilder agents={AGENTS} permissions={PERMISSIONS} />);

    expect(screen.getByText("pages:read")).toBeInTheDocument();
    expect(screen.getByText("repos:read")).toBeInTheDocument();
  });

  it("renders TTL options", () => {
    render(<DelegationBuilder agents={AGENTS} permissions={PERMISSIONS} />);

    expect(screen.getByText("15 minutes")).toBeInTheDocument();
    expect(screen.getByText("1 hour")).toBeInTheDocument();
    expect(screen.getByText("8 hours")).toBeInTheDocument();
    expect(screen.getByText("24 hours")).toBeInTheDocument();
    expect(screen.getByText("7 days")).toBeInTheDocument();
  });

  it("disables submit button when no agent selected", () => {
    render(<DelegationBuilder agents={AGENTS} permissions={PERMISSIONS} />);

    const submit = screen.getByRole("button", { name: /create delegation/i });
    expect(submit).toBeDisabled();
  });

  it("disables submit button when no permissions selected", () => {
    render(<DelegationBuilder agents={AGENTS} permissions={PERMISSIONS} />);

    fireEvent.change(screen.getByLabelText("Select agent"), {
      target: { value: "agent-1" },
    });

    const submit = screen.getByRole("button", { name: /create delegation/i });
    expect(submit).toBeDisabled();
  });

  it("enables submit when agent and permissions are selected", () => {
    render(<DelegationBuilder agents={AGENTS} permissions={PERMISSIONS} />);

    fireEvent.change(screen.getByLabelText("Select agent"), {
      target: { value: "agent-1" },
    });

    const checkbox = screen.getAllByRole("checkbox").find(
      (cb) => cb.getAttribute("aria-label") === "pages:read",
    );
    fireEvent.click(checkbox!);

    const submit = screen.getByRole("button", { name: /create delegation/i });
    expect(submit).not.toBeDisabled();
  });

  it("submits delegation with correct payload", async () => {
    mockApiClient.mockResolvedValueOnce({ delegation_id: "del-123" });

    render(<DelegationBuilder agents={AGENTS} permissions={PERMISSIONS} />);

    fireEvent.change(screen.getByLabelText("Select agent"), {
      target: { value: "agent-1" },
    });

    const pagesRead = screen.getAllByRole("checkbox").find(
      (cb) => cb.getAttribute("aria-label") === "pages:read",
    );
    fireEvent.click(pagesRead!);

    const reposRead = screen.getAllByRole("checkbox").find(
      (cb) => cb.getAttribute("aria-label") === "repos:read",
    );
    fireEvent.click(reposRead!);

    fireEvent.click(screen.getByText("24 hours"));
    fireEvent.click(screen.getByRole("button", { name: /create delegation/i }));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("auth/delegate", {
        method: "POST",
        body: JSON.stringify({
          agent_id: "agent-1",
          permissions: ["notion:pages:read", "github:repos:read"],
          ttl: 86400,
        }),
      });
    });
  });

  it("shows success state with delegation_id after submission", async () => {
    mockApiClient.mockResolvedValueOnce({ delegation_id: "del-abc-456" });

    render(<DelegationBuilder agents={AGENTS} permissions={PERMISSIONS} />);

    fireEvent.change(screen.getByLabelText("Select agent"), {
      target: { value: "agent-1" },
    });

    const checkbox = screen.getAllByRole("checkbox").find(
      (cb) => cb.getAttribute("aria-label") === "pages:read",
    );
    fireEvent.click(checkbox!);
    fireEvent.click(screen.getByRole("button", { name: /create delegation/i }));

    await waitFor(() => {
      expect(screen.getByText("Delegation Created")).toBeInTheDocument();
    });
    expect(screen.getByTestId("delegation-id")).toHaveTextContent("del-abc-456");
  });

  it("shows error message on API failure", async () => {
    mockApiClient.mockRejectedValueOnce(
      new ApiError(403, "Forbidden"),
    );

    render(<DelegationBuilder agents={AGENTS} permissions={PERMISSIONS} />);

    fireEvent.change(screen.getByLabelText("Select agent"), {
      target: { value: "agent-1" },
    });

    const checkbox = screen.getAllByRole("checkbox").find(
      (cb) => cb.getAttribute("aria-label") === "pages:read",
    );
    fireEvent.click(checkbox!);
    fireEvent.click(screen.getByRole("button", { name: /create delegation/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Failed to create delegation (403)"),
      ).toBeInTheDocument();
    });
  });

  it("shows generic error for non-ApiError failures", async () => {
    mockApiClient.mockRejectedValueOnce(new Error("Network error"));

    render(<DelegationBuilder agents={AGENTS} permissions={PERMISSIONS} />);

    fireEvent.change(screen.getByLabelText("Select agent"), {
      target: { value: "agent-1" },
    });

    const checkbox = screen.getAllByRole("checkbox").find(
      (cb) => cb.getAttribute("aria-label") === "pages:read",
    );
    fireEvent.click(checkbox!);
    fireEvent.click(screen.getByRole("button", { name: /create delegation/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Failed to create delegation. Please try again."),
      ).toBeInTheDocument();
    });
  });

  it("resets form when Create Another is clicked", async () => {
    mockApiClient.mockResolvedValueOnce({ delegation_id: "del-xyz" });

    render(<DelegationBuilder agents={AGENTS} permissions={PERMISSIONS} />);

    fireEvent.change(screen.getByLabelText("Select agent"), {
      target: { value: "agent-1" },
    });

    const checkbox = screen.getAllByRole("checkbox").find(
      (cb) => cb.getAttribute("aria-label") === "pages:read",
    );
    fireEvent.click(checkbox!);
    fireEvent.click(screen.getByRole("button", { name: /create delegation/i }));

    await waitFor(() => {
      expect(screen.getByText("Delegation Created")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /create another/i }));

    expect(screen.getByLabelText("Select agent")).toBeInTheDocument();
    expect((screen.getByLabelText("Select agent") as HTMLSelectElement).value).toBe("");
  });

  it("shows selected permission count badge", () => {
    render(<DelegationBuilder agents={AGENTS} permissions={PERMISSIONS} />);

    const checkbox = screen.getAllByRole("checkbox").find(
      (cb) => cb.getAttribute("aria-label") === "pages:read",
    );
    fireEvent.click(checkbox!);

    expect(screen.getByText("1 selected")).toBeInTheDocument();
  });

  it("updates summary text when agent is selected", () => {
    render(<DelegationBuilder agents={AGENTS} permissions={PERMISSIONS} />);

    fireEvent.change(screen.getByLabelText("Select agent"), {
      target: { value: "agent-1" },
    });

    expect(
      screen.getByText("Delegating 0 permission(s) to agent-1"),
    ).toBeInTheDocument();
  });
});
