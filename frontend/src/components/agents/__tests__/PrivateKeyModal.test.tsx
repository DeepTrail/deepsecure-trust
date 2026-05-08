import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PrivateKeyModal } from "../PrivateKeyModal";

const PROPS = {
  agentId: "test-agent-001",
  publicKey: "dGVzdC1wdWJsaWMta2V5LWJhc2U2NA==",
  privateKey: "dGVzdC1wcml2YXRlLWtleS1iYXNlNjQ=",
  onDismiss: vi.fn(),
};

describe("PrivateKeyModal", () => {
  beforeEach(() => {
    PROPS.onDismiss.mockClear();

    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the modal with dialog role", () => {
    render(<PrivateKeyModal {...PROPS} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("displays the agent ID", () => {
    render(<PrivateKeyModal {...PROPS} />);
    expect(screen.getByText("test-agent-001")).toBeInTheDocument();
  });

  it("displays the public key (truncated with full key in title)", () => {
    render(<PrivateKeyModal {...PROPS} />);
    const el = screen.getByTitle(PROPS.publicKey);
    expect(el).toBeInTheDocument();
    expect(el.textContent).toContain("...");
  });

  it("displays the private key", () => {
    render(<PrivateKeyModal {...PROPS} />);
    expect(screen.getByTestId("private-key-display")).toHaveTextContent(
      PROPS.privateKey
    );
  });

  it("shows the warning message", () => {
    render(<PrivateKeyModal {...PROPS} />);
    expect(
      screen.getByText(/this private key will not be shown again/i)
    ).toBeInTheDocument();
  });

  it("has Close button disabled initially", () => {
    render(<PrivateKeyModal {...PROPS} />);
    const closeButton = screen.getByRole("button", { name: /close/i });
    expect(closeButton).toBeDisabled();
  });

  it("enables Close button after checking the confirmation checkbox", () => {
    render(<PrivateKeyModal {...PROPS} />);

    const checkbox = screen.getByTestId("confirm-checkbox");
    fireEvent.click(checkbox);

    const closeButton = screen.getByRole("button", { name: /close/i });
    expect(closeButton).toBeEnabled();
  });

  it("disables Close button when checkbox is unchecked", () => {
    render(<PrivateKeyModal {...PROPS} />);

    const checkbox = screen.getByTestId("confirm-checkbox");
    fireEvent.click(checkbox);
    fireEvent.click(checkbox);

    const closeButton = screen.getByRole("button", { name: /close/i });
    expect(closeButton).toBeDisabled();
  });

  it("calls onDismiss when Close is clicked after confirmation", () => {
    render(<PrivateKeyModal {...PROPS} />);

    fireEvent.click(screen.getByTestId("confirm-checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    expect(PROPS.onDismiss).toHaveBeenCalledOnce();
  });

  it("does not call onDismiss when Close is clicked without confirmation", () => {
    render(<PrivateKeyModal {...PROPS} />);
    const closeButton = screen.getByRole("button", { name: /close/i });

    expect(closeButton).toBeDisabled();
    expect(PROPS.onDismiss).not.toHaveBeenCalled();
  });

  it("copies private key to clipboard when copy button is clicked", async () => {
    render(<PrivateKeyModal {...PROPS} />);

    const copyButton = screen.getByRole("button", { name: /copy private key/i });
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        PROPS.privateKey
      );
    });
  });

  it("shows 'Copied!' text after copying", async () => {
    render(<PrivateKeyModal {...PROPS} />);

    const copyTextButton = screen.getByRole("button", { name: /copy to clipboard/i });
    fireEvent.click(copyTextButton);

    await waitFor(() => {
      expect(screen.getByText("Copied!")).toBeInTheDocument();
    });
  });

  it("renders the download button", () => {
    render(<PrivateKeyModal {...PROPS} />);
    expect(
      screen.getByRole("button", { name: /download as file/i })
    ).toBeInTheDocument();
  });

  it("triggers file download when download button is clicked", () => {
    const createObjectURL = vi.fn().mockReturnValue("blob:test");
    const revokeObjectURL = vi.fn();
    Object.assign(URL, { createObjectURL, revokeObjectURL });

    const clickSpy = vi.fn();
    const createElementOrig = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const el = createElementOrig(tag);
      if (tag === "a") {
        Object.defineProperty(el, "click", { value: clickSpy });
      }
      return el;
    });

    render(<PrivateKeyModal {...PROPS} />);

    fireEvent.click(screen.getByRole("button", { name: /download as file/i }));

    expect(createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:test");
  });

  it("shows the confirmation checkbox label", () => {
    render(<PrivateKeyModal {...PROPS} />);
    expect(
      screen.getByText("I have saved my private key")
    ).toBeInTheDocument();
  });

  it("has title 'Agent Keypair Generated'", () => {
    render(<PrivateKeyModal {...PROPS} />);
    expect(screen.getByText("Agent Keypair Generated")).toBeInTheDocument();
  });
});
