"use client";

import { useEffect, useState, type FormEvent } from "react";
import { cookiePacks, labelForGiftId } from "@/lib/gift-catalog";

export type StageRecipe = {
  stage_name: string;
  gift_id: string;
  note?: string | null;
};

const EMPTY_RECIPE: StageRecipe = {
  stage_name: "",
  gift_id: "cookies-4",
  note: "",
};

type StageRecipesProps = {
  recipes: StageRecipe[];
  saving: boolean;
  onSave: (recipes: StageRecipe[]) => Promise<void>;
};

export function StageRecipes({ recipes, saving, onSave }: StageRecipesProps) {
  const [drafts, setDrafts] = useState<StageRecipe[]>(recipes.length ? recipes : [EMPTY_RECIPE]);

  useEffect(() => {
    setDrafts(recipes.length ? recipes : [EMPTY_RECIPE]);
  }, [recipes]);

  function update(index: number, patch: Partial<StageRecipe>) {
    setDrafts((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const cleaned = drafts
      .map((row) => ({
        stage_name: row.stage_name.trim(),
        gift_id: row.gift_id,
        note: (row.note || "").trim() || null,
      }))
      .filter((row) => row.stage_name);
    if (!cleaned.length) return;
    await onSave(cleaned);
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className="space-y-3">
      <div>
        <p className="text-sm font-medium text-espresso">Stage recipes</p>
        <p className="mt-0.5 text-xs text-stone-500">
          Send a different pack when a deal hits Demo Completed, Closed Won, or Renewal (or any
          stage you add). Stage names match your CRM, ignoring case.
        </p>
      </div>

      <div className="space-y-3">
        {drafts.map((row, index) => (
          <div
            key={index}
            className="grid gap-2 rounded-xl border border-stone-200 bg-stone-50/60 p-3 sm:grid-cols-[1fr_auto_auto]"
          >
            <label className="block text-sm">
              <span className="text-stone-500">Stage name</span>
              <input
                className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2"
                value={row.stage_name}
                onChange={(e) => update(index, { stage_name: e.target.value })}
                placeholder="Demo Completed"
              />
            </label>
            <label className="block text-sm">
              <span className="text-stone-500">Pack</span>
              <select
                className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 sm:w-40"
                value={row.gift_id}
                onChange={(e) => update(index, { gift_id: e.target.value })}
              >
                {cookiePacks.map((pack) => (
                  <option key={pack.id} value={pack.id}>
                    {labelForGiftId(pack.id)}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-end">
              <button
                type="button"
                onClick={() => setDrafts((prev) => prev.filter((_, i) => i !== index))}
                disabled={drafts.length <= 1}
                className="rounded-full border border-stone-200 bg-white px-3 py-2 text-sm text-stone-600 hover:bg-stone-50 disabled:opacity-40"
              >
                Remove
              </button>
            </div>
            <label className="block text-sm sm:col-span-3">
              <span className="text-stone-500">Note override (optional)</span>
              <input
                className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2"
                value={row.note || ""}
                onChange={(e) => update(index, { note: e.target.value })}
                placeholder="Used when Cookie Note is blank"
              />
            </label>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setDrafts((prev) => [...prev, { ...EMPTY_RECIPE }])}
          className="rounded-full border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-espresso hover:bg-stone-50"
        >
          Add stage
        </button>
        <button
          type="submit"
          disabled={saving || !drafts.some((row) => row.stage_name.trim())}
          className="rounded-full bg-wood px-4 py-2 text-sm font-medium text-white hover:bg-wood-dark disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save recipes"}
        </button>
      </div>
    </form>
  );
}
