"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { ApiError, apiFetch } from "@/lib/api";
import { labelForGiftId } from "@/lib/gift-catalog";

type CreatedOrder = {
  id: number;
  gift_id: string;
  recipient_name: string;
  recipient_email: string | null;
  shipping_address: string | null;
  status: string;
  checkout_url: string | null;
};

type ImportError = {
  row: number;
  message: string;
};

// Google Sheets "Download as CSV" is often registered as an Excel CSV
// (`application/vnd.ms-excel`). A text/csv-only filter leaves that file
// visible in the dialog but not selectable.
const CSV_ACCEPT =
  ".csv,text/csv,application/csv,text/comma-separated-values,text/x-csv,text/plain,application/vnd.ms-excel";

const WORKBOOK_EXTENSIONS = [".xlsx", ".xlsm", ".xls", ".numbers", ".ods"];

const EXCEL_SAVE_AS =
  "In Excel choose File → Save As and pick CSV UTF-8 (Comma delimited) (*.csv). Older Excel lists this as CSV (Comma delimited) (*.csv).";
const SHEETS_DOWNLOAD =
  "In Google Sheets choose File → Download → Comma-separated values (.csv).";

const CSV_SAVE_HINT = `${EXCEL_SAVE_AS} ${SHEETS_DOWNLOAD} You can import another file after this one.`;

function workbookError(filename: string): string {
  const name = filename.trim().toLowerCase();
  if (name.endsWith(".numbers")) {
    return "This is an Apple Numbers spreadsheet, not a CSV. In Numbers choose File → Export To → CSV, then upload that file.";
  }
  if (name.endsWith(".ods")) {
    return `This is a spreadsheet workbook (.ods), not a CSV. Save it as Text CSV (.csv), then upload that file. ${EXCEL_SAVE_AS} ${SHEETS_DOWNLOAD}`;
  }
  const extension = [".xlsx", ".xlsm", ".xls"].find((suffix) => name.endsWith(suffix));
  const labeled = extension ? ` (${extension})` : "";
  return `This is an Excel workbook${labeled}, not a CSV. Upload the .csv you save, not the workbook. ${EXCEL_SAVE_AS} ${SHEETS_DOWNLOAD} You can import another file after this one.`;
}

