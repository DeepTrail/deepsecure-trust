import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AgentIntegrationSection } from "../AgentIntegrationSection";

Object.assign(navigator, {
  clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
});

const mockApiClient = vi.fn();
vi.mock("@/lib/api/client", () => ({
  apiClient: (...args: unknown[]) => mockApiClient(...args),
  ApiError: class extends Error {
    status: number;
    statusText: string;
    constructor(status: number, statusText: string) {
      super(`API error: ${status} ${statusText}`);
      this.status = status;
      this.statusText = statusText;
    }
  },
}));

describe("AgentIntegrationSection", () => {
  beforeEach(() => {
    vi.mocked(navigator.clipboard.writeText).mockClear();
    mockApiClient.mockReset();
    mockApiClient.mockResolvedValue([]);
  });

  it("renders the title 'Agent Integration'", () => {
    render(<AgentIntegrationSection agentId="test-agent-42" />);
    expect(screen.getByText("Agent Integration")).toBeInTheDocument();
  });

  it("renders all five tab buttons", () => {
    render(<AgentIntegrationSection agentId="test-agent-42" />);

    const buttons = screen.getAllByRole("button");
    const tabLabels = buttons.map((b) => b.textContent?.trim());
    expect(tabLabels).toContain("Environment");
    expect(tabLabels).toContain("GCP");
    expect(tabLabels).toContain("AWS");
    expect(tabLabels).toContain("Kubernetes");
    expect(tabLabels).toContain("Attestation Policy");
  });

  it("shows environment snippet with agentId by default", () => {
    render(<AgentIntegrationSection agentId="my-agent-id" />);

    expect(screen.getByText(/DEEPSECURE_AGENT_ID="my-agent-id"/)).toBeInTheDocument();
    expect(
      screen.getByText(/Set environment variables/)
    ).toBeInTheDocument();
  });

  it("switches to GCP tab when clicked", () => {
    render(<AgentIntegrationSection agentId="my-agent-id" />);

    fireEvent.click(screen.getByText("GCP"));

    expect(
      screen.getByText(/zero-secret authentication/)
    ).toBeInTheDocument();
  });

  it("switches to AWS tab when clicked", () => {
    render(<AgentIntegrationSection agentId="my-agent-id" />);

    fireEvent.click(screen.getByText("AWS"));

    expect(
      screen.getByText(/DEEPSECURE_AGENT_ID=my-agent-id/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/IAM role-based identity/)
    ).toBeInTheDocument();
  });

  it("switches to Kubernetes tab when clicked", () => {
    render(<AgentIntegrationSection agentId="my-agent-id" />);

    fireEvent.click(screen.getByText("Kubernetes"));

    expect(
      screen.getByText(/--from-literal=agent-id="my-agent-id"/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/projected service account token/)
    ).toBeInTheDocument();
  });

  it("switches to Attestation Policy tab and renders AttestationPolicyCard", async () => {
    mockApiClient.mockResolvedValue([]);

    render(<AgentIntegrationSection agentId="my-agent-id" />);

    fireEvent.click(screen.getByText("Attestation Policy"));

    expect(
      screen.getByText(/platform attestation policies/)
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByText(/No attestation policies configured/)
      ).toBeInTheDocument();
    });
  });

  it("copy button calls clipboard API with snippet text", async () => {
    render(<AgentIntegrationSection agentId="copy-test" />);

    const copyBtn = screen.getByRole("button", { name: /copy/i });
    fireEvent.click(copyBtn);

    expect(navigator.clipboard.writeText).toHaveBeenCalledOnce();
    const arg = vi.mocked(navigator.clipboard.writeText).mock.calls[0][0];
    expect(arg).toContain("DEEPSECURE_AGENT_ID");
    expect(arg).toContain("copy-test");
  });

  it("applies custom className to root Card", () => {
    const { container } = render(
      <AgentIntegrationSection agentId="a" className="extra-class" />
    );
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain("extra-class");
  });
});
