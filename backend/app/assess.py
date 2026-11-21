"""Finer classification and plain assessment of signals and alerts.

Everything here is deterministic and explainable, so it works with or without an LLM:
  - subcategory   the kind of incident inside a category (e.g. cyber -> ransomware)
  - cause         deliberate | accidental | natural | unknown. "unknown" is the default: we never
                  assume hostile intent without words in the text that point to it. For
                  disinformation, "deliberate" = disinformation and "accidental" = misinformation.
  - claim         confirmed | alleged | opinion | reported (how the source states it)
  - target        who or what is affected, when the text names it
  - bands         severity LOW..CRITICAL and confidence low/medium/high, kept separate
  - assessment    impact, urgency, geographic scope, people affected, evidence quality
"""
import re
from datetime import datetime
from functools import lru_cache

from .gazetteer import precision_at
from .normalize import parse_iso

# --- subcategories ----------------------------------------------------------------
# Keyword stems (EN, plus Albanian and German where useful); leading word boundary, so stems
# match inflections. The first subcategory with the most hits wins.
SUBCATEGORIES: dict[str, dict[str, list[str]]] = {
    "cyber": {
        "ransomware": ["ransomware", "ransom", "lösegeld", "erpressungssoftware"],
        "ddos": ["ddos", "denial-of-service", "denial of service", "ddos-angriff"],
        "data_breach": ["data breach", "breach", "data leak", "leaked data", "stolen data", "leak site",
                        "rrjedhje të dhënash", "datenleck"],
        "phishing": ["phishing", "spear-phishing", "smishing", "lure"],
        "espionage": ["espionage", "spionage", "spyware", "apt", "state-sponsored", "state-linked"],
        "intrusion": ["intrusion", "unauthorized access", "unauthorised access", "compromised", "hacked",
                      "hakuar", "gehackt", "backdoor", "access broker"],
        "vulnerability": ["vulnerability", "vulnerabilities", "cve-", "zero-day", "exploit", "flaw", "patch",
                          "cenueshmëri", "sicherheitslücke", "schwachstelle"],
        "malware": ["malware", "wiper", "infostealer", "trojan", "botnet", "softuer keqdashës", "schadsoftware"],
    },
    "disinformation": {
        "deepfake": ["deepfake", "manipulated video", "manipulated image", "cloned voice", "doctored"],
        "bot_network": ["bot network", "bots", "inauthentic", "fake accounts", "troll", "llogari të rreme",
                        "bot-netzwerk"],
        "impersonation": ["impersonat", "cloned", "cloning", "spoofed", "falsely attributed"],
        "coordinated_campaign": ["coordinated", "campaign", "influence operation", "information operation",
                                 "amplif", "doppelganger", "einflussoperation"],
        "fake_news": ["fake news", "hoax", "false claim", "fabricated", "falsely", "rumour", "rumor",
                      "lajm i rremë", "lajme të rreme", "pretendim i rremë", "falschmeldung", "falschnachricht"],
        "propaganda": ["propagand", "narrative", "narrativ", "conspiracy", "verschwörung"],
    },
    "political": {
        "election_interference": ["election interference", "electoral interference", "vote buying",
                                  "vote-buying", "electoral fraud", "election fraud", "ndërhyrje në zgjedhje",
                                  "blerje votash", "manipulim zgjedhor", "wahlbeeinflussung", "wahlmanipulation",
                                  "stimmenkauf"],
        "foreign_interference": ["foreign interference", "meddling", "foreign agent", "covert funding",
                                 "illegal funding", "ndërhyrje e huaj", "einmischung"],
        "coercion": ["coercion", "coerce", "blackmail", "ultimatum", "diplomatic pressure", "economic pressure",
                     "political pressure", "presion diplomatik", "erpressung", "diplomatischer druck"],
        "destabilization": ["destabiliz", "destabilis", "coup", "puppet government", "secession", "separatist",
                            "undermine democracy", "grusht shteti", "putsch", "destabilisier"],
    },
    "infrastructure": {
        "energy": ["power grid", "grid", "outage", "blackout", "power cut", "substation", "power plant",
                   "electricity", "interconnector", "pipeline", "gas supply", "ndërprerja e rrymës", "pa rrymë",
                   "rrjeti elektrik", "energji elektrike", "nënstacion", "termocentral", "gazsjellës",
                   "stromausfall", "stromnetz", "umspannwerk", "kraftwerk"],
        "water": ["water supply", "water treatment", "furnizim me ujë", "furnizimi me ujë", "wasserversorgung"],
        "transport": ["railway", "airport", "container terminal", "port", "flight", "rail"],
        "telecom": ["telecom", "mobile operator", "subsea", "undersea", "cable", "internet outage",
                    "unterseekabel"],
        "ics": ["scada", "ics", "plc", "hmi", "control system", "industrial control"],
    },
    "physical": {
        "terrorism": ["terror", "extremist", "bomb", "hostage", "geisel"],
        "organized_crime": ["organized crime", "organised crime", "trafficking", "smuggling", "cartel",
                            "krim i organizuar", "trafikim", "kontraband", "organisierte kriminalität",
                            "menschenhandel", "schleus"],
        "border": ["border incident", "border", "incursion", "airspace", "illegal crossing", "incident kufitar"],
        "military": ["military", "troops", "missile", "airstrike", "warship", "navy", "mobilisation",
                     "mobilization", "ushtri", "ushtarak", "raket", "militär", "rakete", "bundeswehr"],
        "sabotage": ["sabotage", "sabotim", "anchor", "drone", "drones", "dron", "drohne", "jamming",
                     "gps interference", "störsender", "gps-störung"],
        "unrest": ["protest", "riot", "clashes", "unrest", "trazira", "përleshje", "demonstration"],
        "violent_incident": ["shooting", "explosion", "armed", "assassination", "stabbing", "shpërthim",
                             "sulm i armatosur", "anschlag"],
    },
}

