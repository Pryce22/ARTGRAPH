"""V2 — compact denormalized schema (aggregate-oriented, lossless).

Only artists and artworks become nodes, in the style of an aggregate/document
store: every other dimension is embedded in the node that uses it. Sets with
no internal structure (materials, genres, subjects, movements, patrons)
become list properties. The location chain has internal structure (which
collection sits in which city and country), so it is embedded as one aligned
composite tuple per collection — `location_facts`, encoded as
'collection|||city|||country|||coordinates' strings, the property-graph
equivalent of an embedded subdocument. This keeps the denormalization
lossless with respect to the workload, so every query remains answerable
exactly. Relations among the surviving nodes (CREATED, INFLUENCED_BY,
STUDENT_OF) are kept as edges because they cannot be flattened into scalars.
"""

from collections import defaultdict

from src.loading.db import clean


def load(session, dataset: dict) -> None:
    ent = dataset["entities"]
    name_of = {
        e["qid"]: e.get("name") or e.get("title")
        for group in ent.values()
        for e in group
    }

    # Index every relation once: source qid -> {type -> [target qids]}
    out_edges: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for r in dataset["relations"]:
        out_edges[r["source"]][r["type"]].append(r["target"])
    patron_of = defaultdict(list)  # artwork qid -> patron names
    for r in dataset["relations"]:
        if r["type"] == "COMMISSIONED":
            patron_of[r["target"]].append(name_of[r["source"]])

    def names(qid: str, rtype: str) -> list[str]:
        return sorted(name_of[t] for t in out_edges[qid][rtype])

    def first(qid: str, rtype: str) -> str | None:
        targets = out_edges[qid][rtype]
        return name_of[targets[0]] if targets else None

    # --- Artist nodes: places and movements flattened to strings -----------
    def place_country(qid: str, rtype: str) -> str | None:
        for place in out_edges[qid][rtype]:
            for country in out_edges[place]["IN_COUNTRY"]:
                return name_of[country]
        return None

    artists = []
    for a in ent["artists"]:
        artists.append(clean({
            **a,
            "birth_place": first(a["qid"], "BORN_IN"),
            "birth_country": place_country(a["qid"], "BORN_IN"),
            "death_place": first(a["qid"], "DIED_IN"),
            "death_country": place_country(a["qid"], "DIED_IN"),
            "movements": names(a["qid"], "ASSOCIATED_WITH") or None,
        }))

    # --- Artwork nodes: lossless location facts and classifications --------
    # One aligned tuple per collection of the work; fields are empty strings
    # when the source chain is incomplete, so that a collection without a
    # known city still keeps its name (mirroring V3's OPTIONAL traversals).
    SEP = "|||"
    coordinates = {p["qid"]: p.get("coordinates") or "" for p in ent["places"]}
    artworks = []
    for w in ent["artworks"]:
        location_facts = []
        for coll in out_edges[w["qid"]]["IN_COLLECTION"]:
            places = out_edges[coll]["LOCATED_IN"]
            place = places[0] if places else None
            ks = out_edges[place]["IN_COUNTRY"] if place else []
            location_facts.append(SEP.join((
                name_of[coll],
                name_of[place] if place else "",
                name_of[ks[0]] if ks else "",
                coordinates[place] if place else "",
            )))
        artworks.append(clean({
            **w,
            "location_facts": sorted(location_facts) or None,
            "materials": names(w["qid"], "USES_MATERIAL") or None,
            "genres": names(w["qid"], "HAS_GENRE") or None,
            "subjects": names(w["qid"], "DEPICTS") or None,
            "movements": names(w["qid"], "CLASSIFIED_IN") or None,
            "patrons": sorted(patron_of[w["qid"]]) or None,
        }))

    for label, key, rows in (("Artist", "name", artists),
                             ("Artwork", "title", artworks)):
        session.run(
            f"CREATE CONSTRAINT {label.lower()}_qid IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.qid IS UNIQUE"
        )
        session.run(
            f"CREATE INDEX {label.lower()}_{key} IF NOT EXISTS "
            f"FOR (n:{label}) ON (n.{key})"
        )
        session.run(f"UNWIND $rows AS row CREATE (n:{label}) SET n = row", rows=rows)

    # --- Edges that survive denormalization --------------------------------
    for rtype, tgt in (("CREATED", "Artwork"), ("INFLUENCED_BY", "Artist"),
                       ("STUDENT_OF", "Artist")):
        pairs = [[r["source"], r["target"]] for r in dataset["relations"]
                 if r["type"] == rtype]
        session.run(
            f"UNWIND $pairs AS p "
            f"MATCH (s:Artist {{qid: p[0]}}), (t:{tgt} {{qid: p[1]}}) "
            f"CREATE (s)-[:{rtype}]->(t)",
            pairs=pairs,
        )




