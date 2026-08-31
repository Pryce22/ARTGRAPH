"""Step 1 — Resolve the curated artist names to Wikidata QIDs.

For each name in data/seed/artist_names.txt the Wikidata search API returns
candidate entities; a single SPARQL query then keeps only candidates whose
occupation (P106) is painter, so homonyms are discarded. The result is a
human-checkable seed file with QID, label and description per artist.

Run:  python -m src.extraction.resolve_artists
"""

import json
import time

from config import SEED_DIR, WIKIDATA_API
from src.extraction.sparql import api_get, qid, sparql_select

PAINTER = "Q1028181"  # occupation: painter


def search_candidates(name: str) -> list[dict]:
    """Top 5 Wikidata entities matching `name` (label search, English)."""
    data = api_get(
        WIKIDATA_API,
        {
            "action": "wbsearchentities",
            "search": name,
            "language": "en",
            "type": "item",
            "limit": 5,
        },
    )
    return data.get("search", [])


def painter_qids(candidate_qids: set[str]) -> set[str]:
    """Subset of `candidate_qids` having occupation painter."""
    values = " ".join(f"wd:{q}" for q in candidate_qids)
    rows = sparql_select(
        f"SELECT ?a WHERE {{ VALUES ?a {{ {values} }} ?a wdt:P106 wd:{PAINTER} . }}"
    )
    return {qid(r["a"]) for r in rows}


def main() -> None:
    names = (SEED_DIR / "artist_names.txt").read_text(encoding="utf-8").split("\n")
    names = [n.strip() for n in names if n.strip()]

    candidates = {}
    for name in names:  # throttled: the anonymous Action API rate limit is low
        candidates[name] = search_candidates(name)
        time.sleep(1.0)
    all_qids = {c["id"] for cands in candidates.values() for c in cands}
    painters = painter_qids(all_qids)

    resolved, missing = [], []
    for name, cands in candidates.items():
        match = next((c for c in cands if c["id"] in painters), None)
        if match is None:
            missing.append(name)
            continue
        resolved.append(
            {
                "qid": match["id"],
                "name": name,
                "label": match.get("label", name),
                "description": match.get("description", ""),
            }
        )

    out = SEED_DIR / "artists.json"
    out.write_text(
        json.dumps(resolved, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Resolved {len(resolved)}/{len(names)} artists -> {out}")
    if missing:
        print("NOT resolved (fix manually):", missing)


if __name__ == "__main__":
    main()