CAUSE_WORDS = {
    "natural": ["storm", "weather", "earthquake", "flood", "wildfire", "heatwave", "lightning", "landslide",
                "stuhi", "tërmet", "përmbytje", "sturm", "unwetter", "erdbeben", "hochwasser"],
    "accidental": ["technical fault", "technical failure", "malfunction", "maintenance", "human error",
                   "accident", "misconfiguration", "software bug", "mistakenly", "misinformation", "misleading",
                   "unintentional", "defekt", "wartung", "mirëmbajtje", "defekt teknik", "gabim teknik"],
    "deliberate": ["attack", "sabotage", "sabotim", "ransomware", "cyberattack", "hacked", "hacker", "intrusion",
                   "malicious", "state-sponsored", "state-linked", "bot network", "inauthentic", "coordinated",
                   "fabricated", "deliberately", "influence operation", "propaganda", "disinformation campaign",
                   "impersonat", "espionage", "interference", "coercion", "blackmail", "terror", "sulm",
                   "angriff", "anschlag", "dezinformat", "desinformation"],
}
CLAIM_WORDS = {
    "opinion": ["opinion", "op-ed", "commentary", "editorial", "column:", "analysis:", "we believe",
                "mendim", "koment", "meinung", "kommentar"],
    "alleged": ["allegedly", "alleged", "claims", "claimed", "reportedly", "suspected", "accused", "unconfirmed",
                "rumour", "rumor", "according to unverified", "said to", "pretendohet", "dyshohet", "akuzohet",
                "angeblich", "mutmaßlich", "soll ", "verdacht"],
    "confirmed": ["confirmed", "confirms", "officially", "official statement", "announced", "acknowledged",
                  "konfirmoi", "konfirmon", "zyrtarisht", "bestätigt", "offiziell"],
}
TARGET_WORDS = [
    "ministry", "government", "parliament", "electoral commission", "election commission", "police", "army",
    "hospital", "hospitals", "bank", "central bank", "grid operator", "power plant", "water utility",
    "airport", "port", "railway", "telecom operator", "mobile operator", "school", "schools", "municipality",
    "university", "embassy", "pipeline", "substation", "interconnector", "cable",
    "ministria", "qeveria", "kuvendi", "policia", "spitali", "spitale", "banka", "aeroporti", "komuna",
    "ministerium", "regierung", "parlament", "polizei", "krankenhaus", "flughafen", "hafen",
]
CRITICAL_SECTORS = re.compile(
    r"hospital|grid|power|water|electoral|election|government|ministr|parliament|airport|port|pipeline|"
    r"telecom|bank|spital|rrjet|qeveri|krankenhaus|regierung|wahl", re.I)
OFFICIAL_TYPES = ("official", "advisory", "research")


def _stems(terms: list[str]) -> re.Pattern:
    """One pattern for a whole word list (leading word boundary, so stems match inflections)."""
    alts = "|".join(re.escape(t) for t in sorted(set(terms), key=len, reverse=True))
    return re.compile(r"(?<![\w])(?:" + alts + ")", re.I)


