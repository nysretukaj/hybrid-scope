"""Local, zero-cost analyzer: weighted-keyword classification + gazetteer/regex entity extraction.

It runs on every live item when no LLM is configured, and it also enriches every signal
(including LLM-analysed ones) with locations and CVEs, which deterministic extraction
handles more reliably than an LLM.
"""
import re

from ..gazetteer import find_places, primary_place

CATEGORY_LABELS = {
    "disinformation": "Disinformation",
    "cyber": "Cyber",
    "infrastructure": "Infrastructure",
    "physical": "Physical / Geopolitical",
}

KEYWORDS: dict[str, dict[str, int]] = {
    "cyber": {
        "ransomware": 3, "malware": 3, "phishing": 3, "spear-phishing": 3, "ddos": 3, "denial-of-service": 3,
        "cyberattack": 3, "cyber attack": 3, "cyber-attack": 3, "intrusion": 3, "exploit": 3, "zero-day": 3,
        "backdoor": 3, "wiper": 3, "spyware": 3, "defaced": 3, "defacement": 3, "data breach": 3, "breach": 2,
        "hacker": 2, "hacked": 2, "hacking": 2, "hacktivist": 3, "vulnerability": 2, "vulnerabilities": 2,
        "cve-": 3, "flaw": 2, "flaws": 2, "attacker": 2, "attackers": 2, "malicious": 2,
        "persistent access": 2, "compromised": 2, "botnet": 2, "credential": 2, "leak site": 3, "stolen data": 2, "threat actor": 2,
        "authentication bypass": 3, "remote code execution": 3, "infostealer": 3, "access broker": 3,
        "patch": 1, "scada": 1, "encrypted": 1,
    },
    "disinformation": {
        "disinformation": 3, "misinformation": 2, "propaganda": 3, "fake news": 3, "deepfake": 3,
        "bot network": 3, "bots": 2, "inauthentic": 3, "influence operation": 3, "information operation": 3,
        "hoax": 3, "false claim": 3, "falsely": 2, "fabricated": 3, "cloned": 2, "cloning": 2,
        "impersonat": 2, "troll": 2, "conspiracy": 2, "amplif": 2, "rumour": 2, "rumor": 2,
        "manipulated video": 3, "fact-check": 2, "debunk": 2, "smear": 2, "doppelganger": 3,
    },
    "infrastructure": {
        "power grid": 3, "grid": 2, "outage": 3, "outages": 3, "blackout": 3, "power cut": 3, "substation": 3,
        "power plant": 3, "electricity": 2, "interconnector": 3, "subsea": 3, "undersea": 3, "cable": 2,
        "pipeline": 3, "water supply": 3, "water treatment": 3, "telecom": 2, "mobile operator": 2,
        "critical infrastructure": 3, "energy infrastructure": 3, "transmission network": 3, "railway": 2,
        "airport": 1, "container terminal": 2, "gas supply": 2, "supply disruption": 2,
    },
    "physical": {
        "drone": 3, "drones": 3, "explosion": 3, "sabotage": 3, "protest": 2, "riot": 3, "clashes": 3,
        "military": 2, "troops": 2, "missile": 3, "airstrike": 3, "strikes": 1, "vessel": 2, "warship": 3,
        "navy": 2, "coast guard": 2, "jamming": 3, "gps interference": 3, "incursion": 3, "airspace": 2,
        "armed": 2, "border": 1, "mobilisation": 2, "mobilization": 2, "evacuation": 2, "anchor": 2,
        "assassination": 3, "shooting": 3, "bomb": 3,
    },
}