export default function ImportOrdersPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const dragDepth = useRef(0);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rowErrors, setRowErrors] = useState<ImportError[]>([]);
  const [created, setCreated] = useState<CreatedOrder[] | null>(null);
  const [batchCheckoutUrl, setBatchCheckoutUrl] = useState<string | null>(null);

  const withAddress = useMemo(
    () => (created ?? []).filter((order) => Boolean(order.shipping_address)),
    [created],
  );
  const needsAddress = useMemo(
    () => (created ?? []).filter((order) => !order.shipping_address),
    [created],
  );

  function chooseFile(next: File | null) {
    setCreated(null);
    setBatchCheckoutUrl(null);
    setRowErrors([]);
    if (!next) {
      setFile(null);
      setError(null);
      return;
    }
    const name = next.name.trim().toLowerCase();
    if (WORKBOOK_EXTENSIONS.some((ext) => name.endsWith(ext))) {
      setFile(null);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
      setError(workbookError(name));
      return;
    }
    setFile(next);
    setError(null);
  }

  async function downloadCsv(kind: "template" | "example") {
    setError(null);
    try {
      const blob = await apiFetch<Blob>(`/gift-orders/import/${kind}`, {
        responseType: "blob",
        errorMessage: `Unable to download ${kind}.`,
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download =
        kind === "template" ? "cookie-orders-template.csv" : "cookie-orders-example.csv";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (downloadError) {
      setError(
        downloadError instanceof Error ? downloadError.message : `Unable to download ${kind}.`,
      );
    }
  }

  async function upload() {
    if (!file) {
      setError("Choose a CSV file to upload.");
      return;
    }
    setUploading(true);
    setError(null);
    setRowErrors([]);
    setCreated(null);
    setBatchCheckoutUrl(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const data = await apiFetch<{
        created?: CreatedOrder[];
        batch_checkout_url?: string | null;
      }>("/gift-orders/import", {
        method: "POST",
        body,
        errorMessage: "Unable to import CSV.",
      });

      setCreated(data.created ?? []);
      setBatchCheckoutUrl(data.batch_checkout_url ?? null);
      setFile(null);
    } catch (uploadError) {
      if (uploadError instanceof ApiError) {
        const detail = uploadError.detail;
        if (typeof detail === "object" && detail !== null && "errors" in detail) {
          const validation = detail as { message?: string; errors?: ImportError[] };
          setRowErrors(validation.errors ?? []);
          setError(validation.message ?? uploadError.message);
          return;
        }
      }
      setError(uploadError instanceof Error ? uploadError.message : "Unable to import CSV.");
    } finally {
      setUploading(false);
      // Clearing the control lets the next pick register, including a Google
      // Sheets re-download that kept the same filename.
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  }

  return (
    <>
      <PageHeader
        title="Import cookie orders"
        description="Upload a CSV to create multiple cookie orders at once. Leave street/city/state/ZIP blank to email the recipient for shipping after you authorize payment."
        action={
          <Link
            href="/orders"
            className="rounded-full border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-espresso shadow-sm hover:bg-stone-50"
          >
            Back to orders
          </Link>
        }
      />

      <div className="space-y-6">
        <section className="rounded-2xl border border-stone-200/90 bg-white/90 p-5 shadow-sm">
          <h2 className="text-base font-semibold text-espresso">CSV format</h2>
          <p className="mt-1 text-sm text-stone-600">
            Keep the header names below. In <strong>Cookies</strong>, type <strong>4</strong> or{" "}
            <strong>12</strong>. Do not put that note in the header. A column named{" "}
            <span className="font-medium text-espresso">Number of Cookies (4 or 12)</span> is
            rejected. Company is optional. Street, city, state, and ZIP are optional together.
          </p>
          <p className="mt-2 text-xs text-stone-500">
            The template download starts with a one-line reminder, then this header. You can
            delete the reminder; import skips it. Cookie count and Number of cookies also work
            as that column name, as long as nothing else is added.
          </p>
          <div className="mt-3 overflow-x-auto rounded-xl border border-stone-200 bg-cream/40">
            <pre className="px-4 py-3 text-xs text-stone-700 sm:text-sm">{`Name,Email,Cookies,Company,Street,Street2,City,State,Postal Code
Jane Smith,jane@example.com,4,,123 Main St,,Springfield,IL,62704
Bob Jones,bob@example.com,12,,,,,,`}</pre>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" variant="secondary" onClick={() => void downloadCsv("template")}>
              Download template
            </Button>
            <Button type="button" variant="secondary" onClick={() => void downloadCsv("example")}>
              Download example
            </Button>
          </div>
        </section>

        <section
          className={`rounded-2xl border bg-white/90 p-5 shadow-sm ${
            dragOver ? "border-wood bg-wood/5" : "border-stone-200/90"
          }`}
          onDragEnter={(event) => {
            event.preventDefault();
            dragDepth.current += 1;
            setDragOver(true);
          }}
          onDragOver={(event) => {
            event.preventDefault();
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            dragDepth.current -= 1;
            if (dragDepth.current <= 0) {
              dragDepth.current = 0;
              setDragOver(false);
            }
          }}
          onDrop={(event) => {
            event.preventDefault();
            dragDepth.current = 0;
            setDragOver(false);
            const dropped = Array.from(event.dataTransfer.files);
            const csv =
              dropped.find((item) => item.name.toLowerCase().endsWith(".csv")) ??
              dropped[0] ??
              null;
            chooseFile(csv);
          }}
        >
          <h2 className="text-base font-semibold text-espresso">Upload</h2>
          <p className="mt-1 text-sm text-stone-600">
            Rows with an address are charged together in one Stripe checkout. Rows without an
            address each get their own authorize-then-capture payment. {CSV_SAVE_HINT}
          </p>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <input
              ref={inputRef}
              type="file"
              accept={CSV_ACCEPT}
              className="block w-full text-sm text-stone-600 file:mr-3 file:rounded-full file:border-0 file:bg-wood/15 file:px-4 file:py-2 file:text-sm file:font-medium file:text-wood-dark hover:file:bg-wood/25"
              onClick={(event) => {
                // Empty the control before the dialog opens so choosing the same
                // downloaded filename (Google Sheets re-exports) fires onChange.
                event.currentTarget.value = "";
              }}
              onChange={(event) => {
                chooseFile(event.target.files?.[0] ?? null);
              }}
            />
            <Button type="button" disabled={uploading || !file} onClick={() => void upload()}>
              {uploading ? "Importing…" : "Import CSV"}
            </Button>
          </div>
          {file ? (
            <p className="mt-2 text-sm text-stone-600">
              Ready to import <span className="font-medium text-espresso">{file.name}</span>
            </p>
          ) : (
            <p className="mt-2 text-xs text-stone-500">Or drop a CSV file here.</p>
          )}
        </section>

        {error ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            <p>{error}</p>
            {rowErrors.length > 0 ? (
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {rowErrors.map((rowError, index) => (
                  <li key={`${rowError.row}-${index}`}>
                    {rowError.row > 0 ? `Row ${rowError.row}: ` : null}
                    {rowError.message}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        {created ? (
          <section className="rounded-2xl border border-emerald-200/80 bg-emerald-50/60 p-5 shadow-sm">
            <h2 className="text-base font-semibold text-espresso">
              Created {created.length} order{created.length === 1 ? "" : "s"}
            </h2>

            {batchCheckoutUrl && withAddress.length > 0 ? (
              <div className="mt-4 rounded-xl border border-emerald-200/80 bg-white px-4 py-4">
                <p className="text-sm text-stone-600">
                  {withAddress.length} order{withAddress.length === 1 ? "" : "s"} with an address 
                  pay once for all of them.
                </p>
                <p className="mt-1 text-xs text-stone-500">
                  Have a code? Enter it on the Stripe checkout page.
                </p>
                <a
                  href={batchCheckoutUrl}
                  className="mt-3 inline-flex rounded-full bg-wood px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-wood-dark"
                >
                  Pay {withAddress.length} order{withAddress.length === 1 ? "" : "s"} together
                </a>
                <ul className="mt-4 divide-y divide-stone-100 border-t border-stone-100">
                  {withAddress.map((order) => (
                    <li key={order.id} className="flex items-center justify-between gap-3 py-2">
                      <div>
                        <div className="text-sm font-medium text-espresso">
                          <Link href={`/orders/${order.id}`} className="hover:underline">
                            {order.recipient_name}
                          </Link>
                        </div>
                        <div className="text-xs text-stone-500">
                          {order.recipient_email} · {labelForGiftId(order.gift_id)}
                        </div>
                      </div>
                      <Link
                        href={`/orders/${order.id}`}
                        className="text-xs font-medium text-stone-600 hover:underline"
                      >
                        View
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {needsAddress.length > 0 ? (
              <div className="mt-4">
                <p className="text-sm text-stone-600">
                  {needsAddress.length} order{needsAddress.length === 1 ? "" : "s"} need an address
                  from the recipient authorize each separately, then we email them for shipping.
                </p>
                <p className="mt-1 text-xs text-stone-500">
                  Have a code? Enter it on the Stripe checkout page.
                </p>
                <ul className="mt-3 divide-y divide-emerald-100/80 overflow-hidden rounded-xl border border-emerald-200/70 bg-white">
                  {needsAddress.map((order) => (
                    <li
                      key={order.id}
                      className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div>
                        <div className="font-medium text-espresso">
                          <Link href={`/orders/${order.id}`} className="hover:underline">
                            {order.recipient_name}
                          </Link>
                        </div>
                        <div className="text-xs text-stone-500">
                          {order.recipient_email} · {labelForGiftId(order.gift_id)}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Link
                          href={`/orders/${order.id}`}
                          className="rounded-full border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-espresso hover:bg-stone-50"
                        >
                          View
                        </Link>
                        {order.checkout_url ? (
                          <a
                            href={order.checkout_url}
                            className="rounded-full bg-wood px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-wood-dark"
                          >
                            Authorize payment
                          </a>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>
        ) : null}
      </div>
    </>
  );
}
