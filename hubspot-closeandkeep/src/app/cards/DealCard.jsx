import React, { useEffect, useState } from "react";
import {
  Alert,
  Divider,
  Flex,
  Link,
  LoadingSpinner,
  Text,
  hubspot,
  useExtensionContext,
} from "@hubspot/ui-extensions";
import { useCrmProperties } from "@hubspot/ui-extensions/crm";

const API = "https://closeandkeep-api.onrender.com";
const ACCOUNT_URL = "https://www.closeandkeep.com/integrations";

const FIELDS = [
  ["cookie_note", "Cookie note"],
  ["cookie_street", "Street"],
  ["cookie_city", "City"],
  ["cookie_state", "State"],
  ["cookie_postal_code", "ZIP"],
];

const DEAL_PROPERTIES = [
  "dealname",
  "cookie_note",
  "cookie_street",
  "cookie_city",
  "cookie_state",
  "cookie_postal_code",
];

hubspot.extend(() => <Extension />);

const Extension = () => {
  const context = useExtensionContext();
  const { properties, isLoading, error } = useCrmProperties(DEAL_PROPERTIES);
  const [account, setAccount] = useState(null);
  const [accountError, setAccountError] = useState("");

  const dealId = context?.crm?.objectId ? String(context.crm.objectId) : "";

  useEffect(() => {
    let cancelled = false;
    const query = dealId ? `?dealId=${encodeURIComponent(dealId)}` : "";
    hubspot
      .fetch(`${API}/integrations/hubspot/card${query}`)
      .then(async (response) => {
        const body = await response.json().catch(() => ({}));
        if (!response.ok) {
          const detail = typeof body.detail === "string" ? body.detail : "";
          throw new Error(detail || "CloseAndKeep could not be reached.");
        }
        if (!cancelled) {
          setAccount(body);
        }
      })
      .catch((loadError) => {
        if (!cancelled) {
          setAccountError(loadError?.message || "CloseAndKeep could not be reached.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dealId]);

  if (isLoading) {
    return <LoadingSpinner label="Loading deal" />;
  }

  const filled = FIELDS.filter(([name]) => String(properties?.[name] || "").trim());
  const missing = FIELDS.filter(([name]) => !String(properties?.[name] || "").trim());
  const dealLabel = properties?.dealname ? ` for ${properties.dealname}` : "";

  return (
    <Flex direction="column" gap="medium">
      <Text>
        Send cookies after this pitch{dealLabel}. CloseAndKeep reads the cookie fields on
        the deal when it moves into Demo Completed, Closed Won, or Renewal.
      </Text>
      {error ? (
        <Alert title="Deal fields" variant="warning">
          Cookie fields could not be loaded. Add cookie_note, cookie_street, cookie_city,
          cookie_state, and cookie_postal_code on the deal.
        </Alert>
      ) : (
        <Text>
          {filled.length} of {FIELDS.length} cookie fields are filled
          {missing.length ? ` (still need ${missing.map(([, label]) => label).join(", ")})` : ""}.
        </Text>
      )}
      <Divider />
      {accountError ? (
        <Alert title="CloseAndKeep" variant="warning">
          {accountError}
        </Alert>
      ) : null}
      {account && account.linked === false ? (
        <Alert title="Link this portal" variant="info">
          This HubSpot account is not linked to CloseAndKeep yet. Open CloseAndKeep and finish
          linking so stage changes can send cookies.
        </Alert>
      ) : null}
      {account && account.linked && account.token_status === "needs_reconnect" ? (
        <Alert title="Reconnect HubSpot" variant="warning">
          The CloseAndKeep connection expired. Reconnect HubSpot from Integrations.
        </Alert>
      ) : null}
      {account?.deal?.status_label ? <Text>{account.deal.status_label}</Text> : null}
      {account?.linked && !account?.deal?.status ? (
        <Text>No cookie action for this deal yet.</Text>
      ) : null}
      <Link href={{ url: ACCOUNT_URL, external: true }}>Open CloseAndKeep</Link>
    </Flex>
  );
};
