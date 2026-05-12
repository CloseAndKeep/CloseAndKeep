import { cn } from "@/lib/utils";

export function StatCard({
  label,
  value,
  hint,
  className,
}: {
  label: string;
  value: string | number;
  hint?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-stone-200/90 bg-white/80 p-5 shadow-sm",
        className
      )}
    >
      <p className="text-sm font-medium text-stone-500">{label}</p>
      <p className="mt-1 font-display text-3xl text-espresso">{value}</p>
      {hint ? <p className="mt-2 text-xs text-stone-500">{hint}</p> : null}
    </div>
  );
}
