"use client";

import { useState } from "react";

import { CodeBlock } from "@/components/ui/code-block";
import { cn } from "@/lib/utils";

type Tab = "widget" | "rest" | "node" | "python" | "schema";

const TABS: { id: Tab; label: string }[] = [
  { id: "widget", label: "Shop-Widget" },
  { id: "rest", label: "REST · cURL" },
  { id: "node", label: "Node.js" },
  { id: "python", label: "Python" },
  { id: "schema", label: "Antwortformat" },
];

const HIDDEN_FIELDS = [
  ["dc_status", "ok | degraded | queued | processing | error | timeout", "Ergebnis oder Status der Analyse."],
  ["dc_category", "WHERE_IS_MY_ORDER …", "Eine der fünf Kategorien."],
  ["dc_urgency", "1 – 5", "5 = Kundenwut oder rechtliche Drohung."],
  ["dc_is_cancellation_request", "true | false", "Sofortiger Stornierungswunsch."],
  ["dc_contains_order_number", "true | false", "Nachricht enthält eine Bestellnummer."],
  ["dc_confidence", "0.0 – 1.0", "Sicherheit der Klassifikation."],
  ["dc_analysis_id", "ana_…", "Referenz für Support-Anfragen."],
  ["dc_degraded", "true | false", "True, wenn die Heuristik statt des Modells entschieden hat."],
  ["dc_job_id", "job_…", "Job-ID für eine spätere Statusabfrage."],
  ["dc_status_url", "/api/v1/analysis-jobs/…", "Status-URL für das Shop-Backend."],
  ["dc_idempotency_key", "…", "Schützt Wiederholungen vor doppelten Analysen."],
];

