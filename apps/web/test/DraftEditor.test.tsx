import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const generateDraft = vi.fn();
vi.mock("@/app/desktop/(app)/dashboard/actions", () => ({
  generateDraft: (...args: unknown[]) => generateDraft(...args),
  saveDraft: vi.fn(),
  scheduleSend: vi.fn(),
  sendNow: vi.fn(),
  cancelScheduledSend: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
}));

import DraftEditor from "@/components/DraftEditor";
import type { Target } from "@/lib/types";

const target = {
  id: "t1",
  name: "Alex",
  email: "alex@example.com",
  company: "ExampleCorp",
  role: "Founder",
  target_type: "founder",
  company_type: "ai",
  timezone: "UTC",
  hook: "their post",
  intent: "internship",
  links: {},
  verification: { status: "valid" },
  status: "active",
  status_detail: "",
  touches_sent: 0,
  touches_remaining: 3,
  last_touch_at: null,
  can_send: true,
  blocked_reason: "",
  gmail_thread_url: "",
} as unknown as Target;

const templates = [
  { key: "specific_hook", name: "Specific hook", description: "Lead with the hook." },
];

function mount() {
  return render(
    <DraftEditor
      target={target}
      initial={null}
      templates={templates as never}
    />,
  );
}

describe("DraftEditor", () => {
  beforeEach(() => {
    generateDraft.mockReset();
    window.sessionStorage.setItem("gemini_api_key", "test-key");
  });

  it("shows that it is writing while the model is still thinking", async () => {
    // The bug this covers: setting the flag inside the transition meant it
    // painted only once the work was over, so a slow generate looked like a
    // button that did nothing.
    let finish: (value: unknown) => void = () => {};
    generateDraft.mockReturnValue(new Promise((resolve) => (finish = resolve)));

    mount();
    await userEvent.click(await screen.findByRole("button", { name: "Write it for me" }));

    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("Writing");
    expect(screen.getByRole("button", { name: "Writing…" })).toBeInTheDocument();

    finish({ ok: true, data: { subject: "S", body: "B", warnings: [], step: 1 } });
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
  });

  it("tells the user a rerun is the fix for a draft they do not like", async () => {
    mount();
    expect(
      await screen.findByText(/Each run writes a fresh draft/),
    ).toBeInTheDocument();
  });
});
