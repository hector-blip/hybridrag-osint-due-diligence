# 🔬 Résumé des Fonctionnalités — Scientific Due Diligence V9

> **Prototype OSINT & Knowledge Graph** pour l'identification d'experts et la cartographie de la chaîne de valeur scientifique et industrielle (cas d'usage : batteries lithium-ion / état solide).

---

## 🏗️ Architecture Générale

```
Frontend (Streamlit)  ←→  Backend (FastAPI/Uvicorn)  ←→  Neo4j (Graph DB)
       app.py                     main.py                  neo4j_client.py
                                     │
                          ┌──────────┼───────────────────┐
                          │          │                   │
                     Collecteurs   Parseurs            GraphRAG
                   (agents/)    (extraction/)          (rag/)
```

Le pipeline suit 3 étapes principales :
1. **Collecte** des documents scientifiques (multi-sources)
2. **Extraction LLM** + **Validation humaine** (Human-in-the-Loop)
3. **Ingestion Neo4j** + **Interrogation GraphRAG**

---

## 📥 1. Sources de Collecte (Multi-Sources)

### 1.1 OpenAlex (en ligne, par défaut)
- **Fichier** : `backend/agents/collection.py` → `_collect_openalex()`
- Collecte via l'API publique OpenAlex (gratuite, sans clé)
- Couvre : **arXiv, PubMed, CrossRef** et autres dépôts indexés
- Filtre par année de publication (`min_year`)
- Reconstruit les abstracts depuis l'index inversé de l'API
- Extrait auteurs, affiliations institutionnelles, DOI

### 1.2 Import Web of Science (fichier)
- **Fichier** : `backend/extraction/wos_parser.py`
- Parseur de fichiers d'export Clarivate WoS
- Formats supportés : `.txt` (tab-délimité), `.tsv`, `.xlsx`, `.xls`, `.csv`
- Détection dynamique de la ligne d'en-tête (skiprows auto)
- Parsing du champ C1 (affiliations avec auteurs entre crochets)
- Mapping insensible à la casse (tags WoS : TI, AU, C1, AB, PY, DI, UT)
- Construction de l'URL source (DOI prioritaire, puis ID WoS)

### 1.3 Import Google Scholar Excel (semi-manuel)
- **Fichier** : `backend/extraction/scholar_excel_parser.py`
- Compatible : exports **Publish or Perish**, **Zotero**, **BibTeX converti**
- Formats supportés : `.xlsx`, `.xls`, `.csv`, `.tsv`
- Mapping de colonnes par synonymes (insensible à la casse, FR + EN)
- **Fonctionnalité clé** : détection et préservation des **colonnes supplémentaires** ajoutées manuellement par le chercheur (ex: annotations du directeur de thèse) → intégrées dans `extra_metadata` et injectées dans l'abstract envoyé au LLM
- Parsing intelligent des auteurs (séparateurs : `;`, ` and `, `&`)
- Encodage UTF-8 et latin-1 (exports Scholar)
- Aperçu du fichier avant soumission dans l'interface

### 1.4 Google Scholar (scraping en ligne)
- **Fichier** : `backend/agents/google_scholar_collector.py`
- Via la bibliothèque `scholarly` (scraping non officiel)
- Rate-limiting intégré : délai de 3s + aléatoire (±1s) entre requêtes
- Support proxy optionnel via **ScraperAPI** (variable `SCHOLAR_PROXY_API_KEY`)
- Filtre par année, max 100-200 articles conseillé
- Exécution asynchrone dans un thread pool (ne bloque pas FastAPI)

### 1.5 Google Books (API officielle)
- **Fichier** : `backend/agents/google_books_collector.py`
- API officielle Google Books (`googleapis.com/books/v1/volumes`)
- Clé API optionnelle (`GOOGLE_API_KEY`) → quotas 10 req/j sans clé, 1000 avec
- Pagination automatique (max 40 résultats par appel)
- Inclut : titre + sous-titre, auteurs, description, éditeur (comme affiliation)
- Filtre par année de publication

### 1.6 Google Patents (2 modes)
- **Fichier** : `backend/agents/google_patents_collector.py`
- **Mode A — SerpAPI** (si `SERPAPI_KEY` défini) : API fiable, 100 req/mois gratuit
- **Mode B — Scraping XHR direct** (fallback sans clé) : endpoint interne `patents.google.com/xhr/query`
- Extrait : inventeurs (Authors), déposants/assignees (Affiliations), abrégé, date de priorité
- Filtre par date de dépôt (`after:YYYY-01-01`)

---

## ⚙️ 2. Orchestration & Normalisation

### 2.1 Orchestrateur central
- **Fichier** : `backend/agents/collection.py` → `run_osint_mission()`
- **Mode Import** : si des articles pré-collectés sont fournis (WoS, Scholar Excel)
- **Mode Collecte en ligne** : lance les sources sélectionnées en **parallèle** (`asyncio.gather`)
- Normalisation de tous les articles au format unifié (`_normalize_article()`) :
  - Champs : Title, Authors, Affiliations, Year, Abstract, Source_URL, Journal
  - Les `extra_metadata` (annotations Scholar) sont injectées dans l'abstract

### 2.2 Modèles de données
- **Fichier** : `backend/models.py`
- `MissionRequest` : besoin de recherche, sources, année min, règles LLM, max documents
- `Triplet` : sujet, type sujet, relation, objet, type objet, justification, score de confiance, URL source, statut NAATBatt
- `ValidationPayload` : identifiant de mission + liste de triplets validés

---

## 🤖 3. Extraction par LLM (GPT-4o-mini)

### 3.1 Parser LLM asynchrone avec batching
- **Fichier** : `backend/extraction/llm_parser.py`
- Modèle : **GPT-4o-mini** via LangChain + OpenAI
- **Batching** : 15 articles par lot, jusqu'à 5 lots en parallèle (contrôle via `asyncio.Semaphore`)
- **Structured Output** : sorties Pydantic validées (évite les hallucinations de format)
- **Prompt système** :
  - Lit la description du besoin + les règles d'extraction strictes définies par l'utilisateur
  - Identifie les auteurs pertinents dans les articles
  - Génère des triplets de connaissance obligatoires et recommandés

### 3.2 Triplets générés par le LLM
| Triplet | Description |
|---------|-------------|
| `(Auteur) -[AFFILIÉ_À]→ (Institution)` | Lien affiliation (obligatoire) |
| `(Auteur) -[A_POUR_EXPERTISE]→ (Concept)` | Domaine d'expertise (obligatoire) |
| `(Auteur) -[PARTENAIRE_DE]→ (Partenaire/Financement)` | Partenariat ou source de financement (recommandé) |
| `(Auteur) -[TRAVAILLE_SUR]→ (Mot-clé)` | Thématique de recherche (recommandé) |
| `(Auteur) -[PUBLIÉ_DANS]→ (Journal)` | Revue de publication (recommandé) |

### 3.3 Vérificateur NLI (Anti-hallucination)
- **Fichier** : `backend/extraction/nli_verifier.py`
- Modèle local : **DeBERTa-v3-small** (cross-encoder NLI via HuggingFace)
- Calcule un score de **vraisemblance mathématique** (score d'entailment Softmax)
- Traduit les relations métier (françaises) en hypothèses anglaises pour le modèle
- Vérifie que l'abstract soutient réellement le triplet extrait

---

## ✅ 4. Validation Industrielle — Base NAATBatt

- **Fichiers** : `backend/database/naatbatt.py` + `backend/database/naatbatt_db.json`
- Croisement automatique des **institutions/entreprises détectées** avec la **NAATBatt Lithium-Ion Battery Supply Chain Database (NLR/NREL)**
- Matching intelligent : suppression des suffixes légaux (Inc, Corp, Ltd...), matching par sous-chaîne
- Résultats :
  - ✅ **NAATBatt** : acteur validé de la chaîne de valeur nord-américaine (avec segment et localisation)
  - 🎓 **Academic Research** : institution académique reconnue (université, labo...)
  - 🌍 **International / Unlisted** : acteur non répertorié
- Recherche manuelle dans la sidebar (page Validation Humaine)

---

## 🖥️ 5. Interface Utilisateur (Streamlit)

- **Fichier** : `frontend/app.py`
- Architecture **3 pages** (navigation via sidebar) :

### Page 1 — Configuration de la Mission
4 onglets de collecte :
1. **🌐 OpenAlex (en ligne)** : requête libre, sélection multi-sources, filtre année, règles LLM personnalisées, budget documents (slider)
2. **📄 Import Web of Science** : upload fichier, paramétrage LLM
3. **📊 Import Google Scholar (Excel)** : upload + **aperçu du fichier avant soumission** (3 premières lignes)
4. **🔍 Collecte Google Multi-Sources** : checkboxes Scholar/Books/Patents, cartes visuelles descriptives par source

### Page 2 — Validation Humaine (Human-in-the-Loop)
- Affichage du statut de la mission (running / completed / failed)
- **Métriques de résumé** : nombre d'experts, triplets générés, institutions croisées NAATBatt
- **Table éditable** (`st.data_editor`) avec :
  - Case à cocher par triplet (validation individuelle)
  - Colonnes configurées : Expert, Type, Relation, Objet, Type Objet, Justification, Confiance, URL Source, Statut NAATBatt
- **Export CSV** des résultats
- **Ingestion sélective vers Neo4j** (uniquement les triplets cochés)
- Barre latérale : **recherche manuelle NAATBatt** en temps réel

### Page 3 — Dashboard & GraphRAG
- **Onglet Cartographie Visuelle** :
  - Graphe interactif (`streamlit-agraph`) avec physique ForceAtlas2
  - Nœuds colorés par type : 🔴 Auteurs, 🟡 Institutions, 🔵 Concepts, 🟣 Mots-clés, 💗 Partenaires, 🔹 Journaux
  - Formes distinctes par type (dot, triangle, star, diamond, square, hexagon)
  - Légende visuelle
- **Onglet GraphRAG (Chat)** :
  - Requête en langage naturel sur les données validées
  - Réponse générée **uniquement** depuis les relations Neo4j (anti-hallucination)
  - Citations des sources incluses dans la réponse

---

## 🗄️ 6. Base de Données Neo4j (Knowledge Graph)

### 6.1 Client Neo4j
- **Fichier** : `backend/database/neo4j_client.py`
- Connexion via Bolt (`bolt://localhost:7687`)
- **Ingestion par MERGE Cypher** : pas de doublons, idempotent
- Stocke sur chaque relation : score de confiance, justification, source URL
- Fallback gracieux si Neo4j est hors ligne (mode mock)

### 6.2 Script d'ingestion manuelle (données Excel)
- **Fichier** : `ingestNeoj.py`
- Import direct depuis `Excel-Data-Abbcari-Battery-materials.xlsx`
- Crée les nœuds : Article, Researcher, Institution, Organization, Topic
- Crée les relations : A_PUBLIÉ, AFFILIÉ_À, PARTENAIRE_DE, A_POUR_EXPERTISE
- Affiche les statistiques du graphe après ingestion

---

## 💬 7. GraphRAG (Retrieval-Augmented Generation)

- **Fichier** : `backend/rag/graph_rag.py`
- **Étape 1 — Retrieval** : requête Cypher sur les 200 dernières relations du graphe Neo4j
- **Étape 2 — Context Formulation** : conversion des triplets graphe en texte structuré pour le LLM
- **Étape 3 — Generation** : GPT-4o-mini répond **uniquement sur la base du contexte graphe**
  - Refuse explicitement de formuler des hypothèses externes
  - Cite les institutions et concepts d'expertise dans les réponses

---

## 🔌 8. API REST (FastAPI)

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/mission/start` | POST | Lance une mission OpenAlex (JSON) |
| `/api/mission/start-wos` | POST | Lance une mission WoS (multipart/form-data) |
| `/api/mission/start-scholar-excel` | POST | Lance une mission Scholar Excel (multipart/form-data) |
| `/api/mission/start-google` | POST | Lance une mission Google multi-sources (form-data) |
| `/api/mission/{id}/results` | GET | Récupère les triplets d'une mission |
| `/api/mission/{id}/info` | GET | Métadonnées de la mission (source, compteurs) |
| `/api/graph/ingest` | POST | Ingère les triplets validés dans Neo4j |
| `/api/graph/rag` | POST | Interroge le graphe via GraphRAG |

- Toutes les missions s'exécutent en **tâches de fond** (`BackgroundTasks` FastAPI)
- Stockage en mémoire (`missions_db`) — prototype uniquement

---

## 🔑 9. Configuration (.env)

| Variable | Usage |
|----------|-------|
| `OPENAI_API_KEY` | Clé OpenAI pour GPT-4o-mini (LLM extraction + RAG) |
| `NEO4J_URI` | URI de connexion Neo4j (défaut: `bolt://127.0.0.1:7687`) |
| `NEO4J_USER` | Utilisateur Neo4j |
| `NEO4J_PASSWORD` | Mot de passe Neo4j |
| `GOOGLE_API_KEY` | Google Books API (optionnel, augmente les quotas) |
| `SERPAPI_KEY` | SerpAPI pour Google Patents (optionnel, 100 req/mois gratuit) |
| `SCHOLAR_PROXY_API_KEY` | ScraperAPI pour Google Scholar (optionnel, évite les CAPTCHA) |

---

## 📊 10. Fichiers de Données & Tests

| Fichier | Description |
|---------|-------------|
| `Excel-Data-Abbcari-Battery-materials.xlsx` | Dataset principal (batterie matériaux, ingestion directe Neo4j) |
| `exemple_import_wos.xlsx` | Fichier exemple pour tester l'import WoS |
| `backend/database/naatbatt_db.json` | Base NAATBatt locale (chaîne de valeur batteries Amérique du Nord) |
| `test/wilcoxon_test.py` | Test statistique Wilcoxon (validation scientifique des scores) |
| `test_neo4j_connection.py` | Test de connectivité Neo4j |
| `test_wos_naatbatt.py` | Test du parseur WoS + validation NAATBatt |
| `create_exemple_excel.py` | Générateur de fichier Excel d'exemple Scholar |

---

## 🔄 Flux de Données Complet

```
1. Utilisateur définit le besoin (Page 1)
         ↓
2. Collecte multi-sources (OpenAlex / WoS / Scholar / Google)
         ↓
3. Normalisation des articles au format unifié
         ↓
4. LLM GPT-4o-mini extrait les triplets (par lots de 15, parallèle ×5)
         ↓
5. Validation NAATBatt automatique des institutions
         ↓
6. Utilisateur valide/édite les triplets (Page 2 — HITL)
         ↓
7. Ingestion des triplets validés dans Neo4j (MERGE Cypher)
         ↓
8. Visualisation graphe interactif + Interrogation GraphRAG (Page 3)
```
