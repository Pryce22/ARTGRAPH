"""Full 35-query workload on V2 (compact denormalized, lossless).

Traversals become list-membership tests on the embedded properties; the
location chain is reconstructed by splitting the aligned `location_facts`
tuples ('collection|||city|||country|||coordinates', empty fields when the
source chain is incomplete). `nullif(x, '')` maps empty fields back to null
so that results match V3's OPTIONAL traversals exactly.
"""

QUERIES = {
    # --- Descriptive ---------------------------------------------------------
    "q01": """
        MATCH (a:Artist {name: $artist})
        RETURN a.name AS artist, a.birth_date AS born,
               a.birth_place AS birth_place, a.death_date AS died,
               a.death_place AS death_place, a.ulan_id AS ulan
    """,
    "q02": """
        MATCH (w:Artwork {title: $artwork})
        RETURN w.title AS title, w.height_cm AS height_cm,
               w.width_cm AS width_cm, w.inception_year AS year,
               w.image_url AS image
    """,
    # --- One hop -------------------------------------------------------------
    "q03": """
        MATCH (w:Artwork {title: $artwork})
        UNWIND w.materials AS m
        RETURN m AS material
    """,
    "q04": """
        MATCH (w:Artwork)
        UNWIND w.location_facts AS f
        WITH split(f, '|||') AS x
        WHERE x[0] = $collection AND x[1] <> ''
        RETURN DISTINCT x[1] AS city, nullif(x[3], '') AS coordinates
    """,
    "q05": """
        MATCH (w:Artwork)
        WHERE $movement IN coalesce(w.movements, [])
        RETURN w.title AS title, w.inception_year AS year
    """,
    "q06": """
        MATCH (x:Artist)-[:INFLUENCED_BY]->(:Artist {name: $influencer})
        RETURN x.name AS artist
    """,
    # --- Multi hop -------------------------------------------------------------
    "q07": """
        MATCH (:Artist {name: $artist})-[:CREATED]->(w:Artwork)
        UNWIND coalesce(w.location_facts, []) AS f
        WITH w, split(f, '|||') AS x
        WHERE x[2] <> ''
        RETURN DISTINCT w.title AS title, x[2] AS country
    """,
    "q08": """
        MATCH (:Artist {name: $artist})-[:STUDENT_OF]->(m:Artist)
        RETURN m.name AS master, coalesce(m.movements, []) AS movements
    """,
    "q09": """
        MATCH (a:Artist {name: $artist})-[:CREATED]->(w:Artwork)
        UNWIND coalesce(w.location_facts, []) AS f
        WITH a, w, split(f, '|||') AS x
        WHERE x[1] = a.birth_place
        RETURN w.title AS title, x[0] AS collection, x[1] AS city
    """,
    "q10": """
        MATCH (w:Artwork)
        WHERE $subject IN coalesce(w.subjects, [])
        UNWIND coalesce(w.movements, []) AS m
        RETURN DISTINCT m AS movement
    """,
    "q11": """
        MATCH (a:Artist)-[:CREATED]->(w:Artwork)
        WHERE $genre IN coalesce(w.genres, []) AND a.death_place = $city
        RETURN a.name AS artist, w.title AS title
    """,
    "q12": """
        MATCH (:Artist {name: $commissioned_artist})-[:CREATED]->(w:Artwork)
        UNWIND coalesce(w.patrons, []) AS p
        RETURN p AS patron, w.title AS title
    """,
    "q13": """
        MATCH (w:Artwork {title: $artwork})
        MATCH (a:Artist)-[:CREATED]->(o:Artwork)
        WHERE o.title <> $artwork
          AND any(s IN coalesce(o.subjects, []) WHERE s IN coalesce(w.subjects, []))
        RETURN DISTINCT o.title AS title, a.name AS artist
    """,
    "q14": """
        MATCH (w:Artwork)
        WHERE $material IN coalesce(w.materials, [])
          AND $movement IN coalesce(w.movements, [])
        UNWIND w.location_facts AS f
        WITH split(f, '|||') AS x
        RETURN DISTINCT x[0] AS museum
    """,
    "q15": """
        MATCH (a:Artist)
        WHERE a.birth_country IS NOT NULL
          AND a.birth_country = a.death_country
        RETURN a.name AS artist, a.birth_country AS country,
               coalesce(a.movements, []) AS movements
    """,
    "q16": """
        MATCH (:Artist)-[:CREATED]->(w:Artwork)
        WHERE $patron IN coalesce(w.patrons, [])
        UNWIND coalesce(w.location_facts, []) AS f
        WITH w, split(f, '|||') AS x
        RETURN w.title AS title, x[0] AS collection, nullif(x[1], '') AS city
    """,
    "q17": """
        CALL {
            MATCH (w:Artwork) WHERE $subject IN coalesce(w.subjects, [])
            UNWIND coalesce(w.materials, []) AS m
            RETURN collect(DISTINCT m) AS materials
        }
        CALL {
            MATCH (w:Artwork) WHERE $subject IN coalesce(w.subjects, [])
            UNWIND coalesce(w.genres, []) AS g
            RETURN collect(DISTINCT g) AS genres
        }
        RETURN materials, genres
    """,
    "q18": """
        MATCH (x:Artist)-[:INFLUENCED_BY]->(:Artist {name: $influencer})
        UNWIND coalesce(x.movements, []) AS m
        RETURN DISTINCT x.name AS artist, m AS movement
    """,
    "q19": """
        MATCH (s:Artist)-[:STUDENT_OF]->(:Artist {name: $master})
        MATCH (s)-[:CREATED]->(w:Artwork)
        UNWIND coalesce(w.location_facts, []) AS f
        WITH s, split(f, '|||') AS x
        WHERE x[2] = $country
        RETURN DISTINCT x[0] AS museum, s.name AS student
    """,
    "q20": """
        MATCH (a:Artist)-[:CREATED]->(w:Artwork)
        WHERE w.height_cm >= $min_size_cm OR w.width_cm >= $min_size_cm
        UNWIND coalesce(w.location_facts, ['|||']) AS f
        WITH a, w, split(f, '|||') AS x
        RETURN w.title AS title, w.height_cm AS height_cm,
               w.width_cm AS width_cm, a.name AS artist,
               nullif(x[0], '') AS museum
    """,
    # --- Analytic --------------------------------------------------------------
    "q21": """
        MATCH (w:Artwork)
        WHERE w.movements IS NOT NULL
          AND w.height_cm IS NOT NULL AND w.width_cm IS NOT NULL
        UNWIND w.movements AS m
        RETURN m AS movement, count(w) AS works,
               round(avg(w.height_cm * w.width_cm)) AS avg_area_cm2,
               round(max(w.height_cm * w.width_cm)) AS max_area_cm2,
               round(min(w.height_cm * w.width_cm)) AS min_area_cm2
        ORDER BY works DESC, movement
    """,
    "q22": """
        MATCH (w:Artwork)
        WHERE $movement IN coalesce(w.movements, [])
        UNWIND coalesce(w.subjects, []) AS s
        RETURN s AS subject, count(*) AS frequency
        ORDER BY frequency DESC, subject LIMIT 10
    """,
    "q24": """
        MATCH (a:Artist)-[:CREATED]->(w:Artwork)
        UNWIND coalesce(w.patrons, []) AS p
        WITH p, count(DISTINCT w) AS works, collect(DISTINCT a.name) AS artists
        RETURN p AS patron, works, artists
        ORDER BY works DESC, patron LIMIT 5
    """,
    "q25": """
        MATCH (a1:Artist), (a2:Artist)
        WHERE a1.qid < a2.qid AND a1.birth_place IS NOT NULL
          AND a1.birth_place = a2.birth_place
        UNWIND coalesce(a1.movements, []) AS m
        WITH a1, a2, m
        WHERE m IN coalesce(a2.movements, [])
        RETURN a1.name AS artist1, a2.name AS artist2,
               a1.birth_place AS city, m AS movement
    """,
    "q26": """
        MATCH (a:Artist)-[:CREATED]->(w:Artwork)
        WHERE a.birth_country = $country
        UNWIND coalesce(w.materials, []) AS m
        RETURN m AS material, count(*) AS uses
        ORDER BY uses DESC, material
    """,
    "q27": """
        MATCH (a:Artist)-[:CREATED]->(w:Artwork)
        WHERE w.width_cm >= w.height_cm * $ratio
        UNWIND coalesce(w.location_facts, ['|||']) AS f
        WITH a, w, split(f, '|||') AS x
        RETURN w.title AS title, w.width_cm AS width_cm,
               w.height_cm AS height_cm, a.name AS artist,
               nullif(x[0], '') AS museum
    """,
    "q30": """
        MATCH (w:Artwork)
        WHERE w.inception_year IS NOT NULL
        UNWIND coalesce(w.genres, []) AS g
        RETURN (w.inception_year / 10) * 10 AS decade, g AS genre,
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
        MATCH (a:Artist)-[:CREATED]->(w:Artwork)
        UNWIND coalesce(w.patrons, []) AS p
        UNWIND coalesce(a.movements, []) AS m
        WITH p, collect(DISTINCT m) AS movements
        WHERE size(movements) >= 2
        RETURN p AS patron, movements
    """,
    "q35": """
        MATCH (w:Artwork)
        WHERE w.movements IS NOT NULL
        UNWIND w.location_facts AS f
        WITH w, split(f, '|||') AS x
        WHERE x[2] <> ''
        UNWIND w.movements AS m
        RETURN x[2] AS country, count(DISTINCT m) AS movements
        ORDER BY movements DESC, country
    """,
    # --- Multi hop (advanced) ---------------------------------------------------
    "q28": """
        MATCH (m:Artist {name: $master})-[:CREATED]->(mw:Artwork),
              (s:Artist)-[:STUDENT_OF]->(m), (s)-[:CREATED]->(sw:Artwork)
        UNWIND coalesce(mw.location_facts, []) AS mf
        UNWIND coalesce(sw.location_facts, []) AS sf
        WITH s, split(mf, '|||')[0] AS museum, split(sf, '|||')[0] AS smuseum
        WHERE museum = smuseum
        RETURN DISTINCT museum, collect(DISTINCT s.name) AS students
    """,
    "q29": """
        MATCH (s:Artist)-[:STUDENT_OF]->(m:Artist)
        WITH s, m, coalesce(s.movements, []) AS sm, coalesce(m.movements, []) AS mm
        WHERE size(mm) > 0 AND any(x IN sm WHERE NOT x IN mm)
        RETURN s.name AS student, sm AS student_movements,
               m.name AS master, mm AS master_movements
    """,
    "q33": """
        MATCH (a:Artist)-[:CREATED]->(w:Artwork)
        UNWIND coalesce(w.location_facts, []) AS f
        WITH a, split(f, '|||') AS x
        WHERE x[2] <> '' AND x[2] <> a.birth_country AND x[2] <> a.death_country
        RETURN a.name AS artist, collect(DISTINCT x[2]) AS foreign_countries
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
