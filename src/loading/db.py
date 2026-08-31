"""Neo4j helpers shared by the three schema loaders."""

import json

from neo4j import GraphDatabase

from config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER, PROCESSED_DIR


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def load_dataset() -> dict:
    return json.loads((PROCESSED_DIR / "dataset.json").read_text(encoding="utf-8"))


def wipe(session) -> None:
    """Drop all data, constraints and indexes (each version gets a clean DB)."""
    session.run("MATCH (n) DETACH DELETE n")
    for row in session.run("SHOW CONSTRAINTS YIELD name").data():
        session.run(f"DROP CONSTRAINT {row['name']}")
    for row in session.run("SHOW INDEXES YIELD name, type WHERE type <> 'LOOKUP'").data():
        session.run(f"DROP INDEX {row['name']}")


def clean(props: dict) -> dict:
    """Strip None values (Neo4j properties cannot be null)."""
    return {k: v for k, v in props.items() if v is not None}


# Fixed record sizes (bytes) of the Neo4j standard store format: the basis
# of the logical volume estimate. Long values (strings/arrays) spill over to
# dynamic stores, so this is a lower bound that excludes indexes as well.
NODE_RECORD_B, REL_RECORD_B, PROP_RECORD_B = 15, 34, 41


def storage_stats(session) -> dict:
    """Volume metrics: record counts and estimated store size."""
    nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
    rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    node_props = session.run(
        "MATCH (n) RETURN sum(size(keys(n))) AS c").single()["c"]
    rel_props = session.run(
        "MATCH ()-[r]->() RETURN sum(size(keys(r))) AS c").single()["c"]
    props = (node_props or 0) + (rel_props or 0)
    estimate = nodes * NODE_RECORD_B + rels * REL_RECORD_B + props * PROP_RECORD_B
    return {"nodes": nodes, "relationships": rels, "properties": props,
            "record_store_estimate_kb": round(estimate / 1024)}


# Note: the on-disk store size is deliberately NOT measured. Neo4j store
# files never shrink after deletes (deleted records are only reused), so in
# a wipe-and-reload cycle every version would inherit the high-water mark of
# the largest one; a fair per-version disk measurement would require a fresh
# store for each load. The record-size estimate above is used instead.
