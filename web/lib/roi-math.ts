/** CloseAndKeep ROI calculator math — faithful to the Excel workbook formulas. */

export type NewBusinessInputs = {
  prospects: number;
  asp: number;
  baselineClose: number;
  closeRateLift: number;
  pctSent: number;
  costPerGift: number;
};

export type RetentionInputs = {
  customers: number;
  customerValue: number;
  baselineChurn: number;
  churnReduction: number;
  pctSent: number;
  costPerGift: number;
};

export type RoiInputs = {
  newBusiness: NewBusinessInputs;
  retention: RetentionInputs;
};

export type SectionResults = {
  sent: number;
  baselineOutcome: number;
  withCookiesOutcome: number;
  incrementalOutcome: number;
  incrementalRevenue: number;
  investment: number;
  netRevenue: number;
  /** net / investment; null when investment is 0 */
  roiRatio: number | null;
  /** incrementalRevenue / investment; null when investment is 0 */
  roiMultiple: number | null;
};

export type CombinedResults = {
  totalInvestment: number;
  totalIncrementalRevenue: number;
  totalNetRevenue: number;
  blendedRoiRatio: number | null;
  blendedRoiMultiple: number | null;
};

export type BreakevenResults = {
  /** cost / closeRateLift; null when lift is 0 */
  breakevenAsp: number | null;
  /** cost / churnReduction; null when reduction is 0 */
  breakevenCustomerValue: number | null;
};

export type RoiComputation = {
  newBusiness: SectionResults;
  retention: SectionResults;
  combined: CombinedResults;
  breakeven: BreakevenResults;
};

export type SensitivityRow = {
  value: number;
  incrementalPerUnit: number;
  costPerUnit: number;
  netPerUnit: number;
  roiRatio: number | null;
};

/** Yellow-cell defaults from the ROI Calculator sheet. */
export const DEFAULT_ROI_INPUTS: RoiInputs = {
  newBusiness: {
    prospects: 240,
    asp: 8000,
    baselineClose: 0.2,
    closeRateLift: 0.02,
    pctSent: 0.25,
    costPerGift: 64,
  },
  retention: {
    customers: 50,
    customerValue: 40000,
    baselineChurn: 0.1,
    churnReduction: 0.03,
    pctSent: 0.5,
    costPerGift: 64,
  },
};

/** ASP / customer-value grid from the Sensitivity Analysis sheet. */
export const SENSITIVITY_VALUES = [
  200, 500, 1000, 1500, 2000, 3000, 4000, 5000, 7500, 10000, 15000,
] as const;

function ratioOrNull(numerator: number, denominator: number): number | null {
  if (denominator === 0) return null;
  return numerator / denominator;
}

export function computeNewBusiness(inputs: NewBusinessInputs): SectionResults {
  const sent = inputs.prospects * inputs.pctSent;
  const baselineOutcome = inputs.prospects * inputs.baselineClose;
  const withCookiesOutcome = inputs.prospects * (inputs.baselineClose + inputs.closeRateLift);
  const incrementalOutcome = withCookiesOutcome - baselineOutcome;
  const incrementalRevenue = incrementalOutcome * inputs.asp;
  const investment = sent * inputs.costPerGift;
  const netRevenue = incrementalRevenue - investment;
  return {
    sent,
    baselineOutcome,
    withCookiesOutcome,
    incrementalOutcome,
    incrementalRevenue,
    investment,
    netRevenue,
    roiRatio: ratioOrNull(netRevenue, investment),
    roiMultiple: ratioOrNull(incrementalRevenue, investment),
  };
}

export function computeRetention(inputs: RetentionInputs): SectionResults {
  const sent = inputs.customers * inputs.pctSent;
  const baselineOutcome = sent * inputs.baselineChurn;
  const withCookiesOutcome = sent * (inputs.baselineChurn - inputs.churnReduction);
  const incrementalOutcome = baselineOutcome - withCookiesOutcome;
  const incrementalRevenue = incrementalOutcome * inputs.customerValue;
  const investment = sent * inputs.costPerGift;
  const netRevenue = incrementalRevenue - investment;
  return {
    sent,
    baselineOutcome,
    withCookiesOutcome,
    incrementalOutcome,
    incrementalRevenue,
    investment,
    netRevenue,
    roiRatio: ratioOrNull(netRevenue, investment),
    roiMultiple: ratioOrNull(incrementalRevenue, investment),
  };
}

export function computeRoi(inputs: RoiInputs): RoiComputation {
  const newBusiness = computeNewBusiness(inputs.newBusiness);
  const retention = computeRetention(inputs.retention);
  const totalInvestment = newBusiness.investment + retention.investment;
  const totalIncrementalRevenue =
    newBusiness.incrementalRevenue + retention.incrementalRevenue;
  const totalNetRevenue = totalIncrementalRevenue - totalInvestment;
  return {
    newBusiness,
    retention,
    combined: {
      totalInvestment,
      totalIncrementalRevenue,
      totalNetRevenue,
      blendedRoiRatio: ratioOrNull(totalNetRevenue, totalInvestment),
      blendedRoiMultiple: ratioOrNull(totalIncrementalRevenue, totalInvestment),
    },
    breakeven: {
      breakevenAsp: ratioOrNull(inputs.newBusiness.costPerGift, inputs.newBusiness.closeRateLift),
      breakevenCustomerValue: ratioOrNull(
        inputs.retention.costPerGift,
        inputs.retention.churnReduction,
      ),
    },
  };
}

/** New business: incremental revenue / prospect = ASP * closeRateLift; cost = gift cost. */
export function newBusinessSensitivity(
  closeRateLift: number,
  costPerGift: number,
  values: readonly number[] = SENSITIVITY_VALUES,
): SensitivityRow[] {
  return values.map((value) => {
    const incrementalPerUnit = value * closeRateLift;
    const costPerUnit = costPerGift;
    const netPerUnit = incrementalPerUnit - costPerUnit;
    return {
      value,
      incrementalPerUnit,
      costPerUnit,
      netPerUnit,
      roiRatio: ratioOrNull(netPerUnit, costPerUnit),
    };
  });
}

/** Retention: retained revenue / customer = customerValue * churnReduction; cost = gift cost. */
export function retentionSensitivity(
  churnReduction: number,
  costPerGift: number,
  values: readonly number[] = SENSITIVITY_VALUES,
): SensitivityRow[] {
  return values.map((value) => {
    const incrementalPerUnit = value * churnReduction;
    const costPerUnit = costPerGift;
    const netPerUnit = incrementalPerUnit - costPerUnit;
    return {
      value,
      incrementalPerUnit,
      costPerUnit,
      netPerUnit,
      roiRatio: ratioOrNull(netPerUnit, costPerUnit),
    };
  });
}

export function formatMoney(n: number, digits = 0): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(n);
}

/** Excel ROI % cells store ratios (e.g. 9 → 900%). */
export function formatRoiPercent(ratio: number | null): string {
  if (ratio === null) return "n/a";
  return `${(ratio * 100).toLocaleString("en-US", {
    maximumFractionDigits: 1,
  })}%`;
}

export function formatMultiple(ratio: number | null): string {
  if (ratio === null) return "n/a";
  return `${ratio.toLocaleString("en-US", {
    maximumFractionDigits: 2,
  })}×`;
}

export function formatNumber(n: number, digits = 1): string {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}
