import { PageHeader } from "@/components/ui/page-header";
import { GiftOrderWizard } from "@/components/orders/gift-order-wizard";
import Link from "next/link";
import { Suspense } from "react";

export default function NewOrderPage() {
  return (
    <>
      <PageHeader
        title="New cookie order"
        description="Pick prospect and cookie count, then delivery details. Prefer a spreadsheet? Import a CSV instead."
        action={
          <Link
            href="/orders/import"
            className="rounded-full border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-espresso shadow-sm hover:bg-stone-50"
          >
            Import CSV
          </Link>
        }
      />
      <Suspense fallback={<p className="text-sm text-stone-500">Loading order form…</p>}>
        <GiftOrderWizard />
      </Suspense>
    </>
  );
}
