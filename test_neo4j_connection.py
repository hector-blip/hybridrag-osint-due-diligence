"""
Test de connexion Neo4j — à exécuter APRÈS avoir démarré le DBMS dans Neo4j Desktop
"""
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

BOLT_URL = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER     = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")  # défini dans .env

try:
    driver = GraphDatabase.driver(BOLT_URL, auth=(USER, PASSWORD))
    driver.verify_connectivity()
    print("✅ Connexion Neo4j réussie !")
    driver.close()
except Exception as e:
    print(f"❌ Échec de connexion : {e}")
