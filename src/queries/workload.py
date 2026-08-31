"""Query workload: specifications shared by every schema version.

The 35 queries of the report are grouped in five classes:
  descriptive  node-property lookups
  one_hop      direct relations
  multi_hop    2+ hop traversals
  analytic     aggregations (distributions, averages, rankings)
  path         variable-length path finding

Fair-comparison contract: every query is defined by its *semantics* (the
description below), independently of any schema. Each version implements all
35 queries in its own idiom, with the same column aliases, and the benchmark
verifies that the three implementations return identical canonical result
sets. Queries with LIMIT carry a deterministic tie-breaking ORDER BY.

Every implementation is parametric; PARAMS holds grounded default values,
verified to return non-empty results on the extracted dataset.
"""

# Default parameters (Wikidata English labels, as loaded in the graph)
PARAMS = {
    "artist": "Claude Monet",
    "artist2": "Camille Pissarro",     # path endpoint for q32
    "artwork": "Olympia",
    "collection": "Musée d'Orsay",
    "movement": "Impressionism",
    "material": "oil paint",
    "genre": "portrait",
    "subject": "woman",
    "master": "Camille Pissarro",      # has students AND own works in graph
    "influencer": "Gustave Courbet",   # root of 2+ hop influence chains
    "patron": "Sergei Shchukin",
    "commissioned_artist": "Henri Matisse",  # Shchukin commissioned 'Music'
    "city": "Paris",
    "country": "France",
    "min_size_cm": 200,                # threshold for 'large' works
    "ratio": 1.5,                      # width/height ratio for q27
}

SPECS = {
    "q01": ("descriptive", "Birth, death and external identifiers of an artist"),
    "q02": ("descriptive", "Dimensions, creation year and image URL of an artwork"),
    "q03": ("one_hop", "Materials an artwork is made of"),
    "q04": ("one_hop", "Coordinates of the city hosting a collection"),
    "q05": ("one_hop", "Paintings explicitly classified in a movement"),
    "q06": ("one_hop", "Artists directly influenced by a given author"),
    "q07": ("multi_hop", "Works of an artist and the countries where they are kept"),
    "q08": ("multi_hop", "Masters of an artist and the movements of those masters"),
    "q09": ("multi_hop", "Works of an artist kept in the artist's birth city"),
    "q10": ("multi_hop", "Movements of artworks depicting a given subject"),
    "q11": ("multi_hop", "Works of a genre by artists who died in a given city"),
    "q12": ("multi_hop", "Patrons who commissioned works by a given artist"),
    "q13": ("multi_hop", "Other paintings depicting the same subjects as a work"),
    "q14": ("multi_hop", "Museums holding works of a material and movement"),
    "q15": ("multi_hop", "Artists born and dead in the same country, with movements"),
    "q16": ("multi_hop", "Current location of works commissioned by a patron"),
    "q17": ("multi_hop", "Materials and genres used to depict a subject"),
    "q18": ("multi_hop", "Movements of painters influenced by an artist"),
    "q19": ("multi_hop", "Museums of a country holding works by a master's students"),
    "q20": ("multi_hop", "Works above a size threshold, with author and museum"),
    "q21": ("analytic", "Average/max/min artwork area per movement"),
    "q22": ("analytic", "Most frequently depicted subjects within a movement"),
    "q23": ("path", "Indirect influence lines from a progenitor artist"),
    "q24": ("analytic", "Top 5 patrons by commissioned works, with artists"),
    "q25": ("analytic", "Artist pairs born in the same city and same movement"),
    "q26": ("analytic", "Materials preferred by artists born in a country"),
    "q27": ("analytic", "Predominantly horizontal paintings, author and location"),
    "q28": ("multi_hop", "Museums holding works of a master and of their students"),
    "q29": ("multi_hop", "Students with movements beyond their master's"),
    "q30": ("analytic", "Genre frequency per creation decade"),
    "q31": ("analytic", "Artist pairs sharing at least two influences"),
    "q32": ("path", "Paths (max 4 hops) between two artists via works, influence and apprenticeship"),
    "q33": ("multi_hop", "Artists whose works are kept outside birth/death countries"),
    "q34": ("analytic", "Patrons who funded artists of different movements"),
    "q35": ("analytic", "Countries ranked by distinct movements in their museums"),
}