export function IntegrationGuide({ appUrl, apiUrl }: { appUrl: string; apiUrl: string }) {
  const [tab, setTab] = useState<Tab>("widget");

  const snippets: Record<Exclude<Tab, "schema">, { title: string; code: string }[]> = {
    widget: [
      {
        title: "Shop-Template · vor </body>",
        code: `<script
  src="${appUrl}/decidecommerce-widget.js"
  data-api-key="dc_pk_DEIN_PUBLISHABLE_KEY"
  data-endpoint="${apiUrl}"
  data-form="#contact-form"
  data-message-field="message"
  defer
></script>`,
      },
      {
        title: "Optional · auf das Ergebnis reagieren",
        code: `document.addEventListener("decidecommerce:decision", (event) => {
  const decision = event.detail;
  if (decision.flags.is_cancellation_request) {
    // z. B. Hinweis anzeigen: "Wir stoppen deine Bestellung sofort."
  }
});`,
      },
  {
    title: "AJAX · langsame Analyse abwarten",
        code: `document.addEventListener("decidecommerce:processing", (event) => {
  const job = event.detail;
  // Jobreferenz im Helpdesk speichern; das Widget pollt und sendet später "decidecommerce:decision".
  console.log(job.id, job.status_url);
});`,
  },
    ],
    rest: [
      {
        title: "cURL",
        code: `curl -X POST ${apiUrl}/api/v1/analyze-ticket \\
  -H "x-api-key: $DECIDECOMMERCE_API_KEY" \\
  -H "content-type: application/json" \\
  -d '{
    "text": "Hallo, wo bleibt meine Bestellung #1001? Ich warte seit 2 Wochen!",
    "subject": "Lieferung",
    "external_id": "zendesk-48213"
  }'`,
      },
    ],
    node: [
      {
        title: "Node.js 18+ · fetch",
        code: `const API_URL = "${apiUrl}";
const headers = {
  "x-api-key": process.env.DECIDECOMMERCE_API_KEY,
  "content-type": "application/json",
  "Idempotency-Key": crypto.randomUUID(),
};
const response = await fetch(API_URL + "/api/v1/analyze-ticket", {
  method: "POST",
  headers,
  body: JSON.stringify({ text: ticket.body, external_id: ticket.id }),
});
let decision = await response.json();
if (response.status === 202) {
  let job;
  do {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    const poll = await fetch(API_URL + decision.status_url, { headers });
    job = await poll.json();
  } while (["queued", "processing"].includes(job.status));
  if (!job.result) throw new Error(job.error?.message ?? "Analyse fehlgeschlagen");
  decision = job.result;
} else if (!response.ok) {
  throw new Error(decision.error.message);
}

if (decision.flags.is_cancellation_request) await holdShipment(ticket.orderId);
if (decision.urgency >= 4) await assignTo(ticket.id, "senior-support");`,
      },
    ],
    python: [
      {
        title: "Python · httpx",
        code: `import os
    import time
import httpx

    api_url = "${apiUrl}"
    headers = {"x-api-key": os.environ["DECIDECOMMERCE_API_KEY"]}
    response = httpx.post(
      f"{api_url}/api/v1/analyze-ticket",
      headers=headers,
    json={"text": ticket_body, "external_id": ticket_id},
      timeout=5,
)
decision = response.json()
    if response.status_code == 202:
      job = decision
      while True:
        time.sleep(job.get("retry_after_seconds", 1))
        job_response = httpx.get(f"{api_url}{job['status_url']}", headers=headers, timeout=5)
        job_response.raise_for_status()
        job = job_response.json()
        if job["status"] in {"succeeded", "degraded", "failed"}:
          break
      if not job.get("result"):
        raise RuntimeError(job.get("error", {}).get("message", "Analyse fehlgeschlagen"))
      decision = job["result"]
    elif not response.is_success:
      response.raise_for_status()

if decision["category"] == "WHERE_IS_MY_ORDER" and decision["flags"]["contains_order_number"]:
    send_tracking_macro(ticket_id)`,
      },
    ],
  };

  const exampleResponse = `{
  "id": "ana_3f2a…",
  "external_id": "zendesk-48213",
  "category": "WHERE_IS_MY_ORDER",
  "urgency": 4,
  "flags": {
    "is_cancellation_request": false,
    "contains_order_number": true
  },
  "confidence": 0.94,
  "engine": "anthropic:claude-opus-5-5",
  "degraded": false,
  "latency_ms": 412,
  "pii": { "redacted": true, "entities": { "NAME": 1, "EMAIL": 1 } },
  "anonymized_text": "Hallo, wo bleibt meine Bestellung #1001? … [ANONYMOUS_NAME]"
}`;

  return (
    <div>
      <div className="mb-5 flex gap-1 overflow-x-auto border-b border-border" role="tablist" aria-label="Integrationsart">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            onClick={() => setTab(item.id)}
            className={cn(
              "-mb-px shrink-0 border-b-2 px-3 py-2.5 text-sm transition-colors",
              tab === item.id ? "border-accent text-foreground" : "border-transparent text-muted hover:text-foreground",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "widget" && (
        <div className="flex flex-col gap-5">
          <ol className="flex list-decimal flex-col gap-2 pl-5 text-sm text-secondary marker:text-muted">
            <li>
              Erzeuge unter <strong className="text-foreground">API-Keys</strong> einen{" "}
              <strong className="text-foreground">Publishable Key</strong> und gib die Domain deines Shops frei.
            </li>
            <li>Füge das Script-Tag in dein Shop-Template ein (Shopify: theme.liquid, Shopware: base.html.twig).</li>
            <li>
              Das Widget fängt den Submit ab, analysiert die Nachricht und hängt das Ergebnis als Hidden-Inputs an. Dein
              Formular-Backend oder Helpdesk erhält die Felder automatisch mit.
            </li>
          </ol>
          {snippets.widget.map((snippet) => (
            <CodeBlock key={snippet.title} title={snippet.title} code={snippet.code} />
          ))}
          <div className="overflow-x-auto rounded-xl border border-border">
            <table className="w-full min-w-[560px] text-left text-[13px]">
              <thead className="bg-surface text-muted">
                <tr>
                  <th className="px-4 py-2.5 font-normal">Hidden-Input</th>
                  <th className="px-4 py-2.5 font-normal">Werte</th>
                  <th className="px-4 py-2.5 font-normal">Bedeutung</th>
                </tr>
              </thead>
              <tbody>
                {HIDDEN_FIELDS.map(([name, values, meaning]) => (
                  <tr key={name} className="border-t border-border">
                    <td className="px-4 py-2.5 font-mono text-foreground">{name}</td>
                    <td className="px-4 py-2.5 font-mono text-secondary">{values}</td>
                    <td className="px-4 py-2.5 text-secondary">{meaning}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[13px] text-muted">
            Weitere Attribute: <code className="font-mono">data-subject-field</code>,{" "}
            <code className="font-mono">data-field-prefix</code>, <code className="font-mono">data-timeout</code> (ms,
            Standard 3000), <code className="font-mono">data-debug</code>. Formulare mit{" "}
            <code className="font-mono">data-decidecommerce-ignore</code> werden übersprungen.
          </p>
        </div>
      )}

      {(tab === "rest" || tab === "node" || tab === "python") && (
        <div className="flex flex-col gap-5">
          <p className="text-sm text-secondary">
            Verwende einen <strong className="text-foreground">Secret Key</strong> ausschließlich serverseitig, z. B. in
            einer Zendesk-/Freshdesk-Automation, einem Shopify-Flow-Webhook oder deinem Mail-Ingest.
          </p>
          {snippets[tab].map((snippet) => (
            <CodeBlock key={snippet.title} title={snippet.title} code={snippet.code} />
          ))}
        </div>
      )}

      {tab === "schema" && (
        <div className="flex flex-col gap-5">
          <CodeBlock title="200 OK · application/json" code={exampleResponse} />
          <div className="overflow-x-auto rounded-xl border border-border">
            <table className="w-full min-w-[520px] text-left text-[13px]">
              <thead className="bg-surface text-muted">
                <tr>
                  <th className="px-4 py-2.5 font-normal">Status</th>
                  <th className="px-4 py-2.5 font-normal">error.code</th>
                  <th className="px-4 py-2.5 font-normal">Bedeutung</th>
                </tr>
              </thead>
              <tbody className="text-secondary">
                {[
                  ["401", "missing_api_key / invalid_api_key", "Schlüssel fehlt, ist falsch oder widerrufen"],
                  ["402", "monthly_quota_exceeded", "Free-Kontingent aufgebraucht"],
                  ["402", "subscription_inactive", "Pro-Abo unbezahlt oder pausiert"],
                  ["403", "origin_not_allowed", "Publishable Key auf nicht freigegebener Domain"],
                  ["413", "payload_too_large", "Text länger als 20.000 Zeichen"],
                  ["422", "invalid_request", "Ungültiger Request-Body"],
                  ["429", "rate_limited", "Zu viele Anfragen, siehe Retry-After"],
                ].map(([status, code, meaning]) => (
                  <tr key={code} className="border-t border-border">
                    <td className="px-4 py-2.5 font-mono text-foreground">{status}</td>
                    <td className="px-4 py-2.5 font-mono">{code}</td>
                    <td className="px-4 py-2.5">{meaning}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[13px] text-muted">
            Interaktive OpenAPI-Referenz:{" "}
            <a href={`${apiUrl}/docs`} className="text-foreground underline-offset-4 hover:underline">
              {apiUrl}/docs
            </a>
          </p>
        </div>
      )}
    </div>
  );
}
