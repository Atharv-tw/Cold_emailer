"use client";

import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";

import { submitPaymentProof } from "@/app/desktop/(app)/pool/purchase/actions";
import type { Billing } from "@/lib/types";

/**
 * Pay by UPI, then prove it.
 *
 * There is no payment gateway, so nothing here can tell whether money moved -
 * a person checks the screenshot later. That shapes the copy: every state has
 * to be honest that this is a human process with a delay, rather than
 * implying an instant unlock that is not coming.
 *
 * The QR is built from the UPI id and the amount rather than being an image
 * somebody uploaded, so the amount cannot drift out of step with the price the
 * server charges, and there is no file to keep in sync.
 */
export default function PurchasePanel({ billing }: { billing: Billing }) {
  const [file, setFile] = useState<File | null>(null);
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(billing.request_status === "pending");

  if (!billing.available) {
    return (
      <div className="dz-card">
        <h3>Not available yet</h3>
        <p className="text-muted">
          Payments are not set up on this deployment. Nothing to do here for now.
        </p>
      </div>
    );
  }

  if (done) {
    return (
      <div className="dz-card">
        <h3>Sent for review</h3>
        <p className="text-muted">
          Your screenshot is with us. Someone checks these by hand, so it is not instant.
          Access shows up on the pool page once it is approved — you do not need to do
          anything else, and paying again will not make it faster.
        </p>
      </div>
    );
  }

  // The UPI deep link every Indian payment app understands. `am` fixes the
  // amount so it is not typed by hand, and `cu` is required alongside it.
  const upiUrl =
    `upi://pay?pa=${encodeURIComponent(billing.upi_id)}` +
    `&pn=${encodeURIComponent(billing.payee_name || "Outreach")}` +
    `&am=${billing.price_inr}&cu=INR`;

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!file || busy) return;

    setBusy(true);
    setError("");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("upi_reference", reference);

    const result = await submitPaymentProof(formData);
    setBusy(false);
    if (result.ok) setDone(true);
    else setError(result.error.message || "That did not go through.");
  }

  return (
    // Two steps, so two columns once there is room for them: pay on the left,
    // prove it on the right. They stack below `lg` because the QR needs its
    // 196px and the form needs room to type in, and neither survives being
    // squeezed into half a phone. `items-start` keeps the short QR card its own
    // height instead of stretching it to match the taller form.
    <div className="grid items-start gap-4 md:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
      <div className="dz-card items-center gap-3 text-center">
        <h3>Pay ₹{billing.price_inr}</h3>
        <div className="rounded-2xl bg-white p-4">
          <QRCodeSVG value={upiUrl} size={196} />
        </div>
        <p className="text-muted">
          Scan with any UPI app, or pay{" "}
          <strong className="text-fg">{billing.upi_id}</strong> directly.
        </p>
        {/* The deep link only does anything on a device with a UPI app
            installed, which is the phone case - on a laptop it is a dead
            link, so it is not offered as the primary path. */}
        <a href={upiUrl} className="text-sm text-muted underline">
          Open a UPI app on this device
        </a>
      </div>

      <form onSubmit={onSubmit} className="dz-card gap-4">
        <div>
          <h3>Then send us the screenshot</h3>
          <p className="text-muted">
            Take a screenshot of the successful payment and upload it here.
          </p>
        </div>

        {/* Stated before the file picker, not after, and specific about what
            is in a UPI receipt. Somebody agreeing to share a payment
            screenshot should know it usually carries their UPI handle, their
            phone number and their bank. */}
        <p className="text-sm text-muted">
          Pressing Done emails the screenshot to us from your own Gmail account, so we
          can check the payment. A UPI receipt normally shows your UPI ID, your phone
          number and your bank. It is only used to confirm this payment.
        </p>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-fg">Payment screenshot</span>
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            required
          />
          <span className="text-xs text-muted">PNG, JPEG or WebP, up to 5 MB.</span>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-fg">
            Reference number <span className="text-muted">(optional)</span>
          </span>
          <input
            type="text"
            value={reference}
            onChange={(event) => setReference(event.target.value)}
            placeholder="UPI transaction ID, if you have it handy"
          />
          <span className="text-xs text-muted">
            Helps us match your payment if the screenshot is hard to read.
          </span>
        </label>

        {error && <p className="text-sm text-danger">{error}</p>}

        <div>
          <button type="submit" className="primary" disabled={!file || busy}>
            {busy ? "Sending…" : "Done"}
          </button>
        </div>
      </form>
    </div>
  );
}
