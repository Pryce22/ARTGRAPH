"""Benchmark the three schema versions on the full 35-query workload.

Fairness contract enforced here:
  - every version must implement every query (the run refuses otherwise);
  - the three implementations of each query must return identical canonical
    result sets (rows as multisets, lists sorted, floats rounded) — verified
    on every run and reported in results/equivalence.csv;
  - every version is measured on the same freshly loaded data, after index
    population, with one discarded warm-up and `--runs` timed executions.

Reported metrics (standard practice for database benchmarking):
    latency        mean / median (p50) / 95th percentile (p95) / min, in ms
    database hits  Neo4j's storage-engine work units, from PROFILE plans
    rows           result cardinality
    volume         node/relationship/property counts, store estimate, load time
    summary        per-version totals and geometric means of the per-query
                   ratios to the best version (SPEC-style relative performance)

Outputs: results/storage_metrics.csv, results/query_metrics.csv,
         results/equivalence.csv, results/summary.json

Usage:
    python run_benchmark.py                        # all versions, 20 runs
    python run_benchmark.py --equivalence-only     # fast correctness check
"""

import argparse
import csv
import json
import math
import statistics
import time

from config import RESULTS_DIR
from load_graph import load_version
from src.loading.db import get_driver
from src.queries import v1, v2, v3
from src.queries.workload import PARAMS, SPECS

QUERIES = {"v1": v1.QUERIES, "v2": v2.QUERIES, "v3": v3.QUERIES}


def canonical(rows: list[dict]) -> list[str]:
    """Order-independent canonical form of a result set.

    Lists are sorted (their order is not part of any query's semantics) and
    floats rounded, so that equal result sets compare equal across versions.
    """
    def canon(value):
        if isinstance(value, float):
            return round(value, 4)
        if isinstance(value, list):
            return sorted((canon(x) for x in value), key=json.dumps)
        return value

    return sorted(
        json.dumps({k: canon(v) for k, v in row.items()}, sort_keys=True)
        for row in rows
    )


def profile_db_hits(plan) -> int:
    """Recursively sum DbHits over a PROFILE plan tree."""
    hits = plan.get("args", {}).get("DbHits", 0)
    return hits + sum(profile_db_hits(c) for c in plan.get("children", []))


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(p * len(ordered)) - 1)]


def run_query(session, cypher: str, runs: int) -> tuple[dict, list[str]]:
    """Return (metrics, canonical result). The warm-up run feeds the
    equivalence check; only the subsequent `runs` executions are timed."""
    data = session.run(cypher, **PARAMS).data()
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        session.run(cypher, **PARAMS).consume()
        times.append((time.perf_counter() - start) * 1000)
    summary = session.run("PROFILE " + cypher, **PARAMS).consume()
    metrics = {
        "rows": len(data),
        "avg_ms": round(statistics.mean(times), 2),
        "p50_ms": round(statistics.median(times), 2),
        "p95_ms": round(percentile(times, 0.95), 2),
        "min_ms": round(min(times), 2),
        "db_hits": profile_db_hits(summary.profile or {}),
    }
    return metrics, canonical(data)


def geomean(values) -> float:
    return round(statistics.geometric_mean(values), 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versions", nargs="+", default=["v1", "v2", "v3"],
                        choices=QUERIES)
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--equivalence-only", action="store_true",
                        help="single execution per query, correctness check only")
    args = parser.parse_args()
    runs = 1 if args.equivalence_only else args.runs

    # A schema ranking is valid only when every version implements the
    # complete workload: refuse to compare a favourable subset.
    for v in args.versions:
        missing = sorted(set(SPECS) - set(QUERIES[v]))
        if missing:
            raise SystemExit(f"{v} does not implement {missing}; benchmark refused")

    driver = get_driver()
    storage_rows, query_rows = [], []
    results: dict[tuple[str, str], list[str]] = {}
    for version in args.versions:
        print(f"=== {version} ===")
        stats = load_version(version, driver)
        storage_rows.append({"version": version, **stats})
        print(f"  loaded: {stats}")

        with driver.session() as session:
            for query_id in SPECS:
                metrics, results[(version, query_id)] = run_query(
                    session, QUERIES[version][query_id], runs)
                qclass, description = SPECS[query_id]
                query_rows.append({
                    "version": version, "query": query_id, "class": qclass,
                    **metrics, "description": description,
                })
                flag = "  [EMPTY]" if metrics["rows"] == 0 else ""
                print(f"  {query_id} p50 {metrics['p50_ms']:>7.2f} ms  "
                      f"p95 {metrics['p95_ms']:>7.2f} ms  "
                      f"{metrics['db_hits']:>8} hits {metrics['rows']:>5} rows{flag}")
    driver.close()

    # --- Result-set equivalence across versions ------------------------------
    reference = args.versions[0]
    equivalence_rows, mismatches = [], []
    for query_id in SPECS:
        same = all(results[(v, query_id)] == results[(reference, query_id)]
                   for v in args.versions)
        equivalence_rows.append({
            "query": query_id,
            **{f"rows_{v}": len(results[(v, query_id)]) for v in args.versions},
            "equivalent": same,
        })
        if not same:
            mismatches.append(query_id)

    RESULTS_DIR.mkdir(exist_ok=True)
    if mismatches:
        for query_id in mismatches:
            detail = {v: results[(v, query_id)] for v in args.versions}
            path = RESULTS_DIR / f"mismatch_{query_id}.json"
            path.write_text(json.dumps(detail, indent=1, ensure_ascii=False),
                            encoding="utf-8")
        print(f"NOT EQUIVALENT: {mismatches} (details in results/mismatch_*.json)")
    else:
        print(f"result-set equivalence: {len(SPECS)}/{len(SPECS)} queries")

    # --- Cross-version summary over the full workload ------------------------
    lat = {(r["version"], r["query"]): r["p50_ms"] for r in query_rows}
    hits = {(r["version"], r["query"]): max(r["db_hits"], 1) for r in query_rows}
    best_lat = {q: min(lat[(v, q)] for v in args.versions) for q in SPECS}
    best_hits = {q: min(hits[(v, q)] for v in args.versions) for q in SPECS}
    summary = {}
    for v in args.versions:
        summary[v] = {
            **next(r for r in storage_rows if r["version"] == v),
            "equivalent_queries":
                f"{sum(r['equivalent'] for r in equivalence_rows)}/{len(SPECS)}",
            "sum_p50_ms": round(sum(lat[(v, q)] for q in SPECS), 1),
            "sum_db_hits": sum(hits[(v, q)] for q in SPECS),
            "latency_ratio_geomean": geomean(
                lat[(v, q)] / best_lat[q] for q in SPECS),
            "db_hits_ratio_geomean": geomean(
                hits[(v, q)] / best_hits[q] for q in SPECS),
        }

    for name, rows in (("storage_metrics", storage_rows),
                       ("query_metrics", query_rows),
                       ("equivalence", equivalence_rows)):
        path = RESULTS_DIR / f"{name}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"saved {path}")
    summary_path = RESULTS_DIR / "summary.json"
    summary_path.write_text(json.dumps(
        {"runs_per_query": runs, "queries": len(SPECS), "versions": summary},
        indent=2), encoding="utf-8")
    print(f"saved {summary_path}")
    for v, row in summary.items():
        print(f"{v}: {row}")


if __name__ == "__main__":
    main()
