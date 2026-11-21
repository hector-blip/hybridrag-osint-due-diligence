import sys
# Force UTF-8 sur Windows (évite l'erreur charmap avec les caractères Unicode des abstracts)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form
from backend.models import MissionRequest, ValidationPayload, Triplet
from backend.agents.collection import run_osint_mission
from backend.database.neo4j_client import graph_db
from backend.rag.graph_rag import ask_graph_rag
from backend.extraction.wos_parser import parse_wos_file
from backend.extraction.scholar_excel_parser import parse_scholar_excel
import uuid

app = FastAPI(
    title="Scientific Due Diligence API",
    description="Backend engine for OSINT collection and Knowledge Graph extraction",
    version="2.0.0"
)

# In-memory store for mission results (prototype only)
missions_db = {}


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint existant — Collecte en ligne OpenAlex
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/mission/start")
async def start_mission(request: MissionRequest, background_tasks: BackgroundTasks):
    mission_id = str(uuid.uuid4())
    missions_db[mission_id] = {"status": "running", "results": [], "source": "OpenAlex"}

    async def process_mission(m_id, req):
        try:
            triplets = await run_osint_mission(
                need_description=req.need_description,
                sources=req.sources,
                min_year=req.min_year,
                extraction_rules=req.extraction_rules,
                max_docs=req.max_documents
            )
            missions_db[m_id]["status"] = "completed"
            missions_db[m_id]["results"] = [t.dict() for t in triplets]
        except Exception as e:
            missions_db[m_id]["status"] = "failed"
            missions_db[m_id]["error"] = str(e)

    background_tasks.add_task(process_mission, mission_id, request)
    return {
        "mission_id": mission_id,
        "status": "started",
        "message": f"Mission for '{request.need_description}' launched."
    }


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint existant — Import Web of Science (fichier .txt/.xlsx)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/mission/start-wos")
async def start_mission_wos(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    need_description: str = Form(...),
    extraction_rules: str = Form(...),
    max_documents: int = Form(100)
):
    content = await file.read()
    articles = parse_wos_file(content, file.filename)
    if not articles:
        return {
            "status": "error",
            "message": "Le fichier Web of Science est vide ou n'a pas pu être analysé."
        }

    mission_id = str(uuid.uuid4())
    missions_db[mission_id] = {"status": "running", "results": [], "source": "Web of Science"}

    rules_list = [r.strip() for r in extraction_rules.split("\n") if r.strip()]

    async def process_mission(m_id, need_desc, rules, max_docs, raw_articles):
        try:
            triplets = await run_osint_mission(
                need_description=need_desc,
                sources=["Web of Science"],
                min_year=2020,
                extraction_rules=rules,
                max_docs=max_docs,
                precollected_articles=raw_articles
            )
            missions_db[m_id]["status"] = "completed"
            missions_db[m_id]["results"] = [t.dict() for t in triplets]
        except Exception as e:
            missions_db[m_id]["status"] = "failed"
            missions_db[m_id]["error"] = str(e)

    background_tasks.add_task(process_mission, mission_id, need_description, rules_list, max_documents, articles)
    return {
        "mission_id": mission_id,
        "status": "started",
        "message": f"Mission d'import Web of Science ({len(articles)} articles) lancée."
    }


# ─────────────────────────────────────────────────────────────────────────────
# NOUVEAU — Import Google Scholar (fichier Excel semi-manuel)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/mission/start-scholar-excel")
async def start_mission_scholar_excel(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    need_description: str = Form(...),
    extraction_rules: str = Form(...),
    max_documents: int = Form(200)
):
    """
    Endpoint pour l'import du fichier Excel Google Scholar généré semi-manuellement.
    Compatible avec les exports Publish or Perish, Zotero, et tout Excel Scholar.
    Les colonnes supplémentaires ajoutées manuellement sont automatiquement détectées
    et intégrées comme contexte supplémentaire pour le LLM.
    """
    content = await file.read()
    articles = parse_scholar_excel(content, file.filename)

    if not articles:
        return {
            "status": "error",
            "message": "Le fichier Google Scholar est vide ou n'a pas pu être analysé. "
                       "Vérifiez le format (Excel .xlsx, .csv ou .tsv)."
        }

    mission_id = str(uuid.uuid4())
    missions_db[mission_id] = {
        "status": "running",
        "results": [],
        "source": "Google Scholar (Excel)",
        "article_count": len(articles)
    }

    rules_list = [r.strip() for r in extraction_rules.split("\n") if r.strip()]

    async def process_mission(m_id, need_desc, rules, max_docs, raw_articles):
        try:
            triplets = await run_osint_mission(
                need_description=need_desc,
                sources=["Google Scholar"],
                min_year=2000,
                extraction_rules=rules,
                max_docs=max_docs,
                precollected_articles=raw_articles
            )
            missions_db[m_id]["status"] = "completed"
            missions_db[m_id]["results"] = [t.dict() for t in triplets]
        except Exception as e:
            missions_db[m_id]["status"] = "failed"
            missions_db[m_id]["error"] = str(e)

    background_tasks.add_task(
        process_mission, mission_id, need_description, rules_list, max_documents, articles
    )
    return {
        "mission_id": mission_id,
        "status": "started",
        "article_count": len(articles),
        "message": f"Mission Google Scholar Excel ({len(articles)} articles détectés) lancée."
    }


