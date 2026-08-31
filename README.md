# ArtGraph - Impressionism Knowledge Graph on Neo4j

ArtGraph builds an Impressionism knowledge graph from **Wikidata**, compares
RDF and **Neo4j** data models on a 35-query workload, and benchmarks seven RAG
and GraphRAG pipelines across Gemma 4 models from 2B to 26B parameters.

## Repository layout

```
├── config.py                  # paths, endpoints, Neo4j connection
├── docker-compose.yml         # Neo4j 5 Community (user neo4j / artgraph)
├── load_graph.py              # CLI: load one schema version into Neo4j
├── run_benchmark.py           # CLI: workload benchmark + equivalence check
├── data/
│   ├── seed/                  # curated artist names + resolved QIDs
│   ├── raw/                   # raw SPARQL/API downloads (reproducible)
│   ├── processed/dataset.json # normalized schema-agnostic dataset
│   └── corpus/documents.jsonl # Wikipedia intros for the RAG experiments
├── src/
│   ├── extraction/
│   │   ├── sparql.py          # WDQS / Wikimedia API client
│   │   ├── resolve_artists.py # step 1: names -> QIDs (painter-checked)
│   │   ├── download.py        # step 2: SPARQL + Commons downloads
│   │   ├── transform.py       # step 3: raw -> normalized dataset
│   │   └── build_corpus.py    # step 4: Wikipedia text corpus for RAG
│   ├── loading/
│   │   ├── v1_rdf_faithful.py # V1: statement-node reification
│   │   ├── v2_denormalized.py # V2: artists+artworks only, lossless embedding
│   │   └── v3_entity_centric.py # V3: typed nodes and relations (selected)
│   └── queries/
│       ├── workload.py        # 35 query specs and grounded parameters
│       └── v1.py / v2.py / v3.py  # full workload per schema version
└── results/                   # benchmark output (CSV + summary.json)
```

## Quick start

```bash
uv sync                            # install dependencies (Python >= 3.12)
docker compose up -d               # start Neo4j (browser on :7474)

# Extraction pipeline (only needed to regenerate data/)
uv run python -m src.extraction.resolve_artists
uv run python -m src.extraction.download
uv run python -m src.extraction.transform
uv run python -m src.extraction.build_corpus

# Load a schema version (wipes the DB first)
uv run python load_graph.py --version v3

# Fast correctness check / full benchmark
uv run python run_benchmark.py --equivalence-only
uv run python run_benchmark.py
```

## Fair-comparison contract

The benchmark is designed the way database comparisons are done properly:

- all three versions are loaded from the **same logical dataset**;
- **every version implements all 35 queries** (the benchmark refuses to run
  otherwise — no cherry-picked subsets);
- the three implementations of each query must return **identical canonical
  result sets**, verified automatically on every run (35/35 pass);
- each version gets fresh data, populated indexes, one discarded warm-up and
  20 timed executions per query; metrics come from the client timer (p50/p95)
  and from Neo4j itself (PROFILE database hits, record counts).

V2's denormalization is deliberately **lossless**: set-valued dimensions are
list properties, and the location chain is embedded as aligned
`collection|||city|||country|||coordinates` tuples (the property-graph
analogue of a document-store subdocument), so every query stays answerable
exactly.

## Data grounding

Everything in the graph is traceable to Wikidata:

- artist QIDs are resolved via the Wikidata search API and validated against
  occupation *painter* (P106);
- artworks are paintings (P31=Q3305213) with an image (P18) created by a seed
  artist, ranked by sitelink count and capped at 12 per artist;
- humans referenced by *influenced by* (P737) / *student of* (P1066) extend
  the artist set (50 seed + ~70 referenced);
- the P18 image file's own metadata (pixel size, MIME type, license) is
  fetched from Wikimedia Commons;
- museum/birth/death places are normalized to city level by climbing the
  P131 administrative chain (e.g. *Gare d'Orsay* → *Paris*).

## Benchmark results (summary)

| Version | Nodes | Rels | Props | Store est. | Σ p50 (35 q) | Latency ratio (geo) | DB-hits ratio (geo) |
|---------|------:|-----:|------:|-----------:|-------------:|--------------------:|--------------------:|
| V1 RDF-faithful | 18,721 | 23,043 | 33,240 | 2,370 KiB | 460.8 ms | 3.57 | 54.9 |
| V2 denormalized | 695 | 744 | 10,949 | 473 KiB | 146.4 ms | 1.34 | 1.67 |
| V3 entity-centric | 2,222 | 6,478 | 14,762 | 839 KiB | **115.2 ms** | **1.04** | 3.18 |

All 35 queries return identical results in the three versions. V1 is
dominated (reification doubles every hop). V2 is the smallest and needs the
fewest storage accesses, but pays in latency (list scans and tuple splitting
are CPU work that db hits don't count) and in query readability. V3 is the
fastest overall, the most natural to query, and the only schema where
free-form graph exploration (e.g. movement-mediated paths: 154 vs 35
connections between two sample artists) is possible — it is the selected
model. Full numbers in `results/`, full discussion in the LaTeX report.

## RAG / GraphRAG groundwork

`data/corpus/documents.jsonl` holds one Wikipedia lead section per artist and
artwork, each tagged with the QID of the entity it describes. The planned
evaluation: answer entity-grounded multi-hop questions (derived from the
query workload) with (a) classic RAG over the corpus and (b) GraphRAG over
the V3 Neo4j graph, and compare retrieval quality on the same gold answers
computed with Cypher.
