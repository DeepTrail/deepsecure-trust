import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AgentCreatePage from "../page";
import { apiClient, ApiError } from "@/lib/api/client";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

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

describe("AgentCreatePage", () => {
  beforeEach(() => {
    mockApiClient.mockReset();
    mockPush.mockClear();

    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the registration form with Name as primary field", () => {
    render(<AgentCreatePage />);

    expect(screen.getByRole("heading", { name: /register agent/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/^name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
  });

  it("does not show Agent ID or Public Key by default (hidden in advanced)", () => {
    render(<AgentCreatePage />);

    expect(screen.queryByLabelText(/agent id/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/public key/i)).not.toBeInTheDocument();
  });

  it("shows advanced options when toggled", () => {
    render(<AgentCreatePage />);

    fireEvent.click(screen.getByText(/show advanced options/i));

    expect(screen.getByLabelText(/agent id/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/public key/i)).toBeInTheDocument();
  });

  it("renders the agent type selector", () => {
    render(<AgentCreatePage />);

    expect(screen.getByText("Own Agent")).toBeInTheDocument();
    expect(screen.getByText("Vendor Agent")).toBeInTheDocument();
  });

  it("has agent type 'own' selected by default", () => {
    render(<AgentCreatePage />);

    const agentTypeGroup = screen.getByRole("radiogroup", { name: /agent type/i });
    const radios = Array.from(agentTypeGroup.querySelectorAll("[role=radio]"));
    expect(radios[0]).toHaveAttribute("aria-checked", "true");
  });

  it("allows switching agent type", () => {
    render(<AgentCreatePage />);

    fireEvent.click(screen.getByText("Vendor Agent"));

    const agentTypeGroup = screen.getByRole("radiogroup", { name: /agent type/i });
    const radios = Array.from(agentTypeGroup.querySelectorAll("[role=radio]"));
    expect(radios[1]).toHaveAttribute("aria-checked", "true");
    expect(radios[0]).toHaveAttribute("aria-checked", "false");
  });

  it("submit is enabled without Agent ID (server auto-generates)", () => {
    render(<AgentCreatePage />);

    const submitButton = screen.getByRole("button", { name: /register agent/i });
    expect(submitButton).toBeEnabled();
  });

  it("submits form with only name (minimal payload)", async () => {
    mockApiClient.mockResolvedValueOnce({
      agent_id: "agent-uuid-123",
      name: "My Agent",
      public_key: "generated-pubkey",
      private_key: "generated-privkey",
      private_key_warning: "Save this!",
    });

    render(<AgentCreatePage />);

    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "My Agent" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith("agents/", {
        method: "POST",
        body: JSON.stringify({ name: "My Agent" }),
      });
    });
  });

  it("includes agent_id when provided in advanced options", async () => {
    mockApiClient.mockResolvedValueOnce({
      agent_id: "my-custom-id",
      name: "Custom Agent",
      public_key: "pubkey",
    });

    render(<AgentCreatePage />);

    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "Custom Agent" },
    });
    fireEvent.click(screen.getByText(/show advanced options/i));
    fireEvent.change(screen.getByLabelText(/agent id/i), {
      target: { value: "my-custom-id" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

    await waitFor(() => {
      const call = mockApiClient.mock.calls[0];
      const body = JSON.parse(call[1]!.body as string);
      expect(body.agent_id).toBe("my-custom-id");
      expect(body.name).toBe("Custom Agent");
    });
  });

  it("includes public key in payload when provided via advanced", async () => {
    mockApiClient.mockResolvedValueOnce({
      agent_id: "my-agent",
      name: "My Agent",
      public_key: "user-provided-key",
    });

    render(<AgentCreatePage />);

    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "My Agent" },
    });
    fireEvent.click(screen.getByText(/show advanced options/i));
    fireEvent.change(screen.getByLabelText(/public key/i), {
      target: { value: "user-provided-key" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

    await waitFor(() => {
      const call = mockApiClient.mock.calls[0];
      const body = JSON.parse(call[1]!.body as string);
      expect(body.public_key).toBe("user-provided-key");
    });
  });

  it("redirects to agents list when no private key in response", async () => {
    mockApiClient.mockResolvedValueOnce({
      agent_id: "my-agent",
      name: "My Agent",
      public_key: "pubkey123",
    });

    render(<AgentCreatePage />);

    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "My Agent" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/dashboard/agents");
    });
  });

  it("shows PrivateKeyModal when backend returns private key", async () => {
    mockApiClient.mockResolvedValueOnce({
      agent_id: "agent-uuid-123",
      name: "My Agent",
      public_key: "generated-pubkey",
      private_key: "generated-privkey",
      private_key_warning: "This private key will not be shown again.",
    });

    render(<AgentCreatePage />);

    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "My Agent" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    expect(screen.getByText("Agent Keypair Generated")).toBeInTheDocument();
    expect(screen.getByTestId("private-key-display")).toHaveTextContent(
      "generated-privkey"
    );
  });

  it("redirects after dismissing PrivateKeyModal", async () => {
    mockApiClient.mockResolvedValueOnce({
      agent_id: "agent-uuid-123",
      name: "My Agent",
      public_key: "generated-pubkey",
      private_key: "generated-privkey",
      private_key_warning: "Warning",
    });

    render(<AgentCreatePage />);

    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "My Agent" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("confirm-checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    expect(mockPush).toHaveBeenCalledWith("/dashboard/agents");
  });

  it("shows 409 conflict error", async () => {
    mockApiClient.mockRejectedValueOnce(new ApiError(409, "Conflict"));

    render(<AgentCreatePage />);

    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "Duplicate Agent" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/already exists/i)
      ).toBeInTheDocument();
    });
  });

  it("shows generic error for non-API failures", async () => {
    mockApiClient.mockRejectedValueOnce(new Error("Network error"));

    render(<AgentCreatePage />);

    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "Fail Agent" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Failed to create agent. Please try again.")
      ).toBeInTheDocument();
    });
  });

  it("navigates back when back button is clicked", () => {
    render(<AgentCreatePage />);

    fireEvent.click(screen.getByRole("button", { name: /back to agents/i }));
    expect(mockPush).toHaveBeenCalledWith("/dashboard/agents");
  });

  it("navigates back when cancel button is clicked", () => {
    render(<AgentCreatePage />);

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(mockPush).toHaveBeenCalledWith("/dashboard/agents");
  });

  it("includes description in payload when provided", async () => {
    mockApiClient.mockResolvedValueOnce({
      agent_id: "agent-uuid",
      name: "My Agent",
      public_key: "pubkey123",
      private_key: "privkey",
      private_key_warning: "Save it",
    });

    render(<AgentCreatePage />);

    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "My Agent" },
    });
    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: "A test agent" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

    await waitFor(() => {
      const call = mockApiClient.mock.calls[0];
      const body = JSON.parse(call[1]!.body as string);
      expect(body.description).toBe("A test agent");
    });
  });

  it("shows 'Creating...' text while submitting", async () => {
    let resolveApi: (value: unknown) => void;
    mockApiClient.mockReturnValueOnce(
      new Promise((r) => {
        resolveApi = r;
      })
    );

    render(<AgentCreatePage />);

    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "My Agent" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

    expect(screen.getByText("Creating...")).toBeInTheDocument();

    resolveApi!({ agent_id: "a", name: "My Agent", public_key: "pk", private_key: "sk", private_key_warning: "w" });

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
  });

  it("shows info box explaining auto-generated ID and keypair", () => {
    render(<AgentCreatePage />);

    expect(screen.getByText(/auto-generated by the server/i)).toBeInTheDocument();
    expect(screen.getByText(/will be generated server-side/i)).toBeInTheDocument();
  });

  it("shows contextual public key help text for vendor agent type", () => {
    render(<AgentCreatePage />);

    fireEvent.click(screen.getByText("Vendor Agent"));
    fireEvent.click(screen.getByText(/show advanced options/i));

    expect(screen.getByText(/leave empty.*server will generate/i)).toBeInTheDocument();
  });

  describe("Platform-based registration", () => {
    it("sends platform + selector for GCP identity", async () => {
      mockApiClient.mockResolvedValueOnce({
        agent_id: "agent-gcp-001",
        name: "GCP Agent",
        platform: "gcp_workload_identity",
        selector: "sa@proj.iam.gserviceaccount.com",
      });

      render(<AgentCreatePage />);

      fireEvent.change(screen.getByLabelText(/^name/i), {
        target: { value: "GCP Agent" },
      });
      fireEvent.click(screen.getByText("GCP Workload Identity"));
      fireEvent.change(screen.getByLabelText(/gcp service account email/i), {
        target: { value: "sa@proj.iam.gserviceaccount.com" },
      });
      fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

      await waitFor(() => {
        const call = mockApiClient.mock.calls[0];
        const body = JSON.parse(call[1]!.body as string);
        expect(body.platform).toBe("gcp_workload_identity");
        expect(body.selector).toBe("sa@proj.iam.gserviceaccount.com");
        expect(body.public_key).toBeUndefined();
        expect(body.agent_id).toBeUndefined();
      });
    });

    it("sends platform + selector for AWS identity", async () => {
      mockApiClient.mockResolvedValueOnce({
        agent_id: "agent-aws-001",
        name: "AWS Agent",
        platform: "aws_iam",
        selector: "arn:aws:iam::123456789012:role/my-role",
      });

      render(<AgentCreatePage />);

      fireEvent.change(screen.getByLabelText(/^name/i), {
        target: { value: "AWS Agent" },
      });
      fireEvent.click(screen.getByText("AWS IAM"));
      fireEvent.change(screen.getByLabelText(/aws iam role arn/i), {
        target: { value: "arn:aws:iam::123456789012:role/my-role" },
      });
      fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

      await waitFor(() => {
        const call = mockApiClient.mock.calls[0];
        const body = JSON.parse(call[1]!.body as string);
        expect(body.platform).toBe("aws_iam");
        expect(body.selector).toBe("arn:aws:iam::123456789012:role/my-role");
        expect(body.public_key).toBeUndefined();
        expect(body.agent_id).toBeUndefined();
      });
    });

    it("sends platform + composite selector for K8s identity", async () => {
      mockApiClient.mockResolvedValueOnce({
        agent_id: "agent-k8s-001",
        name: "K8s Agent",
        platform: "kubernetes",
        selector: "namespace=prod,service_account=my-sa",
      });

      render(<AgentCreatePage />);

      fireEvent.change(screen.getByLabelText(/^name/i), {
        target: { value: "K8s Agent" },
      });
      fireEvent.click(screen.getByText("Kubernetes"));
      fireEvent.change(screen.getByLabelText(/namespace/i), {
        target: { value: "prod" },
      });
      fireEvent.change(screen.getByLabelText(/service account name/i), {
        target: { value: "my-sa" },
      });
      fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

      await waitFor(() => {
        const call = mockApiClient.mock.calls[0];
        const body = JSON.parse(call[1]!.body as string);
        expect(body.platform).toBe("kubernetes");
        expect(body.selector).toBe("namespace=prod,service_account=my-sa");
        expect(body.public_key).toBeUndefined();
        expect(body.agent_id).toBeUndefined();
      });
    });

    it("redirects platform agent to delegation create page after registration", async () => {
      mockApiClient.mockResolvedValueOnce({
        agent_id: "agent-gcp-002",
        name: "GCP Agent",
        platform: "gcp_workload_identity",
        selector: "sa@proj.iam.gserviceaccount.com",
      });

      render(<AgentCreatePage />);

      fireEvent.change(screen.getByLabelText(/^name/i), {
        target: { value: "GCP Agent" },
      });
      fireEvent.click(screen.getByText("GCP Workload Identity"));
      fireEvent.change(screen.getByLabelText(/gcp service account email/i), {
        target: { value: "sa@proj.iam.gserviceaccount.com" },
      });
      fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith(
          "/dashboard/delegation/create?agent_id=agent-gcp-002"
        );
      });
    });

    it("does NOT show PrivateKeyModal for platform agents", async () => {
      mockApiClient.mockResolvedValueOnce({
        agent_id: "agent-gcp-003",
        name: "GCP Agent",
        platform: "gcp_workload_identity",
        selector: "sa@proj.iam.gserviceaccount.com",
      });

      render(<AgentCreatePage />);

      fireEvent.change(screen.getByLabelText(/^name/i), {
        target: { value: "GCP Agent" },
      });
      fireEvent.click(screen.getByText("GCP Workload Identity"));
      fireEvent.change(screen.getByLabelText(/gcp service account email/i), {
        target: { value: "sa@proj.iam.gserviceaccount.com" },
      });
      fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalled();
      });
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("shows platform-specific 409 error for platform agents", async () => {
      mockApiClient.mockRejectedValueOnce(new ApiError(409, "Conflict"));

      render(<AgentCreatePage />);

      fireEvent.change(screen.getByLabelText(/^name/i), {
        target: { value: "Dup GCP Agent" },
      });
      fireEvent.click(screen.getByText("GCP Workload Identity"));
      fireEvent.change(screen.getByLabelText(/gcp service account email/i), {
        target: { value: "sa@proj.iam.gserviceaccount.com" },
      });
      fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

      await waitFor(() => {
        expect(
          screen.getByText(/already registered with this platform identity/i)
        ).toBeInTheDocument();
      });
    });

    it("still sends key-based payload when key method is selected", async () => {
      mockApiClient.mockResolvedValueOnce({
        agent_id: "agent-key-001",
        name: "Key Agent",
        public_key: "pubkey",
        private_key: "privkey",
        private_key_warning: "Save this!",
      });

      render(<AgentCreatePage />);

      fireEvent.change(screen.getByLabelText(/^name/i), {
        target: { value: "Key Agent" },
      });
      fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

      await waitFor(() => {
        const call = mockApiClient.mock.calls[0];
        const body = JSON.parse(call[1]!.body as string);
        expect(body.platform).toBeUndefined();
        expect(body.selector).toBeUndefined();
        expect(body.name).toBe("Key Agent");
      });
    });

    it("includes description for platform agents", async () => {
      mockApiClient.mockResolvedValueOnce({
        agent_id: "agent-gcp-004",
        name: "GCP Agent",
        platform: "gcp_workload_identity",
        selector: "sa@proj.iam.gserviceaccount.com",
      });

      render(<AgentCreatePage />);

      fireEvent.change(screen.getByLabelText(/^name/i), {
        target: { value: "GCP Agent" },
      });
      fireEvent.change(screen.getByLabelText(/description/i), {
        target: { value: "Runs on GCP" },
      });
      fireEvent.click(screen.getByText("GCP Workload Identity"));
      fireEvent.change(screen.getByLabelText(/gcp service account email/i), {
        target: { value: "sa@proj.iam.gserviceaccount.com" },
      });
      fireEvent.click(screen.getByRole("button", { name: /register agent/i }));

      await waitFor(() => {
        const call = mockApiClient.mock.calls[0];
        const body = JSON.parse(call[1]!.body as string);
        expect(body.description).toBe("Runs on GCP");
        expect(body.platform).toBe("gcp_workload_identity");
      });
    });
  });

  describe("IdentityMethodSelector", () => {
    it("renders all four identity method cards", () => {
      render(<AgentCreatePage />);

      expect(screen.getByText("Cryptographic Key")).toBeInTheDocument();
      expect(screen.getByText("GCP Workload Identity")).toBeInTheDocument();
      expect(screen.getByText("AWS IAM")).toBeInTheDocument();
      expect(screen.getByText("Kubernetes")).toBeInTheDocument();
    });

    it("has 'key' selected by default", () => {
      render(<AgentCreatePage />);

      const identityGroup = screen.getByRole("radiogroup", { name: /identity method/i });
      const radios = Array.from(identityGroup.querySelectorAll("[role=radio]"));
      expect(radios[0]).toHaveAttribute("aria-checked", "true");
    });

    it("shows GCP service account input when GCP is selected", () => {
      render(<AgentCreatePage />);

      fireEvent.click(screen.getByText("GCP Workload Identity"));

      expect(screen.getByLabelText(/gcp service account email/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/my-agent@my-project/)).toBeInTheDocument();
    });

    it("shows AWS IAM role ARN input when AWS is selected", () => {
      render(<AgentCreatePage />);

      fireEvent.click(screen.getByText("AWS IAM"));

      expect(screen.getByLabelText(/aws iam role arn/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/arn:aws:iam/)).toBeInTheDocument();
    });

    it("shows K8s namespace and service account inputs when K8s is selected", () => {
      render(<AgentCreatePage />);

      fireEvent.click(screen.getByText("Kubernetes"));

      expect(screen.getByLabelText(/namespace/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/service account name/i)).toBeInTheDocument();
    });

    it("hides advanced options (Public Key) when platform method is selected", () => {
      render(<AgentCreatePage />);

      expect(screen.getByText(/show advanced options/i)).toBeInTheDocument();

      fireEvent.click(screen.getByText("GCP Workload Identity"));

      expect(screen.queryByText(/show advanced options/i)).not.toBeInTheDocument();
    });

    it("shows platform info text instead of keypair text when platform method selected", () => {
      render(<AgentCreatePage />);

      expect(screen.getByText(/will be generated server-side/i)).toBeInTheDocument();

      fireEvent.click(screen.getByText("GCP Workload Identity"));

      expect(screen.queryByText(/will be generated server-side/i)).not.toBeInTheDocument();
      expect(screen.getByText(/platform's native token/i)).toBeInTheDocument();
    });

    it("restores advanced options when switching back to key method", () => {
      render(<AgentCreatePage />);

      fireEvent.click(screen.getByText("GCP Workload Identity"));
      expect(screen.queryByText(/show advanced options/i)).not.toBeInTheDocument();

      fireEvent.click(screen.getByText("Cryptographic Key"));
      expect(screen.getByText(/show advanced options/i)).toBeInTheDocument();
    });

    it("does not show platform inputs when key method is selected", () => {
      render(<AgentCreatePage />);

      expect(screen.queryByLabelText(/gcp service account email/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/aws iam role arn/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/namespace/i)).not.toBeInTheDocument();
    });
  });
});
