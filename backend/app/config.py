"""Runtime configuration. Everything can be overridden with environment variables."""
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = Path(os.getenv("OSINT_DB_PATH", str(DATA_DIR / "osint.db")))
SEED_PATH = APP_DIR / "seed" / "scenario.json"
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"

# Re-anchor the synthetic scenario to "now" on every start so the demo always looks fresh.
SEED_ON_START = os.getenv("SEED_ON_START", "1") == "1"

# --- Correlation & scoring -------------------------------------------------
LOOKBACK_HOURS = float(os.getenv("LOOKBACK_HOURS", "240"))          # signals older than this are ignored
CLUSTER_GAP_HOURS = float(os.getenv("CLUSTER_GAP_HOURS", "48"))     # max gap inside one regional cluster
CROSS_CATEGORY_LINK_HOURS = float(os.getenv("CROSS_CATEGORY_LINK_HOURS", "24"))
RECENCY_HALF_LIFE_HOURS = float(os.getenv("RECENCY_HALF_LIFE_HOURS", "48"))

# --- Live ingestion --------------------------------------------------------
LIVE_INGEST_INTERVAL_MIN = float(os.getenv("LIVE_INGEST_INTERVAL_MIN", "0"))  # 0 = only on demand
HTTP_TIMEOUT = 15.0
USER_AGENT = "HybridScope-OSINT/0.1 (research prototype)"

RSS_FEEDS = [
    {"name": "The Record", "url": "https://therecord.media/feed", "type": "news", "reliability": 0.85},
    {"name": "SANS ISC", "url": "https://isc.sans.edu/rssfeed_full.xml", "type": "advisory", "reliability": 0.85},
    {"name": "BleepingComputer", "url": "https://www.bleepingcomputer.com/feed/", "type": "news", "reliability": 0.8},
    {"name": "The Hacker News", "url": "https://feeds.feedburner.com/TheHackersNews", "type": "news", "reliability": 0.75},
    {"name": "Krebs on Security", "url": "https://krebsonsecurity.com/feed/", "type": "news", "reliability": 0.85},
    {"name": "EUvsDisinfo", "url": "https://euvsdisinfo.eu/feed/", "type": "research", "reliability": 0.85},
    {"name": "Balkan Insight", "url": "https://balkaninsight.com/feed/", "type": "news", "reliability": 0.8},
]

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_QUERY = (
    '(cyberattack OR ransomware OR disinformation OR sabotage OR "critical infrastructure" '
    'OR DDoS OR "power outage" OR "subsea cable") sourcelang:english'
)
GDELT_MAX_RECORDS = 75

# Reliability prior for publishers seen via GDELT (unknown domains fall back to the default).
DOMAIN_RELIABILITY = {
    "reuters.com": 0.9, "apnews.com": 0.9, "bbc.com": 0.85, "bbc.co.uk": 0.85, "nytimes.com": 0.85,
    "washingtonpost.com": 0.85, "theguardian.com": 0.8, "ft.com": 0.85, "politico.eu": 0.8,
    "therecord.media": 0.85, "bleepingcomputer.com": 0.8, "securityweek.com": 0.8, "darkreading.com": 0.75,
    "euronews.com": 0.75, "aljazeera.com": 0.75, "rferl.org": 0.75, "balkaninsight.com": 0.8,
    "yle.fi": 0.85, "err.ee": 0.85, "lrt.lt": 0.8, "dw.com": 0.85, "france24.com": 0.8,
}
DEFAULT_RELIABILITY = 0.55

# --- Optional LLM provider (OpenAI-compatible: Groq, Gemini, Ollama, ...) ---
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_FOR_LIVE = os.getenv("LLM_FOR_LIVE", "0") == "1"  # also run the LLM on every live item (rate limits!)


def llm_enabled() -> bool:
    return bool(LLM_BASE_URL and LLM_MODEL)
