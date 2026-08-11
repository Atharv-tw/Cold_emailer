import { render, screen } from "@testing-library/react";
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Working from "@/components/Working";

describe("Working", () => {
  afterEach(() => vi.useRealTimers());

  it("announces itself rather than being a silent spinner", () => {
    render(<Working label="Writing" />);
    expect(screen.getByRole("status")).toHaveTextContent("Writing");
  });

  it("moves through the hints while the wait runs long", () => {
    vi.useFakeTimers();
    render(<Working label="Writing" hints={["first", "second"]} every={1000} />);
    expect(screen.getByRole("status")).toHaveTextContent("first");

    act(() => void vi.advanceTimersByTime(1000));
    expect(screen.getByRole("status")).toHaveTextContent("second");

    // Wraps rather than running out and going blank.
    act(() => void vi.advanceTimersByTime(1000));
    expect(screen.getByRole("status")).toHaveTextContent("first");
  });

  it("holds still when there is only one thing to say", () => {
    vi.useFakeTimers();
    render(<Working label="Reading" hints={["only"]} every={1000} />);
    act(() => void vi.advanceTimersByTime(5000));
    expect(screen.getByRole("status")).toHaveTextContent("only");
  });
});
