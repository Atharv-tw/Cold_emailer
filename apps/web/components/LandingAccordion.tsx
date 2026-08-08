"use client";

import { useState } from "react";

function Item({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="landing-faq-item">
      <button
        type="button"
        className="landing-faq-trigger"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <span>{q}</span>
        <span
          className="landing-faq-icon"
          style={{ transform: open ? "rotate(45deg)" : "rotate(0deg)" }}
        >
          +
        </span>
      </button>
      <div
        className="landing-faq-body"
        style={{
          gridTemplateRows: open ? "1fr" : "0fr",
        }}
      >
        <div style={{ overflow: "hidden" }}>
          <p className="text-sm text-muted" style={{ padding: "0 0 1.25rem" }}>
            {a}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function LandingAccordion({
  items,
}: {
  items: { q: string; a: string }[];
}) {
  return (
    <div className="landing-faq-list">
      {items.map((item) => (
        <Item key={item.q} q={item.q} a={item.a} />
      ))}
    </div>
  );
}