# Albanian (sq) and German (de) indicators. Leading-boundary prefix match, so stems cover inflections
# (e.g. "dezinformat" -> dezinformata, dezinformatave; "drohne" -> Drohnen).
KEYWORDS_I18N: dict[str, dict[str, int]] = {
    "cyber": {
        # sq
        "sulm kibernetik": 3, "sulmi kibernetik": 3, "sulme kibernetike": 3, "kibernetik": 2, "haker": 2,
        "hakuar": 2, "rrjedhje të dhënash": 3, "cenueshmëri": 2, "softuer keqdashës": 3,
        # de
        "cyberangriff": 3, "cyberattacke": 3, "hackerangriff": 3, "schadsoftware": 3, "sicherheitslücke": 3,
        "datenleck": 3, "erpressungssoftware": 3, "angreifer": 2, "ddos-angriff": 3, "gehackt": 2,
        "schwachstelle": 2, "lösegeld": 2,
    },
    "disinformation": {
        # sq
        "dezinformat": 3, "dezinformim": 3, "lajm i rremë": 3, "lajme të rreme": 3, "lajme false": 3,
        "propagand": 3, "llogari të rreme": 3, "pretendim i rremë": 3, "pretendime të rreme": 3, "manipulim": 2,
        "narrativ": 2,
        # de
        "desinformation": 3, "falschnachricht": 3, "falschmeldung": 3, "gefälscht": 2, "manipuliert": 2,
        "bot-netzwerk": 3, "einflussoperation": 3, "verschwörung": 2,
    },
    "infrastructure": {
        # sq
        "ndërprerje": 2, "ndërprerja e rrymës": 3, "pa rrymë": 3, "rrjeti elektrik": 3, "energji elektrike": 2,
        "energjisë elektrike": 2, "nënstacion": 3, "termocentral": 3, "infrastrukturë kritike": 3,
        "infrastruktura kritike": 3, "furnizim me ujë": 3, "furnizimi me ujë": 3, "gazsjellës": 3,
        # de
        "stromausfall": 3, "kritische infrastruktur": 3, "stromnetz": 3, "umspannwerk": 3, "kraftwerk": 3,
        "unterseekabel": 3, "wasserversorgung": 3, "netzbetreiber": 2,
    },
    "physical": {
        # sq
        "dron": 3, "sabotim": 3, "trazira": 3, "shpërthim": 3, "ushtri": 2, "ushtarak": 2, "raket": 3,
        "evakuim": 2, "përleshje": 3, "sulm i armatosur": 3,
        # de
        "drohne": 3, "anschlag": 3, "militär": 2, "rakete": 3, "bundeswehr": 2, "spionage": 2,
        "evakuierung": 2, "störsender": 3, "gps-störung": 3, "demonstration": 1,
    },
}
for _cat, _kws in KEYWORDS_I18N.items():
    KEYWORDS[_cat].update(_kws)

SEVERITY_BOOSTERS = {
    "actively exploited": 0.2, "zero-day": 0.15, "killed": 0.25, "casualties": 0.2, "injured": 0.12,
    "nationwide": 0.1, "widespread": 0.08, "millions": 0.1, "state-sponsored": 0.12, "state-linked": 0.12,
    "critical": 0.08, "emergency": 0.08, "ransomware": 0.08, "wiper": 0.15, "sabotage": 0.12,
    "hospital": 0.1, "election": 0.08, "confirmed": 0.05,
    # sq
    "të vdekur": 0.25, "vrarë": 0.25, "të plagosur": 0.12, "spital": 0.1, "zgjedhje": 0.08, "kritike": 0.08,
    # de
    "getötet": 0.25, "tote": 0.2, "verletzt": 0.12, "krankenhaus": 0.1, "wahl": 0.08, "kritisch": 0.08,
    "aktiv ausgenutzt": 0.2,
}
SEVERITY_DAMPENERS = {
    "storm": -0.2, "weather": -0.2, "earthquake": -0.15, "planned maintenance": -0.2, "drill": -0.15,
    "exercise": -0.1, "no data was compromised": -0.05,
    "stuhi": -0.2, "mirëmbajtje": -0.2, "tërmet": -0.15,
    "sturm": -0.2, "unwetter": -0.2, "wartung": -0.2, "erdbeben": -0.15, "übung": -0.1,
}

KNOWN_ACTORS = [
    "APT28", "APT29", "Fancy Bear", "Cozy Bear", "Sandworm", "Lazarus", "Kimsuky", "Volt Typhoon",
    "Salt Typhoon", "Killnet", "NoName057(16)", "Anonymous Sudan", "Scattered Spider", "LockBit",
    "BlackCat", "ALPHV", "Cl0p", "Akira", "Black Basta", "Ghostwriter", "Storm-1516", "Cyber Army of Russia",
    # fictional actors used in the synthetic exercise scenario
    "GreyMist", "Northern Hydra", "Voice of the Valley", "Pravda-MD",
]
KNOWN_ORGS = [
    "NATO", "European Union", "EU", "KFOR", "OSCE", "United Nations", "CISA", "ENISA", "Europol", "Interpol",
    "FBI", "NSA", "GCHQ", "CERT", "Microsoft", "Google", "Meta", "Apple", "Amazon", "Cloudflare",
    "Central Electoral Commission",
]
TECHNOLOGIES = [
    "SCADA", "ICS", "HMI", "PLC", "VPN", "Fortinet", "FortiGate", "FortiOS", "Ivanti", "Citrix", "NetScaler",
    "Exchange", "SharePoint", "Windows", "Linux", "Android", "iOS", "Chrome", "Starlink", "GPS", "GNSS",
    "AIS", "Cobalt Strike", "Mimikatz", "Modbus", "DNS", "BGP", "MOVEit", "Confluence", "PAN-OS", "Cisco",
    "VMware", "ESXi", "Kubernetes", "WordPress",
    # platforms abused for influence operations
    "Telegram", "TikTok", "Facebook", "YouTube", "WhatsApp", "VKontakte",
]


def _boundary(term: str, flags=0) -> re.Pattern:
    return re.compile(r"(?<![\w])" + re.escape(term) + r"(?![\w])", flags)


