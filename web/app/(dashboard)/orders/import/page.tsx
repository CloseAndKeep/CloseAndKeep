"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { getApiBaseUrl } from "@/lib/api";
import { labelForGiftId } from "@/lib/mock-data";

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

export default function ImportOrdersPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rowErrors, setRowErrors] = useState<ImportError[]>([]);
  const [created, setCreated] = useState<CreatedOrder[] | null>(null);

  async function downloadCsv(kind: "template" | "example") {
    setError(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/gift-orders/import/${kind}`, {
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error(`Unable to download ${kind}.`);
      }
      const blob = await response.blob();
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
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch(`${getApiBaseUrl()}/gift-orders/import`, {
        method: "POST",
        credentials: "include",
        body,
      });
      const data = (await response.json()) as {
        detail?: string | { message?: string; errors?: ImportError[] };
        created?: CreatedOrder[];
        errors?: ImportError[];
      };

      if (!response.ok) {
        if (typeof data.detail === "object" && data.detail?.errors) {
          setRowErrors(data.detail.errors);
          setError(data.detail.message ?? "CSV validation failed.");
        } else {
          setError(
            typeof data.detail === "string" ? data.detail : "Unable to import CSV.",
          );
        }
        return;
      }

      setCreated(data.created ?? []);
      setFile(null);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Unable to import CSV.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Import cookie orders"
        description="Upload a CSV to create multiple cookie orders at once. Leave Address blank to email the recipient for shipping after you authorize payment."
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
            Include a header row. Cookies must be <strong>1</strong>, <strong>4</strong>, or{" "}
            <strong>12</strong>. Address is optional.
          </p>
          <div className="mt-3 overflow-x-auto rounded-xl border border-stone-200 bg-cream/40">
            <pre className="px-4 py-3 text-xs text-stone-700 sm:text-sm">{`Name,Email,Cookies,Address
Jane Smith,jane@example.com,4,"123 Main St, Springfield, IL 62704"
Bob Jones,bob@example.com,1,`}</pre>
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

        <section className="rounded-2xl border border-stone-200/90 bg-white/90 p-5 shadow-sm">
          <h2 className="text-base font-semibold text-espresso">Upload</h2>
          <p className="mt-1 text-sm text-stone-600">
            After import, complete Stripe checkout for each order. Rows without an address
            authorize payment first; we email the recipient for shipping, then charge.
          </p>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <input
              ref={inputRef}
              type="file"
              accept=".csv,text/csv"
              className="block w-full text-sm text-stone-600 file:mr-3 file:rounded-full file:border-0 file:bg-wood/15 file:px-4 file:py-2 file:text-sm file:font-medium file:text-wood-dark hover:file:bg-wood/25"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setError(null);
                setRowErrors([]);
              }}
            />
            <Button type="button" disabled={uploading || !file} onClick={() => void upload()}>
              {uploading ? "Importing…" : "Import CSV"}
            </Button>
          </div>
          {file ? (
            <p className="mt-2 text-xs text-stone-500">Selected: {file.name}</p>
          ) : null}
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
            <p className="mt-1 text-sm text-stone-600">
              Pay each order below. You can also finish payment later from the order detail page.
            </p>
            <ul className="mt-4 divide-y divide-emerald-100/80 overflow-hidden rounded-xl border border-emerald-200/70 bg-white">
              {created.map((order) => (
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
                      {order.recipient_email} · {labelForGiftId(order.gift_id)} ·{" "}
                      {order.shipping_address
                        ? "Address on file"
                        : "Will request address after payment"}
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
                        Pay now
                      </a>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    </>
  );
}
