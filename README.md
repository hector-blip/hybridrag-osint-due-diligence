# HybridRAG OSINT : LLM et graphe de connaissances pour la due diligence scientifique

Prototype développé dans le cadre de mon mémoire de maîtrise en sciences et technologies de l'information (Université du Québec en Outaouais, 2026) :

> *Approche hybride LLM et graphe de connaissances pour la due diligence OSINT des projets de recherche sensibles : application au secteur des batteries.*

Le système collecte des publications scientifiques, en extrait des entités et des relations avec un LLM encadré par des schémas stricts, les fait valider par un humain, puis les stocke dans un graphe Neo4j interrogeable en langage naturel (GraphRAG).

## Architecture

```
Frontend (Streamlit)  <-->  Backend (FastAPI / Uvicorn)  <-->  Neo4j (graphe)
   frontend/app.py              backend/main.py              backend/database/
                                      |
                 +--------------------+--------------------+
                 |                    |                    |
           Collecteurs           Extraction LLM         GraphRAG
         backend/agents/       backend/extraction/    backend/rag/
```

1. **Collecte** multi-sources : OpenAlex, exports Web of Science, exports Google Scholar (Publish or Perish, Zotero), Google Scholar, Google Books, Google Patents.
2. **Extraction** des triplets avec LangChain et GPT-4o-mini en *structured output*, contraint par des modèles Pydantic.
3. **Validation humaine** (*Human-in-the-Loop*) dans l'interface Streamlit, avec visualisation du graphe (streamlit-agraph).
4. **Ingestion** dans Neo4j via Cypher, puis **interrogation GraphRAG**.
5. **Croisement** des organisations avec la base industrielle NAATBatt (`backend/database/naatbatt_db.json`).

## Évaluation (dossier `test/`)

- Comparaison de quatre configurations (VectorRAG, GraphRAG, Hybride sans HITL, Hybride avec HITL) avec le framework **RAGAS** : `run_ragas.py`, scores dans `scores_C*.csv` et `ragas_results.json`.
- Test statistique de Wilcoxon : `wilcoxon_test.py`.
- Accord inter-annotateurs entre un expert humain et un agent LLM : `annotation_agent.py`, `annotations_agent.csv`.

Principal résultat du mémoire : sur ce corpus, l'architecture HybridRAG n'améliore pas significativement les performances par rapport au VectorRAG seul. La richesse structurelle des fragments de texte neutralise l'avantage du graphe.

## Installation

Prérequis : Python 3.13, une base Neo4j (Neo4j Desktop ou AuraDB) et une clé API OpenAI.

```bash
python -m venv venv
venv\Scripts\activate        # Windows  (macOS / Linux : source venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env         # puis remplir les valeurs
```

## Lancement

Depuis la racine du projet, dans deux terminaux :

```bash
uvicorn backend.main:app --reload --port 8000
```

```bash
streamlit run frontend/app.py
```

## Données

Les données brutes (corpus, index FAISS, fichiers Excel sources) ne sont pas publiées. `exemple_import_wos.xlsx` montre le format d'import attendu, et `create_exemple_excel.py` permet d'en générer un.

## Technologies

Python · FastAPI · LangChain · OpenAI GPT-4o-mini · Pydantic · Neo4j / Cypher · Streamlit · RAGAS · FAISS · Pandas

## Auteur

Georges-Hector Amoussou · [LinkedIn](https://www.linkedin.com/in/georges-hector-amoussou/)
