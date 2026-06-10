"use client";

import { useEffect } from "react";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // TODO: forward to an error-reporting service (e.g. Sentry) before launch.
    console.error(error);
  }, [error]);

  return (
    <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6">
      <h2 className="font-display text-lg text-rose-800">Something went wrong</h2>
      <p className="mt-2 text-sm text-rose-700">
        This page hit an unexpected error. Try again, and if it keeps happening, contact support.
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-4 inline-flex rounded-full bg-wood px-4 py-2 text-sm font-medium text-white hover:bg-wood-dark"
      >
        Try again
      </button>
    </div>
  );
}
