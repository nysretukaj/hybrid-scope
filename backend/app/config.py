"""Runtime configuration. Everything can be overridden with environment variables."""
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent


def _load_dotenv(path: Path) -> None:
    """Minimal KEY=VALUE loader so secrets live in backend/.env (git-ignored), never in code.
    Real environment variables win over the file."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


if os.getenv("HYBRIDSCOPE_SKIP_DOTENV") != "1":
    _load_dotenv(BACKEND_DIR / ".env")
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = Path(os.getenv("OSINT_DB_PATH", str(DATA_DIR / "osint.db")))
SEED_PATH = APP_DIR / "seed" / "scenario.json"
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"

# Re-anchor the synthetic scenario to "now" on every start so the demo always looks fresh.
SEED_ON_START = os.getenv("SEED_ON_START", "1") == "1"

# Offline demo: no network calls at all. Live ingest replays a saved snapshot of real, AI-analysed
# signals; Analyze Text answers from cached LLM results. Create the snapshot while online with
# POST /api/demo/snapshot (or `python -m app.snapshot`).
DEMO_OFFLINE = os.getenv("DEMO_OFFLINE", "0") == "1"
# Also load the snapshot when online (e.g. on a fresh cloud instance, so live data shows at once).
LOAD_SNAPSHOT_ON_START = os.getenv("LOAD_SNAPSHOT_ON_START", "0") == "1"

# Public deployment: anyone with the link can look and try Analyze Text, but cannot change the demo.
# State-changing endpoints need the X-Admin-Token header to match ADMIN_TOKEN.
PUBLIC_MODE = os.getenv("PUBLIC_MODE", "0") == "1"
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
ANALYZE_PER_MINUTE = int(os.getenv("ANALYZE_PER_MINUTE", "8"))   # per client IP, public mode only
INGEST_COOLDOWN_S = int(os.getenv("INGEST_COOLDOWN_S", "180"))   # public mode only
SNAPSHOT_PATH = APP_DIR / "seed" / "live_snapshot.json"
SAMPLES_PATH = APP_DIR / "seed" / "analyze_samples.json"

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
    # Kosovo / Albanian-language sources
    {"name": "Prishtina Insight", "url": "https://prishtinainsight.com/feed/", "type": "news", "reliability": 0.8},
    {"name": "Koha", "url": "https://www.koha.net/rss", "type": "news (sq)", "reliability": 0.75},
    {"name": "Kallxo", "url": "https://kallxo.com/feed/", "type": "news (sq)", "reliability": 0.75},
    {"name": "Telegrafi", "url": "https://telegrafi.com/feed/", "type": "news (sq)", "reliability": 0.65},
    {"name": "DW Shqip", "url": "https://rss.dw.com/xml/rss-alb-all", "type": "news (sq)", "reliability": 0.85},
    # German-language sources
    {"name": "heise Security", "url": "https://www.heise.de/security/rss/news-atom.xml", "type": "news (de)", "reliability": 0.85},
    {"name": "tagesschau", "url": "https://www.tagesschau.de/xml/rss2/", "type": "news (de)", "reliability": 0.85},
    {"name": "DW Deutsch", "url": "https://rss.dw.com/xml/rss-de-all", "type": "news (de)", "reliability": 0.85},
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
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
# Provider auto-detected from the key prefix when LLM_BASE_URL is not set.
_KEY_PROVIDERS = {
    "gsk_": "https://api.groq.com/openai/v1",
    "AIza": "https://generativelanguage.googleapis.com/v1beta/openai",
}


def detect_base_url(key: str, explicit: str = "") -> str:
    return (explicit or next((url for prefix, url in _KEY_PROVIDERS.items() if key.startswith(prefix)), "")).rstrip("/")


LLM_BASE_URL = detect_base_url(LLM_API_KEY, os.getenv("LLM_BASE_URL", ""))
LLM_MODEL = os.getenv("LLM_MODEL", "")            # empty = pick the best available model automatically
LLM_MODEL_LIVE = os.getenv("LLM_MODEL_LIVE", "")  # empty = pick a fast model for bulk live analysis
LLM_FOR_LIVE = os.getenv("LLM_FOR_LIVE", "1") == "1"  # upgrade live signals with the LLM in the background
LLM_MAX_PER_INGEST = int(os.getenv("LLM_MAX_PER_INGEST", "60"))
LLM_RPM = float(os.getenv("LLM_RPM", "20"))       # stay under free-tier request/token-per-minute limits


# --- Notifications ------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")
NOTIFY_MIN_LEVEL = os.getenv("NOTIFY_MIN_LEVEL", "CRITICAL")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")


def llm_enabled() -> bool:
    return bool(LLM_BASE_URL and (LLM_MODEL or LLM_API_KEY)) and not DEMO_OFFLINE
