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
    createTarget.mockResolvedValue({ id: "t1" });
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
    createTarget.mockRejectedValue(new Error("That is your own address."));
    render(<TargetForm />);

    await userEvent.type(screen.getByPlaceholderText("alex@example.com"), "me@example.com");
    await userEvent.click(screen.getByRole("button", { name: /Add them/ }));

    expect(await screen.findByText("That is your own address.")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});
