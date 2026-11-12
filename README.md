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

## Data honesty
The **exercise scenario** ("GRIDLOCK") uses real place names with **fictional** events, outlets, actors (GreyMist, Voice of the Valley, Northern Hydra, Pravda-MD) and CVE numbers.
It is labelled `EXERCISE SCENARIO` / `synthetic exercise source` in the UI. Live items always link to their original article.
It is re-anchored to the current time on every API start, or with the **Reset scenario** button.

## Optional: real LLM analysis (free)
```powershell
$env:LLM_BASE_URL = "https://api.groq.com/openai/v1"; $env:LLM_MODEL = "llama-3.1-8b-instant"; $env:LLM_API_KEY = "<key>"
# or local: $env:LLM_BASE_URL = "http://localhost:11434/v1"; $env:LLM_MODEL = "qwen2.5:7b"
$env:LLM_FOR_LIVE = "1"   # also analyse every live item with the LLM (watch rate limits)
```
Other settings: `LIVE_INGEST_INTERVAL_MIN` (auto-ingest), `LOOKBACK_HOURS`, `CLUSTER_GAP_HOURS`, `RECENCY_HALF_LIFE_HOURS`.

## Demo script (≈3 min)
1. **Signal Stream**: "This is the firehose: hundreds of items from 80+ sources."
2. **Threat Board**: the same data becomes about 18 prioritized alerts. Open **Kosovo (CRITICAL 89)**.
3. Follow the **sequence**: Disinformation → Cyber (+12h) → Infrastructure (+41h) → Physical (+43h). No single-domain tool connects these signals.
4. **Correlation timeline**: hover a GreyMist node to see the phishing → SCADA exploit → access sale → CERT confirmation chain.
5. **Why this score?**: every point is explained, and every signal links back to its evidence.
6. Click **Ingest live sources**: real articles arrive and are classified and correlated live (filter: *Live*).
7. **Analyze Text**: paste any article and get entities, domain, severity and region instantly.
