import { CodeBlock } from "@/components/ui/code-block";
import { SectionHeading } from "@/components/marketing/section-heading";

export function IntegrationTeaser({ appUrl, apiUrl }: { appUrl: string; apiUrl: string }) {
  const widget = `<!-- Vor </body> im Shop-Template einfügen -->
<script
  src="${appUrl}/decidecommerce-widget.js"
  data-api-key="dc_pk_…"
  data-endpoint="${apiUrl}"
  data-form="#contact-form"
  defer
></script>`;

  const curl = `curl -X POST ${apiUrl}/api/v1/analyze-ticket \\
  -H "x-api-key: dc_sk_…" \\
  -H "content-type: application/json" \\
  -d '{"text": "Wo bleibt meine Bestellung #1001?"}'`;

  return (
    <section id="integration" className="border-y border-border bg-surface/40">
      <div className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24 sm:px-6">
        <SectionHeading
          eyebrow="Integration"
          title="In fünf Minuten live"
          description="Das Widget hängt sich an dein bestehendes Kontaktformular und schreibt die Entscheidung als versteckte Felder mit, sodass dein Helpdesk sofort danach routen kann. Für alles andere gibt es die REST-API."
        />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <CodeBlock title="Shop-Template · HTML" code={widget} />
          <CodeBlock title="Helpdesk / Backend · cURL" code={curl} />
        </div>
      </div>
    </section>
  );
}