# ─────────────────────────────────────────────────────────────────────────────
# NOUVEAU — Collecte en ligne multi-sources Google (Scholar + Books + Patents)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/mission/start-google")
async def start_mission_google(
    background_tasks: BackgroundTasks,
    need_description: str = Form(...),
    extraction_rules: str = Form(...),
    max_documents: int = Form(100),
    include_scholar: bool = Form(True),
    include_books: bool = Form(True),
    include_patents: bool = Form(True),
    min_year: int = Form(2019)
):
    """
    Endpoint pour la collecte en ligne combinée :
    Google Scholar + Google Books + Google Patents en parallèle.

    Configuration .env requise (optionnelle mais recommandée) :
        GOOGLE_API_KEY=...   pour Google Books (quotas élevés)
        SERPAPI_KEY=...      pour Google Patents (mode SerpAPI)
        SCHOLAR_PROXY_API_KEY=...  pour Google Scholar (éviter les CAPTCHA)
    """
    sources = []
    if include_scholar:
        sources.append("Google Scholar")
    if include_books:
        sources.append("Google Books")
    if include_patents:
        sources.append("Google Patents")

    if not sources:
        return {
            "status": "error",
            "message": "Sélectionnez au moins une source Google (Scholar, Books ou Patents)."
        }

    mission_id = str(uuid.uuid4())
    missions_db[mission_id] = {
        "status": "running",
        "results": [],
        "source": " + ".join(sources),
        "article_count": 0
    }

    rules_list = [r.strip() for r in extraction_rules.split("\n") if r.strip()]

    async def process_mission(m_id, need_desc, srcs, rules, max_docs, yr):
        try:
            triplets = await run_osint_mission(
                need_description=need_desc,
                sources=srcs,
                min_year=yr,
                extraction_rules=rules,
                max_docs=max_docs
            )
            missions_db[m_id]["status"] = "completed"
            missions_db[m_id]["results"] = [t.dict() for t in triplets]
        except Exception as e:
            missions_db[m_id]["status"] = "failed"
            missions_db[m_id]["error"] = str(e)

    background_tasks.add_task(
        process_mission, mission_id, need_description, sources, rules_list, max_documents, min_year
    )
    return {
        "mission_id": mission_id,
        "status": "started",
        "sources": sources,
        "message": f"Mission Google multi-sources ({', '.join(sources)}) lancée pour : '{need_description}'"
    }


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints existants — Résultats, Ingestion Neo4j, GraphRAG
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/mission/{mission_id}/results")
async def get_mission_results(mission_id: str):
    if mission_id not in missions_db:
        return {"mission_id": mission_id, "status": "not_found", "results": []}

    response = {
        "mission_id": mission_id,
        "status": missions_db[mission_id]["status"],
        "results": missions_db[mission_id]["results"],
        "source": missions_db[mission_id].get("source", ""),
    }
    if "error" in missions_db[mission_id]:
        response["error"] = missions_db[mission_id]["error"]

    return response


@app.post("/api/graph/ingest")
async def ingest_validated_data(payload: ValidationPayload):
    try:
        # Récupère la source de la mission depuis missions_db
        mission_info = missions_db.get(payload.mission_id, {})
        source = mission_info.get("source", "unknown")

        success = graph_db.ingest_triplets(
            payload.validated_triplets,
            mission_id=payload.mission_id,
            source=source
        )
        if success:
            return {
                "status": "success",
                "message": f"{len(payload.validated_triplets)} profils ingérés dans Neo4j avec succès !"
            }
        else:
            return {
                "status": "warning",
                "message": "Validé avec succès, mais Neo4j local n'est pas connecté. (Vérifiez le .env)"
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/graph/missions")
async def list_ingested_missions():
    """Liste toutes les missions déjà ingérées dans Neo4j, avec leur source et statistiques."""
    try:
        missions = graph_db.list_missions()
        return {"status": "success", "missions": missions, "count": len(missions)}
    except Exception as e:
        return {"status": "error", "message": str(e), "missions": []}


@app.get("/api/graph/mission/{mission_id}")
async def get_mission_graph(mission_id: str, limit: int = 200):
    """Retourne les triplets d'une mission spécifique depuis Neo4j (pour filtrage dans le dashboard)."""
    try:
        records = graph_db.get_mission_graph(mission_id, limit=limit)
        return {"status": "success", "mission_id": mission_id, "records": records, "count": len(records)}
    except Exception as e:
        return {"status": "error", "message": str(e), "records": []}


@app.get("/api/graph/stats")
async def get_graph_stats():
    """Retourne les statistiques globales du graphe Neo4j (nombre de nœuds par type)."""
    try:
        stats = graph_db.get_graph_stats()
        return {"status": "success", "stats": stats}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/graph/rag")
async def query_graph_rag(query: str):
    try:
        response_dict = ask_graph_rag(query)
        return response_dict
    except Exception as e:
        return {"answer": f"Erreur critique lors de l'exécution du GraphRAG : {e}", "sources": []}


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint utilitaire — Infos sur une mission (source, nombre d'articles, etc.)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/mission/{mission_id}/info")
async def get_mission_info(mission_id: str):
    """Retourne les métadonnées d'une mission (source, statut, compteurs)."""
    if mission_id not in missions_db:
        return {"mission_id": mission_id, "status": "not_found"}
    m = missions_db[mission_id]
    return {
        "mission_id": mission_id,
        "status": m.get("status"),
        "source": m.get("source", "Unknown"),
        "article_count": m.get("article_count", 0),
        "triplet_count": len(m.get("results", [])),
    }
