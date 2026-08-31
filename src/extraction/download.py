"""Step 2 — Download raw data from Wikidata / Wikimedia Commons.

Each phase issues focused SPARQL queries (chunked VALUES clauses, per WDQS
etiquette) and saves its raw output to data/raw/, so every later stage is
reproducible offline. Phases:

  1. artworks         paintings (P31=Q3305213) with an image (P18) created
                      (P170) by a seed artist; ranked by sitelink count and
                      capped at MAX_ARTWORKS_PER_ARTIST per artist
  2. artwork_links    P195 collection, P186 material, P136 genre, P180 depicts,
                      P135 movement, P88 commissioned-by, for selected works
  3. artist_links     P135 movement, P737 influenced-by, P1066 student-of;
                      human targets extend the artist set (grounded growth)
  4. artists          biography of seed + referenced artists: P569/P570 dates,
                      P19/P20 places, P245 ULAN, English Wikipedia article
  5. collections      place of the collection (P276, falling back to P131)
  6. places           P625 coordinates, P17 country, P1667 TGN
  7. countries        P297 ISO code
  8. terms            P1014 AAT + description for movement/material/genre/
                      subject nodes; description for patrons
  9. image_metadata   Commons imageinfo (pixel size, MIME, license) for the
                      image files of the selected artworks

Run:  python -m src.extraction.download
"""

import json
from collections import defaultdict
from urllib.parse import unquote

from config import COMMONS_API, MAX_ARTWORKS_PER_ARTIST, RAW_DIR, SEED_DIR
from src.extraction.sparql import api_get, chunked, qid, sparql_select

LABEL_SERVICE = 'SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mul,fr,de,it,es,nl,sv". }'


def save(name: str, data) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    n = len(data)
    print(f"  saved {n:>5} rows -> {path.name}")


def values(qids) -> str:
    return " ".join(f"wd:{q}" for q in qids)


# --------------------------------------------------------------------------
# Phase 1: artworks (paintings with an image, by seed artists)
# --------------------------------------------------------------------------
def download_artworks(seed_qids: list[str]) -> list[dict]:
    rows = []
    for chunk in chunked(seed_qids, 10):
        rows += sparql_select(f"""
        SELECT ?work ?workLabel ?creator ?sitelinks
               (SAMPLE(YEAR(?inc)) AS ?year) (SAMPLE(?img) AS ?image)
               (SAMPLE(?hM) AS ?heightM) (SAMPLE(?wM) AS ?widthM)
               (SAMPLE(?art) AS ?article)
        WHERE {{
          VALUES ?creator {{ {values(chunk)} }}
          ?work wdt:P31 wd:Q3305213; wdt:P170 ?creator; wdt:P18 ?img;
                wikibase:sitelinks ?sitelinks .
          OPTIONAL {{ ?work wdt:P571 ?inc }}
          # p:/psn: path returns unit-normalized (SI) quantities
          OPTIONAL {{ ?work p:P2048/psn:P2048/wikibase:quantityAmount ?hM }}
          OPTIONAL {{ ?work p:P2049/psn:P2049/wikibase:quantityAmount ?wM }}
          OPTIONAL {{ ?art schema:about ?work;
                          schema:isPartOf <https://en.wikipedia.org/> }}
          {LABEL_SERVICE}
        }}
        GROUP BY ?work ?workLabel ?creator ?sitelinks
        """)

    # Keep the most notable works per artist (sitelink count as proxy),
    # so the graph stays grounded without exploding in size.
    by_artist = defaultdict(list)
    for r in rows:
        by_artist[qid(r["creator"])].append(r)
    selected = []
    for works in by_artist.values():
        works.sort(key=lambda r: int(r["sitelinks"]), reverse=True)
        selected += works[:MAX_ARTWORKS_PER_ARTIST]
    return selected


# --------------------------------------------------------------------------
# Phase 2: artwork relations
# --------------------------------------------------------------------------
def download_artwork_links(work_qids: list[str]) -> list[dict]:
    rows = []
    for chunk in chunked(work_qids, 60):
        rows += sparql_select(f"""
        SELECT ?work ?prop ?target ?targetLabel WHERE {{
          VALUES ?work {{ {values(chunk)} }}
          VALUES ?prop {{ wdt:P195 wdt:P186 wdt:P136 wdt:P180 wdt:P135 wdt:P88 }}
          ?work ?prop ?target .
          {LABEL_SERVICE}
        }}
        """)
    return rows


