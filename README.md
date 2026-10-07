# DecideCommerce

**Strukturierte Triage für E-Commerce-Support.** DecideCommerce liefert Kategorie, Dringlichkeit, Intent-Flags und Konfidenz. Eine lokale Schutzschicht maskiert erkannte PII-Muster vor dem Modellaufruf; die Erkennung ist heuristisch und keine garantierte Anonymisierung.

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
7. [Decision-Engines: Claude, lokales Modell (Ollama/Tev1), TypeSafe Jev](#decision-engines)
8. [Deployment: eigener Server und Vercel](#deployment-eigener-server-und-vercel)
9. [Shop-Widget](#shop-widget)
10. [Stripe einrichten](#stripe-einrichten)
11. [Architekturentscheidungen](#architekturentscheidungen)
12. [Tests & Qualität](#tests--qualität)
13. [Produktions-Checkliste](#produktions-checkliste)

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

  LLM["Decision-Modell<br/>Ollama · Tev1 (lokal)<br/>oder Claude / TypeSafe Jev"]
  ST["Stripe<br/>Checkout · Webhooks · Meter"]

  W -- "x-api-key (Publishable)" --> BE
  H -- "x-api-key (Secret)" --> BE
  FE -- "Prisma Client" --> PG
  FE -- "Live-Demo (internes Secret)" --> BE
  FE -- "Checkout / Portal" --> ST
  BE -- "asyncpg" --> PG
  BE -- "PII-maskierter Text<br/>/v1/systemone" --> LLM
  ST -- "customer.subscription.*" --> BE
  BE -- "Meter Events" --> ST
```

**Request-Pfad `POST /api/v1/analyze-ticket`:**

1. `ApiKeyAuthMiddleware` (reine ASGI-Middleware): Key-Hash gegen PostgreSQL validieren → Tenant zuordnen → Origin-Allowlist (Publishable Keys) → Rate-Limit. Tarif, Kontingent und Queue-Kapazität werden bei der Job-Annahme pro Tenant atomar geprüft.
2. **Lokale PII-Maskierung** (`backend/app/privacy/pii.py`): Erkannte E-Mails, Telefonnummern, Klarnamen, Adressen, IBANs (Prüfsumme), Kreditkarten (Luhn) und IPs werden durch Platzhalter wie `[ANONYMOUS_EMAIL]` ersetzt. Die Heuristiken erkennen nicht jede PII. Bestellnummern bleiben erhalten.
3. **Decision Engine** (Single Pass, per `DECISION_ENGINE` wählbar): ein lokales Decision-Modell über Ollama (Tev1), Claude mit nativen Structured Outputs oder TypeSafe Jev, siehe [Decision-Engines](#decision-engines). Fällt die Engine aus (Timeout, Rate-Limit, Refusal, Modell nicht geladen), entscheidet eine deterministische Heuristik; die Antwort trägt dann `degraded: true`. Deterministische Leitplanken gelten für jede Engine: Eine erkannte Bestellnummer setzt `contains_order_number`, eine Anwalts-, Klage-, Polizei- oder Betrugsdrohung setzt die Dringlichkeit auf 5.
4. Schnelle Analysen antworten synchron. Dauert die Analyse länger als `ANALYSIS_SYNC_WAIT_SECONDS`, wird ein dauerhafter Job mit `202 Accepted` zurückgegeben. Ergebnis und `UsageLog` werden nach erfolgreicher Analyse gemeinsam gespeichert; Pro-Nutzung wird anschließend als Stripe-Meter-Event gemeldet.

## Verzeichnisstruktur

```
.
├── docker-compose.yml            # postgres · migrate · backend · frontend (+ ollama, caddy als Profile)
├── docker-compose.gpu.yml        # NVIDIA-GPU für Ollama
├── deploy/Caddyfile              # HTTPS für den Betrieb auf einem Server
├── .env.example                  # alle Umgebungsvariablen, dokumentiert
├── prisma/                       # Single Source of Truth für das DB-Schema
│   ├── schema.prisma
│   └── migrations/               # von `prisma migrate` erzeugtes SQL
├── backend/                      # FastAPI Decision API (Python 3.12)
│   ├── Dockerfile                # Multi-Stage, Non-Root
│   ├── requirements.txt / requirements-dev.txt / pyproject.toml
│   ├── evals/                    # Messung einer Engine auf gelabelten Tickets
│   ├── app/
│   │   ├── main.py               # App-Factory, Lifespan, Fehlerformat
│   │   ├── config.py             # pydantic-settings
│   │   ├── container.py          # Dependency-Komposition
│   │   ├── db.py                 # asyncpg-Pool
│   │   ├── schemas.py            # TicketDecision & API-Verträge
│   │   ├── security.py           # Key-Format & Hashing
│   │   ├── middleware/api_key_auth.py
│   │   ├── privacy/pii.py, names.py
│   │   ├── decision/             # systemone_engine · anthropic_engine · heuristic_engine · pipeline
│   │   ├── services/             # tenants · entitlements · usage · stripe_sync · rate_limit
│   │   └── routers/              # analyze · webhooks · demo · health
│   └── tests/                    # Unit + Integration gegen PostgreSQL
├── frontend/                     # Next.js 16 (App Router), Tailwind CSS 4, TypeScript
│   ├── Dockerfile                # deps → builder → migrator / runner (standalone)
│   ├── prisma.config.ts          # zeigt auf ../prisma
│   ├── vercel.json               # Region fra1 für das Frontend auf Vercel
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
| `BACKEND_DATABASE_URL` | compose | Externe DB nur fürs Backend (z. B. Neon, wenn das Frontend auf Vercel läuft) |
| `DECISION_ENGINE` | backend | `auto` · `anthropic` · `heuristic` |
| `ANTHROPIC_API_KEY` | backend | Claude-API-Key; ohne Key nutzt `auto` die Heuristik |
| `ANTHROPIC_MODEL` | backend | Standard `claude-opus-5-5`, frei wählbar |
| `SYSTEMONE_BASE_URL`, `SYSTEMONE_MODEL` | backend | Decision-Modell für `DECISION_ENGINE=systemone` (Ollama: `http://ollama:11434`, `tev1:0.8b`/`tev1:4b`) |
| `SYSTEMONE_API_KEY` | backend | Nur für TypeSafe Jev oder einen Auth-Proxy vor Ollama |
| `SYSTEMONE_CANCELLATION_THRESHOLD` | backend | Storno-Schwelle, Standard 0,9 (siehe Evaluation) |
| `COMPOSE_PROFILES` | compose | `local-ai` (Ollama), `https` (Caddy) |
| `ANTHROPIC_EFFORT` | backend | Denkaufwand, Standard `low` (schnell & günstig) |
| `INTERNAL_API_SECRET` | beide | Geteiltes Secret für den Live-Demo-Proxy |
| `APP_URL`, `PUBLIC_API_BASE_URL` | frontend | Öffentliche URLs (Redirects, Snippets, Widget) |
| `STRIPE_SECRET_KEY` | beide | Stripe-API-Key |
| `STRIPE_WEBHOOK_SECRET` | backend | Signing Secret des Webhook-Endpunkts |
| `STRIPE_PRICE_PRO_BASE`, `STRIPE_PRICE_PRO_METERED` | frontend | Preis-IDs für Checkout |
| `STRIPE_METER_EVENT_NAME` | backend | Event-Name des Billing Meters |
| `FREE_TIER_MONTHLY_LIMIT` | beide | Analysen pro Monat im Free-Tarif (Standard 250) |
| `ANALYSIS_SYNC_WAIT_SECONDS` | backend | Maximale Inline-Wartezeit vor `202 Accepted` (Standard 1,5 s) |
| `ANALYSIS_WORKER_CONCURRENCY` | backend | Gleichzeitige Job-Worker pro Backend-Prozess |
| `ANALYSIS_MAX_PENDING_PER_TENANT` | backend | Schutz vor unbegrenzt anwachsenden Tenant-Queues |
| `ANALYSIS_JOB_RETENTION_DAYS` | backend | Aufbewahrungszeit für Jobstatus und anonymisiertes Ergebnis |
| `MAX_TICKET_CHARS` | backend | Maximale Textlänge einer einzelnen Nachricht (Standard 20.000) |
| `MAX_REQUEST_BODY_BYTES` | backend | Harte Grenze für Analyse-Request-Bodies vor JSON-Parsing (Standard 262.144 Bytes) |
| `RATE_LIMIT_SECRET_KEY_PER_MINUTE` | backend | Shared Token-Bucket-Limit für Secret Keys, in PostgreSQL gespeichert (Standard 600) |
| `RATE_LIMIT_PUBLISHABLE_KEY_PER_MINUTE` | backend | Shared Token-Bucket-Limit für Publishable Keys (Standard 60) |

Alle Frontend-Variablen werden **zur Laufzeit** gelesen (keine `NEXT_PUBLIC_*`), damit ein einziges Image in jeder Umgebung läuft.

## Decision API

```bash
curl -X POST http://localhost:8000/api/v1/analyze-ticket \
  -H "x-api-key: dc_sk_…" \
  -H "content-type: application/json" \
  -d '{"text": "Wo bleibt meine Bestellung #1001? Ich warte seit 2 Wochen!", "external_id": "zendesk-48213"}'
```

Der Aufrufer wählt keinen Modus: Das Backend wartet standardmäßig bis zu 1,5 Sekunden. Ist das Ergebnis dann noch nicht fertig, kommt `202` mit `id`, `status` und `status_url`. Mit demselben API-Key den Status abfragen; `Retry-After` gibt den nächsten sinnvollen Abfragezeitpunkt an. Sobald die Analyse fertig ist, enthält `result` dieselbe Antwort wie die synchrone Route.

```bash
curl http://localhost:8000/api/v1/analysis-jobs/job_<id> \
  -H "x-api-key: dc_sk_…"
```

Gleiche Retries mit derselben `external_id` und identischem Inhalt liefern automatisch denselben Job. Ein expliziter `Idempotency-Key` ist für Tickets ohne `external_id` empfohlen; gleicher Schlüssel mit anderem Inhalt wird mit `409 idempotency_key_reused` abgelehnt. Jobs speichern den vorab maskierten Text und das Ergebnis, einschließlich der maskierten Textfassung, bis `ANALYSIS_JOB_RETENTION_DAYS` abläuft. `degraded`-Ergebnisse werden protokolliert, aber nicht an Stripe gemeldet. Publishable Keys dürfen Statusjobs ebenfalls nur von ihrer freigegebenen Origin abrufen.

| Feld | Typ | Beschreibung |
|---|---|---|
| `category` | Enum | `WHERE_IS_MY_ORDER`, `RETURN_OR_REFUND`, `PRODUCT_ISSUE`, `PAYMENT_OR_INVOICE`, `GENERAL_INQUIRY` |
| `urgency` | 1–5 | 5 = Kundenwut oder rechtliche Drohung |
| `flags.is_cancellation_request` | bool | Sofortiger Stornierungswunsch |
| `flags.contains_order_number` | bool | Bestell-/Rechnungsnummer im Text |
| `confidence` | 0.0–1.0 | Sicherheit der Klassifikation |
| `engine`, `degraded` | | Welche Engine entschieden hat; `true`, wenn der Fallback griff |
| `pii` | | Anzahl maskierter Entitäten je Typ |
| `anonymized_text` | string | Der Text, wie ihn das Modell gesehen hat; maskierte Inhalte können weiterhin PII enthalten |

Fehler haben immer die Form `{"error": {"code": "...", "message": "..."}}`: `401 missing_api_key|invalid_api_key`, `402 monthly_quota_exceeded|subscription_inactive`, `403 origin_not_allowed`, `409 idempotency_key_reused`, `413 payload_too_large`, `422 invalid_request`, `429 rate_limited|analysis_queue_full` (mit `Retry-After`), `503 analysis_failed`.

**API-Keys:** `dc_sk_…` (Secret, nur serverseitig) und `dc_pk_…` (Publishable, für das Widget, an freigegebene Domains gebunden und strenger rate-limitiert). Gespeichert wird ausschließlich ein SHA-256-Hash; der Klartext wird genau einmal im Dashboard angezeigt. Ein Widerruf greift nach spätestens `API_KEY_CACHE_TTL_SECONDS` (Standard 15 s).

## Decision-Engines

| `DECISION_ENGINE` | Was entscheidet | API-Key | Daten verlassen den Server | Latenz |
|---|---|---|---|---|
| `systemone` + Ollama | lokales Decision-Modell **Tev1** (Together AI) | nein | **nein** | CPU: ~2 s (0.8b) / ~6 s (4b), GPU: deutlich unter 1 s (nicht gemessen) |
| `systemone` + TypeSafe | gehostetes **Jev** (TypeSafe) | ja | ja (USA) | laut Anbieter 70–500 ms |
| `anthropic` / `auto` | Claude mit Structured Outputs | ja | ja | ~1 s |
| `heuristic` | lokale Regel-Engine | nein | nein | < 1 ms |

### Lokales Decision-Modell mit Ollama (kein API-Key)

„System One“-Modelle wie Tev1 generieren keinen Text. Sie beantworten typisierte Fragen mit Wahrscheinlichkeiten: Kategorie als `choice`, Dringlichkeit als `score`, Storno-Wunsch als `noul`. Ollama stellt dafür seit Version 0.35 den Endpunkt `POST /v1/systemone` bereit; TypeSafe Jev nutzt dasselbe Protokoll. `backend/app/decision/systemone_engine.py` spricht beide.

```bash
# .env
COMPOSE_PROFILES=local-ai
DECISION_ENGINE=systemone
SYSTEMONE_MODEL=tev1:0.8b        # GPU: tev1:4b + docker-compose.gpu.yml

docker compose up --build        # lädt das Modell beim ersten Start (~0,8 bzw. 4,5 GB)
```

Der Job `ollama-pull` lädt das Modell nur, wenn es noch fehlt; Neustarts brauchen also keine Verbindung zur Ollama-Registry. Schlägt der erste Download fehl, startet das Backend trotzdem und entscheidet mit der Heuristik (`degraded: true`); das Log nennt den passenden `ollama pull`-Befehl.

Ohne Docker: Ollama ≥ 0.35 installieren, `ollama pull tev1:0.8b`, dann `DECISION_ENGINE=systemone SYSTEMONE_BASE_URL=http://localhost:11434` für das Backend setzen.

**Messung** (`backend/evals/run_eval.py`, 30 gelabelte DE/EN-Tickets, Ollama 0.35.1, 4 CPU-Kerne, Storno-Schwelle 0,9):

| Engine | Kategorie | Dringlichkeit exakt / ±1 | Storno Precision / Recall | Latenz Median |
|---|---|---|---|---|
| `tev1:4b` | 100 % | 80 % / 97 % | 75 % / 100 % | 6,4 s |
| `tev1:0.8b` | 90 % | 70 % / 93 % | 75 % / 100 % | 1,6 s |
| Heuristik | 93 % | 67 % / 93 % | 100 % / 100 % | < 1 ms |

Die Tickets sind synthetisch und vom selben Autor wie die Heuristik-Regeln – die Heuristik ist darauf also begünstigt. Vor dem Umstieg mit echten, sorgfältig bereinigten Tickets messen; PII-Maskierung garantiert keine Anonymisierung:

```bash
cd backend
python -m evals.run_eval --engine heuristic --tickets meine_tickets.jsonl
DECISION_ENGINE=systemone SYSTEMONE_MODEL=tev1:4b python -m evals.run_eval --engine systemone --tickets meine_tickets.jsonl
```

**Wichtig zu Tev1:**
- **Lizenz:** Die Hugging-Face-Karten von Together AI sagen, die Lizenz der feinjustierten Gewichte werde „noch finalisiert“. Vor dem kommerziellen Einsatz schriftlich bei Together AI bestätigen lassen. Alternative mit Apache-2.0-Lizenz: Nimble 9B (`SYSTEMONE_MODEL=nimble`, ungetestet).
- **Sprache:** Primär auf Englisch trainiert; Deutsch ist vom Hersteller nicht evaluiert (siehe Messung oben). Fragen und Optionen sendet die Engine deshalb auf Englisch, den Ticket-Text unverändert.
- **Kontext:** ca. 2.048 Tokens pro Frage, und jede Frage ist ein eigener Prompt mit vollem Text. Die Engine kürzt den Text daher auf `SYSTEMONE_MAX_STATE_CHARS` (3.000) und stellt nur drei Fragen; `contains_order_number` wird deterministisch per Regex bestimmt.
- **Wahrscheinlichkeiten sind nicht kalibriert.** Schwellen (z. B. `SYSTEMONE_CANCELLATION_THRESHOLD`) an eigenen Tickets einstellen.
- **Widget:** Auf CPU-Servern im Script-Tag `data-timeout="8000"` setzen (Standard 3.000 ms).
- **Sicherheit:** Ollama hat keine Authentifizierung. In Compose ist Port 11434 nur im internen Netz erreichbar – nie veröffentlichen.
- **Kaltstart:** In Compose bleibt das Modell dauerhaft geladen (`OLLAMA_KEEP_ALIVE=-1`); das Backend wärmt es beim Start vor. Ein gesetztes `SYSTEMONE_KEEP_ALIVE` (z. B. `30m`, ohne Docker der Standard) überstimmt das pro Anfrage.

### Gehostetes TypeSafe Jev

`SYSTEMONE_BASE_URL=https://api.typesafe.ai`, `SYSTEMONE_API_KEY=…`, `SYSTEMONE_MODEL=jev-latest` (oder versioniert, z. B. `jev-1.13.0`, wenn Schwellen kalibriert sind), `SYSTEMONE_KEEP_ALIVE=` (leer). Laut Datenschutzerklärung von TypeSafe werden die Daten in den USA verarbeitet (DPA mit Standardvertragsklauseln) – trotz PII-Anonymisierung für DSGVO-sensible Händler abwägen.

## Deployment: eigener Server und Vercel

Ein lokales Modell braucht einen dauerhaft laufenden Prozess mit mehreren GB RAM. **Auf Vercel ist das nicht möglich**: Vercel Functions haben keine GPU, höchstens 4 GB RAM (das 4B-Modell allein hat 4,5 GB), sind kurzlebig und würden das Modell bei jedem Kaltstart neu laden. Vercel eignet sich für das Frontend, nicht für Ollama.

### Option A (empfohlen): alles auf einem Server

Ein EU-Server mit Docker, z. B. Hetzner (Stand Oktober 2026, netto): CPU **AX42** (8 Kerne, 64 GB) ab ca. 97 €/Monat oder **CCX33** (8 vCPU, 32 GB) ca. 138 €/Monat; GPU **GEX45** (RTX PRO 4000, 24 GB) ca. 214 €/Monat für Antworten deutlich unter einer Sekunde.

```bash
# DNS: app.deine-domain.de und api.deine-domain.de -> Server-IP
# .env
COMPOSE_PROFILES=local-ai,https
ENVIRONMENT=production
DECISION_ENGINE=systemone
APP_DOMAIN=app.deine-domain.de
API_DOMAIN=api.deine-domain.de
APP_URL=https://app.deine-domain.de
PUBLIC_API_BASE_URL=https://api.deine-domain.de
BACKEND_BIND=127.0.0.1
FRONTEND_BIND=127.0.0.1
POSTGRES_PASSWORD=…            # openssl rand -hex 24
INTERNAL_API_SECRET=…          # openssl rand -hex 32

docker compose up -d --build
```

Caddy (`deploy/Caddyfile`) holt die TLS-Zertifikate automatisch; die Ports 80 und 443 müssen offen sein. Ollama, Postgres und das Backend sind nur intern bzw. über Caddy erreichbar; die Ticket-Texte bleiben auf diesem Server.

### Option B: Frontend auf Vercel, Backend + Modell auf dem Server

1. **Server** wie in Option A, aber ohne Frontend-Domain; das Backend ist unter `https://api.deine-domain.de` erreichbar.
2. **Datenbank:** Das Frontend auf Vercel braucht eine öffentlich erreichbare Postgres-Datenbank – am einfachsten Neon (Vercel Marketplace, Region Frankfurt) für Frontend **und** Backend. Neon liefert `DATABASE_URL` (gepoolt, Laufzeit) und `DATABASE_URL_UNPOOLED` (direkt, Migrationen); `prisma.config.ts` nutzt automatisch die direkte URL. Auf dem Server in `.env` **`BACKEND_DATABASE_URL`** auf die direkte Neon-URL setzen (dauerhafter Server mit kleinem Pool, daher ohne Pooler) und `sslmode=require` durch `sslmode=verify-full` ersetzen, damit das Zertifikat geprüft wird; `channel_binding` entfernt das Backend selbst. Die lokalen Container `postgres`, `migrate` und `frontend` starten dann zwar mit, werden aber nicht genutzt – die Migrationen übernimmt das Vercel-Deployment.
3. **Vercel-Projekt** aus diesem Repo importieren: Root Directory `frontend`, Framework Next.js. Die Option „Include source files outside of the Root Directory in the Build Step“ muss aktiv sein (Standard), weil das Prisma-Schema in `../prisma` liegt. `frontend/vercel.json` setzt die Region `fra1` (Frankfurt).
4. **Umgebungsvariablen** im Vercel-Projekt: `DATABASE_URL`, `DATABASE_URL_UNPOOLED` (Neon), `APP_URL=https://<vercel-domain>`, `PUBLIC_API_BASE_URL` und `BACKEND_INTERNAL_URL=https://api.deine-domain.de`, `INTERNAL_API_SECRET` (gleicher Wert wie im Backend), Stripe-Variablen.
5. **Migrationen:** Das Skript `vercel-build` führt `prisma migrate deploy` nur bei Production-Deployments aus (`scripts/vercel-migrate.mjs`), damit Preview-Deployments nie die Produktions-DB migrieren. Mit Neon-Preview-Branching kann `MIGRATE_PREVIEW=1` gesetzt werden; `MIGRATE_ON_BUILD=0` schaltet es ab (z. B. wenn ein CI-Job migriert).

Das Frontend nutzt auf Vercel `attachDatabasePool` (`@vercel/functions`), damit Fluid Compute Leerlauf-Verbindungen sauber schließt; in Docker ist das wirkungslos.

**Backend auf Vercel?** Technisch unterstützt Vercel FastAPI inzwischen ohne Konfiguration, inklusive Lifespan. Mit einem lokalen Modell bringt das aber nichts – Ollama braucht ohnehin einen Server – und im Serverless-Betrieb fehlen bisher zwei Dinge: Der Stripe-Usage-Reporter läuft als Hintergrundschleife und müsste ein Cron-Endpunkt werden, und Rate-Limits/Key-Cache gelten pro Instanz. Außerdem liest Vercel Abhängigkeiten aus `pyproject.toml` vor `requirements.txt`. Für Claude oder TypeSafe Jev als Engine ist ein Backend auf Vercel denkbar, aber nicht vorbereitet.

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

`dc_status` (`ok` | `degraded` | `queued` | `processing` | `error` | `timeout`), `dc_degraded`, `dc_category`, `dc_urgency`, `dc_is_cancellation_request`, `dc_contains_order_number`, `dc_confidence`, `dc_analysis_id`, `dc_job_id`, `dc_status_url`, `dc_idempotency_key`

Das Formular wird **nie auf die gesamte Analyse blockiert**: Bei schneller Antwort kommen die Entscheidungsfelder direkt mit. Bei `202` wird sofort mit `dc_status=queued|processing` und Job-Referenz gesendet; das Shop-Backend kann `dc_status_url` abfragen. Secret Keys verweigert das Widget. Für AJAX-Formulare gibt es `window.DecideCommerce.analyze(text)`, `getJob(id)`, `waitForJob(id)` und die Events `decidecommerce:processing` sowie `decidecommerce:decision`.

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

**Modellwahl ist Konfiguration.** Neben dem lokalen Decision-Modell (siehe oben) ist Claude die Engine für `DECISION_ENGINE=auto`/`anthropic`: Standard ist `claude-opus-5-5` mit `effort: low` (Klassifikation braucht wenig Denkaufwand) und aktiviertem serverseitigem Refusal-Fallback (`fallbacks: "default"`). Über `ANTHROPIC_MODEL` lässt sich jedes andere Claude-Modell setzen; die Engine passt `effort` und Fallbacks automatisch an die Fähigkeiten des Modells an. Miss Latenz und Kosten pro Analyse an echtem Ticketvolumen, bevor du dich auf ein Modell festlegst. Das gilt auch für die Preisaussage auf der Landingpage.

**Verfügbarkeit vor Perfektion.** LLM-Ausfälle führen zur Heuristik statt zu Fehlern, das Widget blockiert nie ein Kontaktformular, und ein fehlgeschlagener Usage-Eintrag wird geloggt (`USAGE_METERING_FAILED`), statt die Antwort zu verwerfen.

## Tests & Qualität

```bash
# Backend: 91 Tests, Integrationstests gegen echtes PostgreSQL (Schema aus den Prisma-Migrationen)
cd backend && TEST_DATABASE_URL=postgresql://decide:decide@localhost:5432/decidecommerce_test pytest
ruff check . && ruff format --check .

# Frontend
cd frontend && npm run lint && npm run typecheck && npm run build
```

Optional zusätzlich gegen ein laufendes Ollama: `SYSTEMONE_LIVE_URL=http://localhost:11434 SYSTEMONE_LIVE_MODEL=tev1:0.8b pytest -k live`.

Die Tests decken u. a. die PII-Anonymisierung, das System-One-Protokoll (Antwortformat von Ollama 0.35.1, Fehlerpfade, Schwellen, Leitplanken), die Heuristik, das exakte Request-Format an die Claude API (Mock-Transport), Refusal- und Ausfall-Fallback, Auth/Kontingente/Origin-Prüfung/Metering der Middleware, den kompletten Stripe-Subscription-Lifecycle inkl. Duplikaten und Out-of-Order-Events sowie den Usage-Reporter ab. Die CI (`.github/workflows/ci.yml`) führt alles bei jedem Push aus und baut die Docker-Images.

## Produktions-Checkliste

- [ ] `.env` mit starken Werten für `POSTGRES_PASSWORD` und `INTERNAL_API_SECRET` (`openssl rand -hex 32`)
- [ ] HTTPS vor Frontend und API (Reverse Proxy / Load Balancer); `APP_URL` und `PUBLIC_API_BASE_URL` auf die HTTPS-URLs setzen (aktiviert `Secure`-Cookies)
- [ ] Decision-Engine wählen und mit echten Tickets messen (`backend/evals/run_eval.py`); für Tev1 die Lizenz der Gewichte bei Together AI klären
- [ ] Stripe im Live-Modus einrichten (siehe oben) und Webhook-Zustellung prüfen
- [ ] Impressum und Datenschutzerklärung ausfüllen (`frontend/src/app/impressum`, `…/datenschutz`), AV-Verträge mit KI-Anbieter, Hosting und Stripe
- [ ] Postgres-Backups und Monitoring; Alarm auf `USAGE_METERING_FAILED` im Backend-Log
- [ ] Bei mehreren Frontend-Replikas den Besucher-IP-Limiter für die Live-Demo auf einen gemeinsamen Redis-/Upstash-Store umstellen; Backend-API-Key-Limits teilen sich PostgreSQL.
