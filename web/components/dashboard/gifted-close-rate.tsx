import { StatCard } from "@/components/ui/stat-card";

export type GiftedCloseRateCounts = {
  gifted_won: number;
  gifted_lost: number;
  ungifted_won: number;
  ungifted_lost: number;
};

function closeRatePercent(won: number, lost: number): number | null {
  if (won + lost === 0) {
    return null;
  }
  return Math.round((won / (won + lost)) * 100);
}

function outcomeHint(won: number, lost: number): string {
  if (won + lost === 0) {
    return "Not enough outcomes";
  }
  return `${won} won / ${lost} lost`;
}

export function GiftedCloseRate({
  gifted_won,
  gifted_lost,
  ungifted_won,
  ungifted_lost,
}: GiftedCloseRateCounts) {
  const giftedRate = closeRatePercent(gifted_won, gifted_lost);
  const ungiftedRate = closeRatePercent(ungifted_won, ungifted_lost);

  return (
    <section className="mt-6 rounded-2xl border border-stone-200/90 bg-white/80 p-6 shadow-sm">
      <h2 className="font-display text-xl text-espresso">Gifted vs ungifted</h2>
      <p className="mt-2 text-sm text-stone-600">
        Close rate for prospects who received cookies versus those who did not. Open
        deals are not included.
      </p>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <StatCard
          label="Gifted close rate"
          value={giftedRate !== null ? `${giftedRate}%` : "—"}
          hint={outcomeHint(gifted_won, gifted_lost)}
        />
        <StatCard
          label="Ungifted close rate"
          value={ungiftedRate !== null ? `${ungiftedRate}%` : "—"}
          hint={outcomeHint(ungifted_won, ungifted_lost)}
        />
      </div>
    </section>
  );
}
