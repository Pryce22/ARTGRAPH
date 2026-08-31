"""Step 3 — Transform raw downloads into a normalized, schema-agnostic dataset.

Output: data/processed/dataset.json with two top-level keys:

  entities   {artists, artworks, movements, collections, places, countries,
              materials, genres, subjects, patrons} — one list per node type,
              each entity carrying its scalar properties (the LPG loaders map
              these to node labels/properties)
  relations  [{type, source, target}] — the 14 typed relations of the model
              (the LPG loaders map these to edges or statement nodes)

Run:  python -m src.extraction.transform
"""

import json
from collections import Counter

from config import PROCESSED_DIR, RAW_DIR, SEED_DIR
from src.extraction.sparql import qid

WD = "http://www.wikidata.org/entity/"

# Wikidata property -> (relation type, term entity type of the target)
ARTWORK_PROPS = {
    "P195": ("IN_COLLECTION", None),
    "P186": ("USES_MATERIAL", "materials"),
    "P136": ("HAS_GENRE", "genres"),
    "P180": ("DEPICTS", "subjects"),
    "P135": ("CLASSIFIED_IN", "movements"),
    # P88 is inverted: the LPG edge goes (:Patron)-[:COMMISSIONED]->(:Artwork)
    "P88": ("COMMISSIONED", "patrons"),
}


def load(name: str) -> list[dict]:
    return json.loads((RAW_DIR / f"{name}.json").read_text(encoding="utf-8"))


def date(value: str | None) -> str | None:
    """'1840-11-14T00:00:00Z' -> '1840-11-14'."""
    return value[:10] if value else None


