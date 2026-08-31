"""Full 35-query workload on V1 (RDF-faithful with statement nodes).

Every conceptual hop costs two physical hops here:
    (subject)-[:HAS_STATEMENT]->(:Statement {pid})-[:VALUE]->(object)
and literals live on statement nodes instead of entity properties, which is
exactly the overhead the comparison is meant to expose.

Planner note: anchored OPTIONAL MATCHes filter the statement pid in a WHERE
clause; with the inline {pid: ...} form the planner prefers a full scan of
the Statement pid index over expanding from the anchor node.
"""

QUERIES = {
    # --- Descriptive ---------------------------------------------------------
    "q01": """
        MATCH (a:Entity {name: $artist})
        OPTIONAL MATCH (a)-[:HAS_STATEMENT]->(sb:Statement) WHERE sb.pid = 'P569'
        OPTIONAL MATCH (a)-[:HAS_STATEMENT]->(sd:Statement) WHERE sd.pid = 'P570'
        OPTIONAL MATCH (a)-[:HAS_STATEMENT]->(pb:Statement)-[:VALUE]->(bp)
            WHERE pb.pid = 'P19'
        OPTIONAL MATCH (a)-[:HAS_STATEMENT]->(pd:Statement)-[:VALUE]->(dp)
            WHERE pd.pid = 'P20'
        OPTIONAL MATCH (a)-[:HAS_STATEMENT]->(su:Statement) WHERE su.pid = 'P245'
        RETURN a.name AS artist, sb.value AS born, bp.name AS birth_place,
               sd.value AS died, dp.name AS death_place, su.value AS ulan
    """,
    "q02": """
        MATCH (w:Entity {name: $artwork})
        OPTIONAL MATCH (w)-[:HAS_STATEMENT]->(sh:Statement) WHERE sh.pid = 'P2048'
        OPTIONAL MATCH (w)-[:HAS_STATEMENT]->(sw:Statement) WHERE sw.pid = 'P2049'
        OPTIONAL MATCH (w)-[:HAS_STATEMENT]->(sy:Statement) WHERE sy.pid = 'P571'
        OPTIONAL MATCH (w)-[:HAS_STATEMENT]->(si:Statement) WHERE si.pid = 'P18'
        RETURN w.name AS title, sh.value AS height_cm, sw.value AS width_cm,
               sy.value AS year, si.value AS image
    """,
    # --- One hop -------------------------------------------------------------
    "q03": """
        MATCH (:Entity {name: $artwork})-[:HAS_STATEMENT]->
              (:Statement {pid: 'P186'})-[:VALUE]->(m:Entity)
        RETURN m.name AS material
    """,
    "q04": """
        MATCH (:Entity {name: $collection})-[:HAS_STATEMENT]->
              (:Statement {pid: 'P276'})-[:VALUE]->(p:Entity)
        OPTIONAL MATCH (p)-[:HAS_STATEMENT]->(sc:Statement) WHERE sc.pid = 'P625'
        RETURN p.name AS city, sc.value AS coordinates
    """,
    "q05": """
        MATCH (w:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P135'})
              -[:VALUE]->(:Entity {name: $movement})
        WHERE 'Artwork' IN w.etypes
        OPTIONAL MATCH (w)-[:HAS_STATEMENT]->(sy:Statement) WHERE sy.pid = 'P571'
        RETURN w.name AS title, sy.value AS year
    """,
    "q06": """
        MATCH (x:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P737'})
              -[:VALUE]->(:Entity {name: $influencer})
        RETURN x.name AS artist
    """,
    # --- Multi hop -------------------------------------------------------------
    "q07": """
        MATCH (:Entity {name: $artist})<-[:VALUE]-(:Statement {pid: 'P170'})
              <-[:HAS_STATEMENT]-(w:Entity)-[:HAS_STATEMENT]->
              (:Statement {pid: 'P195'})-[:VALUE]->(:Entity)-[:HAS_STATEMENT]->
              (:Statement {pid: 'P276'})-[:VALUE]->(:Entity)-[:HAS_STATEMENT]->
              (:Statement {pid: 'P17'})-[:VALUE]->(k:Entity)
        RETURN DISTINCT w.name AS title, k.name AS country
    """,
    "q08": """
        MATCH (:Entity {name: $artist})-[:HAS_STATEMENT]->
              (:Statement {pid: 'P1066'})-[:VALUE]->(m:Entity)
        OPTIONAL MATCH (m)-[:HAS_STATEMENT]->(sm:Statement)-[:VALUE]->(mv:Entity)
            WHERE sm.pid = 'P135'
        RETURN m.name AS master, collect(DISTINCT mv.name) AS movements
    """,
    "q09": """
        MATCH (a:Entity {name: $artist})-[:HAS_STATEMENT]->
              (:Statement {pid: 'P19'})-[:VALUE]->(p:Entity)
        MATCH (a)<-[:VALUE]-(:Statement {pid: 'P170'})<-[:HAS_STATEMENT]-
              (w:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P195'})
              -[:VALUE]->(c:Entity)-[:HAS_STATEMENT]->
              (:Statement {pid: 'P276'})-[:VALUE]->(p)
        RETURN w.name AS title, c.name AS collection, p.name AS city
    """,
    "q10": """
        MATCH (:Entity {name: $subject})<-[:VALUE]-(:Statement {pid: 'P180'})
              <-[:HAS_STATEMENT]-(:Entity)-[:HAS_STATEMENT]->
              (:Statement {pid: 'P135'})-[:VALUE]->(m:Entity)
        RETURN DISTINCT m.name AS movement
    """,
    "q11": """
        MATCH (w:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P136'})
              -[:VALUE]->(:Entity {name: $genre}),
              (w)-[:HAS_STATEMENT]->(:Statement {pid: 'P170'})-[:VALUE]->(a:Entity),
              (a)-[:HAS_STATEMENT]->(:Statement {pid: 'P20'})
              -[:VALUE]->(:Entity {name: $city})
        RETURN a.name AS artist, w.name AS title
    """,
    "q12": """
        MATCH (w:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P88'})
              -[:VALUE]->(p:Entity),
              (w)-[:HAS_STATEMENT]->(:Statement {pid: 'P170'})
              -[:VALUE]->(:Entity {name: $commissioned_artist})
        RETURN p.name AS patron, w.name AS title
    """,
    "q13": """
        MATCH (:Entity {name: $artwork})-[:HAS_STATEMENT]->
              (:Statement {pid: 'P180'})-[:VALUE]->(:Entity)<-[:VALUE]-
              (:Statement {pid: 'P180'})<-[:HAS_STATEMENT]-(o:Entity)
        WHERE o.name <> $artwork
        MATCH (o)-[:HAS_STATEMENT]->(:Statement {pid: 'P170'})-[:VALUE]->(a:Entity)
        RETURN DISTINCT o.name AS title, a.name AS artist
    """,
    "q14": """
        MATCH (c:Entity)<-[:VALUE]-(:Statement {pid: 'P195'})
              <-[:HAS_STATEMENT]-(w:Entity),
              (w)-[:HAS_STATEMENT]->(:Statement {pid: 'P186'})
              -[:VALUE]->(:Entity {name: $material}),
              (w)-[:HAS_STATEMENT]->(:Statement {pid: 'P135'})
              -[:VALUE]->(:Entity {name: $movement})
        RETURN DISTINCT c.name AS museum
    """,
    "q15": """
        // two MATCH clauses: with a single pattern, artists born and dead in
        // the same city would be excluded by relationship uniqueness
        MATCH (a:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P19'})-[:VALUE]->
              (:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P17'})-[:VALUE]->(k:Entity)
        MATCH (a)-[:HAS_STATEMENT]->(:Statement {pid: 'P20'})-[:VALUE]->
              (:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P17'})-[:VALUE]->(k)
        RETURN a.name AS artist, k.name AS country,
               [(a)-[:HAS_STATEMENT]->(:Statement {pid: 'P135'})-[:VALUE]->(m:Entity)
                | m.name] AS movements
    """,
    "q16": """
        MATCH (:Entity {name: $patron})<-[:VALUE]-(:Statement {pid: 'P88'})
              <-[:HAS_STATEMENT]-(w:Entity)-[:HAS_STATEMENT]->
              (:Statement {pid: 'P195'})-[:VALUE]->(c:Entity)
        OPTIONAL MATCH (c)-[:HAS_STATEMENT]->(sp:Statement)-[:VALUE]->(p:Entity)
            WHERE sp.pid = 'P276'
        RETURN w.name AS title, c.name AS collection, p.name AS city
    """,
    "q17": """
        MATCH (:Entity {name: $subject})<-[:VALUE]-(:Statement {pid: 'P180'})
              <-[:HAS_STATEMENT]-(w:Entity)
        OPTIONAL MATCH (w)-[:HAS_STATEMENT]->(sm:Statement)-[:VALUE]->(m:Entity)
            WHERE sm.pid = 'P186'
        OPTIONAL MATCH (w)-[:HAS_STATEMENT]->(sg:Statement)-[:VALUE]->(g:Entity)
            WHERE sg.pid = 'P136'
        RETURN collect(DISTINCT m.name) AS materials,
               collect(DISTINCT g.name) AS genres
    """,
    "q18": """
        MATCH (x:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P737'})
              -[:VALUE]->(:Entity {name: $influencer}),
              (x)-[:HAS_STATEMENT]->(:Statement {pid: 'P135'})-[:VALUE]->(m:Entity)
        RETURN DISTINCT x.name AS artist, m.name AS movement
    """,
    "q19": """
        MATCH (:Entity {name: $master})<-[:VALUE]-(:Statement {pid: 'P1066'})
              <-[:HAS_STATEMENT]-(s:Entity)<-[:VALUE]-(:Statement {pid: 'P170'})
              <-[:HAS_STATEMENT]-(:Entity)-[:HAS_STATEMENT]->
              (:Statement {pid: 'P195'})-[:VALUE]->(c:Entity)-[:HAS_STATEMENT]->
              (:Statement {pid: 'P276'})-[:VALUE]->(:Entity)-[:HAS_STATEMENT]->
              (:Statement {pid: 'P17'})-[:VALUE]->(:Entity {name: $country})
        RETURN DISTINCT c.name AS museum, s.name AS student
    """,
    "q20": """
        MATCH (a:Entity)<-[:VALUE]-(:Statement {pid: 'P170'})
              <-[:HAS_STATEMENT]-(w:Entity)
        OPTIONAL MATCH (w)-[:HAS_STATEMENT]->(sh:Statement) WHERE sh.pid = 'P2048'
        OPTIONAL MATCH (w)-[:HAS_STATEMENT]->(sw:Statement) WHERE sw.pid = 'P2049'
        WITH a, w, sh.value AS height, sw.value AS width
        WHERE height >= $min_size_cm OR width >= $min_size_cm
        OPTIONAL MATCH (w)-[:HAS_STATEMENT]->(sc:Statement)-[:VALUE]->(c:Entity)
            WHERE sc.pid = 'P195'
        RETURN w.name AS title, height AS height_cm, width AS width_cm,
               a.name AS artist, c.name AS museum
    """,
    # --- Analytic --------------------------------------------------------------
    "q21": """
        MATCH (w:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P135'})
              -[:VALUE]->(m:Entity)
        WHERE 'Artwork' IN w.etypes
        MATCH (w)-[:HAS_STATEMENT]->(sh:Statement {pid: 'P2048'})
        MATCH (w)-[:HAS_STATEMENT]->(sw:Statement {pid: 'P2049'})
        RETURN m.name AS movement, count(w) AS works,
               round(avg(sh.value * sw.value)) AS avg_area_cm2,
               round(max(sh.value * sw.value)) AS max_area_cm2,
               round(min(sh.value * sw.value)) AS min_area_cm2
        ORDER BY works DESC, movement
    """,
    "q22": """
        MATCH (:Entity {name: $movement})<-[:VALUE]-(:Statement {pid: 'P135'})
              <-[:HAS_STATEMENT]-(w:Entity)-[:HAS_STATEMENT]->
              (:Statement {pid: 'P180'})-[:VALUE]->(s:Entity)
        WHERE 'Artwork' IN w.etypes
        RETURN s.name AS subject, count(*) AS frequency
        ORDER BY frequency DESC, subject LIMIT 10
    """,
    "q24": """
        MATCH (p:Entity)<-[:VALUE]-(:Statement {pid: 'P88'})
              <-[:HAS_STATEMENT]-(w:Entity),
              (w)-[:HAS_STATEMENT]->(:Statement {pid: 'P170'})-[:VALUE]->(a:Entity)
        RETURN p.name AS patron, count(DISTINCT w) AS works,
               collect(DISTINCT a.name) AS artists
        ORDER BY works DESC, patron LIMIT 5
    """,
    "q25": """
        MATCH (a1:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P19'})
              -[:VALUE]->(p:Entity)<-[:VALUE]-(:Statement {pid: 'P19'})
              <-[:HAS_STATEMENT]-(a2:Entity),
              (a1)-[:HAS_STATEMENT]->(:Statement {pid: 'P135'})
              -[:VALUE]->(m:Entity)<-[:VALUE]-(:Statement {pid: 'P135'})
              <-[:HAS_STATEMENT]-(a2)
        WHERE a1.qid < a2.qid
        RETURN a1.name AS artist1, a2.name AS artist2,
               p.name AS city, m.name AS movement
    """,
    "q26": """
        MATCH (:Entity {name: $country})<-[:VALUE]-(:Statement {pid: 'P17'})
              <-[:HAS_STATEMENT]-(:Entity)<-[:VALUE]-(:Statement {pid: 'P19'})
              <-[:HAS_STATEMENT]-(a:Entity)<-[:VALUE]-(:Statement {pid: 'P170'})
              <-[:HAS_STATEMENT]-(:Entity)-[:HAS_STATEMENT]->
              (:Statement {pid: 'P186'})-[:VALUE]->(m:Entity)
        RETURN m.name AS material, count(*) AS uses
        ORDER BY uses DESC, material
    """,
    "q27": """
        MATCH (a:Entity)<-[:VALUE]-(:Statement {pid: 'P170'})
              <-[:HAS_STATEMENT]-(w:Entity),
              (w)-[:HAS_STATEMENT]->(sh:Statement {pid: 'P2048'}),
              (w)-[:HAS_STATEMENT]->(sw:Statement {pid: 'P2049'})
        WHERE sw.value >= sh.value * $ratio
        OPTIONAL MATCH (w)-[:HAS_STATEMENT]->(sc:Statement)-[:VALUE]->(c:Entity)
            WHERE sc.pid = 'P195'
        RETURN w.name AS title, sw.value AS width_cm, sh.value AS height_cm,
               a.name AS artist, c.name AS museum
    """,
    "q30": """
        MATCH (w:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P136'})
              -[:VALUE]->(g:Entity),
              (w)-[:HAS_STATEMENT]->(sy:Statement {pid: 'P571'})
        RETURN (sy.value / 10) * 10 AS decade, g.name AS genre, count(*) AS works
        ORDER BY decade, works DESC, genre
    """,
    "q31": """
        MATCH (a1:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P737'})
              -[:VALUE]->(x:Entity)<-[:VALUE]-(:Statement {pid: 'P737'})
              <-[:HAS_STATEMENT]-(a2:Entity)
        WHERE a1.qid < a2.qid
        WITH a1, a2, collect(DISTINCT x.name) AS shared
        WHERE size(shared) >= 2
        RETURN a1.name AS artist1, a2.name AS artist2, shared
    """,
    "q34": """
        MATCH (p:Entity)<-[:VALUE]-(:Statement {pid: 'P88'})
              <-[:HAS_STATEMENT]-(:Entity)-[:HAS_STATEMENT]->
              (:Statement {pid: 'P170'})-[:VALUE]->(a:Entity),
              (a)-[:HAS_STATEMENT]->(:Statement {pid: 'P135'})-[:VALUE]->(m:Entity)
        WITH p, collect(DISTINCT m.name) AS movements
        WHERE size(movements) >= 2
        RETURN p.name AS patron, movements
    """,
    "q35": """
        MATCH (k:Entity)<-[:VALUE]-(:Statement {pid: 'P17'})<-[:HAS_STATEMENT]-
              (:Entity)<-[:VALUE]-(:Statement {pid: 'P276'})<-[:HAS_STATEMENT]-
              (:Entity)<-[:VALUE]-(:Statement {pid: 'P195'})<-[:HAS_STATEMENT]-
              (w:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P135'})
              -[:VALUE]->(m:Entity)
        WHERE 'Country' IN k.etypes
        RETURN k.name AS country, count(DISTINCT m) AS movements
        ORDER BY movements DESC, country
    """,
    # --- Multi hop (advanced) ---------------------------------------------------
    "q28": """
        MATCH (m:Entity {name: $master})<-[:VALUE]-(:Statement {pid: 'P170'})
              <-[:HAS_STATEMENT]-(:Entity)-[:HAS_STATEMENT]->
              (:Statement {pid: 'P195'})-[:VALUE]->(c:Entity),
              (c)<-[:VALUE]-(:Statement {pid: 'P195'})<-[:HAS_STATEMENT]-
              (:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P170'})
              -[:VALUE]->(s:Entity),
              (s)-[:HAS_STATEMENT]->(:Statement {pid: 'P1066'})-[:VALUE]->(m)
        RETURN DISTINCT c.name AS museum, collect(DISTINCT s.name) AS students
    """,
    "q29": """
        MATCH (s:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P1066'})
              -[:VALUE]->(m:Entity)
        WITH s, m,
             [(s)-[:HAS_STATEMENT]->(:Statement {pid: 'P135'})-[:VALUE]->(x:Entity)
              | x.name] AS sm,
             [(m)-[:HAS_STATEMENT]->(:Statement {pid: 'P135'})-[:VALUE]->(y:Entity)
              | y.name] AS mm
        WHERE size(mm) > 0 AND any(x IN sm WHERE NOT x IN mm)
        RETURN s.name AS student, sm AS student_movements,
               m.name AS master, mm AS master_movements
    """,
    "q33": """
        // separate MATCH clauses (see q15): birth and death chains may share
        // the same P17 statement
        MATCH (a:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P19'})-[:VALUE]->
              (:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P17'})-[:VALUE]->(bk:Entity)
        MATCH (a)-[:HAS_STATEMENT]->(:Statement {pid: 'P20'})-[:VALUE]->
              (:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P17'})-[:VALUE]->(dk:Entity)
        MATCH (a)<-[:VALUE]-(:Statement {pid: 'P170'})<-[:HAS_STATEMENT]-
              (:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P195'})-[:VALUE]->
              (:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P276'})-[:VALUE]->
              (:Entity)-[:HAS_STATEMENT]->(:Statement {pid: 'P17'})-[:VALUE]->(k:Entity)
        WHERE k <> bk AND k <> dk
        RETURN a.name AS artist, collect(DISTINCT k.name) AS foreign_countries
    """,
    # --- Path ---------------------------------------------------------------
    "q23": """
        MATCH path = (a:Entity)-[:HAS_STATEMENT|VALUE*2..8]->
              (:Entity {name: $influencer})
        WHERE all(n IN nodes(path)[1..-1] WHERE
                  (n:Statement AND n.pid = 'P737') OR 'Artist' IN n.etypes)
        RETURN [n IN nodes(path) WHERE NOT n:Statement | n.name] AS influence_line,
               length(path) / 2 AS hops
    """,
    "q32": """
        MATCH path = (:Entity {name: $artist})-[:HAS_STATEMENT|VALUE*1..8]-
              (:Entity {name: $artist2})
        WHERE all(n IN nodes(path) WHERE NOT n:Statement OR
                  n.pid IN ['P170', 'P737', 'P1066'])
        RETURN count(path) AS paths, min(length(path) / 2) AS shortest
    """,
}
