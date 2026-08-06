"use client";

import ImportWizard from "@/components/ImportWizard";
import Modal from "@/components/Modal";

export default function ImportModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Modal open={open} onClose={onClose} title="Import contacts" widthClassName="max-w-2xl">
      <p className="mb-4 text-sm text-muted">
        Every row is checked before anything is saved — duplicates, addresses you&rsquo;ve already
        stopped contacting, and rows missing required details are flagged before import. Importing
        adds people as drafts; nothing sends until you do it yourself, one email at a time.
      </p>
      <ImportWizard />
    </Modal>
  );
}
