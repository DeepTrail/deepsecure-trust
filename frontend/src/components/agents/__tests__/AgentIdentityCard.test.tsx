import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AgentIdentityCard } from "../AgentIdentityCard";

beforeEach(() => {
  Object.assign(navigator, {
    clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

describe("AgentIdentityCard — key-based (no platform)", () => {
  it("renders DEEPSECURE_AGENT_ID env var", () => {
    render(<AgentIdentityCard agentId="test-agent-001" />);

    expect(screen.getByText("DEEPSECURE_AGENT_ID")).toBeInTheDocument();
    expect(screen.getByText("test-agent-001")).toBeInTheDocument();
  });

  it("renders DEEPSECURE_PRIVATE_KEY env var", () => {
    render(<AgentIdentityCard agentId="test-agent-001" />);

    expect(screen.getByText("DEEPSECURE_PRIVATE_KEY")).toBeInTheDocument();
  });

  it("renders Cryptographic Key method label", () => {
    render(<AgentIdentityCard agentId="test-agent-001" />);

    expect(screen.getByText("Cryptographic Key (Ed25519)")).toBeInTheDocument();
  });

  it("renders env var setup instruction", () => {
    render(<AgentIdentityCard agentId="test-agent-001" />);

    expect(
      screen.getByText(/Set these environment variables/)
    ).toBeInTheDocument();
  });

  it("renders Identity Method title", () => {
    render(<AgentIdentityCard agentId="test-agent-001" />);

    expect(screen.getByText("Identity Method")).toBeInTheDocument();
  });

  it("renders when platform is explicitly null", () => {
    render(<AgentIdentityCard agentId="test-agent-002" platform={null} />);

    expect(screen.getByText("DEEPSECURE_AGENT_ID")).toBeInTheDocument();
    expect(screen.getByText("test-agent-002")).toBeInTheDocument();
  });
});

describe("AgentIdentityCard — GCP platform", () => {
  it("renders GCP Workload Identity label", () => {
    render(
      <AgentIdentityCard
        agentId="gcp-agent"
        platform="gcp_workload_identity"
        selector="sa@project.iam.gserviceaccount.com"
      />
    );

    expect(screen.getByText("GCP Workload Identity")).toBeInTheDocument();
  });

  it("renders the selector (service account email)", () => {
    render(
      <AgentIdentityCard
        agentId="gcp-agent"
        platform="gcp_workload_identity"
        selector="sa@project.iam.gserviceaccount.com"
      />
    );

    expect(
      screen.getByText("sa@project.iam.gserviceaccount.com")
    ).toBeInTheDocument();
  });

  it("shows 'No keys or environment variables needed' message", () => {
    render(
      <AgentIdentityCard
        agentId="gcp-agent"
        platform="gcp_workload_identity"
        selector="sa@project.iam.gserviceaccount.com"
      />
    );

    expect(
      screen.getByText("No keys or environment variables needed.")
    ).toBeInTheDocument();
  });

  it("shows automatic authentication note", () => {
    render(
      <AgentIdentityCard
        agentId="gcp-agent"
        platform="gcp_workload_identity"
      />
    );

    expect(
      screen.getByText(/authenticates automatically via its platform identity/)
    ).toBeInTheDocument();
  });
});

describe("AgentIdentityCard — AWS platform", () => {
  it("renders AWS IAM label", () => {
    render(
      <AgentIdentityCard
        agentId="aws-agent"
        platform="aws_iam"
        selector="arn:aws:iam::123456789012:role/my-role"
      />
    );

    expect(screen.getByText("AWS IAM")).toBeInTheDocument();
  });

  it("renders the selector (role ARN)", () => {
    render(
      <AgentIdentityCard
        agentId="aws-agent"
        platform="aws_iam"
        selector="arn:aws:iam::123456789012:role/my-role"
      />
    );

    expect(
      screen.getByText("arn:aws:iam::123456789012:role/my-role")
    ).toBeInTheDocument();
  });
});

describe("AgentIdentityCard — Kubernetes platform", () => {
  it("renders Kubernetes label", () => {
    render(
      <AgentIdentityCard
        agentId="k8s-agent"
        platform="kubernetes"
        selector="my-sa@my-namespace"
      />
    );

    expect(screen.getByText("Kubernetes")).toBeInTheDocument();
  });

  it("renders the selector", () => {
    render(
      <AgentIdentityCard
        agentId="k8s-agent"
        platform="kubernetes"
        selector="my-sa@my-namespace"
      />
    );

    expect(screen.getByText("my-sa@my-namespace")).toBeInTheDocument();
  });
});

describe("AgentIdentityCard — unknown platform", () => {
  it("renders raw platform string as fallback label", () => {
    render(
      <AgentIdentityCard
        agentId="mystery-agent"
        platform="azure_ad"
        selector="some-selector"
      />
    );

    expect(screen.getByText("azure_ad")).toBeInTheDocument();
  });

  it("still shows the no-keys message for unknown platforms", () => {
    render(
      <AgentIdentityCard
        agentId="mystery-agent"
        platform="azure_ad"
      />
    );

    expect(
      screen.getByText("No keys or environment variables needed.")
    ).toBeInTheDocument();
  });
});

describe("AgentIdentityCard — selector omitted", () => {
  it("does not render Selector row when selector is null", () => {
    render(
      <AgentIdentityCard
        agentId="no-selector-agent"
        platform="gcp_workload_identity"
        selector={null}
      />
    );

    expect(screen.queryByText("Selector:")).not.toBeInTheDocument();
  });

  it("does not render Selector row when selector is undefined", () => {
    render(
      <AgentIdentityCard
        agentId="no-selector-agent"
        platform="aws_iam"
      />
    );

    expect(screen.queryByText("Selector:")).not.toBeInTheDocument();
  });
});