def _hits(rx: re.Pattern, text: str) -> int:
    """Number of different words of the list found in the text."""
    return len({m.lower() for m in rx.findall(text)})


_SUB = {cat: [(sub, _stems(words)) for sub, words in subs.items()] for cat, subs in SUBCATEGORIES.items()}
_CAUSE = {k: _stems(v) for k, v in CAUSE_WORDS.items()}
_CLAIM = {k: _stems(v) for k, v in CLAIM_WORDS.items()}
# up to three Capitalised words before the noun ("Kosovo Electoral Commission"); the noun itself in any case
_TARGET = re.compile(
    r"(?<![\w])((?-i:(?:[A-Z][\w'’\-]+\s){0,3})(?:" + "|".join(re.escape(w) for w in sorted(TARGET_WORDS, key=len, reverse=True))
    + r"))(?![\w])", re.I)
_PEOPLE = re.compile(
    r"(\d{1,3}(?:[ ,.]\d{3})+|\d+(?:\.\d+)?)\s*(million|thousand|mln|k)?\s+"
    r"(people|residents|households|customers|users|patients|citizens|homes|banor|qytetar|familje|konsumator|"
    r"menschen|haushalte|kunden|einwohner)", re.I)
_WORD_COUNTS = [(re.compile(r"\bmillions\b|miliona|millionen", re.I), 1_000_000),
                (re.compile(r"\bthousands\b|mijëra|tausende", re.I), 1_000)]

VALID_SUBCATEGORIES = {sub for subs in SUBCATEGORIES.values() for sub in subs} | {"general"}
CAUSES = ("deliberate", "accidental", "natural", "unknown")
CLAIMS = ("confirmed", "alleged", "opinion", "reported")


def subcategory_for(category: str, text: str) -> str:
    best, best_hits = "general", 0
    for sub, rx in _SUB.get(category, []):
        hits = _hits(rx, text)
        if hits > best_hits:
            best, best_hits = sub, hits
    return best


def cause_for(category: str, text: str) -> str:
    """Only call something deliberate when the text says so; natural or accidental causes win
    when they are named and nothing points to an attack."""
    if category == "other":
        return "unknown"
    hits = {k: _hits(rx, text) for k, rx in _CAUSE.items()}
    if hits["deliberate"] and hits["deliberate"] >= max(hits["natural"], hits["accidental"]):
        return "deliberate"
    if hits["natural"] and hits["natural"] >= hits["accidental"]:
        return "natural"
    if hits["accidental"]:
        return "accidental"
    return "unknown"


@lru_cache(maxsize=8192)
def claim_for(text: str) -> str:
    for kind in ("opinion", "alleged", "confirmed"):
        if _CLAIM[kind].search(text):
            return kind
    return "reported"


def target_for(text: str) -> str | None:
    m = _TARGET.search(text or "")
    if not m:
        return None
    target = re.sub(r"^(?:The|A|An|Its|Their)\s+", "", m.group(1).strip(), flags=re.I)
    return target[:80] or None


@lru_cache(maxsize=8192)
def affected_count(text: str) -> int | None:
    best = 0
    for m in _PEOPLE.finditer(text or ""):
        raw, scale = m.group(1), (m.group(2) or "").lower()
        try:
            n = float(re.sub(r"[ ,]", "", raw)) if not re.search(r"[ ,.]\d{3}$", raw) else float(re.sub(r"[ ,.]", "", raw))
        except ValueError:
            continue
        n *= {"million": 1_000_000, "mln": 1_000_000, "thousand": 1_000, "k": 1_000}.get(scale, 1)
        best = max(best, int(n))
    if not best:
        for rx, n in _WORD_COUNTS:
            if rx.search(text or ""):
                best = max(best, n)
    return best or None


def classify_extra(category: str, title: str, text: str) -> dict:
    return dict(_classify_extra(category, title or "", text or ""))


@lru_cache(maxsize=8192)
def _classify_extra(category: str, title: str, text: str) -> tuple:
    """Cached: the same report is read again on every request until it leaves the window."""
    full = f"{title}. {text}"
    return tuple({
        "subcategory": subcategory_for(category, full) if category != "other" else None,
        "cause": cause_for(category, full),
        "claim": claim_for(full),
        "target": target_for(full),
    }.items())


# --- bands ----------------------------------------------------------------------
def severity_band(x: float) -> str:
    return "CRITICAL" if x >= 0.75 else "HIGH" if x >= 0.55 else "MEDIUM" if x >= 0.35 else "LOW"


