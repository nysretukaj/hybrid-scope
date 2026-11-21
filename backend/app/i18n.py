"""Server-side translations (English, Albanian, German) for every text the backend generates:
alert titles and summaries, score explanations, link reasons, the intelligence brief, local-NLP
rationales, zone names and notifications.

Live article titles and texts stay in their original language: they are source evidence.
MITRE ATT&CK / DISARM technique names stay in English: they are international identifiers.
"""
LANGS = ("en", "sq", "de")
DEFAULT = "en"


def norm_lang(lang: str | None) -> str:
    return lang if lang in LANGS else DEFAULT


T: dict[str, dict[str, str]] = {
    # --- categories, levels, entity types -----------------------------------------
    "cat.disinformation": {"en": "Disinformation", "sq": "Dezinformim", "de": "Desinformation"},
    "cat.cyber": {"en": "Cyber", "sq": "Kibernetik", "de": "Cyber"},
    "cat.infrastructure": {"en": "Infrastructure", "sq": "Infrastrukturë", "de": "Infrastruktur"},
    "cat.political": {"en": "Political", "sq": "Politik", "de": "Politisch"},
    "cat.physical": {"en": "Security", "sq": "Siguri", "de": "Sicherheit"},
    "cat.other": {"en": "Not threat-relevant", "sq": "Jo relevant", "de": "Nicht relevant"},
    "level.CRITICAL": {"en": "CRITICAL", "sq": "KRITIK", "de": "KRITISCH"},
    "level.HIGH": {"en": "HIGH", "sq": "I LARTË", "de": "HOCH"},
    "level.MEDIUM": {"en": "MEDIUM", "sq": "MESATAR", "de": "MITTEL"},
    "level.LOW": {"en": "LOW", "sq": "I ULËT", "de": "NIEDRIG"},
    "etype.actor": {"en": "actor", "sq": "aktor", "de": "Akteur"},
    "etype.organisation": {"en": "organisation", "sq": "organizatë", "de": "Organisation"},
    "etype.technology": {"en": "technology", "sq": "teknologji", "de": "Technologie"},
    "etype.CVE": {"en": "CVE", "sq": "CVE", "de": "CVE"},
    "etype.narrative": {"en": "narrative", "sq": "narrativë", "de": "Narrativ"},
    "and": {"en": " and ", "sq": " dhe ", "de": " und "},

    # --- alerts ------------------------------------------------------------------
    "alert.title.hybrid": {"en": "Hybrid threat pattern - {zone}", "sq": "Model kërcënimi hibrid - {zone}",
                           "de": "Hybrides Bedrohungsmuster - {zone}"},
    "alert.title.single": {"en": "{cat} activity - {zone}", "sq": "Aktivitet ({cat}) - {zone}",
                           "de": "{cat}-Aktivität - {zone}"},
    "alert.title.multi": {"en": "Multi-domain activity - {zone}", "sq": "Aktivitet në disa domene - {zone}",
                          "de": "Domänenübergreifende Aktivität - {zone}"},
    "alert.summary": {"en": "{n} signal(s) from {k} source(s) in {zone} over {h}h spanning {cats}.",
                      "sq": "{n} sinjale nga {k} burime në {zone} gjatë {h} orëve, në domenet: {cats}.",
                      "de": "{n} Signale aus {k} Quellen in {zone} über {h} Std., Domänen: {cats}."},
    "alert.sequence": {"en": " Sequence: {seq}.", "sq": " Sekuenca: {seq}.", "de": " Abfolge: {seq}."},
    "alert.linked": {"en": " Linked by {ents}.", "sq": " Të lidhura nga: {ents}.", "de": " Verknüpft durch: {ents}."},
    "link.entity": {"en": "Shared {etype}: {name}", "sq": "I përbashkët ({etype}): {name}",
                    "de": "Gemeinsam ({etype}): {name}"},
    "link.temporal": {"en": "{a} -> {b} within {h}h", "sq": "{a} -> {b} brenda {h} orëve",
                      "de": "{a} -> {b} innerhalb von {h} Std."},

    # --- score breakdown -----------------------------------------------------------
    "sc.severity": {"en": "Severity", "sq": "Rëndësia", "de": "Schwere"},
    "sc.hybrid": {"en": "Hybrid (cross-domain)", "sq": "Hibrid (ndër-domene)", "de": "Hybrid (domänenübergreifend)"},
    "sc.corroboration": {"en": "Corroboration", "sq": "Konfirmimi nga burime", "de": "Bestätigung"},
    "sc.recency": {"en": "Recency", "sq": "Aktualiteti", "de": "Aktualität"},
    "sc.reliability": {"en": "Source reliability", "sq": "Besueshmëria e burimeve", "de": "Quellenzuverlässigkeit"},
    "ex.severity": {"en": "Peak severity {max}, mean {mean} across {n} signal(s)",
                    "sq": "Rëndësia maksimale {max}, mesatarja {mean} në {n} sinjale",
                    "de": "Höchste Schwere {max}, Mittel {mean} über {n} Signale"},
    "ex.hybrid.yes": {"en": "{n} linked threat domain(s)", "sq": "{n} domene kërcënimi të lidhura",
                      "de": "{n} verknüpfte Bedrohungsdomänen"},
    "ex.hybrid.no": {"en": "Single threat domain - no cross-domain link",
                     "sq": "Një domen i vetëm - pa lidhje mes domeneve",
                     "de": "Eine einzige Domäne - keine domänenübergreifende Verknüpfung"},
    "ex.corroboration": {"en": "{k} independent source(s) share actors, narratives or infrastructure",
                         "sq": "{k} burime të pavarura ndajnë aktorë, narrativa ose infrastrukturë",
                         "de": "{k} unabhängige Quellen teilen Akteure, Narrative oder Infrastruktur"},
    "ex.recency": {"en": "Latest signal {h}h ago (half-life {hl}h)",
                   "sq": "Sinjali i fundit para {h} orësh (gjysmëjeta {hl} orë)",
                   "de": "Letztes Signal vor {h} Std. (Halbwertszeit {hl} Std.)"},
    "ex.reliability": {"en": "Mean source reliability {r}", "sq": "Besueshmëria mesatare e burimeve {r}",
                       "de": "Mittlere Quellenzuverlässigkeit {r}"},

    # --- local NLP rationale -------------------------------------------------------
    "nlp.other": {"en": "Local NLP: no threat-domain indicators found; kept in the stream but excluded from alerts.",
                  "sq": "NLP lokal: nuk u gjetën tregues kërcënimi; mbetet në rrjedhë, por jo në alarme.",
                  "de": "Lokales NLP: keine Bedrohungsindikatoren gefunden; bleibt im Strom, aber nicht in Warnungen."},
    "nlp.classified": {"en": "Local NLP: classified as {cat} (matched: {kws}).",
                       "sq": "NLP lokal: u klasifikua si {cat} (fjalë kyçe: {kws}).",
                       "de": "Lokales NLP: als {cat} eingestuft (Treffer: {kws})."},
    "nlp.secondary": {"en": " Secondary: {cats}.", "sq": " Dytësore: {cats}.", "de": " Sekundär: {cats}."},
    "nlp.raised": {"en": " Severity raised by: {kws}.", "sq": " Rëndësia u rrit nga: {kws}.",
                   "de": " Schwere erhöht durch: {kws}."},
    "nlp.lowered": {"en": " Severity lowered by: {kws} (likely non-hostile).",
                    "sq": " Rëndësia u ul nga: {kws} (ka gjasa të mos jetë armiqësor).",
                    "de": " Schwere gesenkt durch: {kws} (vermutlich nicht feindlich)."},
    "nlp.factcheck": {
        "en": "Published by a fact-checker and the text points to a false or misleading claim: classified as disinformation (low severity).",
        "sq": "Publikuar nga një verifikues faktesh dhe teksti tregon një pretendim të rremë ose mashtrues: klasifikuar si dezinformim (rëndësi e ulët).",
        "de": "Von einem Faktencheck veröffentlicht, und der Text weist auf eine falsche oder irreführende Behauptung hin: als Desinformation eingestuft (geringe Schwere).",
    },
    "nlp.model": {"en": " Trained model: {cat} ({p}% sure).", "sq": " Modeli i trajnuar: {cat} ({p}% i sigurt).",
                  "de": " Trainiertes Modell: {cat} ({p}% sicher)."},
    "nlp.noloc": {"en": " No known location resolved.", "sq": " Nuk u gjet asnjë vendndodhje e njohur.",
                  "de": " Kein bekannter Ort ermittelt."},

    # --- intelligence brief --------------------------------------------------------
    "est.0": {"en": "almost certain", "sq": "pothuajse e sigurt", "de": "nahezu sicher"},
    "est.1": {"en": "highly likely", "sq": "shumë e mundshme", "de": "sehr wahrscheinlich"},
    "est.2": {"en": "likely", "sq": "e mundshme", "de": "wahrscheinlich"},
    "est.3": {"en": "roughly even chance", "sq": "njëlloj e mundshme dhe e pamundshme", "de": "etwa gleich wahrscheinlich"},
    "est.4": {"en": "unlikely", "sq": "pak e mundshme", "de": "unwahrscheinlich"},
    "est.5": {"en": "highly unlikely", "sq": "shumë pak e mundshme", "de": "sehr unwahrscheinlich"},
    "b.classification": {"en": "UNCLASSIFIED // OSINT", "sq": "E PAKLASIFIKUAR // OSINT", "de": "OFFEN // OSINT"},
    "b.exercise": {"en": " // EXERCISE - SYNTHETIC DATA", "sq": " // STËRVITJE - TË DHËNA SINTETIKE",
                   "de": " // ÜBUNG - SYNTHETISCHE DATEN"},
    "b.bluf.hybrid": {
        "en": "It is {lk} that the activity observed in {zone} over the last {h} hours is a coordinated hybrid campaign "
              "combining {cats} lines of effort, with {target} as the most exposed target. Risk is assessed {level} ({score}/100).",
        "sq": "Është {lk} që aktiviteti i vëzhguar në {zone} gjatë {h} orëve të fundit është një fushatë hibride e "
              "koordinuar që kombinon {cats}. Objektivi më i ekspozuar: {target}. Rreziku vlerësohet {level} ({score}/100).",
        "de": "Es ist {lk}, dass die in {zone} in den letzten {h} Stunden beobachtete Aktivität eine koordinierte hybride "
              "Kampagne ist, die {cats} kombiniert. Am stärksten exponiert: {target}. Das Risiko wird als {level} ({score}/100) bewertet.",
    },
    "b.bluf.single": {
        "en": "It is {lk} that the reported {cat} activity in {zone} is accurate; no linked activity in other threat "
              "domains was found. Risk is assessed {level} ({score}/100).",
        "sq": "Është {lk} që aktiviteti i raportuar ({cat}) në {zone} është i saktë; nuk u gjet aktivitet i lidhur në "
              "domene të tjera. Rreziku vlerësohet {level} ({score}/100).",
        "de": "Es ist {lk}, dass die gemeldete {cat}-Aktivität in {zone} zutrifft; verknüpfte Aktivität in anderen "
              "Domänen wurde nicht gefunden. Das Risiko wird als {level} ({score}/100) bewertet.",
    },
    "b.j.sequence": {
        "en": "The pattern unfolded in sequence: {steps}. A sequence that starts with {first} is consistent with "
              "preparing the information space before disruptive action.",
        "sq": "Modeli u zhvillua në këtë sekuencë: {steps}. Një sekuencë që nis me {first} përputhet me përgatitjen e "
              "hapësirës informative para veprimeve shkatërruese.",
        "de": "Das Muster entfaltete sich in dieser Abfolge: {steps}. Eine Abfolge, die mit {first} beginnt, passt zur "
              "Vorbereitung des Informationsraums vor störenden Aktionen.",
    },
    "b.j.entities": {
        "en": "The signals are linked by shared entities: {list}. Shared entities across independent sources reduce the chance of coincidence.",
        "sq": "Sinjalet lidhen nga entitete të përbashkëta: {list}. Entitetet e përbashkëta mes burimeve të pavarura e ulin mundësinë e rastësisë.",
        "de": "Die Signale sind durch gemeinsame Entitäten verknüpft: {list}. Gemeinsame Entitäten in unabhängigen Quellen machen Zufall unwahrscheinlicher.",
    },
    "b.j.entity_item": {"en": "{name} ({etype}, {n} signals)", "sq": "{name} ({etype}, {n} sinjale)",
                        "de": "{name} ({etype}, {n} Signale)"},
    "b.j.impact": {"en": "The most severe development is \"{title}\" (severity {sev}, {source}).",
                   "sq": "Zhvillimi më i rëndë është \"{title}\" (rëndësia {sev}, {source}).",
                   "de": "Die schwerwiegendste Entwicklung ist „{title}“ (Schwere {sev}, {source})."},
    "b.j.cred": {"en": "The assessment draws on {n} signals from {k} sources (mean reliability {r}).",
                 "sq": "Vlerësimi mbështetet në {n} sinjale nga {k} burime (besueshmëria mesatare {r}).",
                 "de": "Die Bewertung stützt sich auf {n} Signale aus {k} Quellen (mittlere Zuverlässigkeit {r})."},
    "b.j.lowrel": {
        "en": " {n} signal(s) come from low-reliability sources; they are used as indicators of intent, not as confirmation of events.",
        "sq": " {n} sinjale vijnë nga burime me besueshmëri të ulët; ato përdoren si tregues qëllimi, jo si konfirmim i ngjarjeve.",
        "de": " {n} Signale stammen aus wenig zuverlässigen Quellen; sie dienen als Hinweise auf Absichten, nicht als Bestätigung von Ereignissen.",
    },
    "b.cell": {
        "en": "Convene a cross-agency cell (CERT, operators, police, strategic communications) for {zone}; treat the domains as one campaign, not separate incidents.",
        "sq": "Mblidhni një grup ndërinstitucional (CERT, operatorët, policia, komunikimi strategjik) për {zone}; trajtojini domenet si një fushatë të vetme, jo si incidente të veçanta.",
        "de": "Einen behördenübergreifenden Stab (CERT, Betreiber, Polizei, strategische Kommunikation) für {zone} einberufen; die Domänen als eine Kampagne behandeln, nicht als getrennte Vorfälle.",
    },
    "b.action.cyber": {
        "en": "Hunt for indicators tied to {actors}; prioritise patching or mitigating {cves}; restrict and monitor remote access ({tech}).",
        "sq": "Kërkoni tregues të lidhur me {actors}; jepini përparësi përditësimit ose zbutjes së {cves}; kufizoni dhe monitoroni qasjen në distancë ({tech}).",
        "de": "Nach Indikatoren zu {actors} suchen; Patchen oder Absichern von {cves} priorisieren; Fernzugänge ({tech}) einschränken und überwachen.",
    },
    "b.action.disinformation": {
        "en": "Coordinate fast, factual public communication through official channels; prebunk the narrative(s) {narratives}; report coordinated accounts to {platforms}.",
        "sq": "Koordinoni komunikim publik të shpejtë dhe faktik përmes kanaleve zyrtare; parandaloni narrativat {narratives}; raportoni llogaritë e koordinuara te {platforms}.",
        "de": "Schnelle, faktenbasierte Kommunikation über offizielle Kanäle abstimmen; den Narrativen {narratives} vorbeugen (Prebunking); koordinierte Konten an {platforms} melden.",
    },
    "b.action.infrastructure": {
        "en": "Raise the alert level of affected operators ({orgs}); verify manual-fallback readiness and spare capacity.",
        "sq": "Rrisni nivelin e gatishmërisë së operatorëve të prekur ({orgs}); verifikoni gatishmërinë për punë manuale dhe kapacitetet rezervë.",
        "de": "Alarmstufe der betroffenen Betreiber ({orgs}) erhöhen; Bereitschaft für manuellen Betrieb und Reservekapazitäten prüfen.",
    },
    "b.action.physical": {
        "en": "Increase physical protection and patrols around critical sites in {places}; share sightings with law enforcement.",
        "sq": "Shtoni mbrojtjen fizike dhe patrullimet rreth objekteve kritike në {places}; ndani vëzhgimet me policinë.",
        "de": "Objektschutz und Streifen an kritischen Standorten in {places} verstärken; Sichtungen mit der Polizei teilen.",
    },
    "b.action.political": {
        "en": "Brief the government and election bodies in {places}; document pressure or interference attempts and coordinate a joint diplomatic response with partners.",
        "sq": "Informoni qeverinë dhe institucionet zgjedhore në {places}; dokumentoni presionet ose ndërhyrjet dhe koordinoni një reagim të përbashkët diplomatik me partnerët.",
        "de": "Regierung und Wahlbehörden in {places} unterrichten; Druck- oder Einmischungsversuche dokumentieren und eine gemeinsame diplomatische Antwort mit Partnern abstimmen.",
    },
    "b.watch.political": {
        "en": "New statements, funding flows or pressure tactics by {actors} aimed at institutions or elections in {places}",
        "sq": "Deklarata të reja, financime ose presione nga {actors} që synojnë institucionet ose zgjedhjet në {places}",
        "de": "Neue Erklärungen, Geldflüsse oder Druckmittel von {actors} gegen Institutionen oder Wahlen in {places}",
    },
    "b.watch.cyber": {
        "en": "New exploitation, access-sale or leak-site activity involving {actors} or {tech}",
        "sq": "Shfrytëzim i ri, shitje qasjeje ose aktivitet në faqe rrjedhjesh që përfshin {actors} ose {tech}",
        "de": "Neue Ausnutzung, Zugangsverkäufe oder Leak-Site-Aktivität mit Bezug zu {actors} oder {tech}",
    },
    "b.watch.disinformation": {
        "en": "Further amplification of {narratives}, especially calls for offline action or cross-language spread",
        "sq": "Përhapje e mëtejshme e {narratives}, veçanërisht thirrje për veprim në terren ose përhapje në gjuhë të tjera",
        "de": "Weitere Verbreitung von {narratives}, besonders Aufrufe zu Aktionen vor Ort oder Verbreitung in anderen Sprachen",
    },
    "b.watch.infrastructure": {
        "en": "Additional unexplained outages or control-system anomalies at {orgs}",
        "sq": "Ndërprerje të tjera të pashpjegueshme ose anomali në sistemet e kontrollit te {orgs}",
        "de": "Weitere ungeklärte Ausfälle oder Anomalien in Steuerungssystemen bei {orgs}",
    },
    "b.watch.physical": {
        "en": "Drone sightings, vessel loitering, jamming or crowd mobilisation near critical sites in {places}",
        "sq": "Dronë, anije që qëndrojnë pa arsye, bllokim sinjalesh ose mobilizim turmash pranë objekteve kritike në {places}",
        "de": "Drohnen, verdächtig verweilende Schiffe, Störsender oder Menschenansammlungen nahe kritischer Standorte in {places}",
    },
    "b.fb.actors": {"en": "the actors observed", "sq": "aktorët e vëzhguar", "de": "die beobachteten Akteure"},
    "b.fb.orgs": {"en": "affected operators", "sq": "operatorët e prekur", "de": "betroffene Betreiber"},
    "b.fb.tech": {"en": "exposed systems", "sq": "sistemet e ekspozuara", "de": "exponierte Systeme"},
    "b.fb.narratives": {"en": "observed", "sq": "e vëzhguara", "de": "beobachtete"},
    "b.fb.cves": {"en": "relevant vulnerabilities", "sq": "dobësitë përkatëse", "de": "relevante Schwachstellen"},
    "b.fb.platforms": {"en": "the platforms involved", "sq": "platformat e përfshira", "de": "die beteiligten Plattformen"},
    "b.method": {
        "en": "Generated deterministically from correlated signals; estimative language per ICD 203. TTP mappings are heuristic and require analyst validation.",
        "sq": "Gjeneruar në mënyrë deterministe nga sinjalet e korreluara; gjuha e probabilitetit sipas ICD 203. Përputhjet e teknikave (TTP) janë heuristike dhe kërkojnë verifikim nga analisti.",
        "de": "Deterministisch aus korrelierten Signalen erzeugt; Wahrscheinlichkeitssprache nach ICD 203. TTP-Zuordnungen sind heuristisch und müssen von Analysten geprüft werden.",
    },

    # --- notifications -----------------------------------------------------------
    "n.hybrid": {"en": " · HYBRID", "sq": " · HIBRID", "de": " · HYBRID"},
    "n.latest": {"en": "Latest: {h}", "sq": "E fundit: {h}", "de": "Neueste: {h}"},
    "n.domains": {"en": "Domains: {cats} · {n} signals / {k} sources · confidence {c}%",
                  "sq": "Domenet: {cats} · {n} sinjale / {k} burime · besueshmëria {c}%",
                  "de": "Domänen: {cats} · {n} Signale / {k} Quellen · Konfidenz {c}%"},
    "n.exercise": {"en": "[EXERCISE - synthetic scenario data]", "sq": "[STËRVITJE - të dhëna sintetike]",
                   "de": "[ÜBUNG - synthetische Szenariodaten]"},
    "n.open": {"en": "Open in HybridScope", "sq": "Hape në HybridScope", "de": "In HybridScope öffnen"},
    "n.test": {"en": "✅ HybridScope is connected. Alerts will arrive in this chat.",
               "sq": "✅ HybridScope u lidh me sukses. Alarmet do të vijnë në këtë bisedë.",
               "de": "✅ HybridScope ist verbunden. Warnungen kommen in diesem Chat an."},
}

