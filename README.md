# HybridScope: AI-powered OSINT & hybrid threat intelligence

HybridScope ingests open-source signals (news, RSS, GDELT), classifies them with an AI analysis
layer, **correlates signals across threat domains** (cyber · disinformation · infrastructure ·
physical/geopolitical), and gives analysts a prioritized, explainable, risk-scored view instead of a raw firehose.

```
 RSS feeds ─┐                 ┌── entity extraction (actors, orgs, tech, CVEs, narratives, places)
 GDELT API ─┼─► normalize ───►│── threat classification + severity
 scenario  ─┘   (one schema)  └── analyzer: Claude-precomputed | any OpenAI-compatible LLM | local NLP
                                        │
                                        ▼
                     hybrid correlation (zone × time clusters, entity + cross-domain links)
                                        │
                                        ▼
                     explainable risk score ─► FastAPI ─► React dashboard (feed · map · timeline · evidence)
```

## Quick start (Windows)

```powershell
.\setup.ps1     # once: Python venv + npm install
.\start.ps1     # API on :8000, dashboard on http://localhost:5173
```

Single-port alternative: `cd frontend; npm run build`, then run only the API. It serves the dashboard at http://localhost:8000.

Tests: `cd backend; .\.venv\Scripts\python -m pytest -q`

## How it works

**1. Ingestion & normalization** (`backend/app/ingest/`)
Live sources: The Record, SANS ISC, BleepingComputer, The Hacker News, Krebs on Security, EUvsDisinfo, Balkan Insight, and the GDELT DOC API.
Every item is normalized to one schema: `source, type, reliability, timestamp, title, text, url, zone, country, lat/lon, entities, category, tags, severity, confidence, analyzer, rationale`.
A source that fails is reported and the rest of the run continues.

**2. AI analysis layer** (`backend/app/analyzer/`). Pluggable providers:
| Provider | When | Notes |
|---|---|---|
| `claude-precomputed` | scenario dataset | Analysis written by Claude at build time, stored in `seed/scenario.json` |
| `llm:<model>` | if `LLM_BASE_URL` + `LLM_MODEL` set | Any OpenAI-compatible API (Groq / Gemini free tiers, local Ollama) |
| `local-nlp` | always available | Weighted keyword classifier + gazetteer + regex (CVEs, hashtags, orgs) |

Locations and CVEs always come from deterministic extraction, which is more reliable for these fields than an LLM.

**3. Hybrid correlation** (`backend/app/correlation.py`)
- Signals are clustered by correlation zone (country, or a coupled region such as the Baltic Sea) with at most 48h between consecutive signals.
- Links are created when signals share an actor, org, technology, CVE or narrative, or when they hit different domains within 24h.
- A cluster that spans 2 or more domains and has at least one cross-domain link is flagged as a **HYBRID** pattern.

**4. Explainable risk score** (`backend/app/scoring.py`). Score 0–100 = Σ weight × component:

| Component | Weight | Meaning |
|---|---|---|
| Severity | 35 | 0.6·max + 0.4·mean signal severity |
| Hybrid | 25 | (linked domains − 1) / 3 |
| Corroboration | 15 | independent sources sharing entities |
| Recency | 15 | exponential decay, 48h half-life |
| Reliability | 10 | mean source reliability |

Confidence is a noisy-OR over independent sources: each extra corroborating source raises it.
Levels: CRITICAL ≥ 75 · HIGH ≥ 55 · MEDIUM ≥ 35 · LOW.

## What makes it stand out

| Feature | Where | Why it matters |
|---|---|---|
| **Early-warning replay** | ▶ Replay on any alert | Re-runs the scoring as each signal arrived. In the Kosovo scenario the hybrid pattern is flagged **29h before the first outage** (HIGH 21h before). |
| **Intelligence brief + PDF** | ▤ Intel brief | BLUF, key judgments in ICD 203 estimative language, TTPs, indicators to watch, recommended actions, sourced evidence. Export with the browser's *Save as PDF*. |
| **MITRE ATT&CK · ATT&CK for ICS · DISARM** | alert detail, brief | Heuristic technique mapping per domain (`backend/app/ttp.py`), linked to attack.mitre.org. |
| **Analyst feedback loop** | ✓ Confirm / ✗ False positive | Verdicts update every source's reliability: `(prior·4 + confirmed) / (4 + confirmed + rejected)`. Scores change immediately. |
| **Entity network** | Network tab | Force-directed graph of alerts ↔ shared actors, orgs, tech, CVEs and narratives; highlights entities bridging campaigns. |
| **Albanian · English · German** | EN/SQ/DE toggle | Full UI translation; the analyzer understands sq/de keywords and place names (Prishtinë, Mitrovicës, Deutschland, Wien…). |
| **Local sources** | live ingest | Koha, Kallxo, Telegrafi, Prishtina Insight, DW Shqip, heise Security, tagesschau, DW Deutsch. |
| **Push notifications** | optional | Telegram bot and/or Slack/Discord/Teams webhook for new live alerts ≥ `NOTIFY_MIN_LEVEL`. |

