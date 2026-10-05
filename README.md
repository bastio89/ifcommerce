# DecideCommerce

**Semantische If-Statements für deinen Support.** DecideCommerce klassifiziert Support-Tickets und E-Mails von Online-Shops in Echtzeit und liefert in einem einzigen Durchlauf ein festes Entscheidungsobjekt: Kategorie, Dringlichkeit, Intent-Flags und Konfidenz. Personenbezogene Daten werden anonymisiert, bevor irgendein Text ein KI-Modell erreicht.

```json
{
  "category": "WHERE_IS_MY_ORDER",
  "urgency": 5,
  "flags": { "is_cancellation_request": false, "contains_order_number": true },
  "confidence": 0.94
}
```

---

## Inhalt

1. [Architektur](#architektur)
2. [Verzeichnisstruktur](#verzeichnisstruktur)
3. [Schnellstart mit Docker](#schnellstart-mit-docker)
4. [Lokale Entwicklung](#lokale-entwicklung)
5. [Konfiguration](#konfiguration)
6. [Decision API](#decision-api)
7. [Shop-Widget](#shop-widget)
8. [Stripe einrichten](#stripe-einrichten)
9. [Architekturentscheidungen](#architekturentscheidungen)
10. [Tests & Qualität](#tests--qualität)
11. [Produktions-Checkliste](#produktions-checkliste)

---

## Architektur

```mermaid
flowchart LR
  subgraph Shop["Online-Shop des Händlers"]
    W["decidecommerce-widget.js<br/>(Kontaktformular)"]
    H["Helpdesk / Backend<br/>(Zendesk, Shopify Flow …)"]
  end

  subgraph Platform["DecideCommerce"]
    FE["Next.js Frontend<br/>Landingpage · Dashboard · Auth · Billing"]
    BE["FastAPI Decision API"]
    PG[("PostgreSQL<br/>Schema: Prisma")]
  end

  LLM["Claude API<br/>Structured Outputs"]
  ST["Stripe<br/>Checkout · Webhooks · Meter"]

  W -- "x-api-key (Publishable)" --> BE
  H -- "x-api-key (Secret)" --> BE
  FE -- "Prisma Client" --> PG
  FE -- "Live-Demo (internes Secret)" --> BE
  FE -- "Checkout / Portal" --> ST
  BE -- "asyncpg" --> PG
  BE -- "anonymisierter Text" --> LLM
  ST -- "customer.subscription.*" --> BE
  BE -- "Meter Events" --> ST
```

**Request-Pfad `POST /api/v1/analyze-ticket`:**

1. `ApiKeyAuthMiddleware` (reine ASGI-Middleware): Key-Hash gegen PostgreSQL validieren → Tenant zuordnen → Origin-Allowlist (Publishable Keys) → Rate-Limit → Tarif/Kontingent prüfen.
2. **DSGVO-Schutzschicht** (`backend/app/privacy/pii.py`): E-Mails, Telefonnummern, Klarnamen, Adressen, IBANs (Prüfsumme), Kreditkarten (Luhn) und IPs werden durch Platzhalter wie `[ANONYMOUS_EMAIL]` ersetzt. Bestellnummern bleiben erhalten.
3. **Decision Engine** (Single Pass): Claude mit nativen Structured Outputs (`client.beta.messages.parse` + Pydantic-Schema). Fällt das LLM aus (Timeout, Rate-Limit, Refusal), entscheidet eine deterministische Heuristik; die Antwort trägt dann `degraded: true`.
4. Bei einer 2xx-Antwort schreibt die Middleware **vor** der Auslieferung einen `UsageLog`-Eintrag. Pro-Nutzung wird asynchron als Stripe-Meter-Event gemeldet.

## Verzeichnisstruktur

```
.
├── docker-compose.yml            # postgres · migrate · backend · frontend
├── .env.example                  # alle Umgebungsvariablen, dokumentiert
├── prisma/                       # Single Source of Truth für das DB-Schema
│   ├── schema.prisma
│   └── migrations/               # von `prisma migrate` erzeugtes SQL
├── backend/                      # FastAPI Decision API (Python 3.12)
│   ├── Dockerfile                # Multi-Stage, Non-Root
│   ├── requirements.txt / requirements-dev.txt / pyproject.toml
│   ├── app/
│   │   ├── main.py               # App-Factory, Lifespan, Fehlerformat
│   │   ├── config.py             # pydantic-settings
│   │   ├── container.py          # Dependency-Komposition
│   │   ├── db.py                 # asyncpg-Pool
│   │   ├── schemas.py            # TicketDecision & API-Verträge
│   │   ├── security.py           # Key-Format & Hashing
│   │   ├── middleware/api_key_auth.py
│   │   ├── privacy/pii.py, names.py
│   │   ├── decision/             # anthropic_engine · heuristic_engine · pipeline · prompt
│   │   ├── services/             # tenants · entitlements · usage · stripe_sync · rate_limit
│   │   └── routers/              # analyze · webhooks · demo · health
│   └── tests/                    # 52 Tests (Unit + Integration gegen PostgreSQL)
├── frontend/                     # Next.js 16 (App Router), Tailwind CSS 4, TypeScript
│   ├── Dockerfile                # deps → builder → migrator / runner (standalone)
│   ├── prisma.config.ts          # zeigt auf ../prisma
│   ├── public/decidecommerce-widget.js
│   └── src/
│       ├── app/                  # Landingpage, (auth)/login|signup, dashboard/*, api/*
│       ├── components/           # marketing/*, dashboard/*, ui/*
│       └── lib/                  # db, auth, crypto, api-keys, stripe, usage, env
└── .github/workflows/ci.yml      # Lint, Typecheck, Tests, Build, Docker
```

## Schnellstart mit Docker

```bash
docker compose up --build
```

| Dienst | URL |
|---|---|
| Frontend (Landingpage & Dashboard) | http://localhost:3000 |
| Decision API | http://localhost:8000 · OpenAPI unter `/docs` |
| PostgreSQL | `localhost:5432` (nur lokal gebunden) |

Ohne weitere Konfiguration läuft alles mit lokalen Defaults: Die Decision Engine nutzt die Heuristik, Billing ist deaktiviert. Für die volle Funktion `cp .env.example .env` und mindestens `ANTHROPIC_API_KEY`, `INTERNAL_API_SECRET` und `POSTGRES_PASSWORD` setzen.

Ablauf beim Start: `postgres` wird healthy → `migrate` führt `prisma migrate deploy` aus und beendet sich → `backend` startet → `frontend` startet, sobald das Backend healthy ist.

## Lokale Entwicklung

Voraussetzungen: Node.js 22, Python 3.11+, PostgreSQL 16.

```bash
# 1) Datenbank (z. B. nur den Postgres-Container)
docker compose up -d postgres

# 2) Frontend + Migrationen
cd frontend
cp ../.env.example .env          # DATABASE_URL=postgresql://decide:<passwort>@localhost:5432/decidecommerce
npm install                       # führt `prisma generate` aus
npm run db:deploy                 # Migrationen anwenden (Entwicklung: npm run db:migrate)
npm run dev                       # http://localhost:3000

# 3) Backend
cd ../backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example .env
uvicorn app.main:app --reload     # http://localhost:8000/docs
```

Schemaänderungen immer in `prisma/schema.prisma` vornehmen und mit `npm run db:migrate -- --name <name>` (im Ordner `frontend/`) eine Migration erzeugen. Das Backend nutzt dieselben Tabellen per SQL; neue Spalten dort im passenden Repository ergänzen.

## Konfiguration

Alle Variablen sind in [`.env.example`](.env.example) dokumentiert. Die wichtigsten:

| Variable | Dienst | Bedeutung |
|---|---|---|
| `DATABASE_URL` | beide | PostgreSQL-Verbindung (in Compose automatisch gesetzt) |
| `DECISION_ENGINE` | backend | `auto` · `anthropic` · `heuristic` |
| `ANTHROPIC_API_KEY` | backend | Claude-API-Key; ohne Key nutzt `auto` die Heuristik |
| `ANTHROPIC_MODEL` | backend | Standard `claude-opus-5-5`, frei wählbar |
| `ANTHROPIC_EFFORT` | backend | Denkaufwand, Standard `low` (schnell & günstig) |
| `INTERNAL_API_SECRET` | beide | Geteiltes Secret für den Live-Demo-Proxy |
| `APP_URL`, `PUBLIC_API_BASE_URL` | frontend | Öffentliche URLs (Redirects, Snippets, Widget) |
| `STRIPE_SECRET_KEY` | beide | Stripe-API-Key |
| `STRIPE_WEBHOOK_SECRET` | backend | Signing Secret des Webhook-Endpunkts |
| `STRIPE_PRICE_PRO_BASE`, `STRIPE_PRICE_PRO_METERED` | frontend | Preis-IDs für Checkout |
| `STRIPE_METER_EVENT_NAME` | backend | Event-Name des Billing Meters |
| `FREE_TIER_MONTHLY_LIMIT` | beide | Analysen pro Monat im Free-Tarif (Standard 250) |

Alle Frontend-Variablen werden **zur Laufzeit** gelesen (keine `NEXT_PUBLIC_*`), damit ein einziges Image in jeder Umgebung läuft.

## Decision API

```bash
curl -X POST http://localhost:8000/api/v1/analyze-ticket \
  -H "x-api-key: dc_sk_…" \
  -H "content-type: application/json" \
  -d '{"text": "Wo bleibt meine Bestellung #1001? Ich warte seit 2 Wochen!", "external_id": "zendesk-48213"}'
```

| Feld | Typ | Beschreibung |
|---|---|---|
| `category` | Enum | `WHERE_IS_MY_ORDER`, `RETURN_OR_REFUND`, `PRODUCT_ISSUE`, `PAYMENT_OR_INVOICE`, `GENERAL_INQUIRY` |
| `urgency` | 1–5 | 5 = Kundenwut oder rechtliche Drohung |
| `flags.is_cancellation_request` | bool | Sofortiger Stornierungswunsch |
| `flags.contains_order_number` | bool | Bestell-/Rechnungsnummer im Text |
| `confidence` | 0.0–1.0 | Sicherheit der Klassifikation |
| `engine`, `degraded` | | Welche Engine entschieden hat; `true`, wenn der Fallback griff |
| `pii` | | Anzahl anonymisierter Entitäten je Typ |
| `anonymized_text` | string | Der Text, wie ihn das Modell gesehen hat |

Fehler haben immer die Form `{"error": {"code": "...", "message": "..."}}`: `401 missing_api_key|invalid_api_key`, `402 monthly_quota_exceeded|subscription_inactive`, `403 origin_not_allowed`, `413 payload_too_large`, `422 invalid_request`, `429 rate_limited` (mit `Retry-After`).

**API-Keys:** `dc_sk_…` (Secret, nur serverseitig) und `dc_pk_…` (Publishable, für das Widget, an freigegebene Domains gebunden und strenger rate-limitiert). Gespeichert wird ausschließlich ein SHA-256-Hash; der Klartext wird genau einmal im Dashboard angezeigt. Ein Widerruf greift nach spätestens `API_KEY_CACHE_TTL_SECONDS` (Standard 15 s).

## Shop-Widget

```html
<script
  src="https://app.deine-domain.de/decidecommerce-widget.js"
  data-api-key="dc_pk_…"
  data-endpoint="https://api.deine-domain.de"
  data-form="#contact-form"
  defer
></script>
```

Das Widget hängt sich in der Capture-Phase an das `submit`-Event, analysiert die Nachricht und fügt diese Hidden-Inputs hinzu, bevor das Formular per `requestSubmit()` final abgeschickt wird (inklusive Original-Submit-Button und Shop-eigenen Handlern):

`dc_status` (`ok` | `error` | `timeout`), `dc_category`, `dc_urgency`, `dc_is_cancellation_request`, `dc_contains_order_number`, `dc_confidence`, `dc_analysis_id`

Das Formular wird **nie blockiert**: Bei Timeout (`data-timeout`, Standard 3000 ms) oder Fehler wird mit `dc_status=error|timeout` gesendet. Secret Keys verweigert das Widget. Für AJAX-Formulare gibt es `window.DecideCommerce.analyze(text)` und das Event `decidecommerce:decision`.

## Stripe einrichten

1. **Billing Meter** anlegen (Billing → Meters): Event-Name `decidecommerce_ticket_analyzed`, Aggregation *Sum*, Payload-Key für den Wert `value`, Kunden-Mapping `stripe_customer_id`.
2. **Produkt „DecideCommerce Pro“** mit zwei Preisen:
   - Grundgebühr: 49 USD, monatlich, *licensed* → `STRIPE_PRICE_PRO_BASE`
   - Nutzung: monatlich, *metered* mit dem Meter aus Schritt 1, gestaffelt (*graduated*): 0–10.000 Einheiten 0 USD, ab 10.001 0,002 USD → `STRIPE_PRICE_PRO_METERED`
3. **Webhook-Endpunkt** `https://api.deine-domain.de/api/v1/webhooks/stripe` mit den Events `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`. Das Signing Secret als `STRIPE_WEBHOOK_SECRET` setzen.
4. **Customer Portal** aktivieren (Settings → Billing → Customer portal), damit Händler Zahlungsdaten, Rechnungen und Kündigung selbst verwalten.

Lokal testen: `stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe`.

**Statuslogik:** `active`/`trialing`/`past_due` → Pro mit vollem Zugriff (`past_due` als Kulanzzeitraum) · `unpaid`/`paused` → API gesperrt (402) · `incomplete` → Free-Kontingent, bis die Erstzahlung durch ist · `canceled`/`incomplete_expired` → zurück auf Free. Webhooks sind idempotent (`stripe_events`), holen bei vorhandenem API-Key den aktuellen Abo-Stand direkt von Stripe (reihenfolgeunabhängig) und ignorieren Löschungen alter Abos.

Usage-Based Billing: Jede Pro-Analyse wird als Meter-Event mit `identifier = usage_log.id` gemeldet. Stripe dedupliziert über den Identifier; ein Postgres-Advisory-Lock sorgt dafür, dass bei mehreren Workern nur einer meldet. Fehlgeschlagene Meldungen werden im nächsten Lauf wiederholt.

## Architekturentscheidungen

**Prisma als Schema- und Migrationsquelle, asyncpg im Python-Hot-Path.** Prisma Client Python ist seit April 2025 archiviert und an Prisma 5 gebunden; für ein kommerzielles Produkt ist das kein tragfähiges Fundament. Deshalb ist `prisma/schema.prisma` die einzige Quelle der Wahrheit: Prisma erzeugt und migriert das Schema, das Next.js-Dashboard nutzt den typisierten Prisma Client 7, und die FastAPI-Decision-API spricht dieselben Tabellen über einen schlanken asyncpg-Layer an. Snake-Case-Mapping, DB-seitige UUID-Defaults und `timestamptz` sorgen dafür, dass beide Laufzeiten konfliktfrei arbeiten.

**Modellwahl ist Konfiguration.** Standard ist `claude-opus-5-5` mit `effort: low` (Klassifikation braucht wenig Denkaufwand) und aktiviertem serverseitigem Refusal-Fallback (`fallbacks: "default"`). Über `ANTHROPIC_MODEL` lässt sich jedes andere Claude-Modell setzen; die Engine passt `effort` und Fallbacks automatisch an die Fähigkeiten des Modells an. Miss Latenz und Kosten pro Analyse an echtem Ticketvolumen, bevor du dich auf ein Modell festlegst. Das gilt auch für die Preisaussage auf der Landingpage.

**Verfügbarkeit vor Perfektion.** LLM-Ausfälle führen zur Heuristik statt zu Fehlern, das Widget blockiert nie ein Kontaktformular, und ein fehlgeschlagener Usage-Eintrag wird geloggt (`USAGE_METERING_FAILED`), statt die Antwort zu verwerfen.

## Tests & Qualität

```bash
# Backend: 52 Tests, Integrationstests gegen echtes PostgreSQL (Schema aus den Prisma-Migrationen)
cd backend && TEST_DATABASE_URL=postgresql://decide:decide@localhost:5432/decidecommerce_test pytest
ruff check . && ruff format --check .

# Frontend
cd frontend && npm run lint && npm run typecheck && npm run build
```

Die Tests decken u. a. die PII-Anonymisierung, die Heuristik, das exakte Request-Format an die Claude API (Mock-Transport), Refusal- und Ausfall-Fallback, Auth/Kontingente/Origin-Prüfung/Metering der Middleware, den kompletten Stripe-Subscription-Lifecycle inkl. Duplikaten und Out-of-Order-Events sowie den Usage-Reporter ab. Die CI (`.github/workflows/ci.yml`) führt alles bei jedem Push aus und baut die Docker-Images.

## Produktions-Checkliste

- [ ] `.env` mit starken Werten für `POSTGRES_PASSWORD` und `INTERNAL_API_SECRET` (`openssl rand -hex 32`)
- [ ] HTTPS vor Frontend und API (Reverse Proxy / Load Balancer); `APP_URL` und `PUBLIC_API_BASE_URL` auf die HTTPS-URLs setzen (aktiviert `Secure`-Cookies)
- [ ] `ANTHROPIC_API_KEY` setzen und Modell/Effort an echten Tickets evaluieren
- [ ] Stripe im Live-Modus einrichten (siehe oben) und Webhook-Zustellung prüfen
- [ ] Impressum und Datenschutzerklärung ausfüllen (`frontend/src/app/impressum`, `…/datenschutz`), AV-Verträge mit KI-Anbieter, Hosting und Stripe
- [ ] Postgres-Backups und Monitoring; Alarm auf `USAGE_METERING_FAILED` im Backend-Log
- [ ] Bei mehreren Backend-/Frontend-Replikas: Rate-Limiter (`services/rate_limit.py`, `lib/rate-limit.ts`) auf Redis umstellen