# Albanian names use the indefinite form, which reads correctly both alone and after "në" (in).
ZONES: dict[str, dict[str, str]] = {
    "Kosovo": {"sq": "Kosovë", "de": "Kosovo"},
    "Serbia": {"sq": "Serbi", "de": "Serbien"},
    "North Macedonia": {"sq": "Maqedoni e Veriut", "de": "Nordmazedonien"},
    "Albania": {"sq": "Shqipëri", "de": "Albanien"},
    "Bosnia and Herzegovina": {"sq": "Bosnjë e Hercegovinë", "de": "Bosnien und Herzegowina"},
    "Montenegro": {"sq": "Mal i Zi", "de": "Montenegro"},
    "Croatia": {"sq": "Kroaci", "de": "Kroatien"},
    "Baltic Sea Region": {"sq": "Rajoni i Detit Baltik", "de": "Ostseeraum"},
    "Moldova": {"sq": "Moldavi", "de": "Moldau"},
    "Ukraine": {"sq": "Ukrainë", "de": "Ukraine"},
    "Russia": {"sq": "Rusi", "de": "Russland"},
    "Poland": {"sq": "Poloni", "de": "Polen"},
    "Romania": {"sq": "Rumani", "de": "Rumänien"},
    "Bulgaria": {"sq": "Bullgari", "de": "Bulgarien"},
    "Germany": {"sq": "Gjermani", "de": "Deutschland"},
    "France": {"sq": "Francë", "de": "Frankreich"},
    "United Kingdom": {"sq": "Mbretëri e Bashkuar", "de": "Vereinigtes Königreich"},
    "Netherlands": {"sq": "Holandë", "de": "Niederlande"},
    "Belgium": {"sq": "Belgjikë", "de": "Belgien"},
    "Italy": {"sq": "Itali", "de": "Italien"},
    "Spain": {"sq": "Spanjë", "de": "Spanien"},
    "Greece": {"sq": "Greqi", "de": "Griechenland"},
    "Turkey": {"sq": "Turqi", "de": "Türkei"},
    "Austria": {"sq": "Austri", "de": "Österreich"},
    "Switzerland": {"sq": "Zvicër", "de": "Schweiz"},
    "Israel": {"sq": "Izrael", "de": "Israel"},
    "Iran": {"sq": "Iran", "de": "Iran"},
    "China": {"sq": "Kinë", "de": "China"},
    "Taiwan": {"sq": "Tajvan", "de": "Taiwan"},
    "Japan": {"sq": "Japoni", "de": "Japan"},
    "South Korea": {"sq": "Kore e Jugut", "de": "Südkorea"},
    "North Korea": {"sq": "Kore e Veriut", "de": "Nordkorea"},
    "India": {"sq": "Indi", "de": "Indien"},
    "Brazil": {"sq": "Brazil", "de": "Brasilien"},
    "United States": {"sq": "Shtetet e Bashkuara", "de": "Vereinigte Staaten"},
    "Canada": {"sq": "Kanada", "de": "Kanada"},
    "Australia": {"sq": "Australi", "de": "Australien"},
}

