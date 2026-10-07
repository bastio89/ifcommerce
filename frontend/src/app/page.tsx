import { Features } from "@/components/marketing/features";
import { Faq } from "@/components/marketing/faq";
import { FinalCta, Footer } from "@/components/marketing/footer";
import { Hero } from "@/components/marketing/hero";
import { HowItWorks } from "@/components/marketing/how-it-works";
import { IntegrationTeaser } from "@/components/marketing/integration-teaser";
import { LiveDemo } from "@/components/marketing/live-demo";
import { Navbar } from "@/components/marketing/navbar";
import { Pricing } from "@/components/marketing/pricing";
import { SectionHeading } from "@/components/marketing/section-heading";
import { env } from "@/lib/env";

// URLs und Kontingente kommen zur Laufzeit aus der Umgebung (ein Image für alle Umgebungen).
export const dynamic = "force-dynamic";

export default function HomePage() {
  const { APP_URL, PUBLIC_API_BASE_URL, FREE_TIER_MONTHLY_LIMIT } = env();

  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <section id="demo" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24 sm:px-6">
          <SectionHeading
            eyebrow="Live-Demo"
            title="Probier es mit einer echten Kunden-Mail"
            description="Füge ein Beispielticket oder synthetischen Text ein und sieh die strukturierte Einschätzung samt maskierter Textfassung."
          />
          <LiveDemo />
        </section>
        <HowItWorks />
        <Features />
        <Pricing freeLimit={FREE_TIER_MONTHLY_LIMIT} />
        <IntegrationTeaser appUrl={APP_URL} apiUrl={PUBLIC_API_BASE_URL} />
        <Faq />
        <FinalCta />
      </main>
      <Footer apiUrl={PUBLIC_API_BASE_URL} />
    </>
  );
}
