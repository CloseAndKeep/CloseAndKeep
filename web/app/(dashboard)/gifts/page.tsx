import { PageHeader } from "@/components/ui/page-header";
import { gifts } from "@/lib/mock-data";
import Link from "next/link";

export default function GiftsPage() {
  return (
    <>
      <PageHeader
        title="Cookie options"
        description="Starting simple with cookie gifts first — inventory and backend sync can expand later."
      />

      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {gifts.map((g) => (
          <article
            key={g.id}
            className="flex flex-col overflow-hidden rounded-2xl border border-stone-200/90 bg-white shadow-sm"
          >
            <div
              className={`h-36 bg-gradient-to-br ${g.accent} flex items-center justify-center`}
            >
              <span className="font-display text-3xl text-espresso/80">{g.name.charAt(0)}</span>
            </div>
            <div className="flex flex-1 flex-col p-5">
              <h2 className="font-display text-lg text-espresso">{g.name}</h2>
              <p className="mt-2 flex-1 text-sm text-stone-600 leading-relaxed">
                {g.description}
              </p>
              <p className="mt-4 text-xs font-medium uppercase tracking-wide text-stone-400">
                {g.priceHint}
              </p>
              <Link
                href="/orders/new"
                className="mt-4 inline-flex justify-center rounded-full border border-stone-200 py-2 text-sm font-medium text-espresso hover:bg-stone-50"
              >
                Use in new order
              </Link>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
