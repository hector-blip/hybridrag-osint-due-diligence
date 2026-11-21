"""
collection.py  (V9 — Multi-Sources étendu)
===========================================
Orchestrateur central de collecte OSINT.

Sources supportées :
  - "OpenAlex"          → API OpenAlex (collecte en ligne, existant)
  - "Web of Science"    → Import fichier (existant)
  - "Google Scholar"    → scholarly scraper (NOUVEAU)
  - "Google Books"      → Google Books API officielle (NOUVEAU)
  - "Google Patents"    → SerpAPI ou scraping direct (NOUVEAU)
  - "arXiv"             → Via OpenAlex (couvert)
  - "PubMed"            → Via OpenAlex (couvert)

Le format de sortie de TOUS les collecteurs est identique et
normalisé avant transmission au LLM parser.
"""
import asyncio
import json
import requests as req_lib
from typing import List, Dict, Any, Optional

from backend.extraction.llm_parser import extract_knowledge_async
from backend.models import Triplet
from backend.database.naatbatt import validate_entity


# ─── Collecteurs additionnels (imports conditionnels) ─────────────────────────
try:
    from backend.agents.google_scholar_collector import collect_google_scholar
    SCHOLAR_AVAILABLE = True
except ImportError:
    SCHOLAR_AVAILABLE = False

try:
    from backend.agents.google_books_collector import collect_google_books
    BOOKS_AVAILABLE = True
except ImportError:
    BOOKS_AVAILABLE = False

try:
    from backend.agents.google_patents_collector import collect_google_patents
    PATENTS_AVAILABLE = True
except ImportError:
    PATENTS_AVAILABLE = False


# ─── Normalisation du format entre sources ────────────────────────────────────

