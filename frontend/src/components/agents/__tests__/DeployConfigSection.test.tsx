import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DeployConfigSection } from "../DeployConfigSection";

Object.assign(navigator, {
  clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
});

describe("DeployConfigSection", () => {
  beforeEach(() => {
    vi.mocked(navigator.clipboard.writeText).mockClear();
  });

  it("renders the title 'Deploy Configuration'", () => {
    render(<DeployConfigSection agentId="test-agent-42" />);
    expect(screen.getByText("Deploy Configuration")).toBeInTheDocument();
  });

  it("renders all three tab buttons", () => {
    render(<DeployConfigSection agentId="test-agent-42" />);

    const buttons = screen.getAllByRole("button");
    const tabLabels = buttons.map((b) => b.textContent?.trim());
    expect(tabLabels).toContain("Environment");
    expect(tabLabels).toContain("AWS");
    expect(tabLabels).toContain("Kubernetes");
  });

  it("shows environment snippet with agentId by default", () => {
    render(<DeployConfigSection agentId="my-agent-id" />);

    expect(screen.getByText(/DEEPSECURE_AGENT_ID="my-agent-id"/)).toBeInTheDocument();
    expect(
      screen.getByText(/Set environment variables/)
    ).toBeInTheDocument();
  });

  it("switches to AWS tab when clicked", () => {
    render(<DeployConfigSection agentId="my-agent-id" />);

    fireEvent.click(screen.getByText("AWS"));

    expect(
      screen.getByText(/DEEPSECURE_AGENT_ID=my-agent-id/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/IAM role-based identity/)
    ).toBeInTheDocument();
  });

  it("switches to Kubernetes tab when clicked", () => {
    render(<DeployConfigSection agentId="my-agent-id" />);

    fireEvent.click(screen.getByText("Kubernetes"));

    expect(
      screen.getByText(/--from-literal=agent-id="my-agent-id"/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/projected service account token/)
    ).toBeInTheDocument();
  });

  it("copy button calls clipboard API with snippet text", async () => {
    render(<DeployConfigSection agentId="copy-test" />);

    const copyBtn = screen.getByRole("button", { name: /copy/i });
    fireEvent.click(copyBtn);

    expect(navigator.clipboard.writeText).toHaveBeenCalledOnce();
    const arg = vi.mocked(navigator.clipboard.writeText).mock.calls[0][0];
    expect(arg).toContain("DEEPSECURE_AGENT_ID");
    expect(arg).toContain("copy-test");
  });

  it("applies custom className to root Card", () => {
    const { container } = render(
      <DeployConfigSection agentId="a" className="extra-class" />
    );
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain("extra-class");
  });
});