# --------------------------------------------------------------------------
# Phase 3: artist relations (movements, influences, teachers)
# --------------------------------------------------------------------------
def download_artist_links(artist_qids: list[str]) -> list[dict]:
    rows = []
    for chunk in chunked(artist_qids, 25):
        rows += sparql_select(f"""
        SELECT ?artist ?prop ?target ?targetLabel ?targetIsHuman WHERE {{
          VALUES ?artist {{ {values(chunk)} }}
          VALUES ?prop {{ wdt:P135 wdt:P737 wdt:P1066 }}
          ?artist ?prop ?target .
          BIND(EXISTS {{ ?target wdt:P31 wd:Q5 }} AS ?targetIsHuman)
          {LABEL_SERVICE}
        }}
        """)
    return rows


# --------------------------------------------------------------------------
# Phase 4: artist biographies
# --------------------------------------------------------------------------
def download_artists(artist_qids: list[str]) -> list[dict]:
    rows = []
    for chunk in chunked(artist_qids, 25):
        rows += sparql_select(f"""
        SELECT ?artist ?artistLabel ?artistDescription
               (SAMPLE(?b) AS ?birthDate) (SAMPLE(?d) AS ?deathDate)
               (SAMPLE(?bp) AS ?birthPlace) (SAMPLE(?dp) AS ?deathPlace)
               (SAMPLE(?ulan) AS ?ulanId) (SAMPLE(?art) AS ?article)
        WHERE {{
          VALUES ?artist {{ {values(chunk)} }}
          OPTIONAL {{ ?artist wdt:P569 ?b }}
          OPTIONAL {{ ?artist wdt:P570 ?d }}
          OPTIONAL {{ ?artist wdt:P19 ?bp }}
          OPTIONAL {{ ?artist wdt:P20 ?dp }}
          OPTIONAL {{ ?artist wdt:P245 ?ulan }}
          OPTIONAL {{ ?art schema:about ?artist;
                          schema:isPartOf <https://en.wikipedia.org/> }}
          {LABEL_SERVICE}
        }}
        GROUP BY ?artist ?artistLabel ?artistDescription
        """)
    return rows


# --------------------------------------------------------------------------
# Phases 5-7: collections, places, countries
# --------------------------------------------------------------------------
def download_collections(coll_qids: list[str]) -> list[dict]:
    rows = []
    for chunk in chunked(coll_qids, 60):
        rows += sparql_select(f"""
        SELECT ?coll ?collLabel (SAMPLE(?p) AS ?place) WHERE {{
          VALUES ?coll {{ {values(chunk)} }}
          # P276 (location) preferred, P131 (admin territory) as fallback
          OPTIONAL {{ ?coll wdt:P276 ?p276 }}
          OPTIONAL {{ ?coll wdt:P131 ?p131 }}
          BIND(COALESCE(?p276, ?p131) AS ?p)
          {LABEL_SERVICE}
        }}
        GROUP BY ?coll ?collLabel
        """)
    return rows


def download_places(place_qids: list[str]) -> list[dict]:
    """Fetch place details, following P131 parents until a settlement.

    Wikidata locations are heterogeneous in granularity (e.g. the Musée
    d'Orsay is located in the building 'Gare d'Orsay', inside a quarter of
    the 7th arrondissement of Paris). Each place therefore also carries
    `isCity` (instance of city / municipality / town / village) and its
    administrative parent (P131): the transform step climbs the parent chain
    to normalize every place to city level.
    """
    fetched: dict[str, dict] = {}
    frontier = set(place_qids)
    for _ in range(5):  # bounded climb: building -> quarter -> district -> city
        frontier -= fetched.keys()
        if not frontier:
            break
        for chunk in chunked(sorted(frontier), 60):
            for r in sparql_select(f"""
            SELECT ?place ?placeLabel ?isCity
                   (SAMPLE(?c) AS ?coordinates) (SAMPLE(?k) AS ?country)
                   (SAMPLE(?tgn) AS ?tgnId) (SAMPLE(?up) AS ?parent)
            WHERE {{
              VALUES ?place {{ {values(chunk)} }}
              BIND(EXISTS {{
                VALUES ?cls {{ wd:Q515 wd:Q15284 wd:Q3957 wd:Q532 }}
                ?place wdt:P31/wdt:P279* ?cls
              }} AS ?isCity)
              OPTIONAL {{ ?place wdt:P625 ?c }}
              OPTIONAL {{ ?place wdt:P17 ?k }}
              OPTIONAL {{ ?place wdt:P1667 ?tgn }}
              OPTIONAL {{ ?place wdt:P131 ?up }}
              {LABEL_SERVICE}
            }}
            GROUP BY ?place ?placeLabel ?isCity
            """):
                fetched[qid(r["place"])] = r
        frontier = {
            qid(r["parent"])
            for r in fetched.values()
            if r["isCity"] != "true" and r.get("parent")
        }
    return list(fetched.values())


def download_countries(country_qids: list[str]) -> list[dict]:
    return sparql_select(f"""
    SELECT ?country ?countryLabel (SAMPLE(?iso) AS ?isoCode) WHERE {{
      VALUES ?country {{ {values(country_qids)} }}
      OPTIONAL {{ ?country wdt:P297 ?iso }}
      {LABEL_SERVICE}
    }}
    GROUP BY ?country ?countryLabel
    """)


