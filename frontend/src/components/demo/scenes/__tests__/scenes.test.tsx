import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

function filterDomProps(props: Record<string, unknown>) {
  const domProps: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(props)) {
    if (
      key === "className" ||
      key === "style" ||
      key.startsWith("data-") ||
      key.startsWith("aria-")
    ) {
      domProps[key] = value;
    }
  }
  return domProps;
}

vi.mock("framer-motion", () => ({
  motion: {
    div: ({
      children,
      ...props
    }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...filterDomProps(props)}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
  useReducedMotion: () => false,
}));

import {
  SsoLoginScene,
  ServiceConnectionScene,
  AgentRegistrationScene,
  DelegationScene,
  McpToolCallScene,
  AuditReviewScene,
} from "../index";
import type { DemoSceneProps } from "../index";

const scenes = [
  { name: "SsoLoginScene", Component: SsoLoginScene, title: "Step 1: SSO Authentication" },
  { name: "ServiceConnectionScene", Component: ServiceConnectionScene, title: "Step 2: Connect Services" },
  { name: "AgentRegistrationScene", Component: AgentRegistrationScene, title: "Step 3: Register Agent" },
  { name: "DelegationScene", Component: DelegationScene, title: "Step 4: Delegate Permissions" },
  { name: "McpToolCallScene", Component: McpToolCallScene, title: "Step 5: MCP Tool Execution" },
  { name: "AuditReviewScene", Component: AuditReviewScene, title: "Step 6: Audit Review" },
] as const;

describe("Demo Scene Components", () => {
  describe.each(scenes)("$name", ({ Component, title }) => {
    it("renders content when isActive is true", () => {
      render(<Component isActive={true} />);
      expect(screen.getByText(title)).toBeInTheDocument();
    });

    it("does not render content when isActive is false", () => {
      render(<Component isActive={false} />);
      expect(screen.queryByText(title)).not.toBeInTheDocument();
    });

    it("applies className prop to the wrapper", () => {
      const { container } = render(
        <Component isActive={true} className="custom-class" />
      );
      expect(container.querySelector(".custom-class")).toBeInTheDocument();
    });

    it("accepts onComplete callback prop", () => {
      const onComplete = vi.fn();
      expect(() =>
        render(<Component isActive={true} onComplete={onComplete} />)
      ).not.toThrow();
    });
  });

  describe("barrel exports", () => {
    it("exports all 6 scene components from index", () => {
      expect(SsoLoginScene).toBeDefined();
      expect(ServiceConnectionScene).toBeDefined();
      expect(AgentRegistrationScene).toBeDefined();
      expect(DelegationScene).toBeDefined();
      expect(McpToolCallScene).toBeDefined();
      expect(AuditReviewScene).toBeDefined();
    });

    it("exports DemoSceneProps type (compile-time check)", () => {
      const props: DemoSceneProps = {
        isActive: true,
        onComplete: () => {},
        className: "test",
      };
      expect(props.isActive).toBe(true);
    });
  });

  describe("scene-specific content", () => {
    it("SsoLoginScene renders SSO-related badges", () => {
      render(<SsoLoginScene isActive={true} />);
      expect(screen.getByText("Keycloak")).toBeInTheDocument();
      expect(screen.getAllByText("JWT Issued").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("L2 User Token")).toBeInTheDocument();
    });

    it("ServiceConnectionScene renders service names", () => {
      render(<ServiceConnectionScene isActive={true} />);
      expect(screen.getByText("Notion")).toBeInTheDocument();
      expect(screen.getByText("Slack")).toBeInTheDocument();
      expect(screen.getByText("GitHub")).toBeInTheDocument();
    });

    it("AgentRegistrationScene renders registration steps", () => {
      render(<AgentRegistrationScene isActive={true} />);
      expect(screen.getByText("Generate Ed25519 Keypair")).toBeInTheDocument();
      expect(screen.getByText("Register Public Key")).toBeInTheDocument();
      expect(screen.getAllByText("Challenge-Response").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/Agent Verified/)).toBeInTheDocument();
    });

    it("DelegationScene renders permission scopes", () => {
      render(<DelegationScene isActive={true} />);
      expect(screen.getByText("notion:pages:read")).toBeInTheDocument();
      expect(screen.getByText("slack:messages:write")).toBeInTheDocument();
    });

    it("McpToolCallScene renders tool calls with success and denial", () => {
      render(<McpToolCallScene isActive={true} />);
      expect(screen.getByText("notion.search_pages")).toBeInTheDocument();
      expect(screen.getByText("3 pages found")).toBeInTheDocument();
      expect(screen.getByText("Denied")).toBeInTheDocument();
    });

    it("AuditReviewScene renders audit events with layer badges", () => {
      render(<AuditReviewScene isActive={true} />);
      expect(screen.getByText("SSO Login")).toBeInTheDocument();
      expect(screen.getByText("Permission Denied")).toBeInTheDocument();
      expect(screen.getAllByText("L2")).toHaveLength(2);
      expect(screen.getAllByText("L3")).toHaveLength(3);
    });
  });
});
