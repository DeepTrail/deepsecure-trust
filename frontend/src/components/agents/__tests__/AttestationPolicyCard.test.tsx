import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AttestationPolicyCard } from "../AttestationPolicyCard";

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

describe("AttestationPolicyCard", () => {
  beforeEach(() => {
    mockApiClient.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows loading state initially", () => {
    mockApiClient.mockReturnValue(new Promise(() => {}));
    render(<AttestationPolicyCard agentId="agent-1" />);
    expect(screen.getByText(/Loading attestation policies/)).toBeInTheDocument();
  });

  it("shows empty state when no policies match agent", async () => {
    mockApiClient.mockResolvedValue([
      {
        id: "p1",
        platform: "gcp_workload_identity",
        selector: "sa@project.iam.gserviceaccount.com",
        agent_name_to_bootstrap: "other-agent",
      },
    ]);

    render(<AttestationPolicyCard agentId="my-agent" />);

    await waitFor(() => {
      expect(
        screen.getByText(/No attestation policies configured/)
      ).toBeInTheDocument();
    });
  });

  it("renders matching policies with platform badge and selector", async () => {
    mockApiClient.mockResolvedValue([
      {
        id: "p1",
        platform: "gcp_workload_identity",
        selector: "sa@project.iam.gserviceaccount.com",
        agent_name_to_bootstrap: "my-agent",
      },
      {
        id: "p2",
        platform: "aws_iam",
        selector: "arn:aws:iam::123:role/agent",
        agent_name_to_bootstrap: "other-agent",
      },
    ]);

    render(<AttestationPolicyCard agentId="my-agent" />);

    await waitFor(() => {
      expect(screen.getByText("GCP Workload Identity")).toBeInTheDocument();
      expect(
        screen.getByText("sa@project.iam.gserviceaccount.com")
      ).toBeInTheDocument();
    });

    expect(screen.queryByText("AWS IAM")).not.toBeInTheDocument();
  });

  it("shows error state on fetch failure", async () => {
    mockApiClient.mockRejectedValue(new Error("Network error"));

    render(<AttestationPolicyCard agentId="my-agent" />);

    await waitFor(() => {
      expect(
        screen.getByText(/Failed to load attestation policies/)
      ).toBeInTheDocument();
    });
  });

  it("calls the correct API path", async () => {
    mockApiClient.mockResolvedValue([]);

    render(<AttestationPolicyCard agentId="my-agent" />);

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("policies/attestation");
    });
  });
});
