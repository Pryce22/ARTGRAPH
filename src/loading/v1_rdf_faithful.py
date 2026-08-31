"""V1 — RDF-faithful schema with statement reification.

Every entity becomes a generic (:Entity {qid, name, etype}) node; every other
scalar property and every relation is reified into a (:Statement {pid}) node:

    literal   (:Entity)-[:HAS_STATEMENT]->(:Statement {pid, value})
    entity    (:Entity)-[:HAS_STATEMENT]->(:Statement {pid})-[:VALUE]->(:Entity)

Statements attach to the original RDF subject (e.g. the subject of P170
"creator" is the artwork, not the artist). The entity types are kept as a
list property `etypes`, playing the role of rdf:type, so that queries can
still filter by kind of entity without an extra statement hop. As in RDF,
each QID is a single resource: an artist who is also a depicted subject is
one node with etypes ['Artist', 'Subject'].
"""

from src.loading.common import ENTITY_LABELS, NODE_KEYS, PROPERTY_PIDS, RELATION_RDF
from src.loading.db import clean


def load(session, dataset: dict) -> None:
    session.run(
        "CREATE CONSTRAINT entity_qid IF NOT EXISTS "
        "FOR (n:Entity) REQUIRE n.qid IS UNIQUE"
    )
    session.run(
        "CREATE INDEX statement_pid IF NOT EXISTS FOR (s:Statement) ON (s.pid)"
    )
    session.run(
        "CREATE INDEX entity_name IF NOT EXISTS FOR (n:Entity) ON (n.name)"
    )

    # Entity nodes (identity fields only) + literal statements. The same QID
    # may play several roles (e.g. artist and depicted subject): it is merged
    # into a single resource node, and duplicated literals are deduplicated.
    nodes: dict[str, dict] = {}
    literals: set[tuple] = set()
    for group, etype in ENTITY_LABELS.items():
        for e in dataset["entities"][group]:
            e = clean(e)
            node = nodes.setdefault(e["qid"], {
                "qid": e["qid"],
                "name": e.get("name") or e.get("title"),
                "etypes": [],
                **({"is_seed": e["is_seed"]} if "is_seed" in e else {}),
            })
            node["etypes"].append(etype)
            literals.update(
                (e["qid"], PROPERTY_PIDS.get(k, k), v)
                for k, v in e.items()
                if k not in NODE_KEYS
            )
    session.run(
        "UNWIND $rows AS row CREATE (n:Entity) SET n = row",
        rows=list(nodes.values()),
    )
    session.run(
        "UNWIND $rows AS row "
        "MATCH (e:Entity {qid: row[0]}) "
        "CREATE (e)-[:HAS_STATEMENT]->(:Statement {pid: row[1], value: row[2]})",
        rows=[list(t) for t in literals],
    )

    # Relation statements, reified in the original RDF direction
    for rtype, (pid, rdf_subject) in RELATION_RDF.items():
        triples = [
            {
                "subject": r["source"] if rdf_subject == "source" else r["target"],
                "object": r["target"] if rdf_subject == "source" else r["source"],
                "pid": pid,
            }
            for r in dataset["relations"]
            if r["type"] == rtype
        ]
        session.run(
            "UNWIND $rows AS row "
            "MATCH (s:Entity {qid: row.subject}), (o:Entity {qid: row.object}) "
            "CREATE (s)-[:HAS_STATEMENT]->(:Statement {pid: row.pid})-[:VALUE]->(o)",
            rows=triples,
        )
