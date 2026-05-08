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

    const radios = screen.getAllByRole("radio");
    expect(radios[0]).toHaveAttribute("aria-checked", "true");
  });

  it("allows switching agent type", () => {
    render(<AgentCreatePage />);

    fireEvent.click(screen.getByText("Vendor Agent"));

    const radios = screen.getAllByRole("radio");
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
    expect(screen.getByText(/ed25519 keypair/i)).toBeInTheDocument();
  });

  it("shows contextual public key help text for vendor agent type", () => {
    render(<AgentCreatePage />);

    fireEvent.click(screen.getByText("Vendor Agent"));
    fireEvent.click(screen.getByText(/show advanced options/i));

    expect(screen.getByText(/leave empty.*server will generate/i)).toBeInTheDocument();
  });
});
