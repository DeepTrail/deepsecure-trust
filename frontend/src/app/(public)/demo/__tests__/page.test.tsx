import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("framer-motion", () => {
  const React = require("react");
  return {
    motion: {
      div: React.forwardRef(
        (props: React.HTMLAttributes<HTMLDivElement>, ref: React.Ref<HTMLDivElement>) => {
          const { initial, animate, exit, transition, onAnimationComplete, ...rest } = props as Record<string, unknown>;
          return <div ref={ref} {...(rest as Record<string, unknown>)} />;
        }
      ),
    },
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    useReducedMotion: () => false,
  };
});

vi.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    asChild,
    variant,
    size,
    ...rest
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean; variant?: string; size?: string }) => (
    <button onClick={onClick} {...rest}>
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/card", () => ({
  Card: ({ children, ...rest }: React.HTMLAttributes<HTMLDivElement>) => <div {...rest}>{children}</div>,
  CardHeader: ({ children }: React.HTMLAttributes<HTMLDivElement>) => <div>{children}</div>,
  CardTitle: ({ children, ...rest }: React.HTMLAttributes<HTMLDivElement>) => <div {...rest}>{children}</div>,
  CardContent: ({ children, ...rest }: React.HTMLAttributes<HTMLDivElement>) => <div {...rest}>{children}</div>,
}));

vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children, ...rest }: React.HTMLAttributes<HTMLDivElement>) => <span {...rest}>{children}</span>,
}));

vi.mock("lucide-react", () => ({
  Shield: () => <span data-testid="shield-icon">Shield</span>,
  ChevronLeft: () => <span>←</span>,
  ChevronRight: () => <span>→</span>,
}));

import DemoPage from "../page";

describe("DemoPage", () => {
  it("renders the SceneManager with scene content", () => {
    render(<DemoPage />);
    expect(screen.getByRole("region", { name: "Demo scene viewer" })).toBeInTheDocument();
  });

  it("displays the DeepSecure Demo header", () => {
    render(<DemoPage />);
    expect(screen.getByText("DeepSecure Demo")).toBeInTheDocument();
  });

  it("has a CTA link to /login", () => {
    render(<DemoPage />);
    const ctaLinks = screen.getAllByRole("link").filter(
      (link) => link.getAttribute("href") === "/login"
    );
    expect(ctaLinks.length).toBeGreaterThan(0);
  });

  it("has a Try DeepSecure button", () => {
    render(<DemoPage />);
    expect(screen.getByText("Try DeepSecure")).toBeInTheDocument();
  });

  it("displays footer with copyright", () => {
    render(<DemoPage />);
    expect(screen.getByText(/© \d{4} DeepSecure/)).toBeInTheDocument();
  });

  it("displays the footer CTA link", () => {
    render(<DemoPage />);
    expect(screen.getByText("Get started with DeepSecure")).toBeInTheDocument();
  });

  it("renders the shield icon in header", () => {
    render(<DemoPage />);
    expect(screen.getByTestId("shield-icon")).toBeInTheDocument();
  });

  it("exports force-static dynamic config", async () => {
    const mod = await import("../page");
    expect(mod.dynamic).toBe("force-static");
  });

  it("exports metadata with correct title", async () => {
    const mod = await import("../page");
    expect(mod.metadata).toBeDefined();
    expect((mod.metadata as { title: string }).title).toBe("DeepSecure Interactive Demo");
  });
});
