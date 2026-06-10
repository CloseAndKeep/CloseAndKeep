export default function DashboardLoading() {
  return (
    <div className="space-y-4">
      <div className="h-8 w-48 animate-pulse rounded-lg bg-stone-200/70" />
      <div className="h-24 animate-pulse rounded-2xl bg-stone-200/50" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="h-24 animate-pulse rounded-2xl bg-stone-200/50" />
        ))}
      </div>
    </div>
  );
}
