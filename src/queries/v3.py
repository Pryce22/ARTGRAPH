"""Full 35-query workload on V3 (entity-centric normalized).

Reference implementation of the workload semantics: each traversed Wikidata
property is a typed relationship, each scalar a node property. Column
aliases are shared with v1.py / v2.py so that the benchmark can verify
result-set equivalence across versions.
"""

QUERIES = {
    # --- Descriptive ---------------------------------------------------------
    "q01": """
        MATCH (a:Artist {name: $artist})
        OPTIONAL MATCH (a)-[:BORN_IN]->(bp:Place)
        OPTIONAL MATCH (a)-[:DIED_IN]->(dp:Place)
        RETURN a.name AS artist, a.birth_date AS born, bp.name AS birth_place,
               a.death_date AS died, dp.name AS death_place, a.ulan_id AS ulan
    """,
    "q02": """
        MATCH (w:Artwork {title: $artwork})
        RETURN w.title AS title, w.height_cm AS height_cm,
               w.width_cm AS width_cm, w.inception_year AS year,
               w.image_url AS image
    """,
    # --- One hop -------------------------------------------------------------
    "q03": """
        MATCH (:Artwork {title: $artwork})-[:USES_MATERIAL]->(m:Material)
        RETURN m.name AS material
    """,
    "q04": """
        MATCH (:Collection {name: $collection})-[:LOCATED_IN]->(p:Place)
        RETURN p.name AS city, p.coordinates AS coordinates
    """,
    "q05": """
        MATCH (w:Artwork)-[:CLASSIFIED_IN]->(:Movement {name: $movement})
        RETURN w.title AS title, w.inception_year AS year
    """,
    "q06": """
        MATCH (x:Artist)-[:INFLUENCED_BY]->(:Artist {name: $influencer})
        RETURN x.name AS artist
    """,
    # --- Multi hop -------------------------------------------------------------
    "q07": """
        MATCH (:Artist {name: $artist})-[:CREATED]->(w:Artwork)
              -[:IN_COLLECTION]->(:Collection)-[:LOCATED_IN]->(:Place)
              -[:IN_COUNTRY]->(k:Country)
        RETURN DISTINCT w.title AS title, k.name AS country
    """,
    "q08": """
        MATCH (:Artist {name: $artist})-[:STUDENT_OF]->(m:Artist)
        OPTIONAL MATCH (m)-[:ASSOCIATED_WITH]->(mv:Movement)
        RETURN m.name AS master, collect(DISTINCT mv.name) AS movements
    """,
    "q09": """
        MATCH (a:Artist {name: $artist})-[:BORN_IN]->(p:Place)
              <-[:LOCATED_IN]-(c:Collection)<-[:IN_COLLECTION]-(w:Artwork)
              <-[:CREATED]-(a)
        RETURN w.title AS title, c.name AS collection, p.name AS city
    """,
    "q10": """
        MATCH (:Subject {name: $subject})<-[:DEPICTS]-(:Artwork)
              -[:CLASSIFIED_IN]->(m:Movement)
        RETURN DISTINCT m.name AS movement
    """,
    "q11": """
        MATCH (w:Artwork)-[:HAS_GENRE]->(:Genre {name: $genre}),
              (w)<-[:CREATED]-(a:Artist)-[:DIED_IN]->(:Place {name: $city})
        RETURN a.name AS artist, w.title AS title
    """,
    "q12": """
        MATCH (p:Patron)-[:COMMISSIONED]->(w:Artwork)
              <-[:CREATED]-(:Artist {name: $commissioned_artist})
        RETURN p.name AS patron, w.title AS title
    """,
    "q13": """
        MATCH (:Artwork {title: $artwork})-[:DEPICTS]->(s:Subject)
              <-[:DEPICTS]-(o:Artwork)<-[:CREATED]-(a:Artist)
        WHERE o.title <> $artwork
        RETURN DISTINCT o.title AS title, a.name AS artist
    """,
    "q14": """
        MATCH (c:Collection)<-[:IN_COLLECTION]-(w:Artwork)
              -[:USES_MATERIAL]->(:Material {name: $material}),
              (w)-[:CLASSIFIED_IN]->(:Movement {name: $movement})
        RETURN DISTINCT c.name AS museum
    """,
    "q15": """
        // two MATCH clauses: with a single pattern, artists born and dead in
        // the same city would be excluded by relationship uniqueness
        MATCH (a:Artist)-[:BORN_IN]->(:Place)-[:IN_COUNTRY]->(k:Country)
        MATCH (a)-[:DIED_IN]->(:Place)-[:IN_COUNTRY]->(k)
        RETURN a.name AS artist, k.name AS country,
               [(a)-[:ASSOCIATED_WITH]->(m:Movement) | m.name] AS movements
    """,
    "q16": """
        MATCH (:Patron {name: $patron})-[:COMMISSIONED]->(w:Artwork)
              -[:IN_COLLECTION]->(c:Collection)
        OPTIONAL MATCH (c)-[:LOCATED_IN]->(p:Place)
        RETURN w.title AS title, c.name AS collection, p.name AS city
    """,
    "q17": """
        MATCH (:Subject {name: $subject})<-[:DEPICTS]-(w:Artwork)
        OPTIONAL MATCH (w)-[:USES_MATERIAL]->(m:Material)
        OPTIONAL MATCH (w)-[:HAS_GENRE]->(g:Genre)
        RETURN collect(DISTINCT m.name) AS materials,
               collect(DISTINCT g.name) AS genres
    """,
    "q18": """
        MATCH (x:Artist)-[:INFLUENCED_BY]->(:Artist {name: $influencer}),
              (x)-[:ASSOCIATED_WITH]->(m:Movement)
        RETURN DISTINCT x.name AS artist, m.name AS movement
    """,
    "q19": """
        MATCH (s:Artist)-[:STUDENT_OF]->(:Artist {name: $master}),
              (s)-[:CREATED]->(:Artwork)-[:IN_COLLECTION]->(c:Collection)
              -[:LOCATED_IN]->(:Place)-[:IN_COUNTRY]->(:Country {name: $country})
        RETURN DISTINCT c.name AS museum, s.name AS student
    """,
    "q20": """
        MATCH (a:Artist)-[:CREATED]->(w:Artwork)
        WHERE w.height_cm >= $min_size_cm OR w.width_cm >= $min_size_cm
        OPTIONAL MATCH (w)-[:IN_COLLECTION]->(c:Collection)
        RETURN w.title AS title, w.height_cm AS height_cm,
               w.width_cm AS width_cm, a.name AS artist, c.name AS museum
    """,
    # --- Analytic --------------------------------------------------------------
    "q21": """
        MATCH (w:Artwork)-[:CLASSIFIED_IN]->(m:Movement)
        WHERE w.height_cm IS NOT NULL AND w.width_cm IS NOT NULL
        RETURN m.name AS movement, count(w) AS works,
               round(avg(w.height_cm * w.width_cm)) AS avg_area_cm2,
               round(max(w.height_cm * w.width_cm)) AS max_area_cm2,
               round(min(w.height_cm * w.width_cm)) AS min_area_cm2
        ORDER BY works DESC, movement
    """,
    "q22": """
        MATCH (:Movement {name: $movement})<-[:CLASSIFIED_IN]-(:Artwork)
              -[:DEPICTS]->(s:Subject)
        RETURN s.name AS subject, count(*) AS frequency
        ORDER BY frequency DESC, subject LIMIT 10
    """,
    "q24": """
        MATCH (p:Patron)-[:COMMISSIONED]->(w:Artwork)<-[:CREATED]-(a:Artist)
        RETURN p.name AS patron, count(DISTINCT w) AS works,
               collect(DISTINCT a.name) AS artists
        ORDER BY works DESC, patron LIMIT 5
    """,
    "q25": """
        MATCH (a1:Artist)-[:BORN_IN]->(p:Place)<-[:BORN_IN]-(a2:Artist),
              (a1)-[:ASSOCIATED_WITH]->(m:Movement)<-[:ASSOCIATED_WITH]-(a2)
        WHERE a1.qid < a2.qid
        RETURN a1.name AS artist1, a2.name AS artist2,
               p.name AS city, m.name AS movement
    """,
    "q26": """
        MATCH (a:Artist)-[:BORN_IN]->(:Place)
              -[:IN_COUNTRY]->(:Country {name: $country}),
              (a)-[:CREATED]->(:Artwork)-[:USES_MATERIAL]->(m:Material)
        RETURN m.name AS material, count(*) AS uses
        ORDER BY uses DESC, material
    """,
    "q27": """
        MATCH (a:Artist)-[:CREATED]->(w:Artwork)
        WHERE w.width_cm >= w.height_cm * $ratio
        OPTIONAL MATCH (w)-[:IN_COLLECTION]->(c:Collection)
        RETURN w.title AS title, w.width_cm AS width_cm,
               w.height_cm AS height_cm, a.name AS artist, c.name AS museum
    """,
    "q30": """
        MATCH (w:Artwork)-[:HAS_GENRE]->(g:Genre)
        WHERE w.inception_year IS NOT NULL
        RETURN (w.inception_year / 10) * 10 AS decade, g.name AS genre,
               count(*) AS works
        ORDER BY decade, works DESC, genre
    """,
    "q31": """
        MATCH (a1:Artist)-[:INFLUENCED_BY]->(x:Artist)
              <-[:INFLUENCED_BY]-(a2:Artist)
        WHERE a1.qid < a2.qid
        WITH a1, a2, collect(DISTINCT x.name) AS shared
        WHERE size(shared) >= 2
        RETURN a1.name AS artist1, a2.name AS artist2, shared
    """,
    "q34": """
        MATCH (p:Patron)-[:COMMISSIONED]->(:Artwork)<-[:CREATED]-(a:Artist)
              -[:ASSOCIATED_WITH]->(m:Movement)
        WITH p, collect(DISTINCT m.name) AS movements
        WHERE size(movements) >= 2
        RETURN p.name AS patron, movements
    """,
    "q35": """
        MATCH (k:Country)<-[:IN_COUNTRY]-(:Place)<-[:LOCATED_IN]-(:Collection)
              <-[:IN_COLLECTION]-(:Artwork)-[:CLASSIFIED_IN]->(m:Movement)
        RETURN k.name AS country, count(DISTINCT m) AS movements
        ORDER BY movements DESC, country
    """,
    # --- Multi hop (advanced) ---------------------------------------------------
    "q28": """
        MATCH (m:Artist {name: $master})-[:CREATED]->(:Artwork)
              -[:IN_COLLECTION]->(c:Collection),
              (c)<-[:IN_COLLECTION]-(:Artwork)<-[:CREATED]-(s:Artist)
              -[:STUDENT_OF]->(m)
        RETURN DISTINCT c.name AS museum, collect(DISTINCT s.name) AS students
    """,
    "q29": """
        MATCH (s:Artist)-[:STUDENT_OF]->(m:Artist)
        WITH s, m,
             [(s)-[:ASSOCIATED_WITH]->(x:Movement) | x.name] AS sm,
             [(m)-[:ASSOCIATED_WITH]->(y:Movement) | y.name] AS mm
        WHERE size(mm) > 0 AND any(x IN sm WHERE NOT x IN mm)
        RETURN s.name AS student, sm AS student_movements,
               m.name AS master, mm AS master_movements
    """,
    "q33": """
        // separate MATCH clauses (see q15): birth and death chains may share
        // the same IN_COUNTRY relationship
        MATCH (a:Artist)-[:BORN_IN]->(:Place)-[:IN_COUNTRY]->(bk:Country)
        MATCH (a)-[:DIED_IN]->(:Place)-[:IN_COUNTRY]->(dk:Country)
        MATCH (a)-[:CREATED]->(:Artwork)-[:IN_COLLECTION]->(:Collection)
              -[:LOCATED_IN]->(:Place)-[:IN_COUNTRY]->(k:Country)
        WHERE k <> bk AND k <> dk
        RETURN a.name AS artist, collect(DISTINCT k.name) AS foreign_countries
    """,
    # --- Path ---------------------------------------------------------------
    "q23": """
        MATCH path = (a:Artist)-[:INFLUENCED_BY*1..4]->(:Artist {name: $influencer})
        RETURN [n IN nodes(path) | n.name] AS influence_line,
               length(path) AS hops
    """,
    "q32": """
        MATCH path = (:Artist {name: $artist})
              -[:CREATED|INFLUENCED_BY|STUDENT_OF*1..4]-
              (:Artist {name: $artist2})
        RETURN count(path) AS paths, min(length(path)) AS shortest
    """,
}
