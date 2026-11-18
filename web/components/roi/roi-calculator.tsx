"use client";

import { useState } from "react";
import {
  DEFAULT_ROI_INPUTS,
  SENSITIVITY_VALUES,
  computeRoi,
  formatMoney,
  formatMultiple,
  formatNumber,
  formatRoiPercent,
  newBusinessSensitivity,
  retentionSensitivity,
  type NewBusinessInputs,
  type RetentionInputs,
  type RoiInputs,
} from "@/lib/roi-math";

const SENSITIVITY_VALUES_SET = new Set<number>(SENSITIVITY_VALUES);

type NumberFieldProps = {
  id: string;
  label: string;
  hint?: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  step?: string;
  /** Display as percent (0.2 → 20) */
  percent?: boolean;
};

function NumberField({
  id,
  label,
  hint,
  value,
  onChange,
  min = 0,
  step = "any",
  percent = false,
}: NumberFieldProps) {
  const display = percent ? value * 100 : value;
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-espresso">
        {label}
      </label>
      {hint ? <p className="mt-0.5 text-xs text-stone-500">{hint}</p> : null}
      <div className="relative mt-1.5">
        <input
          id={id}
          type="number"
          min={min}
          step={step}
          value={Number.isFinite(display) ? display : ""}
          onChange={(e) => {
            const raw = e.target.valueAsNumber;
            if (Number.isNaN(raw)) {
              onChange(0);
              return;
            }
            onChange(percent ? raw / 100 : raw);
          }}
          className="w-full rounded-xl border border-stone-200 bg-cream/50 px-3 py-2 text-sm text-espresso outline-none focus:border-wood"
        />
        {percent ? (
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-stone-400">
            %
          </span>
        ) : null}
      </div>
    </div>
  );
}

function ResultRow({
  label,
  value,
  emphasize,
}: {
  label: string;
  value: string;
  emphasize?: boolean;
}) {
  return (
    <div
      className={
        emphasize
          ? "flex items-baseline justify-between gap-4 border-t border-stone-200 pt-3"
          : "flex items-baseline justify-between gap-4"
      }
    >
      <span className="text-sm text-stone-600">{label}</span>
      <span
        className={
          emphasize
            ? "font-display text-lg text-espresso"
            : "text-sm font-medium text-espresso tabular-nums"
        }
      >
        {value}
      </span>
    </div>
  );
}

