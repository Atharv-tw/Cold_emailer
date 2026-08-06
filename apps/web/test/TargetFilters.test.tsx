import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/targets",
}));

import TargetFilters from "@/components/TargetFilters";

describe("TargetFilters", () => {
  beforeEach(() => push.mockReset());

  it("puts a chosen facet into the url", async () => {
    render(<TargetFilters active={{}} />);
    await userEvent.click(screen.getByRole("button", { name: "Replied" }));
    expect(push).toHaveBeenCalledWith("/targets?status=replied");
  });

  it("carries a typed search into the url on submit", async () => {
    render(<TargetFilters active={{}} />);
    await userEvent.type(screen.getByLabelText("Search"), "acme");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(push).toHaveBeenCalledWith("/targets?q=acme");
  });

  it("keeps existing facets when a new one is added", async () => {
    render(<TargetFilters active={{ status: "active" }} />);
    await userEvent.click(screen.getByRole("button", { name: "Internship" }));
    const url = push.mock.calls.at(-1)?.[0] as string;
    expect(url).toContain("status=active");
    expect(url).toContain("intent=internship");
  });

  it("clears everything", async () => {
    render(<TargetFilters active={{ status: "active", q: "acme" }} />);
    await userEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(push).toHaveBeenCalledWith("/targets");
  });
});