# --------------------------------------------------------------------------
# Phase 8: classification terms (movements, materials, genres, subjects, patrons)
# --------------------------------------------------------------------------
def download_terms(term_qids: list[str]) -> list[dict]:
    rows = []
    for chunk in chunked(term_qids, 80):
        rows += sparql_select(f"""
        SELECT ?term ?termLabel ?termDescription (SAMPLE(?aat) AS ?aatId) WHERE {{
          VALUES ?term {{ {values(chunk)} }}
          OPTIONAL {{ ?term wdt:P1014 ?aat }}
          {LABEL_SERVICE}
        }}
        GROUP BY ?term ?termLabel ?termDescription
        """)
    return rows


# --------------------------------------------------------------------------
# Phase 9: Commons image metadata (the P18 file itself carries metadata)
# --------------------------------------------------------------------------
def download_image_metadata(image_urls: dict[str, str]) -> list[dict]:
    """image_urls: work QID -> Special:FilePath URL. Returns imageinfo rows."""
    file_by_title = {}
    for work, url in image_urls.items():
        filename = unquote(url.rsplit("/", 1)[-1]).replace("_", " ")
        file_by_title[f"File:{filename}"] = work

    rows = []
    titles = list(file_by_title)
    for chunk in chunked(titles, 40):
        data = api_get(
            COMMONS_API,
            {
                "action": "query",
                "titles": "|".join(chunk),
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiextmetadatafilter": "LicenseShortName",
            },
        )
        pages = data.get("query", {}).get("pages", {})
        normalized = {  # API normalizes titles (e.g. underscores); map back
            n["to"]: n["from"] for n in data.get("query", {}).get("normalized", [])
        }
        for page in pages.values():
            title = normalized.get(page["title"], page["title"])
            info = (page.get("imageinfo") or [{}])[0]
            rows.append(
                {
                    "work": file_by_title.get(title),
                    "file": page["title"],
                    "url": info.get("url"),
                    "width_px": info.get("width"),
                    "height_px": info.get("height"),
                    "mime": info.get("mime"),
                    "license": info.get("extmetadata", {})
                    .get("LicenseShortName", {})
                    .get("value"),
                }
            )
    return rows


def main() -> None:
    seed = json.loads((SEED_DIR / "artists.json").read_text(encoding="utf-8"))
    seed_qids = [a["qid"] for a in seed]

    print("Phase 1: artworks")
    artworks = download_artworks(seed_qids)
    save("artworks", artworks)
    work_qids = sorted({qid(r["work"]) for r in artworks})

    print("Phase 2: artwork links")
    artwork_links = download_artwork_links(work_qids)
    save("artwork_links", artwork_links)

    print("Phase 3: artist links")
    artist_links = download_artist_links(seed_qids)

    # Human targets of influenced-by / student-of extend the artist set;
    # their own links are fetched too (one extra round, no further recursion)
    # so that e.g. the movements of a master are part of the graph.
    referenced = {
        qid(r["target"])
        for r in artist_links
        if r["prop"].endswith(("P737", "P1066")) and r["targetIsHuman"] == "true"
    }
    artist_links += download_artist_links(sorted(referenced))
    save("artist_links", artist_links)
    all_artists = sorted(set(seed_qids) | referenced)

    print(f"Phase 4: artists ({len(seed_qids)} seed + {len(all_artists) - len(seed_qids)} referenced)")
    artists = download_artists(all_artists)
    save("artists", artists)

    print("Phase 5: collections")
    coll_qids = sorted(
        {qid(r["target"]) for r in artwork_links if r["prop"].endswith("P195")}
    )
    collections = download_collections(coll_qids)
    save("collections", collections)

    print("Phase 6: places")
    place_qids = sorted(
        {qid(r["place"]) for r in collections if r.get("place")}
        | {qid(r[k]) for r in artists for k in ("birthPlace", "deathPlace") if r.get(k)}
    )
    places = download_places(place_qids)
    save("places", places)

    print("Phase 7: countries")
    country_qids = sorted({qid(r["country"]) for r in places if r.get("country")})
    save("countries", download_countries(country_qids))

    print("Phase 8: classification terms")
    term_qids = sorted(
        {qid(r["target"]) for r in artwork_links if not r["prop"].endswith("P195")}
        | {qid(r["target"]) for r in artist_links if r["prop"].endswith("P135")}
    )
    save("terms", download_terms(term_qids))

    print("Phase 9: Commons image metadata")
    image_urls = {qid(r["work"]): r["image"] for r in artworks if r.get("image")}
    save("image_metadata", download_image_metadata(image_urls))

    print("Done.")


if __name__ == "__main__":
    main()
