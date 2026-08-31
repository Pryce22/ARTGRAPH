"""Step 4 — Build the text corpus for the RAG vs GraphRAG experiments.

For every artist and artwork that has an English Wikipedia article, the lead
section (intro) is downloaded as plain text. Each document keeps the QID of
the entity it describes, so retrieval results can be evaluated against the
knowledge graph (classic RAG retrieves from this corpus; GraphRAG traverses
the Neo4j graph; both can be scored on the same entity-grounded questions).

Output: data/corpus/documents.jsonl (one JSON document per line)

Run:  python -m src.extraction.build_corpus
"""

import json
import time
from urllib.parse import unquote

from config import CORPUS_DIR, PROCESSED_DIR, WIKIPEDIA_API
from src.extraction.sparql import api_get, chunked


def wiki_title(article_url: str) -> str:
    """'https://en.wikipedia.org/wiki/Claude_Monet' -> 'Claude Monet'."""
    return unquote(article_url.rsplit("/wiki/", 1)[-1]).replace("_", " ")


def fetch_intros(titles: list[str]) -> dict[str, str]:
    """title -> plain-text lead section (batched, 20 titles per request)."""
    intros = {}
    for chunk in chunked(titles, 20):
        data = api_get(
            WIKIPEDIA_API,
            {
                "action": "query",
                "titles": "|".join(chunk),
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "exlimit": "max",
                "redirects": 1,
            },
        )
        query = data.get("query", {})
        # map normalized/redirected titles back to the requested ones
        back = {}
        for mapping in ("normalized", "redirects"):
            for m in query.get(mapping, []):
                back[m["to"]] = back.get(m["from"], m["from"])
        for page in query.get("pages", {}).values():
            requested = back.get(page["title"], page["title"])
            if page.get("extract"):
                intros[requested] = page["extract"].strip()
        time.sleep(0.5)
    return intros


def main() -> None:
    dataset = json.loads(
        (PROCESSED_DIR / "dataset.json").read_text(encoding="utf-8"))

    targets = []  # (entity_type, entity) with a Wikipedia article
    for entity_type in ("artists", "artworks"):
        for e in dataset["entities"][entity_type]:
            if e.get("wikipedia_url"):
                targets.append((entity_type, e))

    intros = fetch_intros([wiki_title(e["wikipedia_url"]) for _, e in targets])

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    out = CORPUS_DIR / "documents.jsonl"
    written = 0
    with out.open("w", encoding="utf-8") as fh:
        for entity_type, e in targets:
            title = wiki_title(e["wikipedia_url"])
            text = intros.get(title)
            if not text:
                continue
            fh.write(json.dumps({
                "doc_id": f"wiki-{e['qid']}",
                "qid": e["qid"],
                "entity_type": entity_type.rstrip("s"),  # artist / artwork
                "title": title,
                "text": text,
                "source_url": e["wikipedia_url"],
            }, ensure_ascii=False) + "\n")
            written += 1

    print(f"Corpus: {written}/{len(targets)} documents -> {out}")


if __name__ == "__main__":
    main()
