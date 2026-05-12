import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PermissionChecklist, type Permission } from "../PermissionChecklist";

const PERMISSIONS: Permission[] = [
  {
    id: "p1",
    service: "notion",
    scope: "pages",
    action: "read",
    locked: false,
  },
  {
    id: "p2",
    service: "notion",
    scope: "pages",
    action: "write",
    locked: "role",
    lockReason: "Requires admin role",
  },
  {
    id: "p3",
    service: "github",
    scope: "repos",
    action: "read",
    locked: false,
  },
  {
    id: "p4",
    service: "github",
    scope: "repos",
    action: "push",
    locked: "oauth",
    lockReason: "Needs repo:write scope",
  },
  {
    id: "p5",
    service: "slack",
    scope: "messages",
    action: "send",
    locked: "oauth",
  },
];

describe("PermissionChecklist", () => {
  it("groups permissions by service", () => {
    const onToggle = vi.fn();
    render(
      <PermissionChecklist
        permissions={PERMISSIONS}
        selected={[]}
        onToggle={onToggle}
      />,
    );

    expect(screen.getByText(/^notion/i)).toBeInTheDocument();
    expect(screen.getByText(/^github/i)).toBeInTheDocument();
    expect(screen.getByText(/^slack/i)).toBeInTheDocument();
  });

  it("renders permission scope:action labels", () => {
    const onToggle = vi.fn();
    render(
      <PermissionChecklist
        permissions={PERMISSIONS}
        selected={[]}
        onToggle={onToggle}
      />,
    );

    expect(screen.getByText("pages:read")).toBeInTheDocument();
    expect(screen.getByText("pages:write")).toBeInTheDocument();
    expect(screen.getByText("repos:read")).toBeInTheDocument();
    expect(screen.getByText("repos:push")).toBeInTheDocument();
    expect(screen.getByText("messages:send")).toBeInTheDocument();
  });

  it("shows role-lock icon for role-locked permissions", () => {
    const onToggle = vi.fn();
    render(
      <PermissionChecklist
        permissions={PERMISSIONS}
        selected={[]}
        onToggle={onToggle}
      />,
    );

    expect(screen.getByTestId("role-lock-icon")).toBeInTheDocument();
  });

  it("shows oauth-lock icon for oauth-locked permissions", () => {
    const onToggle = vi.fn();
    render(
      <PermissionChecklist
        permissions={PERMISSIONS}
        selected={[]}
        onToggle={onToggle}
      />,
    );

    const oauthIcons = screen.getAllByTestId("oauth-lock-icon");
    expect(oauthIcons).toHaveLength(2);
  });

  it("displays lock reason text for oauth-locked permissions with reason", () => {
    const onToggle = vi.fn();
    render(
      <PermissionChecklist
        permissions={PERMISSIONS}
        selected={[]}
        onToggle={onToggle}
      />,
    );

    const oauthIcons = screen.getAllByTestId("oauth-lock-icon");
    const iconWithReason = oauthIcons.find(
      (el) => el.parentElement?.getAttribute("title") === "Needs repo:write scope",
    );
    expect(iconWithReason).toBeTruthy();
  });

  it("disables checkboxes for locked permissions", () => {
    const onToggle = vi.fn();
    render(
      <PermissionChecklist
        permissions={PERMISSIONS}
        selected={[]}
        onToggle={onToggle}
      />,
    );

    const checkboxes = screen.getAllByRole("checkbox");
    const roleLocked = checkboxes.find(
      (cb) => cb.getAttribute("aria-label") === "pages:write",
    );
    const oauthLocked = checkboxes.find(
      (cb) => cb.getAttribute("aria-label") === "repos:push",
    );

    expect(roleLocked).toBeDisabled();
    expect(oauthLocked).toBeDisabled();
  });

  it("enables checkboxes for unlocked permissions", () => {
    const onToggle = vi.fn();
    render(
      <PermissionChecklist
        permissions={PERMISSIONS}
        selected={[]}
        onToggle={onToggle}
      />,
    );

    const checkboxes = screen.getAllByRole("checkbox");
    const unlocked = checkboxes.find(
      (cb) => cb.getAttribute("aria-label") === "pages:read",
    );
    expect(unlocked).not.toBeDisabled();
  });

  it("calls onToggle when an unlocked permission is clicked", () => {
    const onToggle = vi.fn();
    render(
      <PermissionChecklist
        permissions={PERMISSIONS}
        selected={[]}
        onToggle={onToggle}
      />,
    );

    const checkboxes = screen.getAllByRole("checkbox");
    const unlocked = checkboxes.find(
      (cb) => cb.getAttribute("aria-label") === "pages:read",
    );
    fireEvent.click(unlocked!);

    expect(onToggle).toHaveBeenCalledWith("p1");
  });

  it("does not call onToggle when a locked permission is clicked", () => {
    const onToggle = vi.fn();
    render(
      <PermissionChecklist
        permissions={PERMISSIONS}
        selected={[]}
        onToggle={onToggle}
      />,
    );

    const checkboxes = screen.getAllByRole("checkbox");
    const locked = checkboxes.find(
      (cb) => cb.getAttribute("aria-label") === "pages:write",
    );
    fireEvent.click(locked!);

    expect(onToggle).not.toHaveBeenCalled();
  });

  it("reflects selected state via checked attribute", () => {
    const onToggle = vi.fn();
    render(
      <PermissionChecklist
        permissions={PERMISSIONS}
        selected={["p1", "p3"]}
        onToggle={onToggle}
      />,
    );

    const checkboxes = screen.getAllByRole("checkbox");
    const pagesRead = checkboxes.find(
      (cb) => cb.getAttribute("aria-label") === "pages:read",
    ) as HTMLInputElement;
    const reposRead = checkboxes.find(
      (cb) => cb.getAttribute("aria-label") === "repos:read",
    ) as HTMLInputElement;
    const messagesSend = checkboxes.find(
      (cb) => cb.getAttribute("aria-label") === "messages:send",
    ) as HTMLInputElement;

    expect(pagesRead.checked).toBe(true);
    expect(reposRead.checked).toBe(true);
    expect(messagesSend.checked).toBe(false);
  });

  it("renders empty state gracefully with no permissions", () => {
    const onToggle = vi.fn();
    const { container } = render(
      <PermissionChecklist
        permissions={[]}
        selected={[]}
        onToggle={onToggle}
      />,
    );

    expect(container.querySelector('[role="group"]')).toBeInTheDocument();
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
  });
});
