import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  DelegatedToolsCard,
  UnavailableToolsDisclosure,
  ToolsList,
  type AgentTool,
} from "../ToolsList";

const TOOLS: AgentTool[] = [
  {
    name: "notion.search_pages",
    backend: "notion",
    permission: "notion:pages:read",
    available: true,
  },
  {
    name: "notion.create_page",
    backend: "notion",
    permission: "notion:pages:create",
    available: false,
    reason: "Not in delegation",
  },
  {
    name: "slack.post_message",
    backend: "slack",
    permission: "slack:messages:write",
    available: true,
  },
];

describe("DelegatedToolsCard", () => {
  it("renders only available tools as chips", () => {
    render(<DelegatedToolsCard tools={TOOLS} />);

    expect(screen.getByText("search_pages")).toBeInTheDocument();
    expect(screen.getByText("post_message")).toBeInTheDocument();
    expect(screen.queryByText("create_page")).not.toBeInTheDocument();
  });

  it("shows delegated tool count in header", () => {
    render(<DelegatedToolsCard tools={TOOLS} />);

    expect(screen.getByText(/Delegated Tools & Permissions/)).toBeInTheDocument();
  });

  it("groups tools by service", () => {
    render(<DelegatedToolsCard tools={TOOLS} />);

    expect(screen.getByText("notion")).toBeInTheDocument();
    expect(screen.getByText("slack")).toBeInTheDocument();
  });

  it("renders empty state when no tools are delegated", () => {
    const unavailableOnly = TOOLS.filter((t) => !t.available);
    render(<DelegatedToolsCard tools={unavailableOnly} />);

    expect(screen.getByText("No tools delegated yet")).toBeInTheDocument();
  });

  it("renders empty state when tools list is empty", () => {
    render(<DelegatedToolsCard tools={[]} />);

    expect(screen.getByText("No tools delegated yet")).toBeInTheDocument();
  });
});

describe("UnavailableToolsDisclosure", () => {
  it("renders collapsed by default", () => {
    render(<UnavailableToolsDisclosure tools={TOOLS} />);

    expect(
      screen.getByText(/Show 1 unavailable tool/)
    ).toBeInTheDocument();
    expect(screen.queryByText("create_page")).not.toBeInTheDocument();
  });

  it("expands to show unavailable tools on click", async () => {
    const user = userEvent.setup();
    render(<UnavailableToolsDisclosure tools={TOOLS} />);

    await user.click(screen.getByText(/Show 1 unavailable tool/));

    expect(screen.getByText("create_page")).toBeInTheDocument();
  });

  it("returns null when no unavailable tools", () => {
    const availableOnly = TOOLS.filter((t) => t.available);
    const { container } = render(
      <UnavailableToolsDisclosure tools={availableOnly} />
    );

    expect(container.firstChild).toBeNull();
  });
});

describe("ToolsList (legacy wrapper)", () => {
  it("renders both delegated and unavailable sections", () => {
    render(<ToolsList tools={TOOLS} />);

    expect(screen.getByText(/Delegated Tools & Permissions/)).toBeInTheDocument();
    expect(
      screen.getByText(/Show 1 unavailable tool/)
    ).toBeInTheDocument();
  });
});