function SensitivityTable({
  title,
  valueHeader,
  incrementalHeader,
  rows,
  highlightValue,
}: {
  title: string;
  valueHeader: string;
  incrementalHeader: string;
  rows: ReturnType<typeof newBusinessSensitivity>;
  highlightValue: number;
}) {
  return (
    <div>
      <h3 className="font-display text-xl text-espresso">{title}</h3>
      <div className="mt-4 overflow-x-auto rounded-2xl border border-stone-200/90 bg-white/90">
        <table className="w-full min-w-[32rem] text-left text-sm">
          <thead>
            <tr className="border-b border-stone-100 text-stone-500">
              <th className="px-4 py-3 font-medium">{valueHeader}</th>
              <th className="px-4 py-3 font-medium">{incrementalHeader}</th>
              <th className="px-4 py-3 font-medium">Cookie cost</th>
              <th className="px-4 py-3 font-medium">Net</th>
              <th className="px-4 py-3 font-medium">ROI %</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const highlighted = row.value === highlightValue;
              return (
                <tr
                  key={row.value}
                  className={
                    highlighted
                      ? "bg-wood/10 text-espresso"
                      : "border-t border-stone-50 text-stone-700"
                  }
                >
                  <td className="px-4 py-2.5 tabular-nums font-medium">
                    {formatMoney(row.value)}
                    {highlighted ? (
                      <span className="ml-2 text-xs font-normal text-wood-dark">
                        your input
                      </span>
                    ) : null}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">
                    {formatMoney(row.incrementalPerUnit, 2)}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">
                    {formatMoney(row.costPerUnit)}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">
                    {formatMoney(row.netPerUnit, 2)}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">
                    {formatRoiPercent(row.roiRatio)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function RoiCalculator() {
  const [inputs, setInputs] = useState<RoiInputs>(DEFAULT_ROI_INPUTS);
  const result = computeRoi(inputs);

  const setNewBusiness = <K extends keyof NewBusinessInputs>(
    key: K,
    value: NewBusinessInputs[K],
  ) => {
    setInputs((prev) => ({
      ...prev,
      newBusiness: { ...prev.newBusiness, [key]: value },
    }));
  };

  const setRetention = <K extends keyof RetentionInputs>(
    key: K,
    value: RetentionInputs[K],
  ) => {
    setInputs((prev) => ({
      ...prev,
      retention: { ...prev.retention, [key]: value },
    }));
  };

  const nbSens = newBusinessSensitivity(
    inputs.newBusiness.closeRateLift,
    inputs.newBusiness.costPerGift,
  );
  const retSens = retentionSensitivity(
    inputs.retention.churnReduction,
    inputs.retention.costPerGift,
  );

  return (
    <div className="space-y-16">
      <section id="calculator" className="scroll-mt-24 space-y-10">
        <div className="grid gap-10 lg:grid-cols-2">
          <div className="space-y-4 rounded-3xl border border-stone-200/90 bg-white/90 p-6 shadow-sm sm:p-8">
            <h2 className="font-display text-2xl text-espresso">
              New business — sales conversion
            </h2>
            <p className="text-sm text-stone-500">
              Replace the example numbers with your team&apos;s figures.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              <NumberField
                id="nb-prospects"
                label="New deals / prospects this period"
                hint="Total demos in the evaluation period (year)"
                value={inputs.newBusiness.prospects}
                onChange={(v) => setNewBusiness("prospects", v)}
                step="1"
              />
              <NumberField
                id="nb-asp"
                label="Average sale price (ACV)"
                value={inputs.newBusiness.asp}
                onChange={(v) => setNewBusiness("asp", v)}
                step="1"
              />
              <NumberField
                id="nb-baseline"
                label="Baseline close rate (without cookies)"
                value={inputs.newBusiness.baselineClose}
                onChange={(v) => setNewBusiness("baselineClose", v)}
                percent
                step="0.1"
              />
              <NumberField
                id="nb-lift"
                label="Close-rate lift from cookies (points)"
                hint="Points added to baseline (20% + 2 pts = 22%)"
                value={inputs.newBusiness.closeRateLift}
                onChange={(v) => setNewBusiness("closeRateLift", v)}
                percent
                step="0.1"
              />
              <NumberField
                id="nb-pct"
                label="% of prospects sent cookies"
                hint="Strategic / higher-ASP prospects only"
                value={inputs.newBusiness.pctSent}
                onChange={(v) => setNewBusiness("pctSent", v)}
                percent
                step="1"
              />
              <NumberField
                id="nb-cost"
                label="Cost per cookie gift"
                hint="Cookies, address gathering, delivery, tip"
                value={inputs.newBusiness.costPerGift}
                onChange={(v) => setNewBusiness("costPerGift", v)}
                step="1"
              />
            </div>
          </div>

          <div className="space-y-3 rounded-3xl border border-stone-200/90 bg-cream/60 p-6 sm:p-8">
            <h3 className="font-display text-xl text-espresso">Estimated results</h3>
            <p className="text-xs text-stone-500">Estimate only — not a guarantee.</p>
            <div className="space-y-2.5">
              <ResultRow
                label="Prospects sent cookies"
                value={formatNumber(result.newBusiness.sent)}
              />
              <ResultRow
                label="Baseline deals won"
                value={formatNumber(result.newBusiness.baselineOutcome)}
              />
              <ResultRow
                label="Deals won with cookies"
                value={formatNumber(result.newBusiness.withCookiesOutcome)}
              />
              <ResultRow
                label="Incremental deals won"
                value={formatNumber(result.newBusiness.incrementalOutcome)}
              />
              <ResultRow
                label="Estimated incremental revenue"
                value={formatMoney(result.newBusiness.incrementalRevenue)}
              />
              <ResultRow
                label="Cookie investment"
                value={formatMoney(result.newBusiness.investment)}
              />
              <ResultRow
                label="Estimated net revenue impact"
                value={formatMoney(result.newBusiness.netRevenue)}
                emphasize
              />
              <ResultRow
                label="Estimated ROI %"
                value={formatRoiPercent(result.newBusiness.roiRatio)}
                emphasize
              />
              <ResultRow
                label="Estimated ROI multiple"
                value={formatMultiple(result.newBusiness.roiMultiple)}
              />
            </div>
          </div>
        </div>

        <div className="grid gap-10 lg:grid-cols-2">
          <div className="space-y-4 rounded-3xl border border-stone-200/90 bg-white/90 p-6 shadow-sm sm:p-8">
            <h2 className="font-display text-2xl text-espresso">
              Existing customers — retention
            </h2>
            <p className="text-sm text-stone-500">
              Model churn reduction for accounts you gift after the sale.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              <NumberField
                id="ret-customers"
                label="Number of existing customers"
                hint="Total active customers"
                value={inputs.retention.customers}
                onChange={(v) => setRetention("customers", v)}
                step="1"
              />
              <NumberField
                id="ret-value"
                label="Average customer value (annual)"
                hint="Lifetime / annual value, not ASP"
                value={inputs.retention.customerValue}
                onChange={(v) => setRetention("customerValue", v)}
                step="1"
              />
              <NumberField
                id="ret-churn"
                label="Baseline annual churn (without cookies)"
                value={inputs.retention.baselineChurn}
                onChange={(v) => setRetention("baselineChurn", v)}
                percent
                step="0.1"
              />
              <NumberField
                id="ret-reduction"
                label="Churn reduction from cookies (points)"
                hint="Points cut from churn (10% − 3 pts = 7%)"
                value={inputs.retention.churnReduction}
                onChange={(v) => setRetention("churnReduction", v)}
                percent
                step="0.1"
              />
              <NumberField
                id="ret-pct"
                label="% of customers sent cookies"
                hint="Strategic accounts"
                value={inputs.retention.pctSent}
                onChange={(v) => setRetention("pctSent", v)}
                percent
                step="1"
              />
              <NumberField
                id="ret-cost"
                label="Cost per cookie gift"
                hint="Cookies, packaging, shipping"
                value={inputs.retention.costPerGift}
                onChange={(v) => setRetention("costPerGift", v)}
                step="1"
              />
            </div>
          </div>

          <div className="space-y-3 rounded-3xl border border-stone-200/90 bg-cream/60 p-6 sm:p-8">
            <h3 className="font-display text-xl text-espresso">Estimated results</h3>
            <p className="text-xs text-stone-500">Estimate only — not a guarantee.</p>
            <div className="space-y-2.5">
              <ResultRow
                label="Customers sent cookies"
                value={formatNumber(result.retention.sent)}
              />
              <ResultRow
                label="Baseline customers churned"
                value={formatNumber(result.retention.baselineOutcome)}
              />
              <ResultRow
                label="Customers churned with cookies"
                value={formatNumber(result.retention.withCookiesOutcome)}
              />
              <ResultRow
                label="Customers retained"
                value={formatNumber(result.retention.incrementalOutcome)}
              />
              <ResultRow
                label="Estimated retained revenue"
                value={formatMoney(result.retention.incrementalRevenue)}
              />
              <ResultRow
                label="Cookie investment"
                value={formatMoney(result.retention.investment)}
              />
              <ResultRow
                label="Estimated net revenue impact"
                value={formatMoney(result.retention.netRevenue)}
                emphasize
              />
              <ResultRow
                label="Estimated ROI %"
                value={formatRoiPercent(result.retention.roiRatio)}
                emphasize
              />
              <ResultRow
                label="Estimated ROI multiple"
                value={formatMultiple(result.retention.roiMultiple)}
              />
            </div>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-3 rounded-3xl border border-stone-200/90 bg-white/90 p-6 shadow-sm sm:p-8">
            <h2 className="font-display text-2xl text-espresso">
              Combined program estimate
            </h2>
            <p className="text-xs text-stone-500">Estimate only — not a guarantee.</p>
            <div className="mt-4 space-y-2.5">
              <ResultRow
                label="Total cookie investment"
                value={formatMoney(result.combined.totalInvestment)}
              />
              <ResultRow
                label="Estimated total incremental revenue"
                value={formatMoney(result.combined.totalIncrementalRevenue)}
              />
              <ResultRow
                label="Estimated total net revenue impact"
                value={formatMoney(result.combined.totalNetRevenue)}
                emphasize
              />
              <ResultRow
                label="Estimated blended ROI %"
                value={formatRoiPercent(result.combined.blendedRoiRatio)}
                emphasize
              />
              <ResultRow
                label="Estimated blended ROI multiple"
                value={formatMultiple(result.combined.blendedRoiMultiple)}
              />
            </div>
          </div>

          <div className="space-y-3 rounded-3xl border border-wood/30 bg-wood/5 p-6 sm:p-8">
            <h2 className="font-display text-2xl text-espresso">
              Breakeven — the sweet spot
            </h2>
            <p className="text-sm text-stone-600">
              Above these thresholds, every dollar spent on cookie gifting returns
              more than a dollar of revenue. Figures are revenue-based (no margin
              assumption).
            </p>
            <div className="mt-4 space-y-2.5">
              <ResultRow
                label="Breakeven ASP (new business)"
                value={
                  result.breakeven.breakevenAsp === null
                    ? "n/a"
                    : formatMoney(result.breakeven.breakevenAsp)
                }
                emphasize
              />
              <ResultRow
                label="Breakeven customer value (retention)"
                value={
                  result.breakeven.breakevenCustomerValue === null
                    ? "n/a"
                    : formatMoney(result.breakeven.breakevenCustomerValue)
                }
                emphasize
              />
            </div>
          </div>
        </div>
      </section>

      <section id="sensitivity" className="scroll-mt-24 space-y-10">
        <div>
          <h2 className="font-display text-3xl text-espresso">
            Sensitivity analysis
          </h2>
          <p className="mt-2 max-w-2xl text-stone-600">
            Live-linked to your lift and cost inputs — see where deal size or
            customer value lands on the curve relative to breakeven.
          </p>
        </div>

        <SensitivityTable
          title="New business — ROI by average sale price"
          valueHeader="Average sale price"
          incrementalHeader="Incremental revenue / prospect"
          rows={nbSens}
          highlightValue={
            SENSITIVITY_VALUES_SET.has(inputs.newBusiness.asp)
              ? inputs.newBusiness.asp
              : -1
          }
        />
        <p className="text-sm text-stone-600">
          Breakeven ASP:{" "}
          <span className="font-medium text-espresso">
            {result.breakeven.breakevenAsp === null
              ? "n/a"
              : formatMoney(result.breakeven.breakevenAsp)}
          </span>
        </p>

        <SensitivityTable
          title="Retention — ROI by existing customer value"
          valueHeader="Avg. customer value"
          incrementalHeader="Retained revenue / customer"
          rows={retSens}
          highlightValue={
            SENSITIVITY_VALUES_SET.has(inputs.retention.customerValue)
              ? inputs.retention.customerValue
              : -1
          }
        />
        <p className="text-sm text-stone-600">
          Breakeven customer value:{" "}
          <span className="font-medium text-espresso">
            {result.breakeven.breakevenCustomerValue === null
              ? "n/a"
              : formatMoney(result.breakeven.breakevenCustomerValue)}
          </span>
        </p>
      </section>
    </div>
  );
}
