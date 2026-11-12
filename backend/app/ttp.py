"""Heuristic mapping of signals to MITRE ATT&CK (Enterprise + ICS) and DISARM techniques.

Rules are deliberately conservative: each rule only fires for signals in the domains it applies
to (e.g. DISARM only for disinformation). Mappings are analyst aids, to be validated by a human.
"""
import re

CYBER, DISINFO, INFRA = "cyber", "disinformation", "infrastructure"

# (framework, technique id, name, tactic, domains, regex)
RULES = [
    ("ATT&CK", "T1566", "Phishing", "Initial Access", {CYBER}, r"phishing|lure document|malicious attachment"),
    ("ATT&CK", "T1190", "Exploit Public-Facing Application", "Initial Access", {CYBER},
     r"actively exploited|exploitation of|authentication bypass|remote code execution|exploited (a|the) "),
    ("ATT&CK", "T1133", "External Remote Services", "Initial Access", {CYBER}, r"\bvpn\b|remote access"),
    ("ATT&CK", "T1650", "Acquire Access", "Resource Development", {CYBER},
     r"access[^.]{0,60}(for sale|offered|for \d+ ?btc)|offers? '?[^.]{0,40}access|access broker"),
    ("ATT&CK", "T1498", "Network Denial of Service", "Impact", {CYBER}, r"ddos|denial[- ]of[- ]service"),
    ("ATT&CK", "T1491.002", "External Defacement", "Impact", {CYBER}, r"defac"),
    ("ATT&CK", "T1486", "Data Encrypted for Impact", "Impact", {CYBER}, r"ransomware|encrypted systems"),
    ("ATT&CK", "T1485", "Data Destruction", "Impact", {CYBER}, r"\bwiper\b"),
    ("ATT&CK for ICS", "T0883", "Internet Accessible Device", "Initial Access", {CYBER, INFRA},
     r"(internet[- ]exposed|exposed)[\s\S]{0,120}\b(scada|hmi|plc|ics)\b|\b(scada|hmi|plc)\b[\s\S]{0,120}exposed"),
    ("ATT&CK for ICS", "T0827", "Loss of Control", "Impact", {INFRA, CYBER},
     r"manual control|control systems?[^.]{0,40}anomal|anomal[^.]{0,40}control systems?"),
    ("ATT&CK for ICS", "T0826", "Loss of Availability", "Impact", {INFRA},
     r"(outage|blackout|power cut)[^.]*?(control system|scada|interference|transmission network)|"
     r"(control system|scada|transmission network)[^.]*?(outage|blackout)"),
    ("DISARM", "T0007", "Create Inauthentic Social Media Pages and Groups", "Establish Assets", {DISINFO},
     r"newly created accounts|inauthentic accounts|fake accounts"),
    ("DISARM", "T0049", "Flood Information Space", "Maximise Exposure", {DISINFO},
     r"amplif|near-identical|bot network|cross-posted"),
    ("DISARM", "T0087", "Develop Video-Based Content (deepfakes)", "Develop Content", {DISINFO},
     r"deepfake|manipulated video|cloned voice"),
    ("DISARM", "T0013", "Create Inauthentic Websites", "Establish Assets", {DISINFO},
     r"clon(ed|ing)[^.]{0,30}(site|outlet|website)|website cloning"),
    ("DISARM", "T0099", "Prepare Assets Impersonating Legitimate Entities", "Establish Assets", {DISINFO},
     r"falsely attributed|impersonat|appears to announce"),
    ("DISARM", "T0057", "Organise Events", "Drive Offline Activity", {DISINFO},
     r"calls?( on)? (supporters|followers)?[^.]{0,30}(protest|gather)|to gather outside"),
    ("DISARM", "T0068", "Respond to Breaking News Event or Active Crisis", "Develop Narratives", {DISINFO},
     r"within hours of|outage proves|now claims"),
    ("DISARM", "T0022", "Leverage Conspiracy Theory Narratives", "Develop Narratives", {DISINFO},
     r"staged|sabotaged its own|deliberately damaged|is hiding it"),
    ("DISARM", "T0043", "Chat Apps", "Channel Selection", {DISINFO}, r"\bsms\b|telegram|whatsapp"),
]

_COMPILED = [(fw, tid, name, tactic, domains, re.compile(rx, re.I)) for fw, tid, name, tactic, domains, rx in RULES]


def techniques_for(signal: dict) -> list[tuple]:
    domains = {signal["category"], *(signal.get("tags") or [])}
    text = f"{signal['title']}. {signal['text']}"
    return [(fw, tid, name, tactic) for fw, tid, name, tactic, doms, rx in _COMPILED
            if domains & doms and rx.search(text)]


def map_ttps(signals: list[dict]) -> list[dict]:
    found: dict[str, dict] = {}
    for s in signals:
        for fw, tid, name, tactic in techniques_for(s):
            t = found.setdefault(tid, {"framework": fw, "id": tid, "name": name, "tactic": tactic, "signal_ids": []})
            t["signal_ids"].append(s["id"])
    order = {"DISARM": 0, "ATT&CK": 1, "ATT&CK for ICS": 2}
    return sorted(found.values(), key=lambda t: (order[t["framework"]], -len(t["signal_ids"]), t["id"]))
