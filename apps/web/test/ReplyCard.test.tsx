import { describe, expect, it } from "vitest";

import { split } from "@/components/ReplyCard";

/**
 * Splitting a reply from the copy of our own email underneath it.
 *
 * Worth testing directly rather than through the rendered card: the failure
 * mode is silent. Cutting in the wrong place does not throw, it just hides
 * part of what someone wrote behind a toggle nobody thinks to click.
 */
describe("split", () => {
  it("keeps a reply with nothing quoted intact", () => {
    const body = "Thanks for reaching out.\n\nBest,\nAtharv";
    expect(split(body)).toEqual({ text: body, quoted: "" });
  });

  it("cuts at the Gmail attribution line", () => {
    const body = [
      "We don't have an open internship right now.",
      "",
      "Best,",
      "Atharv",
      "",
      "On Tue, Aug 11, 2026 at 4:20 PM Atharv <a@example.com> wrote:",
      "> Hi Test,",
      "> Given your background...",
    ].join("\n");

    const { text, quoted } = split(body);
    expect(text).toBe(
      "We don't have an open internship right now.\n\nBest,\nAtharv",
    );
    expect(quoted).toContain("On Tue, Aug 11, 2026");
    expect(quoted).toContain("Given your background");
  });

  it("cuts at an Outlook header block", () => {
    const body = [
      "Not hiring at the moment.",
      "",
      "From: Atharv <a@example.com>",
      "Sent: Tuesday, August 11, 2026",
      "Subject: AI engineering intern",
    ].join("\n");

    expect(split(body).text).toBe("Not hiring at the moment.");
    expect(split(body).quoted).toContain("Sent: Tuesday");
  });

  it("cuts at the earliest marker when a reply quotes more than once", () => {
    // Both an attribution line and bare `>` quoting are present. Cutting at the
    // last match would leave the first quoted block sitting in the visible
    // text, which is the whole thing this is meant to remove.
    const body = [
      "Short answer: no.",
      "",
      "On Mon, Aug 10, 2026 Atharv wrote:",
      "> first quote",
      "",
      "> second quote",
    ].join("\n");

    expect(split(body).text).toBe("Short answer: no.");
    expect(split(body).quoted.startsWith("On Mon")).toBe(true);
  });

  it("survives an empty body", () => {
    expect(split("")).toEqual({ text: "", quoted: "" });
  });
});
