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
    # Government and international organisations
    {"name": "NCSC UK", "url": "https://www.ncsc.gov.uk/api/1/services/v1/all-rss-feed.xml", "type": "official", "reliability": 0.9},
    {"name": "UN News (Europe)", "url": "https://news.un.org/feed/subscribe/en/news/region/europe/feed/rss.xml",
     "type": "official", "reliability": 0.85},
    {"name": "Europol", "url": "https://www.europol.europa.eu/cms/api/rss/news", "type": "official", "reliability": 0.9},
    {"name": "UN News (peace & security)", "url": "https://news.un.org/feed/subscribe/en/news/topic/peace-and-security/feed/rss.xml",
     "type": "official", "reliability": 0.85},
    {"name": "CERT-EU", "url": "https://cert.europa.eu/publications/security-advisories-rss", "type": "advisory", "reliability": 0.95},
    # Kosovo / Albania: news agencies and investigative media (Albanian)
    {"name": "KosovaPress", "url": "https://kosovapress.com/feed/", "type": "news (sq)", "reliability": 0.75},
    {"name": "Insajderi", "url": "https://insajderi.org/feed/", "type": "news (sq)", "reliability": 0.7},
    {"name": "Reporteri", "url": "https://reporteri.net/feed/", "type": "news (sq)", "reliability": 0.65},
    {"name": "Gazeta Express", "url": "https://www.gazetaexpress.com/feed/", "type": "news (sq)", "reliability": 0.65},
    {"name": "Euronews Albania", "url": "https://euronews.al/feed/", "type": "news (sq)", "reliability": 0.75},
    # Fact-checkers and disinformation research: they name the false claims and who spreads them
    {"name": "Hibrid.info", "url": "https://hibrid.info/feed/", "type": "fact-check (sq)", "reliability": 0.85},
    {"name": "Faktoje", "url": "https://faktoje.al/feed/", "type": "fact-check (sq)", "reliability": 0.85},
    {"name": "CORRECTIV", "url": "https://correctiv.org/feed/", "type": "fact-check (de)", "reliability": 0.85},
    {"name": "StopFake", "url": "https://www.stopfake.org/en/feed/", "type": "fact-check", "reliability": 0.75},
    {"name": "Bellingcat", "url": "https://www.bellingcat.com/feed/", "type": "research", "reliability": 0.9},
    # More cyber security news
    {"name": "SecurityWeek", "url": "https://www.securityweek.com/feed/", "type": "news", "reliability": 0.8},
    {"name": "Dark Reading", "url": "https://www.darkreading.com/rss.xml", "type": "news", "reliability": 0.75},
    {"name": "CyberScoop", "url": "https://cyberscoop.com/feed/", "type": "news", "reliability": 0.8},
    # Natural hazards: tells outages caused by earthquakes or floods apart from attacks
    {"name": "GDACS", "url": "https://www.gdacs.org/xml/rss.xml", "type": "disaster", "reliability": 0.9},
    # Public social media: low reliability, used as early indicators, never as confirmation
    {"name": "Mastodon #disinformation", "url": "https://mastodon.social/tags/disinformation.rss", "type": "social",
     "reliability": 0.4},
    {"name": "Mastodon #cybersecurity", "url": "https://mastodon.social/tags/cybersecurity.rss", "type": "social",
     "reliability": 0.4},
    {"name": "Mastodon #Kosovo", "url": "https://mastodon.social/tags/kosovo.rss", "type": "social", "reliability": 0.4},
    # --- State portals: Kosovo, Albania, Serbia ---
    {"name": "Presidenca e Kosovës", "url": "https://president-ksgov.net/feed/", "type": "official (sq)", "reliability": 0.85},
    {"name": "Policia e Kosovës", "url": "https://www.kosovopolice.com/feed/", "type": "official (sq)", "reliability": 0.9},
    {"name": "Policia e Shtetit (Shqipëri)", "url": "https://www.asp.gov.al/feed/", "type": "official (sq)", "reliability": 0.9},
    # official, but of a party to the Kosovo-Serbia dispute: its claims about Kosovo are weighed accordingly
    {"name": "Vlada Srbije", "url": "https://www.srbija.gov.rs/rss", "type": "official (sr)", "reliability": 0.7, "lang": "sr"},
    # --- Organised crime, investigative journalism and civil society ---
    {"name": "OCCRP", "url": "https://www.occrp.org/en/feed", "type": "investigative", "reliability": 0.9},
    {"name": "GI-TOC", "url": "https://globalinitiative.net/feed/", "type": "research", "reliability": 0.85},
    {"name": "KRIK", "url": "https://www.krik.rs/feed/", "type": "investigative (sr)", "reliability": 0.85, "lang": "sr"},
    {"name": "BIRN Albania (Reporter.al)", "url": "https://www.reporter.al/feed/", "type": "investigative (sq)", "reliability": 0.8},
    {"name": "CRTA", "url": "https://crta.rs/feed/", "type": "ngo (sr)", "reliability": 0.8, "lang": "sr"},
    {"name": "Demokracia Plus", "url": "https://dplus.org/feed/", "type": "ngo (sq)", "reliability": 0.8},
    {"name": "Raskrikavanje", "url": "https://www.raskrikavanje.rs/feed/", "type": "fact-check (sr)", "reliability": 0.85, "lang": "sr"},
    {"name": "Istinomer", "url": "https://www.istinomer.rs/feed/", "type": "fact-check (sr)", "reliability": 0.8, "lang": "sr"},
    {"name": "FakeNews Tragač", "url": "https://fakenews.rs/feed/", "type": "fact-check (sr)", "reliability": 0.8, "lang": "sr"},
    # --- Serbian media ---
    {"name": "N1 Srbija", "url": "https://n1info.rs/feed/", "type": "news (sr)", "reliability": 0.75, "lang": "sr"},
    {"name": "Danas", "url": "https://www.danas.rs/feed/", "type": "news (sr)", "reliability": 0.7, "lang": "sr"},
    {"name": "KoSSev", "url": "https://kossev.info/feed/", "type": "news (sr)", "reliability": 0.65, "lang": "sr"},
    # close to the Serbian government: real events, but framing to watch -> low reliability
    {"name": "Politika", "url": "https://www.politika.rs/rss/", "type": "state-aligned (sr)", "reliability": 0.5, "lang": "sr"},
    {"name": "Kosovo Online", "url": "https://www.kosovo-online.com/rss.xml", "type": "state-aligned (sr)", "reliability": 0.4, "lang": "sr"},
    {"name": "Novosti", "url": "https://www.novosti.rs/rss/vesti", "type": "state-aligned (sr)", "reliability": 0.35, "lang": "sr"},
    # Russian state media: monitored for narratives only, never taken as fact (see ingest/policy.py)
    {"name": "Sputnik Srbija", "url": "https://lat.sputnikportal.rs/export/rss2/archive/index.xml", "type": "state-media (sr)",
     "reliability": 0.2, "lang": "sr"},
]

