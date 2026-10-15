import React, { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Divider,
  Flex,
  Text,
  TextArea,
  TextInput,
  hubspot,
} from "@hubspot/ui-extensions";
import { useCrmProperties } from "@hubspot/ui-extensions/crm";

const API_BASE = "https://closeandkeep-api.onrender.com";

const PROPERTY_KEYS = [
  "cookie_note",
  "cookie_company",
  "cookie_street",
  "cookie_street2",
  "cookie_city",
  "cookie_state",
  "cookie_postal_code",
  "dealstage",
  "dealname",
];

hubspot.extend(({ context, actions }) => (
  <CookieGiftCard context={context} actions={actions} />
));

const CookieGiftCard = ({ context, actions }) => {
  const portalId = String(context?.portal?.id || "");
  const dealId = String(context?.crm?.objectId || "");
  const { properties, isLoading, error, refetch } = useCrmProperties(PROPERTY_KEYS);

  const [note, setNote] = useState("");
  const [company, setCompany] = useState("");
  const [street, setStreet] = useState("");
  const [street2, setStreet2] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [postal, setPostal] = useState("");
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!properties) {
      return;
    }
    setNote(properties.cookie_note || "");
    setCompany(properties.cookie_company || "");
    setStreet(properties.cookie_street || "");
    setStreet2(properties.cookie_street2 || "");
    setCity(properties.cookie_city || "");
    setState(properties.cookie_state || "");
    setPostal(properties.cookie_postal_code || "");
  }, [properties]);

  const saveProperties = async () => {
    setBusy(true);
    setStatus(null);
    try {
      const response = await hubspot.fetch(`${API_BASE}/integrations/hubspot/card/properties`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          portal_id: portalId,
          deal_id: dealId,
          cookie_note: note,
          cookie_company: company,
          cookie_street: street,
          cookie_street2: street2,
          cookie_city: city,
          cookie_state: state,
          cookie_postal_code: postal,
        }),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `Save failed (${response.status})`);
      }
      if (actions?.refreshObjectProperties) {
        actions.refreshObjectProperties();
      }
      if (refetch) {
        refetch();
      }
      setStatus({ type: "success", message: "Cookie fields saved on this deal." });
    } catch (err) {
      setStatus({
        type: "error",
        message: err?.message || "Could not save cookie fields.",
      });
    } finally {
      setBusy(false);
    }
  };

  const queueGift = async () => {
    setBusy(true);
    setStatus(null);
    try {
      // Persist first so the gift uses the values shown on the card.
      const saveResponse = await hubspot.fetch(
        `${API_BASE}/integrations/hubspot/card/properties`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            portal_id: portalId,
            deal_id: dealId,
            cookie_note: note,
            cookie_company: company,
            cookie_street: street,
            cookie_street2: street2,
            cookie_city: city,
            cookie_state: state,
            cookie_postal_code: postal,
          }),
        }
      );
      if (!saveResponse.ok) {
        const detail = await saveResponse.text();
        throw new Error(detail || `Save failed (${saveResponse.status})`);
      }

      const sendResponse = await hubspot.fetch(`${API_BASE}/integrations/hubspot/card/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          portal_id: portalId,
          deal_id: dealId,
        }),
      });
      const body = await sendResponse.json().catch(() => ({}));
      if (!sendResponse.ok) {
        throw new Error(body?.detail || `Send failed (${sendResponse.status})`);
      }
      const resultStatus = body?.status || "ok";
      if (resultStatus === "ignored") {
        setStatus({
          type: "warning",
          message:
            body?.reason === "stage_mismatch"
              ? "Deal stage is not in your CloseAndKeep stage recipes. Move the deal or edit recipes, then try again."
              : `Ignored: ${body?.reason || "unknown"}`,
        });
      } else if (resultStatus === "duplicate") {
        setStatus({
          type: "info",
          message: "This deal already triggered a CloseAndKeep gift or reminder.",
        });
      } else {
        setStatus({
          type: "success",
          message:
            resultStatus === "auto_ordered" || resultStatus === "sent"
              ? "CloseAndKeep queued the cookie gift / reminder."
              : `CloseAndKeep result: ${resultStatus}`,
        });
      }
      if (actions?.refreshObjectProperties) {
        actions.refreshObjectProperties();
      }
    } catch (err) {
      setStatus({
        type: "error",
        message: err?.message || "Could not queue cookie gift.",
      });
    } finally {
      setBusy(false);
    }
  };

  if (isLoading) {
    return <Text>Loading cookie fields…</Text>;
  }

  if (error) {
    return (
      <Alert title="Could not load deal properties" variant="error">
        {error.message || "Check that cookie_* deal properties exist and the app is installed."}
      </Alert>
    );
  }

  return (
    <Flex direction="column" gap="small">
      <Text>
        Fill shipping fields here so CloseAndKeep can auto-order when a stage recipe hits (or
        queue now).
      </Text>
      <TextArea label="Cookie note" name="cookie_note" value={note} onInput={setNote} />
      <TextInput label="Company" name="cookie_company" value={company} onInput={setCompany} />
      <TextInput label="Street" name="cookie_street" value={street} onInput={setStreet} />
      <TextInput
        label="Apt / suite"
        name="cookie_street2"
        value={street2}
        onInput={setStreet2}
      />
      <TextInput label="City" name="cookie_city" value={city} onInput={setCity} />
      <TextInput label="State" name="cookie_state" value={state} onInput={setState} />
      <TextInput
        label="ZIP / postal"
        name="cookie_postal_code"
        value={postal}
        onInput={setPostal}
      />
      <Divider />
      <Flex direction="row" gap="small">
        <Button variant="secondary" disabled={busy || !dealId} onClick={saveProperties}>
          Save fields
        </Button>
        <Button variant="primary" disabled={busy || !dealId} onClick={queueGift}>
          Queue cookie gift
        </Button>
      </Flex>
      {status ? (
        <Alert
          title={status.type === "error" ? "Error" : "CloseAndKeep"}
          variant={
            status.type === "error"
              ? "error"
              : status.type === "warning"
                ? "warning"
                : status.type === "info"
                  ? "info"
                  : "success"
          }
        >
          {status.message}
        </Alert>
      ) : null}
    </Flex>
  );
};
