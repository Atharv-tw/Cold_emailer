import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const createTarget = vi.fn();
vi.mock("@/app/desktop/(app)/dashboard/actions", () => ({
  createTarget: (...args: unknown[]) => createTarget(...args),
}));

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

import TargetForm from "@/components/TargetForm";

describe("TargetForm", () => {
  beforeEach(() => {
    createTarget.mockReset();
    push.mockReset();
  });

  it("sends the answers and moves to the new target", async () => {
    createTarget.mockResolvedValue({ ok: true, data: { id: "t1" } });
    render(<TargetForm />);

    await userEvent.type(screen.getByPlaceholderText("alex@example.com"), "alex@example.com");
    await userEvent.click(screen.getByRole("button", { name: /Add them/ }));

    expect(createTarget).toHaveBeenCalledOnce();
    const payload = createTarget.mock.calls[0][0] as { email: string };
    expect(payload.email).toBe("alex@example.com");
    await waitFor(() => expect(push).toHaveBeenCalledWith("/targets/t1"));
  });

  it("keeps the button disabled until there is an email", () => {
    render(<TargetForm />);
    expect(screen.getByRole("button", { name: /Add them/ })).toBeDisabled();
  });

  it("shows the API's reason when adding is refused", async () => {
    // A refusal is a returned value, not a throw: a thrown one never reaches
    // the browser in a production build. See lib/result.ts.
    createTarget.mockResolvedValue({
      ok: false,
      error: { code: "own_address", message: "That is your own address." },
    });
    render(<TargetForm />);

    await userEvent.type(screen.getByPlaceholderText("alex@example.com"), "me@example.com");
    await userEvent.click(screen.getByRole("button", { name: /Add them/ }));

    expect(await screen.findByText("That is your own address.")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("sends an incomplete profile to the profile page instead of printing it", async () => {
    createTarget.mockResolvedValue({
      ok: false,
      error: {
        code: "profile_incomplete",
        message: "Your profile is not complete enough to write from yet.",
      },
    });
    render(<TargetForm />);

    await userEvent.type(screen.getByPlaceholderText("alex@example.com"), "alex@example.com");
    await userEvent.click(screen.getByRole("button", { name: /Add them/ }));

    const link = await screen.findByRole("link", { name: "Go to profile" });
    expect(link).toHaveAttribute("href", "/profile");
    expect(push).not.toHaveBeenCalled();
  });
});