_KW = {
    cat: [(kw, w, re.compile(r"(?<![\w])" + re.escape(kw), re.I)) for kw, w in kws.items()]
    for cat, kws in KEYWORDS.items()
}
_BOOST = [(k, v, re.compile(r"(?<![\w])" + re.escape(k), re.I)) for k, v in {**SEVERITY_BOOSTERS, **SEVERITY_DAMPENERS}.items()]
_ACTORS = [(n, _boundary(n)) for n in KNOWN_ACTORS]
_ORGS = [(n, _boundary(n)) for n in KNOWN_ORGS]
_TECH = [(n, _boundary(n)) for n in TECHNOLOGIES]
_CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)
_HASHTAG = re.compile(r"(?<![\w#])#[A-Za-z][\w]{2,40}")
_ORG_PHRASE = re.compile(
    r"\b((?:[A-Z][\w'’\-]+\s){1,3}(?:Ministry|Agency|Authority|Commission|Police|Council|Operator|"
    r"Directorate|Service|Coast Guard|Navy|Army|Bank|Parliament))\b"
)
_STOP_PREFIX = re.compile(r"^(?:The|A|An|This|That|Its|Their)\s+")


def _dedupe(items) -> list[str]:
    seen, out = set(), []
    for it in items:
        key = it.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(it.strip())
    return out


def merge_entities(a: dict, b: dict) -> dict:
    keys = list(dict.fromkeys([*a.keys(), *b.keys()]))
    return {k: _dedupe([*(a.get(k) or []), *(b.get(k) or [])]) for k in keys}


def extract_entities(text: str) -> dict:
    places = find_places(text)
    orgs = [n for n, rx in _ORGS if rx.search(text)]
    orgs += [_STOP_PREFIX.sub("", m.group(1)) for m in _ORG_PHRASE.finditer(text)]
    return {
        "actors": _dedupe(n for n, rx in _ACTORS if rx.search(text)),
        "orgs": _dedupe(orgs),
        "technologies": _dedupe(n for n, rx in _TECH if rx.search(text)),
        "cves": _dedupe(m.group(0).upper() for m in _CVE.finditer(text)),
        "narratives": _dedupe(m.group(0) for m in _HASHTAG.finditer(text)),
        "locations": [p["name"] for p in places],
    }, places


def analyze_local(title: str, text: str) -> dict:
    full = f"{title or ''}. {text or ''}".strip(". ")
    scores: dict[str, int] = {}
    hits: dict[str, list[str]] = {}
    for cat, patterns in _KW.items():
        matched = [(kw, w) for kw, w, rx in patterns if rx.search(full)]
        scores[cat] = sum(w for _, w in matched)
        hits[cat] = [kw for kw, _ in matched]

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_cat, top_score = ranked[0]
    # Require at least one strong indicator (weight 3) or several weaker ones.
    category = top_cat if top_score >= 3 else "other"
    tags = [c for c, s in ranked[1:] if s >= max(3, 0.5 * top_score)] if category != "other" else []

    adjustments = [(k, v) for k, v, rx in _BOOST if rx.search(full)]
    boost = min(0.3, sum(v for _, v in adjustments if v > 0))
    damp = sum(v for _, v in adjustments if v < 0)
    severity = 0.25 + min(0.35, 0.04 * top_score) + boost + damp
    if category == "other":
        severity = min(severity, 0.25)
    severity = max(0.05, min(0.97, severity))

    entities, places = extract_entities(full)
    location = primary_place(places)

    n_hits = len(hits.get(top_cat, []))
    confidence = 0.35 + 0.07 * min(6, n_hits)
    if len(ranked) > 1 and top_score and ranked[1][1] / top_score > 0.75:
        confidence -= 0.1  # ambiguous between two domains
    if location:
        confidence += 0.05
    confidence = max(0.3, min(0.85, confidence))

    if category == "other":
        rationale = "Local NLP: no threat-domain indicators found; kept in the stream but excluded from alerts."
    else:
        rationale = f"Local NLP: classified as {CATEGORY_LABELS[category]} (matched: {', '.join(hits[category][:5])})."
        if tags:
            rationale += " Secondary: " + ", ".join(CATEGORY_LABELS[t] for t in tags) + "."
        ups = [k for k, v in adjustments if v > 0]
        downs = [k for k, v in adjustments if v < 0]
        if ups:
            rationale += f" Severity raised by: {', '.join(ups[:4])}."
        if downs:
            rationale += f" Severity lowered by: {', '.join(downs[:3])} (likely non-hostile)."
        if not location:
            rationale += " No known location resolved."

    return {
        "category": category,
        "tags": tags,
        "severity": round(severity, 2),
        "confidence": round(confidence, 2),
        "entities": entities,
        "location": location,
        "rationale": rationale,
        "analyzer": "local-nlp",
        "keyword_scores": scores,
    }