def _normalize_article(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Garantit que chaque article possède exactement les champs attendus
    par le LLM parser, quelle que soit la source d'origine.
    Le champ 'extra_metadata' (annotations manuelles Scholar Excel) est
    sérialisé en texte et ajouté à l'abstract pour enrichir le contexte LLM,
    et est également inclus sous forme de clés de premier niveau.
    """
    title = str(article.get("Title", "")).strip() or "Titre inconnu"
    authors = article.get("Authors", [])
    affiliations = article.get("Affiliations", [])
    year = int(article.get("Year", 2020))
    abstract = str(article.get("Abstract", "Résumé non disponible."))[:1500]
    source_url = str(article.get("Source_URL", "https://openalex.org"))
    journal = str(article.get("Journal", "")).strip()

    # Intégrer les annotations manuelles dans l'abstract pour le LLM
    extra = article.get("extra_metadata", {})
    if extra:
        extra_text = " | ".join(f"{k}: {v}" for k, v in extra.items())
        abstract = f"{abstract}\n\n[Annotations: {extra_text}]"[:1500]

    normalized = {
        "Title": title,
        "Authors": authors if isinstance(authors, list) else [authors],
        "Affiliations": affiliations if isinstance(affiliations, list) else [affiliations],
        "Year": year,
        "Abstract": abstract,
        "Source_URL": source_url,
    }
    if journal:
        normalized["Journal"] = journal

    # Inclure les champs additionnels d'extra_metadata pour un parsing LLM plus direct
    for k, v in extra.items():
        normalized[k] = v

    return normalized


# ─── Collecte OpenAlex (mode existant préservé) ───────────────────────────────

async def _collect_openalex(need_description: str, min_year: int, max_docs: int) -> List[Dict[str, Any]]:
    """Collecte via l'API OpenAlex (comportement d'origine, inchangé)."""
    url = "https://api.openalex.org/works"
    params = {
        "search": need_description,
        "filter": f"from_publication_date:{min_year}-01-01",
        "per-page": min(max_docs, 50),
    }

    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(
            None, lambda: req_lib.get(url, params=params, timeout=15)
        )
        response.raise_for_status()
        data = response.json()
        works = data.get("results", [])
    except Exception as e:
        print(f"[collection] Erreur OpenAlex: {e}")
        return []

    articles = []
    for work in works:
        title = work.get("title", "")
        if not title:
            continue

        authors_list, affiliations_set = [], set()
        for authorship in work.get("authorships", []):
            author_name = authorship.get("author", {}).get("display_name", "")
            if author_name:
                authors_list.append(author_name)
            for inst in authorship.get("institutions", []):
                inst_name = inst.get("display_name", "")
                if inst_name:
                    affiliations_set.add(inst_name)

        abstract = ""
        inverted = work.get("abstract_inverted_index")
        if inverted:
            words = []
            for word, positions in inverted.items():
                for pos in positions:
                    words.append((pos, word))
            words.sort(key=lambda x: x[0])
            abstract = " ".join([w[1] for w in words])
        else:
            abstract = "Abstract non fourni par l'API. Se fier au titre."

        doi_url = work.get("doi")
        fallback_url = work.get("id")
        articles.append({
            "Title": title,
            "Authors": authors_list,
            "Affiliations": list(affiliations_set),
            "Year": work.get("publication_year", min_year),
            "Abstract": abstract[:1500],
            "Source_URL": doi_url if doi_url else fallback_url,
        })

    print(f"[collection] OpenAlex: {len(articles)} articles collectés.")
    return articles


# ─── Fonction principale exportée ─────────────────────────────────────────────

async def run_osint_mission(
    need_description: str,
    sources: list,
    min_year: int,
    extraction_rules: list,
    max_docs: int,
    precollected_articles: Optional[List[Dict[str, Any]]] = None
) -> List[Triplet]:
    """
    Coordonne la collecte multi-sources et l'extraction LLM.

    Modes :
      - Si precollected_articles fourni → Mode Import (WoS ou Scholar Excel)
      - Sinon → Mode Collecte en ligne selon `sources`

    Paramètres
    ----------
    need_description : str
        Description du besoin de recherche (envoyée au LLM).
    sources : list
        Parmi : ["OpenAlex", "Google Scholar", "Google Books",
                 "Google Patents", "Web of Science", "arXiv", "PubMed"]
    min_year : int
        Année de publication minimum pour le filtrage.
    extraction_rules : list
        Directives LLM supplémentaires.
    max_docs : int
        Nombre maximum de documents à traiter.
    precollected_articles : list, optional
        Articles pré-collectés (import fichier WoS ou Scholar Excel).
    """

    # ── Mode Import (fichier pré-parsé) ────────────────────────────────────
    if precollected_articles is not None:
        print(f"[collection] Mode Import: {len(precollected_articles)} articles pré-collectés "
              f"pour le besoin: '{need_description}'")
        articles = [_normalize_article(a) for a in precollected_articles[:max_docs]]

    # ── Mode Collecte en ligne ──────────────────────────────────────────────
    else:
        print(f"[collection] Mode Collecte en ligne | Sources: {sources} | "
              f"Besoin: '{need_description}' | Depuis: {min_year}")

        collected_articles: List[Dict[str, Any]] = []
        tasks = []

        # OpenAlex (inclut arXiv, PubMed)
        if any(s in sources for s in ["OpenAlex", "arXiv", "PubMed"]):
            tasks.append(_collect_openalex(need_description, min_year, max_docs))

        # Google Scholar
        if "Google Scholar" in sources:
            if SCHOLAR_AVAILABLE:
                tasks.append(collect_google_scholar(
                    query=need_description,
                    max_results=min(max_docs, 100),
                    min_year=min_year,
                    rate_limit_seconds=3.0
                ))
            else:
                print("[collection] AVERTISSEMENT: scholarly non installé. "
                      "Ignoré pour 'Google Scholar'.")

        # Google Books
        if "Google Books" in sources:
            if BOOKS_AVAILABLE:
                tasks.append(collect_google_books(
                    query=need_description,
                    max_results=min(max_docs, 40),
                    min_year=min_year
                ))
            else:
                print("[collection] AVERTISSEMENT: Module Google Books non disponible.")

        # Google Patents
        if "Google Patents" in sources:
            if PATENTS_AVAILABLE:
                tasks.append(collect_google_patents(
                    query=need_description,
                    max_results=min(max_docs, 50),
                    min_year=min_year
                ))
            else:
                print("[collection] AVERTISSEMENT: Module Google Patents non disponible.")

        if not tasks:
            print("[collection] Aucune source valide sélectionnée.")
            return []

        # Exécution parallèle de toutes les sources sélectionnées
        results_per_source = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results_per_source:
            if isinstance(result, Exception):
                print(f"[collection] Erreur d'une source: {result}")
                continue
            if isinstance(result, list):
                collected_articles.extend(result)

        print(f"[collection] Total brut toutes sources: {len(collected_articles)} articles")
        articles = [_normalize_article(a) for a in collected_articles[:max_docs]]

    if not articles:
        print("[collection] Aucun article collecté. Pipeline arrêté.")
        return []

    # ── Extraction LLM (Stage B) — traitement par lots asynchrones ───────────
    print(f"[collection] {len(articles)} documents transmis au LLM (mode batching asynchrone)...")

    triplets = await extract_knowledge_async(articles, need_description, extraction_rules)

    # ── Validation NAATBatt post-extraction ────────────────────────────────
    for t in triplets:
        if not t.source_url or t.source_url == "unknown":
            t.source_url = "https://openalex.org"

        if t.object_type == "Institution":
            val_res = validate_entity(t.object)
            t.naatbatt_status = val_res["status_label"]
        else:
            t.naatbatt_status = "Not applicable (Skill/Concept)"

    print(f"[collection] Extraction terminée: {len(triplets)} triplets générés.")
    return triplets
