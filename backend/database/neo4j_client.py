import os
from datetime import datetime
from neo4j import GraphDatabase
from backend.models import Triplet

class Neo4jClient:
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # Optional: verify connection
            self.driver.verify_connectivity()
        except Exception as e:
            print(f"Warning: Could not connect to Neo4j. Pipeline will fallback to mock ingestion. Err: {e}")
            self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()

    def _connect(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.driver.verify_connectivity()
            return True
        except Exception as e:
            self.driver = None
            return False

    def ingest_triplets(self, triplets: list[Triplet], mission_id: str = None, source: str = None):
        """
        Ingère les triplets dans Neo4j.
        
        Chaque nœud est tagué avec :
          - mission_id  : identifiant de la mission d'extraction
          - source      : source des données (OpenAlex, WoS, Google Scholar...)
          - ingested_at : timestamp d'ingestion (ISO 8601)
          
        Cela permet de retrouver et filtrer chaque ingestion dans Neo4j Browser.
        """
        if not self.driver:
            print("Retrying connection to Neo4j...")
            self._connect()
            
        if not self.driver:
            print("Neo4j driver not connected. Skipping DB ingestion.")
            return False

        ingested_at = datetime.utcnow().isoformat()
        mission_tag = mission_id or "unknown"
        source_tag = source or "unknown"

        with self.driver.session() as session:
            for t in triplets:
                # MERGE le nœud sujet et lui assigne les métadonnées de la mission
                # ON CREATE : propriétés définies seulement à la création du nœud
                # ON MATCH  : on ajoute la mission_id à la liste existante (multi-mission)
                cypher_query = f"""
                MERGE (s:{t.subject_type} {{id: $sub_id}})
                ON CREATE SET
                    s.mission_ids   = [$mission_id],
                    s.sources       = [$source],
                    s.first_seen_at = $ingested_at
                ON MATCH SET
                    s.mission_ids   = CASE
                        WHEN NOT $mission_id IN coalesce(s.mission_ids, [])
                        THEN coalesce(s.mission_ids, []) + [$mission_id]
                        ELSE s.mission_ids
                    END,
                    s.sources       = CASE
                        WHEN NOT $source IN coalesce(s.sources, [])
                        THEN coalesce(s.sources, []) + [$source]
                        ELSE s.sources
                    END,
                    s.last_seen_at  = $ingested_at

                MERGE (o:{t.object_type} {{id: $obj_id}})
                ON CREATE SET
                    o.mission_ids   = [$mission_id],
                    o.sources       = [$source],
                    o.first_seen_at = $ingested_at
                ON MATCH SET
                    o.mission_ids   = CASE
                        WHEN NOT $mission_id IN coalesce(o.mission_ids, [])
                        THEN coalesce(o.mission_ids, []) + [$mission_id]
                        ELSE o.mission_ids
                    END,
                    o.sources       = CASE
                        WHEN NOT $source IN coalesce(o.sources, [])
                        THEN coalesce(o.sources, []) + [$source]
                        ELSE o.sources
                    END,
                    o.last_seen_at  = $ingested_at

                MERGE (s)-[r:`{t.relation}`]->(o)
                SET r.confidence  = $conf,
                    r.justification = $just,
                    r.source      = $src,
                    r.mission_id  = $mission_id,
                    r.ingested_at = $ingested_at
                """

                session.run(
                    cypher_query,
                    sub_id=t.subject.strip(),
                    obj_id=t.object.strip(),
                    conf=t.confidence,
                    just=t.justification,
                    src=t.source_url,
                    mission_id=mission_tag,
                    source=source_tag,
                    ingested_at=ingested_at,
                )

        print(f"[neo4j] Ingestion terminée — mission: {mission_tag} | source: {source_tag} | {len(triplets)} triplets")
        return True

    def list_missions(self) -> list[dict]:
        """
        Retourne la liste de toutes les missions ingérées dans le graphe,
        avec le nombre de nœuds et de relations par mission.
        """
        if not self.driver:
            return []

        cypher = """
        MATCH ()-[r]->()
        WHERE r.mission_id IS NOT NULL
        WITH r.mission_id AS mission_id,
             r.source      AS source,
             r.ingested_at AS ingested_at,
             count(r)      AS relation_count
        ORDER BY ingested_at DESC
        RETURN mission_id, source, ingested_at, relation_count
        """
        missions = []
        with self.driver.session() as session:
            result = session.run(cypher)
            for record in result:
                missions.append({
                    "mission_id":     record["mission_id"],
                    "source":         record["source"],
                    "ingested_at":    record["ingested_at"],
                    "relation_count": record["relation_count"],
                })
        return missions

    def get_mission_graph(self, mission_id: str, limit: int = 200) -> list[dict]:
        """
        Retourne tous les triplets d'une mission spécifique depuis Neo4j.
        Utilisé par le GraphRAG et le Dashboard pour filtrer par mission.
        """
        if not self.driver:
            return []

        cypher = """
        MATCH (s)-[r]->(o)
        WHERE r.mission_id = $mission_id
        RETURN labels(s)[0] AS s_type, s.id AS subject,
               type(r)      AS relation,
               labels(o)[0] AS o_type, o.id AS object,
               r.justification AS justification,
               r.source        AS source,
               r.confidence    AS confidence
        LIMIT $limit
        """
        records = []
        with self.driver.session() as session:
            result = session.run(cypher, mission_id=mission_id, limit=limit)
            for record in result:
                records.append(dict(record))
        return records

    def get_graph_stats(self) -> dict:
        """Retourne les statistiques globales du graphe Neo4j."""
        if not self.driver:
            return {}
        cypher = """
        MATCH (n) WITH labels(n)[0] AS lbl, count(n) AS cnt
        RETURN lbl, cnt ORDER BY cnt DESC
        """
        stats = {}
        with self.driver.session() as session:
            result = session.run(cypher)
            for record in result:
                if record["lbl"]:
                    stats[record["lbl"]] = record["cnt"]
        return stats


# Initialize a global client to be imported by the FastAPI app
graph_db = Neo4jClient()
