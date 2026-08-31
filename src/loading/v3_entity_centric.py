"""V3 — entity-centric normalized schema (the model selected in the report).

Every domain entity becomes a node with its own label and scalar properties;
every traversed Wikidata property becomes a typed relationship.
"""

from src.loading.common import ENTITY_LABELS, RELATION_ENDPOINTS
from src.loading.db import clean


def load(session, dataset: dict) -> None:
    # Uniqueness constraints plus lookup indexes on the human-readable key
    for label in ENTITY_LABELS.values():
        session.run(
            f"CREATE CONSTRAINT {label.lower()}_qid IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.qid IS UNIQUE"
        )
        key = "title" if label == "Artwork" else "name"
        session.run(
            f"CREATE INDEX {label.lower()}_{key} IF NOT EXISTS "
            f"FOR (n:{label}) ON (n.{key})"
        )

    # Nodes: one batched UNWIND per entity group
    for group, label in ENTITY_LABELS.items():
        rows = [clean(e) for e in dataset["entities"][group]]
        session.run(
            f"UNWIND $rows AS row CREATE (n:{label}) SET n = row", rows=rows
        )

    # Relationships: one batched UNWIND per relation type
    for rtype, (src, tgt) in RELATION_ENDPOINTS.items():
        pairs = [
            [r["source"], r["target"]]
            for r in dataset["relations"]
            if r["type"] == rtype
        ]
        session.run(
            f"UNWIND $pairs AS p "
            f"MATCH (s:{src} {{qid: p[0]}}), (t:{tgt} {{qid: p[1]}}) "
            f"CREATE (s)-[:{rtype}]->(t)",
            pairs=pairs,
        )
