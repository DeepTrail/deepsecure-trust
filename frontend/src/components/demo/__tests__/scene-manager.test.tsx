import React from "react";
import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  afterEach,
} from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";

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
  ChevronLeft: () => <span data-testid="icon-left">←</span>,
  ChevronRight: () => <span data-testid="icon-right">→</span>,
  Shield: () => <span>Shield</span>,
}));

import { SceneManager } from "../scene-manager";

function getActiveHeading(): string {
  return screen.getByRole("heading", { level: 2 }).textContent ?? "";
}

function getActiveSidebarIndex(): number {
  const nav = screen.getByRole("navigation", { name: "Demo scenes" });
  const buttons = nav.querySelectorAll("button");
  for (let i = 0; i < buttons.length; i++) {
    if (buttons[i].getAttribute("aria-current") === "true") return i;
  }
  return -1;
}

describe("SceneManager", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("renders the first scene initially", () => {
    render(<SceneManager />);
    expect(getActiveHeading()).toBe("SSO Authentication");
    expect(getActiveSidebarIndex()).toBe(0);
  });

  it("renders sidebar with all 6 scene titles", () => {
    render(<SceneManager />);
    const nav = screen.getByRole("navigation", { name: "Demo scenes" });
    expect(nav).toBeInTheDocument();
    const buttons = nav.querySelectorAll("button");
    expect(buttons).toHaveLength(6);
    expect(buttons[0].textContent).toContain("SSO Authentication");
    expect(buttons[1].textContent).toContain("Connect Services");
    expect(buttons[2].textContent).toContain("Register Agent");
    expect(buttons[3].textContent).toContain("Delegate Permissions");
    expect(buttons[4].textContent).toContain("MCP Tool Execution");
    expect(buttons[5].textContent).toContain("Audit Review");
  });

  it("highlights the active scene in the sidebar", () => {
    render(<SceneManager />);
    expect(getActiveSidebarIndex()).toBe(0);
  });

  it("auto-rotates to next scene after interval", () => {
    render(<SceneManager autoRotateInterval={3000} />);
    expect(getActiveHeading()).toBe("SSO Authentication");

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(getActiveHeading()).toBe("Connect Services");
    expect(getActiveSidebarIndex()).toBe(1);
  });

  it("pauses rotation on mouse enter", () => {
    render(<SceneManager autoRotateInterval={3000} />);
    const region = screen.getByRole("region");

    fireEvent.mouseEnter(region);

    act(() => {
      vi.advanceTimersByTime(6000);
    });

    expect(getActiveSidebarIndex()).toBe(0);
  });

  it("resumes rotation on mouse leave", () => {
    render(<SceneManager autoRotateInterval={3000} />);
    const region = screen.getByRole("region");

    fireEvent.mouseEnter(region);
    act(() => { vi.advanceTimersByTime(5000); });
    expect(getActiveSidebarIndex()).toBe(0);

    fireEvent.mouseLeave(region);
    act(() => { vi.advanceTimersByTime(3000); });
    expect(getActiveSidebarIndex()).toBe(1);
  });

  it("navigates to next scene on ArrowRight", () => {
    render(<SceneManager />);
    const region = screen.getByRole("region");

    fireEvent.keyDown(region, { key: "ArrowRight" });

    expect(getActiveHeading()).toBe("Connect Services");
  });

  it("navigates to previous scene on ArrowLeft", () => {
    render(<SceneManager />);
    const region = screen.getByRole("region");

    fireEvent.keyDown(region, { key: "ArrowRight" });
    expect(getActiveHeading()).toBe("Connect Services");

    fireEvent.keyDown(region, { key: "ArrowLeft" });
    expect(getActiveHeading()).toBe("SSO Authentication");
  });

  it("wraps from last scene to first on ArrowRight", () => {
    render(<SceneManager />);
    const region = screen.getByRole("region");

    for (let i = 0; i < 6; i++) {
      fireEvent.keyDown(region, { key: "ArrowRight" });
    }

    expect(getActiveHeading()).toBe("SSO Authentication");
    expect(getActiveSidebarIndex()).toBe(0);
  });

  it("wraps from first scene to last on ArrowLeft", () => {
    render(<SceneManager />);
    const region = screen.getByRole("region");

    fireEvent.keyDown(region, { key: "ArrowLeft" });

    expect(getActiveHeading()).toBe("Audit Review");
    expect(getActiveSidebarIndex()).toBe(5);
  });

  it("navigates to clicked sidebar scene", () => {
    render(<SceneManager />);
    const nav = screen.getByRole("navigation", { name: "Demo scenes" });
    const buttons = nav.querySelectorAll("button");

    fireEvent.click(buttons[3]);

    expect(getActiveHeading()).toBe("Delegate Permissions");
    expect(getActiveSidebarIndex()).toBe(3);
  });

  it("renders progress dots matching scene count", () => {
    render(<SceneManager />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(6);
  });

  it("marks active progress dot as selected", () => {
    render(<SceneManager />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs[0].getAttribute("aria-selected")).toBe("true");
    expect(tabs[1].getAttribute("aria-selected")).toBe("false");
  });

  it("clicking a progress dot navigates to that scene", () => {
    render(<SceneManager />);
    const tabs = screen.getAllByRole("tab");

    fireEvent.click(tabs[4]);

    expect(getActiveHeading()).toBe("MCP Tool Execution");
    expect(getActiveSidebarIndex()).toBe(4);
  });

  it("shows prev/next buttons", () => {
    render(<SceneManager />);
    expect(screen.getByRole("button", { name: "Previous scene" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next scene" })).toBeInTheDocument();
  });

  it("prev button navigates backward", () => {
    render(<SceneManager />);
    const region = screen.getByRole("region");

    fireEvent.keyDown(region, { key: "ArrowRight" });
    expect(getActiveHeading()).toBe("Connect Services");

    fireEvent.click(screen.getByRole("button", { name: "Previous scene" }));
    expect(getActiveHeading()).toBe("SSO Authentication");
  });

  it("next button navigates forward", () => {
    render(<SceneManager />);

    fireEvent.click(screen.getByRole("button", { name: "Next scene" }));

    expect(getActiveHeading()).toBe("Connect Services");
  });

  it("shows pause indicator when hovered", () => {
    render(<SceneManager />);
    const region = screen.getByRole("region");

    expect(screen.queryByText("Auto-rotation paused")).not.toBeInTheDocument();

    fireEvent.mouseEnter(region);

    expect(screen.getByText("Auto-rotation paused")).toBeInTheDocument();
  });

  it("accepts custom className", () => {
    render(<SceneManager className="custom-class" />);
    const region = screen.getByRole("region");
    expect(region.className).toContain("custom-class");
  });
});
