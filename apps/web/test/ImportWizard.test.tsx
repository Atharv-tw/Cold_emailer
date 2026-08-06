import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ImportPreview } from "@/lib/types";

const previewImport = vi.fn();
const commitImport = vi.fn();
vi.mock("@/app/desktop/(app)/targets/import-actions", () => ({
  previewImport: (...args: unknown[]) => previewImport(...args),
  commitImport: (...args: unknown[]) => commitImport(...args),
}));

import ImportWizard from "@/components/ImportWizard";

const PREVIEW: ImportPreview = {
  headers: ["Name", "Email"],
  fields: [
    { key: "name", label: "Name", required: false },
    { key: "email", label: "Email", required: true },
    { key: "hook", label: "Why them", required: false },
  ],
  mapping: { Name: "name", Email: "email" },
  unmapped_required: [],
  rows: [
    { index: 1, name: "Alex", email: "alex@example.com", company: "Acme", role: "", status: "ok", issues: [], importable: true },
    { index: 2, name: "Sam", email: "sam@nope", company: "", role: "", status: "invalid", issues: ["not a valid email address"], importable: false },
  ],
  summary: { total: 2, importable: 1, needs_hook: 0, duplicates: 0, suppressed: 0, invalid: 1 },
};

function csv(): File {
  return new File(["Name,Email\nAlex,alex@example.com"], "leads.csv", { type: "text/csv" });
}

describe("ImportWizard", () => {
  beforeEach(() => {
    previewImport.mockReset();
    commitImport.mockReset();
  });

  it("shows a verdict for each row after a file is chosen", async () => {
    previewImport.mockResolvedValue(PREVIEW);
    render(<ImportWizard />);

    await userEvent.upload(screen.getByLabelText("Choose a CSV or Excel file"), csv());

    expect(await screen.findByText("alex@example.com")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("No valid email")).toBeInTheDocument();
    expect(previewImport).toHaveBeenCalledOnce();
  });

  it("only offers to import the rows that pass, and reports the result", async () => {
    previewImport.mockResolvedValue(PREVIEW);
    commitImport.mockResolvedValue({
      created: 1,
      skipped: 1,
      skipped_reasons: { invalid: 1 },
      summary: PREVIEW.summary,
    });
    render(<ImportWizard />);

    await userEvent.upload(screen.getByLabelText("Choose a CSV or Excel file"), csv());

    const button = await screen.findByRole("button", { name: /Import 1 contact/ });
    await userEvent.click(button);

    expect(await screen.findByText(/1 contact added/)).toBeInTheDocument();
    expect(commitImport).toHaveBeenCalledOnce();
  });
});
