import { createContext, useCallback, useContext, useEffect, useState } from 'react'

export const LANGS = [
  ['en', 'EN'],
  ['sq', 'SQ'],
  ['de', 'DE'],
]

const D = {
  en: {
    'app.subtitle': 'OSINT · Hybrid threat intelligence',
    'tab.board': 'Threat Board', 'tab.network': 'Network', 'tab.signals': 'Signal Stream', 'tab.analyze': 'Analyze Text',
    'hdr.analyzer': 'Analyzer', 'hdr.liveIngest': 'Live ingest', 'hdr.notRun': 'not run yet', 'hdr.items': 'items',
    'hdr.ingest': 'Ingest live sources', 'hdr.ingesting': 'Ingesting…', 'hdr.reset': 'Reset scenario', 'hdr.resetting': 'Resetting…',
    'hdr.resetTitle': 'Re-anchor the synthetic exercise scenario to the current time and clear analyst feedback',
    'kpi.critical': 'Critical alerts', 'kpi.criticalSub': 'score ≥ 75', 'kpi.hybrid': 'Hybrid patterns', 'kpi.hybridSub': 'cross-domain clusters',
    'kpi.active': 'Active alerts', 'kpi.lessNoise': '{n}% less noise than raw feed', 'kpi.signals24': 'Signals (24h)',
    'kpi.inWindow': '{n} in window', 'kpi.relevant': 'Threat-relevant', 'kpi.relevantSub': 'classified by AI layer',
    'kpi.sources': 'Sources', 'kpi.sourcesSub': '{live} live · {scenario} scenario',
    'f.search': 'Search actors, places, narratives, TTPs…', 'f.allDomains': 'All domains', 'f.allRegions': 'All regions',
    'f.all': 'All', 'f.scenario': 'Scenario', 'f.live': 'Live', 'f.minConf': 'Min confidence', 'f.hybridOnly': 'Hybrid only',
    'f.hideDismissed': 'Hide false positives',
    'list.title': 'Prioritized alerts', 'list.none': 'No alerts match the filters.', 'list.sig': 'sig', 'list.src': 'src', 'list.conf': 'conf',
    'd.select': 'Select an alert to see its evidence.', 'd.loading': 'Loading alert…', 'd.hybrid': 'HYBRID PATTERN',
    'd.exercise': 'EXERCISE SCENARIO', 'd.confidence': 'confidence', 'd.timeline': 'Correlation timeline', 'd.links': '{n} correlation links',
    'd.why': 'Why this score?', 'd.linking': 'Linking entities', 'd.evidence': 'Source evidence',
    'd.sigSrc': '{s} signals · {src} sources', 'd.ttps': 'Mapped techniques (MITRE ATT&CK · DISARM)', 'd.ttpHint': 'heuristic mapping - click to jump to evidence',
    'd.replay': 'Replay', 'd.brief': 'Intel brief', 'd.confirm': 'Confirm', 'd.fp': 'False positive',
    'd.confirmed': 'CONFIRMED BY ANALYST', 'd.dismissed': 'FALSE POSITIVE', 'd.undo': 'Undo', 'd.note': 'Optional analyst note…',
    'd.send': 'Send alert', 'd.sent': 'Sent', 'd.ai': 'AI analysis & links', 'd.open': 'Open source ↗', 'd.synthetic': 'synthetic exercise source',
    'd.relAdjusted': 'reliability adjusted by analyst feedback: {a} → {b}', 'd.feedbackHint': 'Your verdict updates the reliability of every source in this alert.',
    'rp.title': 'Replay: how the alert would have evolved live', 'rp.play': 'Play', 'rp.pause': 'Pause', 'rp.restart': 'Restart',
    'rp.close': 'Close replay', 'rp.signal': 'Signal {i} of {n}', 'rp.lead': 'Hybrid pattern flagged {h}h before the first infrastructure impact',
    'rp.leadHigh': 'HIGH risk reached {h}h before impact', 'rp.impact': 'First impact', 'rp.hybridAt': 'hybrid flagged',
    'rp.noLead': 'Impact and hybrid flag arrived together - the platform escalated at the moment of impact.',
    'b.title': 'Intelligence brief', 'b.export': 'Export PDF', 'b.close': 'Close', 'b.bluf': 'Bottom line up front',
    'b.judgments': 'Key judgments', 'b.ttps': 'Techniques observed', 'b.indicators': 'Indicators to watch',
    'b.actions': 'Recommended actions', 'b.sources': 'Sources', 'b.method': 'Method', 'b.period': 'Period', 'b.risk': 'Risk',
    's.raw': 'Raw signal stream:', 's.items': 'normalized items', 's.firehose': 'This is the firehose an analyst would otherwise read by hand. HybridScope condenses it into',
    's.alerts': 'prioritized alerts.', 's.search': 'Search…', 's.allCats': 'All categories', 's.unresolved': 'unresolved',
    'th.time': 'Time', 'th.category': 'Category', 'th.signal': 'Signal', 'th.region': 'Region', 'th.source': 'Source', 'th.severity': 'Severity', 'th.analyzer': 'Analyzer',
    'a.paste': 'Paste any open-source text (English, Albanian or German)', 'a.titlePh': 'Title (optional)', 'a.run': 'Extract & classify',
    'a.running': 'Analyzing…', 'a.output': 'AI analysis output', 'a.empty': 'Run the analyzer to see entities, classification and severity.',
    'a.severity': 'Severity', 'a.confidence': 'Confidence', 'a.region': 'Region',
    'a.baseline': 'Baseline: offline keyword NLP', 'a.agree': 'same domain as the LLM', 'a.disagree': 'the LLM chose a different domain',
    'hdr.aiUpgrading': 'AI upgrading signals {done}/{n}',
    'hdr.offline': 'OFFLINE DEMO', 'm.offlineMap': 'offline map',
    'a.cached': 'cached AI result', 'a.offlineLocal': 'offline: local NLP only', 'a.cachedSample': 'AI answer cached for the offline demo',
    'n.title': 'Entity network', 'n.sub': 'Alerts (large) connected through the actors, organisations, technologies, CVEs and narratives they share. Drag nodes; click an alert to open it.',
    'n.legend': 'Legend', 'n.alertNode': 'alert (number = risk score, solid ring = hybrid)',
    'n.bridges': 'Entities bridging several alerts', 'n.none': 'No shared entities yet.', 'n.alerts': '{n} alerts', 'n.mentions': '{n} mentions',
    'm.hybrid': '● solid = hybrid', 'm.single': '◌ dashed = single-domain', 'm.size': 'size = risk score',
    'tl.cross': 'shared entity across domains', 'tl.same': 'shared entity, same domain', 'tl.temporal': 'cross-domain within 24h',
    'tl.hint': 'node size = severity · hover a node to trace its links',
    'sc.severity': 'Severity', 'sc.hybrid': 'Hybrid (cross-domain)', 'sc.corroboration': 'Corroboration', 'sc.recency': 'Recency', 'sc.reliability': 'Source reliability',
    'cat.disinformation': 'Disinformation', 'cat.cyber': 'Cyber', 'cat.infrastructure': 'Infrastructure', 'cat.physical': 'Physical / Geopolitical', 'cat.other': 'Not threat-relevant',
    'et.actor': 'Actor', 'et.organisation': 'Organisation', 'et.technology': 'Technology', 'et.CVE': 'CVE', 'et.narrative': 'Narrative',
    't.ingest': 'Live ingest: {f} items fetched, {i} new, {r} threat-relevant', 't.failed': 'failed', 't.reset': 'Scenario re-anchored to now ({n} signals)',
    't.feedback': 'Verdict saved - reliability updated for {n} sources', 't.backend': 'Backend unreachable ({e}). Is the API running on :8000?',
  },
  sq: {
    'app.subtitle': 'OSINT · Inteligjencë për kërcënime hibride',
    'tab.board': 'Paneli i kërcënimeve', 'tab.network': 'Rrjeti', 'tab.signals': 'Rrjedha e sinjaleve', 'tab.analyze': 'Analizo tekst',
    'hdr.analyzer': 'Analizuesi', 'hdr.liveIngest': 'Mbledhja live', 'hdr.notRun': 'ende pa u ekzekutuar', 'hdr.items': 'artikuj',
    'hdr.ingest': 'Mblidh burimet live', 'hdr.ingesting': 'Duke mbledhur…', 'hdr.reset': 'Rinis skenarin', 'hdr.resetting': 'Duke rinisur…',
    'hdr.resetTitle': 'Rivendos skenarin sintetik në kohën aktuale dhe fshi vlerësimet e analistit',
    'kpi.critical': 'Alarme kritike', 'kpi.criticalSub': 'pikë ≥ 75', 'kpi.hybrid': 'Modele hibride', 'kpi.hybridSub': 'grupe ndër-domenesh',
    'kpi.active': 'Alarme aktive', 'kpi.lessNoise': '{n}% më pak zhurmë se rrjedha e papërpunuar', 'kpi.signals24': 'Sinjale (24h)',
    'kpi.inWindow': '{n} në dritare', 'kpi.relevant': 'Relevante', 'kpi.relevantSub': 'të klasifikuara nga AI',
    'kpi.sources': 'Burime', 'kpi.sourcesSub': '{live} live · {scenario} skenar',
    'f.search': 'Kërko aktorë, vende, narrativa, TTP…', 'f.allDomains': 'Të gjitha domenet', 'f.allRegions': 'Të gjitha rajonet',
    'f.all': 'Të gjitha', 'f.scenario': 'Skenari', 'f.live': 'Live', 'f.minConf': 'Besueshmëria min.', 'f.hybridOnly': 'Vetëm hibride',
    'f.hideDismissed': 'Fshih alarmet e rreme',
    'list.title': 'Alarmet sipas prioritetit', 'list.none': 'Asnjë alarm nuk përputhet me filtrat.', 'list.sig': 'sinj.', 'list.src': 'burime', 'list.conf': 'bes.',
    'd.select': 'Zgjidh një alarm për të parë evidencën.', 'd.loading': 'Duke ngarkuar alarmin…', 'd.hybrid': 'MODEL HIBRID',
    'd.exercise': 'SKENAR STËRVITJEJE', 'd.confidence': 'besueshmëria', 'd.timeline': 'Vija kohore e korrelimit', 'd.links': '{n} lidhje korrelimi',
    'd.why': 'Pse ky rezultat?', 'd.linking': 'Entitetet lidhëse', 'd.evidence': 'Evidenca nga burimet',
    'd.sigSrc': '{s} sinjale · {src} burime', 'd.ttps': 'Teknikat e identifikuara (MITRE ATT&CK · DISARM)', 'd.ttpHint': 'përputhje heuristike - kliko për evidencën',
    'd.replay': 'Riluaj', 'd.brief': 'Raport inteligjence', 'd.confirm': 'Konfirmo', 'd.fp': 'Alarm i rremë',
    'd.confirmed': 'KONFIRMUAR NGA ANALISTI', 'd.dismissed': 'ALARM I RREMË', 'd.undo': 'Anulo', 'd.note': 'Shënim opsional i analistit…',
    'd.send': 'Dërgo alarmin', 'd.sent': 'U dërgua', 'd.ai': 'Analiza AI dhe lidhjet', 'd.open': 'Hap burimin ↗', 'd.synthetic': 'burim sintetik stërvitjeje',
    'd.relAdjusted': 'besueshmëria e përshtatur nga analisti: {a} → {b}', 'd.feedbackHint': 'Vlerësimi yt përditëson besueshmërinë e çdo burimi në këtë alarm.',
    'rp.title': 'Riluajtja: si do të ishte zhvilluar alarmi live', 'rp.play': 'Luaj', 'rp.pause': 'Pauzë', 'rp.restart': 'Rifillo',
    'rp.close': 'Mbyll riluajtjen', 'rp.signal': 'Sinjali {i} nga {n}', 'rp.lead': 'Modeli hibrid u identifikua {h} orë para ndikimit të parë në infrastrukturë',
    'rp.leadHigh': 'Rreziku HIGH u arrit {h} orë para ndikimit', 'rp.impact': 'Ndikimi i parë', 'rp.hybridAt': 'u shënua hibrid',
    'rp.noLead': 'Ndikimi dhe shenja hibride erdhën njëkohësisht - platforma e ngriti nivelin në momentin e ndikimit.',
    'b.title': 'Raport inteligjence', 'b.export': 'Eksporto PDF', 'b.close': 'Mbyll', 'b.bluf': 'Përfundimi kryesor (BLUF)',
    'b.judgments': 'Gjykimet kryesore', 'b.ttps': 'Teknikat e vëzhguara', 'b.indicators': 'Indikatorët për t’u ndjekur',
    'b.actions': 'Veprimet e rekomanduara', 'b.sources': 'Burimet', 'b.method': 'Metoda', 'b.period': 'Periudha', 'b.risk': 'Rreziku',
    's.raw': 'Rrjedha e papërpunuar:', 's.items': 'artikuj të normalizuar', 's.firehose': 'Kjo është rrjedha që analisti do ta lexonte me dorë. HybridScope e kondenson në',
    's.alerts': 'alarme me prioritet.', 's.search': 'Kërko…', 's.allCats': 'Të gjitha kategoritë', 's.unresolved': 'e pazgjidhur',
    'th.time': 'Koha', 'th.category': 'Kategoria', 'th.signal': 'Sinjali', 'th.region': 'Rajoni', 'th.source': 'Burimi', 'th.severity': 'Rëndësia', 'th.analyzer': 'Analizuesi',
    'a.paste': 'Ngjit çfarëdo teksti publik (anglisht, shqip ose gjermanisht)', 'a.titlePh': 'Titulli (opsional)', 'a.run': 'Nxirr dhe klasifiko',
    'a.running': 'Duke analizuar…', 'a.output': 'Rezultati i analizës AI', 'a.empty': 'Ekzekuto analizuesin për të parë entitetet, klasifikimin dhe rëndësinë.',
    'a.severity': 'Rëndësia', 'a.confidence': 'Besueshmëria', 'a.region': 'Rajoni',
    'a.baseline': 'Krahasimi: NLP lokal me fjalë kyçe', 'a.agree': 'i njëjti domen si LLM', 'a.disagree': 'LLM zgjodhi domen tjetër',
    'hdr.aiUpgrading': 'AI po përmirëson sinjalet {done}/{n}',
    'hdr.offline': 'DEMO OFFLINE', 'm.offlineMap': 'hartë offline',
    'a.cached': 'rezultat AI i ruajtur', 'a.offlineLocal': 'offline: vetëm NLP lokal', 'a.cachedSample': 'përgjigjja e AI-së është ruajtur për demon offline',
    'n.title': 'Rrjeti i entiteteve', 'n.sub': 'Alarmet (të mëdha) të lidhura përmes aktorëve, organizatave, teknologjive, CVE-ve dhe narrativave të përbashkëta. Tërhiq nyjet; kliko një alarm për ta hapur.',
    'n.legend': 'Legjenda', 'n.alertNode': 'alarm (numri = rreziku, unazë e plotë = hibrid)',
    'n.bridges': 'Entitete që lidhin disa alarme', 'n.none': 'Ende pa entitete të përbashkëta.', 'n.alerts': '{n} alarme', 'n.mentions': '{n} përmendje',
    'm.hybrid': '● i plotë = hibrid', 'm.single': '◌ me vija = një domen', 'm.size': 'madhësia = rreziku',
    'tl.cross': 'entitet i përbashkët mes domeneve', 'tl.same': 'entitet i përbashkët, i njëjti domen', 'tl.temporal': 'domene të ndryshme brenda 24h',
    'tl.hint': 'madhësia e nyjes = rëndësia · kalo mbi nyje për të parë lidhjet',
    'sc.severity': 'Rëndësia', 'sc.hybrid': 'Hibrid (ndër-domene)', 'sc.corroboration': 'Konfirmimi nga burime', 'sc.recency': 'Aktualiteti', 'sc.reliability': 'Besueshmëria e burimeve',
    'cat.disinformation': 'Dezinformim', 'cat.cyber': 'Kibernetik', 'cat.infrastructure': 'Infrastrukturë', 'cat.physical': 'Fizik / Gjeopolitik', 'cat.other': 'Jo relevant',
    'et.actor': 'Aktor', 'et.organisation': 'Organizatë', 'et.technology': 'Teknologji', 'et.CVE': 'CVE', 'et.narrative': 'Narrativë',
    't.ingest': 'Mbledhja live: {f} artikuj, {i} të rinj, {r} relevantë', 't.failed': 'dështuan', 't.reset': 'Skenari u rivendos në kohën aktuale ({n} sinjale)',
    't.feedback': 'Vlerësimi u ruajt - besueshmëria u përditësua për {n} burime', 't.backend': 'Backend-i nuk përgjigjet ({e}). A po punon API në :8000?',
  },
  de: {
    'app.subtitle': 'OSINT · Lagebild hybride Bedrohungen',
    'tab.board': 'Lagezentrum', 'tab.network': 'Netzwerk', 'tab.signals': 'Signalstrom', 'tab.analyze': 'Text analysieren',
    'hdr.analyzer': 'Analysator', 'hdr.liveIngest': 'Live-Erfassung', 'hdr.notRun': 'noch nicht ausgeführt', 'hdr.items': 'Einträge',
    'hdr.ingest': 'Live-Quellen erfassen', 'hdr.ingesting': 'Erfasse…', 'hdr.reset': 'Szenario zurücksetzen', 'hdr.resetting': 'Setze zurück…',
    'hdr.resetTitle': 'Synthetisches Übungsszenario auf die aktuelle Zeit setzen und Analysten-Feedback löschen',
    'kpi.critical': 'Kritische Warnungen', 'kpi.criticalSub': 'Score ≥ 75', 'kpi.hybrid': 'Hybride Muster', 'kpi.hybridSub': 'domänenübergreifende Cluster',
    'kpi.active': 'Aktive Warnungen', 'kpi.lessNoise': '{n}% weniger Rauschen als der Rohdatenstrom', 'kpi.signals24': 'Signale (24h)',
    'kpi.inWindow': '{n} im Zeitfenster', 'kpi.relevant': 'Bedrohungsrelevant', 'kpi.relevantSub': 'von der KI klassifiziert',
    'kpi.sources': 'Quellen', 'kpi.sourcesSub': '{live} live · {scenario} Szenario',
    'f.search': 'Akteure, Orte, Narrative, TTPs suchen…', 'f.allDomains': 'Alle Domänen', 'f.allRegions': 'Alle Regionen',
    'f.all': 'Alle', 'f.scenario': 'Szenario', 'f.live': 'Live', 'f.minConf': 'Min. Konfidenz', 'f.hybridOnly': 'Nur hybride',
    'f.hideDismissed': 'Fehlalarme ausblenden',
    'list.title': 'Priorisierte Warnungen', 'list.none': 'Keine Warnungen für diese Filter.', 'list.sig': 'Sig.', 'list.src': 'Qu.', 'list.conf': 'Konf.',
    'd.select': 'Warnung auswählen, um die Belege zu sehen.', 'd.loading': 'Lade Warnung…', 'd.hybrid': 'HYBRIDES MUSTER',
    'd.exercise': 'ÜBUNGSSZENARIO', 'd.confidence': 'Konfidenz', 'd.timeline': 'Korrelations-Zeitleiste', 'd.links': '{n} Korrelationen',
    'd.why': 'Warum dieser Score?', 'd.linking': 'Verbindende Entitäten', 'd.evidence': 'Quellenbelege',
    'd.sigSrc': '{s} Signale · {src} Quellen', 'd.ttps': 'Zugeordnete Techniken (MITRE ATT&CK · DISARM)', 'd.ttpHint': 'heuristische Zuordnung - Klick springt zum Beleg',
    'd.replay': 'Wiedergabe', 'd.brief': 'Lagebericht', 'd.confirm': 'Bestätigen', 'd.fp': 'Fehlalarm',
    'd.confirmed': 'VOM ANALYSTEN BESTÄTIGT', 'd.dismissed': 'FEHLALARM', 'd.undo': 'Rückgängig', 'd.note': 'Optionale Analystennotiz…',
    'd.send': 'Warnung senden', 'd.sent': 'Gesendet', 'd.ai': 'KI-Analyse & Verknüpfungen', 'd.open': 'Quelle öffnen ↗', 'd.synthetic': 'synthetische Übungsquelle',
    'd.relAdjusted': 'Zuverlässigkeit durch Analysten-Feedback angepasst: {a} → {b}', 'd.feedbackHint': 'Ihre Bewertung aktualisiert die Zuverlässigkeit jeder Quelle dieser Warnung.',
    'rp.title': 'Wiedergabe: so hätte sich die Warnung live entwickelt', 'rp.play': 'Abspielen', 'rp.pause': 'Pause', 'rp.restart': 'Neu starten',
    'rp.close': 'Wiedergabe schließen', 'rp.signal': 'Signal {i} von {n}', 'rp.lead': 'Hybrides Muster {h} Std. vor der ersten Infrastruktur-Auswirkung erkannt',
    'rp.leadHigh': 'Risiko HIGH {h} Std. vor der Auswirkung erreicht', 'rp.impact': 'Erste Auswirkung', 'rp.hybridAt': 'als hybrid erkannt',
    'rp.noLead': 'Auswirkung und Hybrid-Erkennung kamen gleichzeitig - die Plattform eskalierte im Moment der Auswirkung.',
    'b.title': 'Lagebericht', 'b.export': 'Als PDF exportieren', 'b.close': 'Schließen', 'b.bluf': 'Kernaussage (BLUF)',
    'b.judgments': 'Zentrale Bewertungen', 'b.ttps': 'Beobachtete Techniken', 'b.indicators': 'Zu beobachtende Indikatoren',
    'b.actions': 'Empfohlene Maßnahmen', 'b.sources': 'Quellen', 'b.method': 'Methode', 'b.period': 'Zeitraum', 'b.risk': 'Risiko',
    's.raw': 'Rohdatenstrom:', 's.items': 'normalisierte Einträge', 's.firehose': 'Diese Datenflut müsste ein Analyst sonst manuell lesen. HybridScope verdichtet sie auf',
    's.alerts': 'priorisierte Warnungen.', 's.search': 'Suchen…', 's.allCats': 'Alle Kategorien', 's.unresolved': 'nicht zugeordnet',
    'th.time': 'Zeit', 'th.category': 'Kategorie', 'th.signal': 'Signal', 'th.region': 'Region', 'th.source': 'Quelle', 'th.severity': 'Schwere', 'th.analyzer': 'Analysator',
    'a.paste': 'Beliebigen offenen Text einfügen (Englisch, Albanisch oder Deutsch)', 'a.titlePh': 'Titel (optional)', 'a.run': 'Extrahieren & klassifizieren',
    'a.running': 'Analysiere…', 'a.output': 'KI-Analyseergebnis', 'a.empty': 'Analysator ausführen, um Entitäten, Klassifizierung und Schwere zu sehen.',
    'a.severity': 'Schwere', 'a.confidence': 'Konfidenz', 'a.region': 'Region',
    'a.baseline': 'Vergleich: Offline-Schlüsselwort-NLP', 'a.agree': 'gleiche Domäne wie das LLM', 'a.disagree': 'das LLM wählte eine andere Domäne',
    'hdr.aiUpgrading': 'KI wertet Signale auf {done}/{n}',
    'hdr.offline': 'OFFLINE-DEMO', 'm.offlineMap': 'Offline-Karte',
    'a.cached': 'gespeichertes KI-Ergebnis', 'a.offlineLocal': 'offline: nur lokales NLP', 'a.cachedSample': 'KI-Antwort für die Offline-Demo gespeichert',
    'n.title': 'Entitäten-Netzwerk', 'n.sub': 'Warnungen (groß), verbunden über gemeinsame Akteure, Organisationen, Technologien, CVEs und Narrative. Knoten ziehen; Warnung anklicken zum Öffnen.',
    'n.legend': 'Legende', 'n.alertNode': 'Warnung (Zahl = Risiko, durchgezogener Ring = hybrid)',
    'n.bridges': 'Entitäten, die mehrere Warnungen verbinden', 'n.none': 'Noch keine gemeinsamen Entitäten.', 'n.alerts': '{n} Warnungen', 'n.mentions': '{n} Erwähnungen',
    'm.hybrid': '● durchgezogen = hybrid', 'm.single': '◌ gestrichelt = eine Domäne', 'm.size': 'Größe = Risiko',
    'tl.cross': 'gemeinsame Entität über Domänen', 'tl.same': 'gemeinsame Entität, gleiche Domäne', 'tl.temporal': 'domänenübergreifend binnen 24h',
    'tl.hint': 'Knotengröße = Schwere · Knoten überfahren, um Verknüpfungen zu sehen',
    'sc.severity': 'Schwere', 'sc.hybrid': 'Hybrid (domänenübergreifend)', 'sc.corroboration': 'Bestätigung', 'sc.recency': 'Aktualität', 'sc.reliability': 'Quellenzuverlässigkeit',
    'cat.disinformation': 'Desinformation', 'cat.cyber': 'Cyber', 'cat.infrastructure': 'Infrastruktur', 'cat.physical': 'Physisch / Geopolitisch', 'cat.other': 'Nicht relevant',
    'et.actor': 'Akteur', 'et.organisation': 'Organisation', 'et.technology': 'Technologie', 'et.CVE': 'CVE', 'et.narrative': 'Narrativ',
    't.ingest': 'Live-Erfassung: {f} Einträge, {i} neu, {r} bedrohungsrelevant', 't.failed': 'fehlgeschlagen', 't.reset': 'Szenario auf jetzt gesetzt ({n} Signale)',
    't.feedback': 'Bewertung gespeichert - Zuverlässigkeit für {n} Quellen aktualisiert', 't.backend': 'Backend nicht erreichbar ({e}). Läuft die API auf :8000?',
  },
}

const LangContext = createContext({ lang: 'en', setLang: () => {}, t: (k) => k })

function readLang() {
  try {
    const v = localStorage.getItem('hs-lang')
    return D[v] ? v : 'en'
  } catch {
    return 'en'
  }
}

export function LangProvider({ children }) {
  const [lang, setLangState] = useState(readLang)
  const setLang = (v) => {
    setLangState(v)
    try { localStorage.setItem('hs-lang', v) } catch { /* storage unavailable */ }
  }
  useEffect(() => { document.documentElement.lang = lang }, [lang])
  const t = useCallback((key, vars) => {
    let s = D[lang][key] ?? D.en[key] ?? key
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v)
    return s
  }, [lang])
  return <LangContext.Provider value={{ lang, setLang, t }}>{children}</LangContext.Provider>
}

export const useI18n = () => useContext(LangContext)
