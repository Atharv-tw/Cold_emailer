"use client";

import { useState } from "react";

import NewEmailModal from "@/components/NewEmailModal";

export default function NewEmailButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        className="primary"
        style={{ borderRadius: "2rem", padding: "0.5rem 1.25rem", fontWeight: 600 }}
        onClick={() => setOpen(true)}
      >
        + New Email
      </button>
      <NewEmailModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}
