"use client";

import { useState } from "react";

import ImportModal from "@/components/ImportModal";

export default function ImportButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        className="secondary"
        style={{ borderRadius: "2rem", padding: "0.5rem 1.25rem", fontWeight: 600 }}
        onClick={() => setOpen(true)}
      >
        Import
      </button>
      <ImportModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}
