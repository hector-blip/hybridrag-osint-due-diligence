# ingestNeo4j.py
import pandas as pd
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

BOLT_URL = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER     = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")  # défini dans .env

df = pd.read_excel('Excel-Data-Abbcari-Battery-materials.xlsx')
driver = GraphDatabase.driver(BOLT_URL, auth=(USER, PASSWORD))

triplets_avant_hitl = 0

def insert_article(tx, row):
    global triplets_avant_hitl

    # Nœud Article
    tx.run("""
        MERGE (a:Article {doi: $doi})
        SET a.title = $title, a.year = $year, a.journal = $journal
    """, doi=str(row['DOI or webLink']),
         title=str(row['Title']),
         year=int(row['Year']),
         journal=str(row['Journal']))

    # Auteurs → AFFILIÉ_À Institutions
    authors  = [a.strip() for a in str(row['Authors']).split(',') if a.strip()]
    affils   = [a.strip() for a in str(row['Affiliations']).split(',') if a.strip()]
    partners = [p.strip() for p in str(row['Partners or funding sources']).split(',') if p.strip()]
    keywords = [k.strip() for k in str(row['Key words']).split(',') if k.strip()]

    for author in authors:
        tx.run("""
            MERGE (r:Researcher {name: $name})
            WITH r
            MATCH (a:Article {doi: $doi})
            MERGE (r)-[:A_PUBLIÉ]->(a)
        """, name=author, doi=str(row['DOI or webLink']))
        triplets_avant_hitl += 1

        for affil in affils:
            tx.run("""
                MERGE (i:Institution {name: $name})
                WITH i
                MATCH (r:Researcher {name: $rname})
                MERGE (r)-[:AFFILIÉ_À]->(i)
            """, name=affil, rname=author)
            triplets_avant_hitl += 1

    # Partenaires
    for partner in partners:
        for author in authors:
            tx.run("""
                MERGE (o:Organization {name: $oname})
                WITH o
                MATCH (r:Researcher {name: $rname})
                MERGE (r)-[:PARTENAIRE_DE]->(o)
            """, oname=partner, rname=author)
            triplets_avant_hitl += 1

    # Mots-clés → expertise
    for kw in keywords:
        for author in authors:
            tx.run("""
                MERGE (t:Topic {name: $kw})
                WITH t
                MATCH (r:Researcher {name: $rname})
                MERGE (r)-[:A_POUR_EXPERTISE]->(t)
            """, kw=kw, rname=author)
            triplets_avant_hitl += 1

with driver.session() as session:
    for _, row in df.iterrows():
        session.execute_write(insert_article, row)

print(f"Ingestion terminée.")
print(f"Triplets créés (avant HITL) : {triplets_avant_hitl}")

# Statistiques Neo4j après ingestion
def get_graph_stats(tx):
    return {
        "articles"     : tx.run("MATCH (n:Article) RETURN count(n) AS n").single()["n"],
        "researchers"  : tx.run("MATCH (n:Researcher) RETURN count(n) AS n").single()["n"],
        "institutions" : tx.run("MATCH (n:Institution) RETURN count(n) AS n").single()["n"],
        "organizations": tx.run("MATCH (n:Organization) RETURN count(n) AS n").single()["n"],
        "topics"       : tx.run("MATCH (n:Topic) RETURN count(n) AS n").single()["n"],
        "triplets_total": tx.run("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"],
        "affilié_à"    : tx.run("MATCH ()-[r:AFFILIÉ_À]->() RETURN count(r) AS n").single()["n"],
        "partenaire_de": tx.run("MATCH ()-[r:PARTENAIRE_DE]->() RETURN count(r) AS n").single()["n"],
        "expertise"    : tx.run("MATCH ()-[r:A_POUR_EXPERTISE]->() RETURN count(r) AS n").single()["n"],
    }

with driver.session() as session:
    stats = session.execute_read(get_graph_stats)

print("\n── Graphe Neo4j après ingestion ──")
for k, v in stats.items():
    print(f"  {k:<20} : {v}")