# Public Telegram channels, read from the public web preview (t.me/s/<channel>), no account. Channels of
# hacktivist/DDoS groups can be added here when they are public; Telegram closes many of them quickly.
TELEGRAM_CHANNELS = [
    {"name": "RT Balkan (Telegram)", "channel": "rtbalkan", "type": "state-media (sr)", "reliability": 0.2, "lang": "sr"},
]
# Reports in Serbian are understood by the local AI (the keyword rules cover sq/en/de): this many new
# Serbian reports per ingest are queued for it, threat-looking ones first.
SERBIAN_LOCAL_AI_PER_INGEST = int(os.getenv("SERBIAN_LOCAL_AI_PER_INGEST", "15"))

# Ransomware victims announced by the gangs on their leak sites (via ransomware.live). These are the
# criminals' own claims: low reliability, "alleged"; we link to ransomware.live, never to the leak sites.
RANSOMWARE_URL = "https://api.ransomware.live/v2/recentvictims"
RANSOMWARE_DAYS = 3

# Public websites without a feed, read politely: robots.txt is respected, at most `max` new
# articles per run, one request per second, and only the page's own title/summary/date are kept.
SCRAPE_SOURCES = [
    {"name": "KOS-CERT", "list_url": "https://kos-cert.org/lajme-njoftime",
     "pattern": r"^/lajme-njoftime/[a-z0-9\-]{8,}/?$", "type": "advisory (sq)", "reliability": 0.9, "max": 8,
     "strip_title": " | KOS-CERT"},
    {"name": "Qeveria e Kosovës", "list_url": "https://kryeministri.rks-gov.net/lajme/",
     "pattern": r"^/(?:lajme|news)/[a-z0-9\-]{10,}/?$", "type": "official (sq)", "reliability": 0.85, "max": 8,
     "strip_title": " - Kryeministri"},
]
SCRAPE_DELAY_S = 1.0

# Public incident database: vulnerabilities CISA has seen exploited in real attacks.
CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
CISA_KEV_DAYS = 10   # only entries added in the last N days

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
NOTIFY_LANG = os.getenv("NOTIFY_LANG", "sq") if os.getenv("NOTIFY_LANG", "sq") in ("en", "sq", "de") else "en"
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")


# --- Local AI (Ollama) ----------------------------------------------------------
# Runs on this computer, needs no API key and no internet. "auto" uses it whenever the Ollama
# server answers; "0" switches it off (tests, public deployment), "1" expects it to be there.
# 127.0.0.1, not "localhost": on Windows "localhost" tries IPv6 first and costs ~3 s per request
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "auto").strip().lower()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")            # reads text and images
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")   # multilingual text embeddings
OLLAMA_CUSTOM_MODEL = os.getenv("OLLAMA_CUSTOM_MODEL", "hybridscope")  # built by POST /api/ml/create-model
# Gemma 3 1B fine-tuned (LoRA) on our reports + EUvsDisinfo + Polyglot fake news; does the fake-news check.
# Built with training/finetune_cpu.py + export_ollama.py; empty = no fake-news check.
OLLAMA_FT_MODEL = os.getenv("OLLAMA_FT_MODEL", "hybridscope-ft")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "240"))      # CPU-only machines are slow
LOCAL_LLM_FOR_LIVE = os.getenv("LOCAL_LLM_FOR_LIVE", "0") == "1"  # label new live items with the local LLM
MODELS_DIR = Path(os.getenv("HYBRIDSCOPE_MODELS_DIR", str(DATA_DIR / "models")))
DATASET_DIR = Path(os.getenv("HYBRIDSCOPE_DATASET_DIR", str(DATA_DIR / "dataset")))
CLASSIFIER_MIN_PROB = float(os.getenv("CLASSIFIER_MIN_PROB", "0.7"))  # never decide below this certainty
# The trained model decides on its own only above the certainty at which its decisions were right at
# least this often in cross-validation (the threshold is measured at every training).
CLASSIFIER_TARGET_PRECISION = float(os.getenv("CLASSIFIER_TARGET_PRECISION", "0.9"))
IMAGE_MODEL_ENABLED = os.getenv("IMAGE_MODEL_ENABLED", "1") == "1"  # CLIP vectors of pictures for training
IMAGE_MAX_BYTES = 5 * 1024 * 1024
IMAGE_MAX_SIDE = 1024


def llm_enabled() -> bool:
    return bool(LLM_BASE_URL and (LLM_MODEL or LLM_API_KEY)) and not DEMO_OFFLINE
