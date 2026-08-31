"""Shared mapping tables between the normalized dataset and the LPG schemas."""

# entity group in dataset.json -> node label (V3) / entity type tag (V1)
ENTITY_LABELS = {
    "artists": "Artist",
    "artworks": "Artwork",
    "movements": "Movement",
    "collections": "Collection",
    "places": "Place",
    "countries": "Country",
    "materials": "Material",
    "genres": "Genre",
    "subjects": "Subject",
    "patrons": "Patron",
}

# relation type -> (source label, target label), as designed in the report
RELATION_ENDPOINTS = {
    "CREATED": ("Artist", "Artwork"),
    "ASSOCIATED_WITH": ("Artist", "Movement"),
    "CLASSIFIED_IN": ("Artwork", "Movement"),
    "IN_COLLECTION": ("Artwork", "Collection"),
    "LOCATED_IN": ("Collection", "Place"),
    "IN_COUNTRY": ("Place", "Country"),
    "USES_MATERIAL": ("Artwork", "Material"),
    "HAS_GENRE": ("Artwork", "Genre"),
    "DEPICTS": ("Artwork", "Subject"),
    "BORN_IN": ("Artist", "Place"),
    "DIED_IN": ("Artist", "Place"),
    "INFLUENCED_BY": ("Artist", "Artist"),
    "STUDENT_OF": ("Artist", "Artist"),
    "COMMISSIONED": ("Patron", "Artwork"),
}

# relation type -> (Wikidata PID, RDF subject side).  In RDF the subject of
# P170 (creator) and P88 (commissioned by) is the artwork, while the LPG edge
# starts from the artist/patron: V1 reifies the original RDF direction.
RELATION_RDF = {
    "CREATED": ("P170", "target"),
    "ASSOCIATED_WITH": ("P135", "source"),
    "CLASSIFIED_IN": ("P135", "source"),
    "IN_COLLECTION": ("P195", "source"),
    "LOCATED_IN": ("P276", "source"),
    "IN_COUNTRY": ("P17", "source"),
    "USES_MATERIAL": ("P186", "source"),
    "HAS_GENRE": ("P136", "source"),
    "DEPICTS": ("P180", "source"),
    "BORN_IN": ("P19", "source"),
    "DIED_IN": ("P20", "source"),
    "INFLUENCED_BY": ("P737", "source"),
    "STUDENT_OF": ("P1066", "source"),
    "COMMISSIONED": ("P88", "target"),
}

# scalar property -> Wikidata PID (properties without a PID are Wikimedia
# metadata and keep their own name as pseudo-PID in the V1 statements)
PROPERTY_PIDS = {
    "birth_date": "P569",
    "death_date": "P570",
    "ulan_id": "P245",
    "inception_year": "P571",
    "image_url": "P18",
    "height_cm": "P2048",
    "width_cm": "P2049",
    "coordinates": "P625",
    "iso_code": "P297",
    "tgn_id": "P1667",
    "aat_id": "P1014",
}

# identity fields kept directly on nodes in every version
NODE_KEYS = ("qid", "name", "title", "is_seed")
