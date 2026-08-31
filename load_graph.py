"""Load one schema version into Neo4j (wiping whatever was loaded before).

Usage:
    python load_graph.py --version v3
    python load_graph.py --version v1 v2 v3   # load sequentially (last wins)
"""

import argparse
import time

from src.loading import v1_rdf_faithful, v2_denormalized, v3_entity_centric
from src.loading.db import get_driver, load_dataset, storage_stats, wipe

LOADERS = {
    "v1": v1_rdf_faithful.load,
    "v2": v2_denormalized.load,
    "v3": v3_entity_centric.load,
}


def load_version(version: str, driver=None, dataset=None) -> dict:
    """Wipe the database, load `version`, return its storage stats."""
    driver = driver or get_driver()
    dataset = dataset or load_dataset()
    with driver.session() as session:
        wipe(session)
        start = time.perf_counter()
        LOADERS[version](session, dataset)
        session.run("CALL db.awaitIndexes()")  # indexes populate asynchronously
        elapsed = time.perf_counter() - start
        stats = storage_stats(session)
    stats["load_seconds"] = round(elapsed, 2)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", nargs="+", choices=LOADERS, required=True)
    args = parser.parse_args()

    driver, dataset = get_driver(), load_dataset()
    for version in args.version:
        stats = load_version(version, driver, dataset)
        print(f"{version}: {stats}")
    driver.close()


if __name__ == "__main__":
    main()
