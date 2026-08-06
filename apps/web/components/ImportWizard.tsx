"use client";

import { useRef, useState, useTransition } from "react";

import { commitImport, previewImport } from "@/app/desktop/(app)/targets/import-actions";
import type {
  ImportCommitResult,
  ImportPreview,
  ImportRow,
  ImportRowStatus,
} from "@/lib/types";

/**
 * Upload → review → import.
 *
 * The file stays in the browser between steps and is re-sent each time: the
 * API re-reads it on commit rather than trusting the rows shown here, so this
 * component's job is only to show the verdict and let the mapping be corrected,
 * never to be the source of what gets saved.
 */

const STATUS_LABEL: Record<ImportRowStatus, string> = {
  ok: "Ready",
  needs_hook: "Needs a reason",
  duplicate: "Already on your list",
  suppressed: "Do-not-contact",
  invalid: "No valid email",
};

function buildForm(file: File, mapping: Record<string, string>): FormData {
  const form = new FormData();
  form.append("file", file);
  const chosen: Record<string, string> = {};
  for (const [header, field] of Object.entries(mapping)) {
    if (field) chosen[header] = field;
  }
  form.append("mapping", JSON.stringify(chosen));
  return form;
}

export default function ImportWizard() {
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ImportCommitResult | null>(null);
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();

  function runPreview(chosenFile: File, chosenMapping: Record<string, string>) {
    setError("");
    setResult(null);
    startTransition(async () => {
      try {
        const next = await previewImport(buildForm(chosenFile, chosenMapping));
        setPreview(next);
        setMapping(next.mapping);
      } catch (exception) {
        setPreview(null);
        setError(exception instanceof Error ? exception.message : "Could not read that file.");
      }
    });
  }

  function onFileChosen(event: React.ChangeEvent<HTMLInputElement>) {
    const chosen = event.target.files?.[0] ?? null;
    setFile(chosen);
    setPreview(null);
    setResult(null);
    setError("");
    if (chosen) runPreview(chosen, {});
  }

  function commit() {
    if (!file) return;
    setError("");
    startTransition(async () => {
      try {
        setResult(await commitImport(buildForm(file, mapping)));
        setPreview(null);
      } catch (exception) {
        setError(exception instanceof Error ? exception.message : "Could not import them.");
      }
    });
  }

  function reset() {
    setFile(null);
    setPreview(null);
    setMapping({});
    setResult(null);
    setError("");
    if (fileInput.current) fileInput.current.value = "";
  }

  const summary = preview?.summary;
  const emailUnmapped = preview?.unmapped_required.includes("email") ?? false;

  return (
    <div className="stack">
      {error && <p className="error">{error}</p>}

      {!result && (
        <section>
          <label>
            Choose a CSV or Excel file
            <input
              ref={fileInput}
              type="file"
              accept=".csv,.tsv,.txt,.xlsx,.xlsm"
              onChange={onFileChosen}
              disabled={pending}
            />
          </label>
          {pending && !preview && <p className="muted">Reading the file…</p>}
        </section>
      )}

      {preview && !result && (
        <>
          <section>
            <h2>Match the columns</h2>
            <p className="muted">
              We guessed which column is which. Change anything that is wrong,
              then re-check.
            </p>
            <div className="map-grid">
              {preview.headers.map((header) => (
                <label key={header} className="map-row">
                  <span className="map-header">{header}</span>
                  <select
                    value={mapping[header] ?? ""}
                    onChange={(event) =>
                      setMapping({ ...mapping, [header]: event.target.value })
                    }
                  >
                    <option value="">— ignore —</option>
                    {preview.fields.map((field) => (
                      <option key={field.key} value={field.key}>
                        {field.label}
                        {field.required ? " (required)" : ""}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <div>
              <button
                type="button"
                className="quiet"
                onClick={() => file && runPreview(file, mapping)}
                disabled={pending}
              >
                {pending ? "Re-checking…" : "Re-check with this mapping"}
              </button>
            </div>
            {emailUnmapped && (
              <p className="error">
                No column is mapped to Email. Map one — without it there is
                nobody to write to.
              </p>
            )}
          </section>

          {summary && (
            <section>
              <h2>What is in the file</h2>
              <p className="muted">
                {summary.total} row{summary.total === 1 ? "" : "s"} ·{" "}
                <strong>{summary.importable} ready to import</strong>
                {summary.needs_hook > 0 && ` · ${summary.needs_hook} still need a reason`}
                {summary.duplicates > 0 && ` · ${summary.duplicates} already on your list`}
                {summary.suppressed > 0 && ` · ${summary.suppressed} on do-not-contact`}
                {summary.invalid > 0 && ` · ${summary.invalid} without a valid email`}
              </p>
            </section>
          )}

          <section>
            <PreviewTable rows={preview.rows} />
          </section>

          <section>
            <button
              type="button"
              onClick={commit}
              disabled={pending || !summary || summary.importable === 0}
            >
              {pending
                ? "Importing…"
                : `Import ${summary?.importable ?? 0} contact${
                    summary?.importable === 1 ? "" : "s"
                  }`}
            </button>
            <p className="muted">
              Rows that are duplicates, suppressed, or missing an email are
              skipped. Rows missing only a reason are imported — you add the
              reason before writing to them.
            </p>
          </section>
        </>
      )}

      {result && (
        <section>
          <h2>Imported</h2>
          <p className="ok">
            {result.created} contact{result.created === 1 ? "" : "s"} added.
          </p>
          {result.skipped > 0 && (
            <p className="muted">
              {result.skipped} skipped
              {Object.keys(result.skipped_reasons).length > 0 &&
                ` — ${Object.entries(result.skipped_reasons)
                  .map(([reason, count]) => `${count} ${reason.replace(/_/g, " ")}`)
                  .join(", ")}`}
              .
            </p>
          )}
          <div>
            <button type="button" className="quiet" onClick={reset}>
              Import another list
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

function PreviewTable({ rows }: { rows: ImportRow[] }) {
  if (rows.length === 0) return <p className="muted">No rows to show.</p>;
  return (
    <div className="table-scroll">
      <table className="preview">
        <thead>
          <tr>
            <th>#</th>
            <th>Name</th>
            <th>Email</th>
            <th>Company</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.index} className={row.importable ? "" : "row-skip"}>
              <td className="muted">{row.index}</td>
              <td>{row.name || <span className="muted">—</span>}</td>
              <td>{row.email || <span className="muted">—</span>}</td>
              <td>{row.company || <span className="muted">—</span>}</td>
              <td>
                <span className={`pill pill-${row.status}`}>{STATUS_LABEL[row.status]}</span>
                {row.issues.length > 0 && (
                  <span className="muted"> · {row.issues[0]}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
