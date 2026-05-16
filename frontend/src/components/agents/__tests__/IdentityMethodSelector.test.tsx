import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { IdentityMethodSelector } from "../IdentityMethodSelector";

describe("IdentityMethodSelector", () => {
  it("renders all 4 identity method cards", () => {
    render(<IdentityMethodSelector value="key" onChange={() => {}} />);

    expect(screen.getByText("Cryptographic Key")).toBeInTheDocument();
    expect(screen.getByText("GCP Workload Identity")).toBeInTheDocument();
    expect(screen.getByText("AWS IAM")).toBeInTheDocument();
    expect(screen.getByText("Kubernetes")).toBeInTheDocument();
  });

  it("renders descriptions for each method", () => {
    render(<IdentityMethodSelector value="key" onChange={() => {}} />);

    expect(
      screen.getByText(/Ed25519 keypair/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Google Cloud service account/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/AWS IAM Role/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/K8s Service Account/)
    ).toBeInTheDocument();
  });

  it("has a radiogroup role on the container", () => {
    render(<IdentityMethodSelector value="key" onChange={() => {}} />);

    expect(screen.getByRole("radiogroup")).toBeInTheDocument();
  });

  it("has an accessible label on the radiogroup", () => {
    render(<IdentityMethodSelector value="key" onChange={() => {}} />);

    expect(screen.getByRole("radiogroup")).toHaveAttribute(
      "aria-label",
      "Identity method"
    );
  });

  it("marks the selected method as checked", () => {
    render(<IdentityMethodSelector value="key" onChange={() => {}} />);

    const radios = screen.getAllByRole("radio");
    expect(radios[0]).toHaveAttribute("aria-checked", "true");
    expect(radios[1]).toHaveAttribute("aria-checked", "false");
    expect(radios[2]).toHaveAttribute("aria-checked", "false");
    expect(radios[3]).toHaveAttribute("aria-checked", "false");
  });

  it("marks gcp method as checked when selected", () => {
    render(<IdentityMethodSelector value="gcp" onChange={() => {}} />);

    const radios = screen.getAllByRole("radio");
    expect(radios[0]).toHaveAttribute("aria-checked", "false");
    expect(radios[1]).toHaveAttribute("aria-checked", "true");
    expect(radios[2]).toHaveAttribute("aria-checked", "false");
    expect(radios[3]).toHaveAttribute("aria-checked", "false");
  });

  it("marks aws method as checked when selected", () => {
    render(<IdentityMethodSelector value="aws" onChange={() => {}} />);

    const radios = screen.getAllByRole("radio");
    expect(radios[2]).toHaveAttribute("aria-checked", "true");
  });

  it("marks k8s method as checked when selected", () => {
    render(<IdentityMethodSelector value="k8s" onChange={() => {}} />);

    const radios = screen.getAllByRole("radio");
    expect(radios[3]).toHaveAttribute("aria-checked", "true");
  });

  it("calls onChange with 'gcp' when GCP card is clicked", () => {
    const onChange = vi.fn();
    render(<IdentityMethodSelector value="key" onChange={onChange} />);

    fireEvent.click(screen.getByText("GCP Workload Identity"));
    expect(onChange).toHaveBeenCalledWith("gcp");
  });

  it("calls onChange with 'aws' when AWS card is clicked", () => {
    const onChange = vi.fn();
    render(<IdentityMethodSelector value="key" onChange={onChange} />);

    fireEvent.click(screen.getByText("AWS IAM"));
    expect(onChange).toHaveBeenCalledWith("aws");
  });

  it("calls onChange with 'k8s' when Kubernetes card is clicked", () => {
    const onChange = vi.fn();
    render(<IdentityMethodSelector value="key" onChange={onChange} />);

    fireEvent.click(screen.getByText("Kubernetes"));
    expect(onChange).toHaveBeenCalledWith("k8s");
  });

  it("calls onChange with 'key' when Cryptographic Key card is clicked", () => {
    const onChange = vi.fn();
    render(<IdentityMethodSelector value="gcp" onChange={onChange} />);

    fireEvent.click(screen.getByText("Cryptographic Key"));
    expect(onChange).toHaveBeenCalledWith("key");
  });

  it("renders exactly 4 radio buttons", () => {
    render(<IdentityMethodSelector value="key" onChange={() => {}} />);

    expect(screen.getAllByRole("radio")).toHaveLength(4);
  });
});
