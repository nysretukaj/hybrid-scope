"""Small offline gazetteer: place name -> correlation zone, country and coordinates.

`zone` is the geographic unit used for correlation. Usually a country, but closely coupled
areas (e.g. the Baltic Sea littoral) share one zone so cross-border hybrid campaigns cluster.
specificity: 2 = city / sea area, 1 = country.
"""
import re

BALTIC = "Baltic Sea Region"

PLACES = [
    # Western Balkans
    (("Kosovo",), "Kosovo", "Kosovo", 42.60, 20.90, 1),
    (("Pristina", "Prishtina", "Prishtinë"), "Kosovo", "Kosovo", 42.6629, 21.1655, 2),
    (("Obiliq", "Obilić"), "Kosovo", "Kosovo", 42.6869, 21.0703, 2),
    (("Mitrovica",), "Kosovo", "Kosovo", 42.8914, 20.8660, 2),
    (("Prizren",), "Kosovo", "Kosovo", 42.2139, 20.7397, 2),
    (("Peja", "Peć"), "Kosovo", "Kosovo", 42.6593, 20.2887, 2),
    (("Gjilan",), "Kosovo", "Kosovo", 42.4635, 21.4694, 2),
    (("Ferizaj",), "Kosovo", "Kosovo", 42.3702, 21.1553, 2),
    (("Serbia",), "Serbia", "Serbia", 44.0, 20.9, 1),
    (("Belgrade",), "Serbia", "Serbia", 44.7866, 20.4489, 2),
    (("Novi Sad",), "Serbia", "Serbia", 45.2671, 19.8335, 2),
    (("North Macedonia",), "North Macedonia", "North Macedonia", 41.6, 21.7, 1),
    (("Skopje",), "North Macedonia", "North Macedonia", 41.9981, 21.4254, 2),
    (("Albania",), "Albania", "Albania", 41.15, 20.17, 1),
    (("Tirana",), "Albania", "Albania", 41.3275, 19.8187, 2),
    (("Bosnia",), "Bosnia and Herzegovina", "Bosnia and Herzegovina", 44.17, 17.9, 1),
    (("Sarajevo",), "Bosnia and Herzegovina", "Bosnia and Herzegovina", 43.8563, 18.4131, 2),
    (("Montenegro",), "Montenegro", "Montenegro", 42.7, 19.37, 1),
    (("Podgorica",), "Montenegro", "Montenegro", 42.4304, 19.2594, 2),
    (("Croatia",), "Croatia", "Croatia", 45.1, 15.2, 1),
    (("Zagreb",), "Croatia", "Croatia", 45.815, 15.9819, 2),
    # Baltic Sea region
    (("Estonia",), BALTIC, "Estonia", 58.6, 25.0, 1),
    (("Tallinn",), BALTIC, "Estonia", 59.437, 24.7536, 2),
    (("Narva",), BALTIC, "Estonia", 59.3797, 28.1791, 2),
    (("Finland",), BALTIC, "Finland", 61.9, 25.7, 1),
    (("Helsinki",), BALTIC, "Finland", 60.1699, 24.9384, 2),
    (("Gulf of Finland",), BALTIC, "Finland", 59.8, 25.5, 2),
    (("Baltic Sea",), BALTIC, "International waters", 58.5, 19.5, 2),
    (("Latvia",), BALTIC, "Latvia", 56.88, 24.6, 1),
    (("Riga",), BALTIC, "Latvia", 56.9496, 24.1052, 2),
    (("Lithuania",), BALTIC, "Lithuania", 55.17, 23.88, 1),
    (("Vilnius",), BALTIC, "Lithuania", 54.6872, 25.2797, 2),
    # Eastern Europe
    (("Moldova",), "Moldova", "Moldova", 47.4, 28.4, 1),
    (("Chisinau", "Chișinău"), "Moldova", "Moldova", 47.0105, 28.8638, 2),
    (("Transnistria",), "Moldova", "Moldova", 46.85, 29.6, 2),
    (("Ukraine",), "Ukraine", "Ukraine", 49.0, 31.4, 1),
    (("Kyiv", "Kiev"), "Ukraine", "Ukraine", 50.4501, 30.5234, 2),
    (("Kharkiv",), "Ukraine", "Ukraine", 49.9935, 36.2304, 2),
    (("Odesa", "Odessa"), "Ukraine", "Ukraine", 46.4825, 30.7233, 2),
    (("Lviv",), "Ukraine", "Ukraine", 49.8397, 24.0297, 2),
    (("Russia",), "Russia", "Russia", 55.75, 37.6, 1),
    (("Moscow",), "Russia", "Russia", 55.7558, 37.6173, 2),
    (("Poland",), "Poland", "Poland", 51.9, 19.1, 1),
    (("Warsaw",), "Poland", "Poland", 52.2297, 21.0122, 2),
    (("Romania",), "Romania", "Romania", 45.94, 24.97, 1),
    (("Bucharest",), "Romania", "Romania", 44.4268, 26.1025, 2),
    (("Bulgaria",), "Bulgaria", "Bulgaria", 42.73, 25.49, 1),
    (("Sofia",), "Bulgaria", "Bulgaria", 42.6977, 23.3219, 2),
    # Western Europe
    (("Germany",), "Germany", "Germany", 51.2, 10.4, 1),
    (("Berlin",), "Germany", "Germany", 52.52, 13.405, 2),
    (("France",), "France", "France", 46.2, 2.2, 1),
    (("Paris",), "France", "France", 48.8566, 2.3522, 2),
    (("United Kingdom", "Britain", "UK"), "United Kingdom", "United Kingdom", 54.0, -2.0, 1),
    (("London",), "United Kingdom", "United Kingdom", 51.5074, -0.1278, 2),
    (("Netherlands",), "Netherlands", "Netherlands", 52.13, 5.29, 1),
    (("Rotterdam",), "Netherlands", "Netherlands", 51.9244, 4.4777, 2),
    (("Amsterdam",), "Netherlands", "Netherlands", 52.3676, 4.9041, 2),
    (("Belgium",), "Belgium", "Belgium", 50.5, 4.47, 1),
    (("Brussels",), "Belgium", "Belgium", 50.8503, 4.3517, 2),
    (("Italy",), "Italy", "Italy", 41.87, 12.57, 1),
    (("Rome",), "Italy", "Italy", 41.9028, 12.4964, 2),
    (("Spain",), "Spain", "Spain", 40.46, -3.75, 1),
    (("Madrid",), "Spain", "Spain", 40.4168, -3.7038, 2),
    (("Greece",), "Greece", "Greece", 39.07, 21.82, 1),
    (("Athens",), "Greece", "Greece", 37.9838, 23.7275, 2),
    (("Turkey", "Türkiye"), "Turkey", "Turkey", 38.96, 35.24, 1),
    (("Istanbul",), "Turkey", "Turkey", 41.0082, 28.9784, 2),
    (("Ankara",), "Turkey", "Turkey", 39.9334, 32.8597, 2),
    # Rest of world
    (("Israel",), "Israel", "Israel", 31.05, 34.85, 1),
    (("Tel Aviv",), "Israel", "Israel", 32.0853, 34.7818, 2),
    (("Iran",), "Iran", "Iran", 32.43, 53.69, 1),
    (("Tehran",), "Iran", "Iran", 35.6892, 51.389, 2),
    (("China",), "China", "China", 35.86, 104.2, 1),
    (("Beijing",), "China", "China", 39.9042, 116.4074, 2),
    (("Taiwan",), "Taiwan", "Taiwan", 23.7, 120.96, 1),
    (("Taipei",), "Taiwan", "Taiwan", 25.033, 121.5654, 2),
    (("Japan",), "Japan", "Japan", 36.2, 138.25, 1),
    (("Tokyo",), "Japan", "Japan", 35.6762, 139.6503, 2),
    (("South Korea",), "South Korea", "South Korea", 35.9, 127.77, 1),
    (("Seoul",), "South Korea", "South Korea", 37.5665, 126.978, 2),
    (("North Korea",), "North Korea", "North Korea", 40.34, 127.51, 1),
    (("Pyongyang",), "North Korea", "North Korea", 39.0392, 125.7625, 2),
    (("India",), "India", "India", 20.59, 78.96, 1),
    (("New Delhi",), "India", "India", 28.6139, 77.209, 2),
    (("Brazil",), "Brazil", "Brazil", -14.24, -51.93, 1),
    (("São Paulo", "Sao Paulo"), "Brazil", "Brazil", -23.5505, -46.6333, 2),
    (("United States", "U.S."), "United States", "United States", 39.8, -98.6, 1),
    (("Washington",), "United States", "United States", 38.9072, -77.0369, 2),
    (("New York",), "United States", "United States", 40.7128, -74.006, 2),
    (("Canada",), "Canada", "Canada", 56.13, -106.35, 1),
    (("Ottawa",), "Canada", "Canada", 45.4215, -75.6972, 2),
    (("Australia",), "Australia", "Australia", -25.27, 133.78, 1),
    (("Sydney",), "Australia", "Australia", -33.8688, 151.2093, 2),
]

_INDEX: dict[str, dict] = {}
for names, zone, country, lat, lon, spec in PLACES:
    for n in names:
        _INDEX[n] = {"name": names[0], "zone": zone, "country": country, "lat": lat, "lon": lon, "specificity": spec}

# Longest names first so "Gulf of Finland" wins over "Finland"; case-sensitive to avoid noise.
_PATTERN = re.compile(
    r"(?<![\w])(" + "|".join(re.escape(n) for n in sorted(_INDEX, key=len, reverse=True)) + r")(?![\w])"
)


def find_places(text: str) -> list[dict]:
    found: dict[str, dict] = {}
    for m in _PATTERN.finditer(text or ""):
        place = _INDEX[m.group(1)]
        if place["name"] not in found:
            found[place["name"]] = {**place, "pos": m.start()}
    return list(found.values())


def primary_place(places: list[dict]) -> dict | None:
    """Most specific place wins; ties go to the earliest mention."""
    if not places:
        return None
    best = sorted(places, key=lambda p: (-p["specificity"], p["pos"]))[0]
    return {k: v for k, v in best.items() if k != "pos"}