def confidence_band(x: float) -> str:
    return "high" if x >= 0.75 else "medium" if x >= 0.5 else "low"


def _band3(x: float) -> str:
    return "high" if x >= 0.66 else "medium" if x >= 0.4 else "low"


# --- per-signal view --------------------------------------------------------------
STALE_HOURS = 168          # published more than a week ago
RESURFACED_HOURS = 72      # collected long after publication


def signal_view(s: dict, now: datetime) -> dict:
    """Fields computed when signals are read: works for rows stored before these fields existed."""
    out = dict(s)
    if out.get("category") and not out.get("subcategory") and out["category"] != "other":
        out.update({k: v for k, v in classify_extra(out["category"], out["title"], out["text"]).items()
                    if not out.get(k)})
    out["cause"] = out.get("cause") or "unknown"
    out["claim"] = out.get("claim") or claim_for(f"{out['title']}. {out['text']}")
    spec = precision_at(out.get("lat"), out.get("lon"))
    out["geo_precision"] = {2: "city", 1: "country"}.get(spec) if out.get("lat") is not None else None
    published = parse_iso(out["timestamp"])
    collected = parse_iso(out["ingested_at"]) if out.get("ingested_at") else now
    age_h = (now - published).total_seconds() / 3600
    out["stale"] = age_h > STALE_HOURS or (collected - published).total_seconds() / 3600 > RESURFACED_HOURS
    out["severity_level"] = severity_band(out["severity"])
    out["confidence_level"] = confidence_band(out["confidence"])
    out["uncertain"] = out["confidence"] < 0.5
    return out


# --- duplicates -----------------------------------------------------------------
_TOKEN = re.compile(r"[^\W\d_]{3,}", re.U)


@lru_cache(maxsize=8192)
def _tokens(title: str) -> frozenset:
    return frozenset(t.lower() for t in _TOKEN.findall(title or ""))


def mark_duplicates(signals: list[dict], window_hours: float = 72, threshold: float = 0.8) -> int:
    """Near-identical reports (syndicated or copied stories) get `duplicate_of` = the earliest copy.
    Exact repeats are already dropped when stored (same URL or same source + title)."""
    ordered = sorted(signals, key=lambda s: s["timestamp"])
    seen: list[tuple[datetime, frozenset, str]] = []
    count = 0
    for s in ordered:
        s["duplicate_of"] = None
        toks = _tokens(s["title"])
        ts = parse_iso(s["timestamp"])
        if len(toks) >= 4:
            for t0, toks0, sid in reversed(seen):
                if (ts - t0).total_seconds() / 3600 > window_hours:
                    break
                inter = len(toks & toks0)
                if inter and inter / len(toks | toks0) >= threshold:
                    s["duplicate_of"] = sid
                    count += 1
                    break
        if not s["duplicate_of"]:
            seen.append((ts, toks, s["id"]))
    return count


def independent(signals: list[dict]) -> list[dict]:
    """Signals that are not copies of another one."""
    return [s for s in signals if not s.get("duplicate_of")]


# --- automatic verification status --------------------------------------------------
# A reliable source that says the incident did not happen (only used when the alert is not itself
# about disinformation: there, a fact-checker's "false" confirms that the campaign exists).
_DENIAL = re.compile(
    r"\b(?:denied|denies|not true|untrue|false alarm|hoax|debunked|no evidence)\b|"
    r"mohon|mohoi|nuk është e vërtetë|e pavërtetë|alarm i rremë|"
    r"dementiert|bestreitet|nicht wahr|falscher alarm", re.I)
RELIABLE = 0.75


