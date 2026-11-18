import React, { useEffect, useState } from "react";
import {
  Alert,
  Flex,
  Heading,
  Link,
  LoadingSpinner,
  Text,
  hubspot,
} from "@hubspot/ui-extensions";

const API = "https://closeandkeep-api.onrender.com";
const ACCOUNT_URL = "https://www.closeandkeep.com/integrations";

hubspot.extend(({ context }) => <SettingsPage context={context} />);

const SettingsPage = ({ context }) => {
  const [account, setAccount] = useState(null);
  const [error, setError] = useState("");

  const portalId = context?.portal?.id ? String(context.portal.id) : "";

  useEffect(() => {
    let cancelled = false;
    const query = portalId ? `?portalId=${encodeURIComponent(portalId)}` : "";
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
          setError(loadError?.message || "CloseAndKeep could not be reached.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [portalId]);

  return (
    <Flex direction="column" gap="medium">
      <Heading>CloseAndKeep</Heading>
      <Text>
        Cookie gifts go out when a deal reaches a stage in your CloseAndKeep recipes.
        The defaults are Demo Completed (4 cookies), Closed Won (12 cookies), and Renewal
        (4 cookies).
      </Text>
      <Text>
        On each deal, fill cookie_note, cookie_street, cookie_city, cookie_state, and
        cookie_postal_code, and associate a contact with an email. CloseAndKeep reads
        those fields. It does not write back to the deal.
      </Text>
      {!account && !error ? <LoadingSpinner label="Checking link" /> : null}
      {error ? (
        <Alert title="CloseAndKeep" variant="warning">
          {error}
        </Alert>
      ) : null}
      {account && account.linked === false ? (
        <Alert title="Finish linking" variant="info">
          Install started in HubSpot. Sign in to CloseAndKeep to attach portal{" "}
          {portalId || "this account"} to your CloseAndKeep user.
        </Alert>
      ) : null}
      {account && account.linked ? (
        <Alert title="Linked" variant="success">
          This portal is linked
          {account.recipe_stages?.length
            ? `. Recipe stages: ${account.recipe_stages.join(", ")}.`
            : "."}{" "}
          {account.token_status === "needs_reconnect"
            ? "Reconnect HubSpot from CloseAndKeep before the next stage change."
            : "Stage changes send cookies from here."}
        </Alert>
      ) : null}
      <Link href={{ url: ACCOUNT_URL, external: true }}>Open CloseAndKeep Integrations</Link>
    </Flex>
  );
};
