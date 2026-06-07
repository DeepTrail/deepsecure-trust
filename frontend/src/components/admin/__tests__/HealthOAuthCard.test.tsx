import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { HealthOAuthCard } from "../HealthOAuthCard";
import type { ServiceOAuthConfig } from "@/lib/types/admin";

const oauthConfig: ServiceOAuthConfig = {
  service_id: "notion",
  client_id: "client-id-12345678",
  has_client_secret: true,
  auth_url: "https://auth.example.com/oauth",
  token_url: "https://auth.example.com/token",
  scopes: ["read", "write"],
  source: "db",
};

const baseHealth = {
  latencyMs: 42,
  errorCount24h: 1,
  lastCheckedAt: "2026-06-07T12:00:00Z",
  status: "up" as const,
};

describe("HealthOAuthCard", () => {
  it("renders view mode health key-value card", () => {
    render(
      <HealthOAuthCard
        mode="view"
        health={baseHealth}
        showOAuth={false}
      />
    );

    expect(screen.getByTestId("health-oauth-card")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Health" })).toBeInTheDocument();
    expect(screen.getByTestId("health-oauth-unified-card")).toBeInTheDocument();
    expect(screen.getByText("42ms")).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
  });

  it("renders compact OAuth view card in view mode", () => {
    render(
      <HealthOAuthCard
        mode="view"
        health={baseHealth}
        oauthConfig={oauthConfig}
      />
    );

    expect(screen.getByTestId("oauth-view-card")).toBeInTheDocument();
    expect(screen.getByTestId("health-oauth-unified-card")).toBeInTheDocument();
    expect(screen.getByText("OAuth Credentials")).toBeInTheDocument();
    expect(screen.getByText("client-id-12…")).toBeInTheDocument();
    expect(screen.getByText("read, write")).toBeInTheDocument();
  });

  it("renders edit mode OAuth form when editing", () => {
    const onFormChange = vi.fn();
    const onSave = vi.fn();

    render(
      <HealthOAuthCard
        mode="edit"
        health={baseHealth}
        oauthConfig={oauthConfig}
        oauthEditing
        oauthForm={{
          clientId: "cid",
          clientSecret: "",
          authUrl: "https://auth.example.com",
          tokenUrl: "https://token.example.com",
          scopes: "read",
        }}
        onOAuthFormChange={onFormChange}
        onOAuthSave={onSave}
      />
    );

    expect(screen.getByTestId("oauth-edit-form")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("OAuth Client ID"), {
      target: { value: "new-id" },
    });
    expect(onFormChange).toHaveBeenCalledWith("clientId", "new-id");

    fireEvent.click(screen.getByRole("button", { name: /save credentials/i }));
    expect(onSave).toHaveBeenCalledOnce();
  });

  it("shows configure prompt when OAuth is missing", () => {
    const onEditStart = vi.fn();

    render(
      <HealthOAuthCard
        mode="view"
        health={baseHealth}
        oauthConfig={null}
        onOAuthEditStart={onEditStart}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /configure/i }));
    expect(onEditStart).toHaveBeenCalledOnce();
  });
});
