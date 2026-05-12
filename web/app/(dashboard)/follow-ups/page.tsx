import Link from "next/link";
import { PageHeader } from "@/components/ui/page-header";
import { followUps, prospects } from "@/lib/mock-data";

export default function FollowUpsPage() {
  return (
    <>
      <PageHeader
        title="Follow-ups"
        description="Reminders tied to prospects — email delivery will connect to your provider later."
      />

      <ul className="space-y-4">
        {followUps.map((f) => {
          const prospect = prospects.find((x) => x.id === f.prospectId);
          return (
            <li
              key={f.id}
              className="rounded-2xl border border-stone-200/90 bg-white/90 p-5 shadow-sm"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-display text-lg text-espresso">{prospect?.name}</p>
                  <p className="text-sm text-stone-500">{prospect?.company}</p>
                </div>
                <time className="rounded-full bg-cream px-3 py-1 text-sm font-medium text-wood-dark">
                  {f.dueDate}
                </time>
              </div>
              <p className="mt-3 text-stone-700">{f.note}</p>
              <Link
                href={`/prospects/${f.prospectId}`}
                className="mt-3 inline-block text-sm font-medium text-wood-dark hover:underline"
              >
                Open prospect →
              </Link>
            </li>
          );
        })}
      </ul>
    </>
  );
}