# Descriptive entity names from the exercise scenario. Proper names (GreyMist, Voice of the Valley,
# SCADA, KFOR...) stay as they are.
ENTITIES: dict[str, dict[str, str]] = {
    "national grid operator": {"sq": "operatori kombëtar i rrjetit", "de": "nationaler Netzbetreiber"},
    "national CERT": {"sq": "CERT-i kombëtar", "de": "nationales CERT"},
    "Ministry of Economy": {"sq": "Ministria e Ekonomisë", "de": "Wirtschaftsministerium"},
    "Kosovo Police": {"sq": "Policia e Kosovës", "de": "Polizei des Kosovo"},
    "Central Electoral Commission": {"sq": "Komisioni Qendror Zgjedhor", "de": "Zentrale Wahlkommission"},
    "Estonia-Finland interconnector": {"sq": "interkonektori Estoni-Finlandë", "de": "Stromverbindung Estland-Finnland"},
    "Finland-Estonia subsea cable": {"sq": "kablli nënujor Finlandë-Estoni", "de": "Unterseekabel Finnland-Estland"},
    "Estonian authorities": {"sq": "autoritetet estoneze", "de": "estnische Behörden"},
    "Finnish Coast Guard": {"sq": "Roja Bregdetare Finlandeze", "de": "Finnische Küstenwache"},
    "Port of Tallinn": {"sq": "Porti i Talinit", "de": "Hafen Tallinn"},
    "mobile operator": {"sq": "operatori celular", "de": "Mobilfunkbetreiber"},
    "energy corruption": {"sq": "korrupsioni në energji", "de": "Energiekorruption"},
    "grid collapse": {"sq": "kolapsi i rrjetit", "de": "Netzkollaps"},
    "power rationing": {"sq": "kufizimi i rrymës", "de": "Stromrationierung"},
    "foreign forces staged outages": {"sq": "forcat e huaja inskenuan ndërprerjet",
                                      "de": "ausländische Kräfte inszenierten Ausfälle"},
    "evacuation hoax": {"sq": "mashtrimi me evakuimin", "de": "Evakuierungs-Falschmeldung"},
    "military escalation": {"sq": "përshkallëzimi ushtarak", "de": "militärische Eskalation"},
    "gas price hike": {"sq": "rritja e çmimit të gazit", "de": "Gaspreiserhöhung"},
    "stolen elections": {"sq": "zgjedhjet e vjedhura", "de": "gestohlene Wahlen"},
    "malicious loader": {"sq": "program keqdashës", "de": "Schad-Loader"},
    "drone": {"sq": "dron", "de": "Drohne"},
}


