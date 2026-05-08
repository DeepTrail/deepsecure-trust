import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AgentTypeSelector } from "../AgentTypeSelector";

describe("AgentTypeSelector", () => {
  it("renders both agent type options", () => {
    render(<AgentTypeSelector value="own" onChange={() => {}} />);

    expect(screen.getByText("Own Agent")).toBeInTheDocument();
    expect(screen.getByText("Vendor Agent")).toBeInTheDocument();
  });

  it("renders descriptions for both types", () => {
    render(<AgentTypeSelector value="own" onChange={() => {}} />);

    expect(
      screen.getByText(/agent you build and control/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/third-party agent/)
    ).toBeInTheDocument();
  });

  it("marks the selected type as checked", () => {
    render(<AgentTypeSelector value="own" onChange={() => {}} />);

    const radios = screen.getAllByRole("radio");
    expect(radios[0]).toHaveAttribute("aria-checked", "true");
    expect(radios[1]).toHaveAttribute("aria-checked", "false");
  });

  it("marks vendor type as checked when selected", () => {
    render(<AgentTypeSelector value="vendor" onChange={() => {}} />);

    const radios = screen.getAllByRole("radio");
    expect(radios[0]).toHaveAttribute("aria-checked", "false");
    expect(radios[1]).toHaveAttribute("aria-checked", "true");
  });

  it("calls onChange when a type is clicked", () => {
    const onChange = vi.fn();
    render(<AgentTypeSelector value="own" onChange={onChange} />);

    fireEvent.click(screen.getByText("Vendor Agent"));
    expect(onChange).toHaveBeenCalledWith("vendor");
  });

  it("calls onChange with 'own' when Own Agent is clicked", () => {
    const onChange = vi.fn();
    render(<AgentTypeSelector value="vendor" onChange={onChange} />);

    fireEvent.click(screen.getByText("Own Agent"));
    expect(onChange).toHaveBeenCalledWith("own");
  });

  it("has a radiogroup role on the container", () => {
    render(<AgentTypeSelector value="own" onChange={() => {}} />);

    expect(screen.getByRole("radiogroup")).toBeInTheDocument();
  });

  it("has an accessible label on the radiogroup", () => {
    render(<AgentTypeSelector value="own" onChange={() => {}} />);

    expect(screen.getByRole("radiogroup")).toHaveAttribute(
      "aria-label",
      "Agent type"
    );
  });
});
