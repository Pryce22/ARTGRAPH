"""Central configuration: paths, external endpoints, Neo4j connection.

Every script is meant to be run from the repository root, e.g.:
    python -m src.extraction.download
"""

import os
from pathlib import Path

# --- Paths -----------------------------------------------------------------
ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
SEED_DIR = DATA_DIR / "seed"           # curated input (artist names)
RAW_DIR = DATA_DIR / "raw"             # raw API/SPARQL downloads
PROCESSED_DIR = DATA_DIR / "processed" # normalized, schema-agnostic dataset
CORPUS_DIR = DATA_DIR / "corpus"       # text corpus for the RAG experiments
RESULTS_DIR = ROOT / "results"         # benchmark metrics

# --- External data sources ---------------------------------------------------
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
# Wikimedia etiquette: clients must identify themselves with a contact.
USER_AGENT = "UNIVPM-NGD-ArtGraph/1.0 (university exam project)"

# Keep the graph grounded and manageable: at most this many artworks per
# seed artist, ranked by Wikidata sitelink count (a notability proxy).
MAX_ARTWORKS_PER_ARTIST = 12

# --- Neo4j (must match docker-compose.yml) -----------------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "artgraph")