# Names of the exercise scenario's fictional sources (real outlets such as Koha keep their names).
SOURCES: dict[str, dict[str, str]] = {
    "Forum monitor": {"sq": "Monitorim forumesh", "de": "Forenbeobachtung"},
    "SecVendor Threat Blog": {"sq": "Blogu i kërcënimeve SecVendor", "de": "SecVendor-Bedrohungsblog"},
    "National CERT advisory": {"sq": "Njoftim i CERT-it kombëtar", "de": "Warnung des nationalen CERT"},
    "Regional news wire": {"sq": "Agjenci rajonale lajmesh", "de": "Regionale Nachrichtenagentur"},
    "Fact-check desk": {"sq": "Redaksi e verifikimit të fakteve", "de": "Faktencheck-Redaktion"},
    "Geolocated social posts": {"sq": "Postime sociale me vendndodhje", "de": "Geolokalisierte Social-Media-Beiträge"},
    "Leak-site monitor": {"sq": "Monitorim i faqeve të rrjedhjeve", "de": "Leak-Site-Beobachtung"},
    "Maritime tracker": {"sq": "Gjurmues detar", "de": "Schiffsverfolgung"},
    "Nordic news agency": {"sq": "Agjenci nordike lajmesh", "de": "Nordische Nachrichtenagentur"},
    "Aviation safety notices": {"sq": "Njoftime për sigurinë e aviacionit", "de": "Flugsicherheitsmeldungen"},
    "Telegram channel monitor": {"sq": "Monitorim kanalesh Telegram", "de": "Telegram-Kanalbeobachtung"},
    "Grid operator bulletin": {"sq": "Buletin i operatorit të rrjetit", "de": "Mitteilung des Netzbetreibers"},
    "Media monitor": {"sq": "Monitorim mediash", "de": "Medienbeobachtung"},
    "Platform transparency report": {"sq": "Raport transparence i platformës", "de": "Transparenzbericht der Plattform"},
    "International news agency": {"sq": "Agjenci ndërkombëtare lajmesh", "de": "Internationale Nachrichtenagentur"},
    "Energy ministry statement": {"sq": "Deklaratë e ministrisë së energjisë", "de": "Erklärung des Energieministeriums"},
    "Security news": {"sq": "Lajme sigurie", "de": "Sicherheitsnachrichten"},
    "Vendor security bulletin": {"sq": "Buletin sigurie i prodhuesit", "de": "Sicherheitsbulletin des Herstellers"},
    "Disaster bulletin": {"sq": "Buletin për fatkeqësitë", "de": "Katastrophenmeldung"},
    "Social media": {"sq": "Rrjete sociale", "de": "Soziale Medien"},
    "Port authority statement": {"sq": "Deklaratë e autoritetit portual", "de": "Erklärung der Hafenbehörde"},
}
SOURCE_TYPES: dict[str, dict[str, str]] = {
    "news": {"sq": "lajme", "de": "Nachrichten"}, "social": {"sq": "rrjete sociale", "de": "soziale Medien"},
    "forum": {"sq": "forum", "de": "Forum"}, "research": {"sq": "kërkim", "de": "Recherche"},
    "advisory": {"sq": "njoftim sigurie", "de": "Sicherheitswarnung"}, "leak": {"sq": "rrjedhje", "de": "Leak"},
    "maritime": {"sq": "detar", "de": "maritim"}, "official": {"sq": "zyrtar", "de": "amtlich"},
    "fact-check": {"sq": "verifikim faktesh", "de": "Faktencheck"}, "disaster": {"sq": "fatkeqësi natyrore", "de": "Katastrophe"},
}