## Data honesty
The **exercise scenario** ("GRIDLOCK") uses real place names with **fictional** events, outlets, actors (GreyMist, Voice of the Valley, Northern Hydra, Pravda-MD) and CVE numbers.
It is labelled `EXERCISE SCENARIO` / `synthetic exercise source` in the UI. Live items always link to their original article.
It is re-anchored to the current time on every API start, or with the **Reset scenario** button.

## Real LLM analysis (free)
1. Create a free key at https://console.groq.com/keys (or a Gemini key at https://aistudio.google.com/apikey).
2. Copy `backend/.env.example` to `backend/.env` (git-ignored) and set `LLM_API_KEY=...`.
3. Restart the API. The provider is detected from the key prefix, and models are picked from the provider's live model list. On Groq today these are `openai/gpt-oss-120b` for **Analyze Text** and `openai/gpt-oss-20b` for live signals.

What happens then:
- **Analyze Text** uses the LLM (~2–3 s) and shows the offline keyword-NLP result next to it as a baseline.
- **Live signals** are stored instantly with local NLP, then upgraded by the LLM in the background. The header shows "AI upgrading signals n/N", paced at `LLM_RPM` (default 20/min). Rate limits (HTTP 429) pause and retry.
- Any LLM failure falls back to local NLP, so the demo never breaks. `POST /api/llm/enrich?limit=60` backfills older live signals.

Local alternative without a key: `LLM_BASE_URL=http://localhost:11434/v1` and `LLM_MODEL=qwen2.5:7b` (Ollama).
Other settings: `LIVE_INGEST_INTERVAL_MIN` (auto-ingest), `LOOKBACK_HOURS`, `CLUSTER_GAP_HOURS`, `RECENCY_HALF_LIFE_HOURS`.

## Public URL (Render, free)
The repo contains a `Dockerfile` (it builds the dashboard and serves it with the API on one port) and a `render.yaml` blueprint.

1. Sign in at https://render.com with GitHub.
2. Go to **New → Blueprint** and pick this repository. Render reads `render.yaml`.
3. When asked, paste your Groq key as `LLM_API_KEY`. `ADMIN_TOKEN` is generated automatically.
4. Click **Apply**. The first build takes ~5–8 minutes, and every push to `main` redeploys.

The blueprint runs in **public mode**: visitors can browse everything and try Analyze Text (8 analyses per minute per visitor). Reset, analyst feedback, snapshot export and notifications need the `X-Admin-Token` header, and live ingest refetches at most every 3 minutes. Live sources refresh hourly with AI enrichment capped for the free Groq quota.

Note: free Render instances sleep after ~15 minutes without traffic. Open the URL a minute before you present.

## Offline demo (no internet at the venue)
The repo ships `backend/app/seed/live_snapshot.json`: real live signals already analysed by the LLM, plus cached LLM answers for the Analyze Text samples.

```powershell
cd backend; $env:DEMO_OFFLINE = "1"; .\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

In offline mode the API makes **no network calls**. The UI shows an `OFFLINE DEMO` badge.
- The snapshot loads re-anchored to the current time, so it looks fresh.
- **Ingest live sources** replays the snapshot.
- **Analyze Text** answers from the cached AI results. Other texts fall back to local NLP.
- The map switches to bundled country outlines, and fonts are self-hosted.

To refresh the snapshot the day before the demo, run online with an LLM key: click **Ingest live sources** and wait for the "AI upgrading" badge to finish. Optionally try more texts in **Analyze Text**, since every LLM answer is cached. Then:
```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/demo/snapshot    # or: python -m app.snapshot
```
Only titles, short excerpts (≤ 280 characters) and links of third-party articles are stored.

## Optional: push notifications
```powershell
$env:TELEGRAM_BOT_TOKEN = "<from @BotFather>"; $env:TELEGRAM_CHAT_ID = "<chat id>"
$env:ALERT_WEBHOOK_URL = "<Slack/Discord/Teams incoming webhook>"   # optional, either or both
$env:NOTIFY_MIN_LEVEL = "CRITICAL"; $env:PUBLIC_URL = "http://localhost:8000"
```
New live alerts at or above the level are pushed once after each ingest. A **Send alert** button appears on every alert.

## Demo script (≈4 min)
1. **Signal Stream**: "This is the firehose: hundreds of items from 15 sources in three languages."
2. **Threat Board**: the same data becomes about 20 prioritized alerts. Open **Kosovo (CRITICAL 89)**.
3. Press **▶ Replay**: watch the score climb signal by signal. The hybrid flag appears at the phishing wave, **29 hours before the first outage**. *This is the pitch.*
4. **Correlation timeline** + **MITRE ATT&CK / DISARM** chips: phishing → SCADA exploit → access sale → CERT confirmation, alongside bot amplification and a deepfake.
5. **▤ Intel brief** → *Export PDF*: a ready-to-send product for decision makers.
6. **✓ Confirm** the alert: source reliabilities update live (the system learns from analysts).
7. **Network** tab: entities such as Telegram bridge the Kosovo and Baltic campaigns.
8. Switch **SQ / DE**, click **Ingest live sources** (Koha, Kallxo, heise, tagesschau…) and paste an Albanian article into **Analyze Text**.