def main() -> None:
    seed_qids = {a["qid"] for a in json.loads(
        (SEED_DIR / "artists.json").read_text(encoding="utf-8"))}
    raw = {name: load(name) for name in (
        "artists", "artworks", "artist_links", "artwork_links",
        "collections", "places", "countries", "terms", "image_metadata")}

    terms = {qid(r["term"]): r for r in raw["terms"]}
    images = {r["work"]: r for r in raw["image_metadata"] if r.get("work")}
    relations: list[dict] = []

    def rel(rtype: str, source: str, target: str) -> None:
        relations.append({"type": rtype, "source": source, "target": target})

    # --- Place normalization: climb P131 parents up to the first city-level
    # entity (see download_places), so that e.g. 'Gare d'Orsay' becomes
    # 'Paris' and city-level queries behave consistently.
    place_rows = {qid(r["place"]): r for r in raw["places"]}

    def settle(place: str) -> str:
        current = place
        for _ in range(5):
            row = place_rows.get(current)
            if row is None or row["isCity"] == "true" or not row.get("parent"):
                return current if row else place
            current = qid(row["parent"])
        return place

    # --- Artists (seed + referenced humans) --------------------------------
    artists = []
    for r in raw["artists"]:
        a = qid(r["artist"])
        artists.append({
            "qid": a,
            "name": r.get("artistLabel", a),
            "description": r.get("artistDescription"),
            "birth_date": date(r.get("birthDate")),
            "death_date": date(r.get("deathDate")),
            "ulan_id": r.get("ulanId"),
            "wikipedia_url": r.get("article"),
            "wikidata_url": WD + a,
            "is_seed": a in seed_qids,
        })
        if r.get("birthPlace"):
            rel("BORN_IN", a, settle(qid(r["birthPlace"])))
        if r.get("deathPlace"):
            rel("DIED_IN", a, settle(qid(r["deathPlace"])))
    artist_qids = {a["qid"] for a in artists}

    # --- Artist links: movement / influence / apprenticeship ---------------
    term_usage: dict[str, set[str]] = {t: set() for t in
                                       ("movements", "materials", "genres",
                                        "subjects", "patrons")}
    for r in raw["artist_links"]:
        a, t, prop = qid(r["artist"]), qid(r["target"]), qid(r["prop"])
        if prop == "P135":
            rel("ASSOCIATED_WITH", a, t)
            term_usage["movements"].add(t)
        elif t in artist_qids:  # P737 / P1066, humans already fetched as artists
            rel("INFLUENCED_BY" if prop == "P737" else "STUDENT_OF", a, t)

    # --- Artworks -----------------------------------------------------------
    artworks = []
    for r in raw["artworks"]:
        w = qid(r["work"])
        img = images.get(w, {})
        artworks.append({
            "qid": w,
            "title": r.get("workLabel", w),
            "inception_year": int(r["year"]) if r.get("year") else None,
            "height_cm": round(float(r["heightM"]) * 100, 1) if r.get("heightM") else None,
            "width_cm": round(float(r["widthM"]) * 100, 1) if r.get("widthM") else None,
            "sitelinks": int(r["sitelinks"]),
            "wikipedia_url": r.get("article"),
            "wikidata_url": WD + w,
            # metadata of the P18 image file, from Wikimedia Commons
            "image_url": img.get("url") or r.get("image"),
            "image_width_px": img.get("width_px"),
            "image_height_px": img.get("height_px"),
            "image_mime": img.get("mime"),
            "image_license": img.get("license"),
        })
        rel("CREATED", qid(r["creator"]), w)
    artwork_qids = {w["qid"] for w in artworks}

    # --- Artwork links ------------------------------------------------------
    collection_qids = set()
    for r in raw["artwork_links"]:
        w, t, prop = qid(r["work"]), qid(r["target"]), qid(r["prop"])
        if w not in artwork_qids:
            continue
        rtype, term_type = ARTWORK_PROPS[prop]
        if prop == "P195":
            rel(rtype, w, t)
            collection_qids.add(t)
        elif prop == "P88":
            rel(rtype, t, w)  # inverted: patron -> artwork
            term_usage["patrons"].add(t)
        else:
            rel(rtype, w, t)
            term_usage[term_type].add(t)

    # --- Term entities (movements, materials, genres, subjects, patrons) ---
    def term_entities(term_type: str) -> list[dict]:
        out = []
        for t in sorted(term_usage[term_type]):
            info = terms.get(t, {})
            out.append({
                "qid": t,
                "name": info.get("termLabel", t),
                "description": info.get("termDescription"),
                "aat_id": info.get("aatId"),
                "wikidata_url": WD + t,
            })
        return out

    # --- Collections, places, countries -------------------------------------
    collections = []
    for r in raw["collections"]:
        c = qid(r["coll"])
        if c not in collection_qids:
            continue
        collections.append({"qid": c, "name": r.get("collLabel", c),
                            "wikidata_url": WD + c})
        if r.get("place"):
            rel("LOCATED_IN", c, settle(qid(r["place"])))

    used_places = {r["target"] for r in relations
                   if r["type"] in ("LOCATED_IN", "BORN_IN", "DIED_IN")}
    places = []
    for r in raw["places"]:
        p = qid(r["place"])
        if p not in used_places:  # skip intermediate admin entities
            continue
        places.append({
            "qid": p,
            "name": r.get("placeLabel", p),
            "coordinates": r.get("coordinates"),
            "tgn_id": r.get("tgnId"),
            "wikidata_url": WD + p,
        })
        # a few museums resolve to country level (e.g. P276 = Sweden):
        # skip the degenerate self country link in that case
        if r.get("country") and qid(r["country"]) != p:
            rel("IN_COUNTRY", p, qid(r["country"]))

    countries = [{"qid": qid(r["country"]), "name": r.get("countryLabel"),
                  "iso_code": r.get("isoCode"),
                  "wikidata_url": WD + qid(r["country"])}
                 for r in raw["countries"]]

    # --- Prune dangling relations and dedupe --------------------------------
    entities = {
        "artists": artists, "artworks": artworks,
        "movements": term_entities("movements"),
        "collections": collections, "places": places, "countries": countries,
        "materials": term_entities("materials"),
        "genres": term_entities("genres"),
        "subjects": term_entities("subjects"),
        "patrons": term_entities("patrons"),
    }
    known = {e["qid"] for group in entities.values() for e in group}
    unique = {(r["type"], r["source"], r["target"]) for r in relations}
    relations = [{"type": t, "source": s, "target": o}
                 for t, s, o in sorted(unique)
                 if s in known and o in known]

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / "dataset.json"
    out.write_text(json.dumps({"entities": entities, "relations": relations},
                              indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"Entities -> {out}")
    for name, group in entities.items():
        print(f"  {name:<12} {len(group):>5}")
    print(f"Relations   {len(relations):>5}")
    for rtype, n in Counter(r["type"] for r in relations).most_common():
        print(f"  {rtype:<16} {n:>5}")


if __name__ == "__main__":
    main()