def source_label(name: str, lang: str | None = None) -> str:
    lang = norm_lang(lang)
    if lang == DEFAULT:
        return name
    if name.startswith("Telegram: "):
        return name  # channel names are proper names
    return SOURCES.get(name, {}).get(lang, name)


def source_type_label(source_type: str, lang: str | None = None) -> str:
    """'news (sq)' -> 'lajme (sq)': translate the base word, keep the language/feed suffix."""
    lang = norm_lang(lang)
    if lang == DEFAULT or not source_type:
        return source_type
    base, _, rest = source_type.partition(" ")
    label = SOURCE_TYPES.get(base, {}).get(lang, base)
    return f"{label} {rest}".strip()


def entity_name(name: str, lang: str | None = None) -> str:
    lang = norm_lang(lang)
    return name if lang == DEFAULT else ENTITIES.get(name, {}).get(lang, name)


# City and area names that differ in Albanian or German (country names come from ZONES).
PLACES: dict[str, dict[str, str]] = {
    "Pristina": {"sq": "Prishtinë"},
    "Mitrovica": {"sq": "Mitrovicë"},
    "Belgrade": {"sq": "Beograd", "de": "Belgrad"},
    "Skopje": {"sq": "Shkup"},
    "Tirana": {"sq": "Tiranë"},
    "Tallinn": {"sq": "Talin"},
    "Gulf of Finland": {"sq": "Gjiri i Finlandës", "de": "Finnischer Meerbusen"},
    "Baltic Sea": {"sq": "Deti Baltik", "de": "Ostsee"},
    "Chisinau": {"sq": "Kishinau", "de": "Chișinău"},
    "Kyiv": {"sq": "Kiev", "de": "Kyjiw"},
    "Kharkiv": {"de": "Charkiw"},
    "Odesa": {"de": "Odessa"},
    "Moscow": {"sq": "Moskë", "de": "Moskau"},
    "Warsaw": {"sq": "Varshavë", "de": "Warschau"},
    "Vienna": {"sq": "Vjenë", "de": "Wien"},
    "Munich": {"sq": "Mynih", "de": "München"},
    "Brussels": {"sq": "Bruksel", "de": "Brüssel"},
    "Rome": {"sq": "Romë", "de": "Rom"},
    "Athens": {"sq": "Athinë", "de": "Athen"},
    "London": {"sq": "Londër"},
    "Washington": {"sq": "Uashington"},
    "New Delhi": {"sq": "Nju Delhi", "de": "Neu-Delhi"},
    "Tokyo": {"sq": "Tokio", "de": "Tokio"},
}


def place_name(name: str, lang: str | None = None) -> str:
    lang = norm_lang(lang)
    if lang == DEFAULT:
        return name
    if name in ZONES:
        return ZONES[name].get(lang, name)
    return PLACES.get(name, {}).get(lang, name)


def tr(key: str, lang: str | None = None, **kw) -> str:
    entry = T.get(key)
    if entry is None:
        return key
    text = entry.get(norm_lang(lang)) or entry[DEFAULT]
    return text.format(**kw) if kw else text


def zone_name(zone: str | None, lang: str | None = None) -> str | None:
    if not zone:
        return zone
    lang = norm_lang(lang)
    return zone if lang == DEFAULT else ZONES.get(zone, {}).get(lang, zone)


def cat_label(cat: str, lang: str | None = None) -> str:
    return tr(f"cat.{cat}", lang)


def join_list(items: list[str], lang: str | None = None) -> str:
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + tr("and", lang) + items[-1]