def auto_verification(sigs: list[dict]) -> dict:
    """Verification status from the evidence alone, with reasons; an analyst can still override it.

      confirmed       an official/advisory source and another reliable source, or 3+ independent reliable sources
      partial         an official source, or 2 independent reliable sources
      investigating   one reliable source
      unverified      only low-reliability sources, social media or foreign state media
      disproved       a reliable source denies it and no official source confirms it
    """
    indep = independent(sigs)
    role = lambda s: str(s.get("source_type", "")).split(" ")[0]  # noqa: E731
    trusted = [s for s in indep if s["source_reliability"] >= RELIABLE and role(s) not in ("state-media", "social")]
    reliable_sources = sorted({s["source_name"] for s in trusted})
    official = sorted({s["source_name"] for s in trusted if role(s) in ("official", "advisory") and s.get("claim") != "alleged"})
    deniers = sorted({s["source_name"] for s in trusted if _DENIAL.search(f"{s['title']}. {s['text']}")})
    about_disinfo = any(s["category"] == "disinformation" for s in sigs)
    only_state = all(role(s) in ("state-media", "state-aligned") for s in sigs)
    n = len(reliable_sources)

    reasons: list[dict] = []
    if official:
        reasons.append({"k": "official", "names": official[:3]})
    if n:
        reasons.append({"k": "indep", "n": n})
    if deniers and not about_disinfo:
        reasons.append({"k": "denial", "names": deniers[:3]})
    if only_state:
        reasons.append({"k": "state_only"})
    elif not n:
        reasons.append({"k": "low_rel"})

    if deniers and not about_disinfo and not official:
        status, conf = "disproved", 0.6 + 0.1 * min(2, len(deniers))
    elif official and n >= 2:
        status, conf = "confirmed", min(0.95, 0.85 + 0.03 * (n - 2))
    elif n >= 3:
        status, conf = "confirmed", min(0.92, 0.78 + 0.03 * (n - 3))
    elif official or n == 2:
        status, conf = "partial", 0.7
    elif n == 1:
        status, conf = "investigating", 0.55
    else:
        status, conf = "unverified", 0.6 if only_state else 0.45
    return {"status": status, "confidence": round(conf, 2), "reasons": reasons, "reliable_sources": reliable_sources[:8]}


# --- alert assessment -------------------------------------------------------------
def assess_alert(sigs: list[dict], level: str, confidence: float, severity_value: float, now: datetime) -> dict:
    full = " ".join(f"{s['title']}. {s['text']}" for s in sigs)
    targets = [s.get("target") for s in sigs if s.get("target")]
    critical_sector = bool(CRITICAL_SECTORS.search(" ".join(targets))) or any(s["category"] == "infrastructure" for s in sigs)
    affected = max((affected_count(f"{s['title']}. {s['text']}") or 0 for s in sigs), default=0) or None

    impact = max(s["severity"] for s in sigs) + (0.15 if critical_sector else 0) + (0.1 if (affected or 0) >= 10_000 else 0)
    latest_age = min((now - parse_iso(s["timestamp"])).total_seconds() / 3600 for s in sigs)
    urgency = ("high" if latest_age <= 12 and level in ("HIGH", "CRITICAL")
               else "medium" if latest_age <= 48 and level != "LOW" else "low")

    countries = {s["country"] for s in sigs if s.get("country") and s["country"] != "International waters"}
    cities = {(s.get("lat"), s.get("lon")) for s in sigs if s.get("geo_precision") == "city"}
    scope = ("unknown" if not countries else "regional" if len(countries) > 1
             else "local" if len(cities) == 1 and all(s.get("geo_precision") == "city" for s in sigs) else "national")

    indep = independent(sigs)
    sources = {s["source_name"] for s in indep}
    with_url = sum(1 for s in sigs if s.get("url")) / len(sigs)
    official = sum(1 for s in sigs if str(s.get("source_type", "")).split(" ")[0] in OFFICIAL_TYPES) / len(sigs)
    rel = sum(s["source_reliability"] for s in sigs) / len(sigs)
    evidence = 0.4 * rel + 0.3 * min(1.0, len(sources) / 3) + 0.2 * with_url + 0.1 * official
    if any(s.get("claim") == "confirmed" for s in sigs):
        evidence += 0.05
    if all(s.get("claim") in ("alleged", "opinion") for s in sigs):
        evidence -= 0.15

    causes = [s.get("cause") or "unknown" for s in sigs]
    cause = next((c for c in ("deliberate", "natural", "accidental") if c in causes), "unknown")
    return {
        "severity_level": severity_band(severity_value),
        "confidence_level": confidence_band(confidence),
        "impact": _band3(min(1.0, impact)),
        "urgency": urgency,
        "scope": scope,
        "affected": affected,
        "evidence_quality": _band3(evidence),
        "independent_sources": len(sources),
        "duplicates": len(sigs) - len(indep),
        "critical_sector": critical_sector,
        "cause": cause,
        "uncertain": confidence < 0.5,
        "targets": list(dict.fromkeys(targets))[:4],
        "subcategories": list(dict.fromkeys(s["subcategory"] for s in sigs if s.get("subcategory")))[:6],
        "auto_verification": auto_verification(sigs),
    }
