"use client";

export type ShippingAddressValue = {
  street: string;
  street2: string;
  city: string;
  state: string;
  postalCode: string;
};

export const EMPTY_SHIPPING_ADDRESS: ShippingAddressValue = {
  street: "",
  street2: "",
  city: "",
  state: "",
  postalCode: "",
};

export const US_STATES: { value: string; label: string }[] = [
  { value: "AL", label: "AL" },
  { value: "AK", label: "AK" },
  { value: "AZ", label: "AZ" },
  { value: "AR", label: "AR" },
  { value: "CA", label: "CA" },
  { value: "CO", label: "CO" },
  { value: "CT", label: "CT" },
  { value: "DE", label: "DE" },
  { value: "DC", label: "DC" },
  { value: "FL", label: "FL" },
  { value: "GA", label: "GA" },
  { value: "HI", label: "HI" },
  { value: "ID", label: "ID" },
  { value: "IL", label: "IL" },
  { value: "IN", label: "IN" },
  { value: "IA", label: "IA" },
  { value: "KS", label: "KS" },
  { value: "KY", label: "KY" },
  { value: "LA", label: "LA" },
  { value: "ME", label: "ME" },
  { value: "MD", label: "MD" },
  { value: "MA", label: "MA" },
  { value: "MI", label: "MI" },
  { value: "MN", label: "MN" },
  { value: "MS", label: "MS" },
  { value: "MO", label: "MO" },
  { value: "MT", label: "MT" },
  { value: "NE", label: "NE" },
  { value: "NV", label: "NV" },
  { value: "NH", label: "NH" },
  { value: "NJ", label: "NJ" },
  { value: "NM", label: "NM" },
  { value: "NY", label: "NY" },
  { value: "NC", label: "NC" },
  { value: "ND", label: "ND" },
  { value: "OH", label: "OH" },
  { value: "OK", label: "OK" },
  { value: "OR", label: "OR" },
  { value: "PA", label: "PA" },
  { value: "RI", label: "RI" },
  { value: "SC", label: "SC" },
  { value: "SD", label: "SD" },
  { value: "TN", label: "TN" },
  { value: "TX", label: "TX" },
  { value: "UT", label: "UT" },
  { value: "VT", label: "VT" },
  { value: "VA", label: "VA" },
  { value: "WA", label: "WA" },
  { value: "WV", label: "WV" },
  { value: "WI", label: "WI" },
  { value: "WY", label: "WY" },
];

export function isCompleteShippingAddress(value: ShippingAddressValue): boolean {
  return Boolean(
    value.street.trim() && value.city.trim() && value.state.trim() && value.postalCode.trim(),
  );
}

export function formatShippingAddress(value: ShippingAddressValue): string {
  const lines = [value.street.trim()];
  if (value.street2.trim()) {
    lines.push(value.street2.trim());
  }
  const cityState = [value.city.trim(), value.state.trim()].filter(Boolean).join(", ");
  const locality = [cityState, value.postalCode.trim()].filter(Boolean).join(" ");
  if (locality) {
    lines.push(locality);
  }
  return lines.filter(Boolean).join("\n");
}

export function shippingAddressPayload(value: ShippingAddressValue) {
  return {
    shipping_street: value.street.trim(),
    shipping_street2: value.street2.trim() || undefined,
    shipping_city: value.city.trim(),
    shipping_state: value.state.trim(),
    shipping_postal_code: value.postalCode.trim(),
  };
}

type ShippingAddressFieldsProps = {
  value: ShippingAddressValue;
  onChange: (next: ShippingAddressValue) => void;
  idPrefix: string;
  required?: boolean;
};

export function ShippingAddressFields({
  value,
  onChange,
  idPrefix,
  required = true,
}: ShippingAddressFieldsProps) {
  function patch(partial: Partial<ShippingAddressValue>) {
    onChange({ ...value, ...partial });
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-sm font-medium text-espresso" htmlFor={`${idPrefix}-street`}>
          Street address
        </label>
        <input
          id={`${idPrefix}-street`}
          className="mt-2 field-input"
          value={value.street}
          onChange={(event) => patch({ street: event.target.value })}
          placeholder="123 Main St"
          autoComplete="address-line1"
          required={required}
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-espresso" htmlFor={`${idPrefix}-street2`}>
          Apt, suite, unit <span className="font-normal text-stone-500">(optional)</span>
        </label>
        <input
          id={`${idPrefix}-street2`}
          className="mt-2 field-input"
          value={value.street2}
          onChange={(event) => patch({ street2: event.target.value })}
          placeholder="Apt 2"
          autoComplete="address-line2"
        />
      </div>
      <div className="grid grid-cols-6 gap-3">
        <div className="col-span-6 sm:col-span-3">
          <label className="block text-sm font-medium text-espresso" htmlFor={`${idPrefix}-city`}>
            City
          </label>
          <input
            id={`${idPrefix}-city`}
            className="mt-2 field-input"
            value={value.city}
            onChange={(event) => patch({ city: event.target.value })}
            placeholder="Springfield"
            autoComplete="address-level2"
            required={required}
          />
        </div>
        <div className="col-span-3 sm:col-span-1">
          <label className="block text-sm font-medium text-espresso" htmlFor={`${idPrefix}-state`}>
            State
          </label>
          <select
            id={`${idPrefix}-state`}
            className="mt-2 field-input"
            value={value.state}
            onChange={(event) => patch({ state: event.target.value })}
            autoComplete="address-level1"
            required={required}
          >
            <option value="">Select</option>
            {US_STATES.map((state) => (
              <option key={state.value} value={state.value}>
                {state.label}
              </option>
            ))}
          </select>
        </div>
        <div className="col-span-3 sm:col-span-2">
          <label className="block text-sm font-medium text-espresso" htmlFor={`${idPrefix}-postal`}>
            ZIP
          </label>
          <input
            id={`${idPrefix}-postal`}
            className="mt-2 field-input"
            value={value.postalCode}
            onChange={(event) => patch({ postalCode: event.target.value })}
            placeholder="62704"
            autoComplete="postal-code"
            inputMode="numeric"
            required={required}
          />
        </div>
      </div>
    </div>
  );
}
