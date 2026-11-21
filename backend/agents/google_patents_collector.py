"""
google_patents_collector.py
============================
Collecteur Google Patents via le dataset public SerpAPI ou l'API patent-client.

Deux modes d'accès (auto-détection selon .env) :
  Mode A — SerpAPI (recommandé, clé gratuite 100 req/mois)
            SERPAPI_KEY=votre_cle dans .env
            https://serpapi.com/google-patents-api

  Mode B — Scraping direct patents.google.com (sans clé, limité mais fonctionnel)
            Parseur HTML + headers Chrome pour contourner les protections légères.

Format de sortie standardisé :
{
    "Title": str,
    "Authors": list[str],         ← inventeurs
    "Affiliations": list[str],    ← déposants / assignees
    "Year": int,                  ← année de dépôt
    "Abstract": str,              ← abrégé du brevet
    "Source_URL": str,            ← lien Google Patents
}
"""
import asyncio
import os
import re
from typing import List, Dict, Any, Optional

import requests


SERPAPI_URL = "https://serpapi.com/search"
GOOGLE_PATENTS_SEARCH_URL = "https://patents.google.com/xhr/query"


# ────────────────────────────────────────────────────────────────────────────
# Mode A : SerpAPI
# ────────────────────────────────────────────────────────────────────────────

def _parse_serpapi_result(result: dict) -> Optional[Dict[str, Any]]:
    """Convertit un résultat SerpAPI (Google Patents) au format standardisé."""
    title = result.get("title", "").strip()
    if not title:
        return None

    # Inventeurs
    inventors_raw = result.get("inventor", result.get("inventors", ""))
    if isinstance(inventors_raw, list):
        authors_list = [str(i).strip() for i in inventors_raw if i]
    else:
        parts = re.split(r"[;,·]", str(inventors_raw))
        authors_list = [p.strip() for p in parts if p.strip()]

    # Déposant / Assignee
    assignee = result.get("assignee", result.get("owner", ""))
    affiliations_list = [assignee.strip()] if assignee and assignee.strip() else []

    # Année de priorité ou de dépôt
    priority_date = result.get("priority_date", result.get("filing_date", ""))
    grant_date = result.get("grant_date", "")
    pub_date = priority_date or grant_date or ""
    match = re.search(r"\b(19|20)\d{2}\b", str(pub_date))
    pub_year = int(match.group()) if match else 2020

    # Résumé / Snippet
    snippet = result.get("snippet", "").strip()
    abstract = snippet[:1500] if snippet else "Abrégé non disponible."

    # URL
    link = result.get("patent_link", result.get("link", ""))
    patent_id = result.get("patent_id", "")
    if not link and patent_id:
        link = f"https://patents.google.com/patent/{patent_id}"
    source_url = link or "https://patents.google.com"

    return {
        "Title": title,
        "Authors": authors_list,
        "Affiliations": affiliations_list,
        "Year": pub_year,
        "Abstract": abstract,
        "Source_URL": source_url,
    }


def _collect_via_serpapi(query: str, max_results: int, min_year: Optional[int], api_key: str) -> List[Dict[str, Any]]:
    """Collecte via SerpAPI (Mode A — recommandé)."""
    patents = []
    page = 0

    # Construire le filtre d'année pour SerpAPI
    year_filter = ""
    if min_year:
        year_filter = f"after:{min_year}-01-01"

    while len(patents) < max_results:
        params = {
            "engine": "google_patents",
            "q": f"{query} {year_filter}".strip(),
            "api_key": api_key,
            "start": page * 10,
            "num": min(10, max_results - len(patents)),
        }

        try:
            resp = requests.get(SERPAPI_URL, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[google_patents_collector] Erreur SerpAPI: {e}")
            break

        organic_results = data.get("organic_results", [])
        if not organic_results:
            break

        for result in organic_results:
            patent = _parse_serpapi_result(result)
            if patent:
                if min_year and patent["Year"] < min_year:
                    continue
                patents.append(patent)
                if len(patents) >= max_results:
                    break

        # Vérifier s'il y a une page suivante
        if not data.get("serpapi_pagination", {}).get("next"):
            break
        page += 1

    return patents


# ────────────────────────────────────────────────────────────────────────────
# Mode B : Scraping direct patents.google.com (fallback sans clé API)
# ────────────────────────────────────────────────────────────────────────────

def _collect_via_scraping(query: str, max_results: int, min_year: Optional[int]) -> List[Dict[str, Any]]:
    """
    Scraping de l'endpoint XHR interne de Google Patents.
    Fonctionne sans clé API mais est sujet aux changements de structure Google.
    """
    patents = []

    # Construire la requête avec filtre d'année
    q_parts = [query]
    if min_year:
        q_parts.append(f"after:{min_year}-01-01")
    q_str = " ".join(q_parts)

    params = {
        "url": q_str,
        "exp": "",
        "id": "",
        "token": "",
        "query": q_str,
        "cursor": "",
        "page": "&page=0",
        "num_to_return": min(max_results, 50),
        "start": 0,
        "subset": "query",
        "have_data": "false",
        "lang": "ENGLISH",
        "scholar": "false",
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://patents.google.com/",
    }

    try:
        print(f"[google_patents_collector] Scraping Google Patents XHR: '{query}'")
        resp = requests.get(
            GOOGLE_PATENTS_SEARCH_URL,
            params=params,
            headers=headers,
            timeout=20
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[google_patents_collector] Erreur scraping Google Patents: {e}")
        return []

    clusters = data.get("results", {}).get("cluster", [])
    for cluster in clusters:
        for result in cluster.get("result", []):
            patent_info = result.get("patent", {})

            title = patent_info.get("title", "").strip()
            if not title:
                continue

            # Inventeurs
            inventors = [
                inv.get("name", "").strip()
                for inv in patent_info.get("inventor", [])
                if inv.get("name")
            ]

            # Assignees (déposants)
            assignees = [
                asg.get("name", "").strip()
                for asg in patent_info.get("assignee", [])
                if asg.get("name")
            ]

            # Année
            priority_date = patent_info.get("priority_date", patent_info.get("filing_date", ""))
            match = re.search(r"\b(19|20)\d{2}\b", str(priority_date))
            pub_year = int(match.group()) if match else 2020

            if min_year and pub_year < min_year:
                continue

            # Abrégé
            abstract = patent_info.get("abstract", "").strip()
            abstract = abstract[:1500] if abstract else "Abrégé non disponible."

            # URL
            patent_id = patent_info.get("publication_number", "")
            country_code = patent_info.get("country_code", "")
            source_url = (
                f"https://patents.google.com/patent/{patent_id}"
                if patent_id
                else "https://patents.google.com"
            )

            patents.append({
                "Title": title,
                "Authors": inventors,
                "Affiliations": assignees,
                "Year": pub_year,
                "Abstract": abstract,
                "Source_URL": source_url,
            })

            if len(patents) >= max_results:
                break

        if len(patents) >= max_results:
            break

    print(f"[google_patents_collector] {len(patents)} brevets via scraping pour '{query}'")
    return patents


# ────────────────────────────────────────────────────────────────────────────
# Fonction principale exportée
# ────────────────────────────────────────────────────────────────────────────

async def collect_google_patents(
    query: str,
    max_results: int = 50,
    min_year: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Collecte des brevets depuis Google Patents.

    Auto-sélectionne le mode selon la configuration :
      - Si SERPAPI_KEY est défini dans .env → Mode A (SerpAPI, recommandé)
      - Sinon → Mode B (scraping direct, limité mais sans clé)

    Paramètres
    ----------
    query : str
        Requête de recherche (mots-clés techniques en anglais).
    max_results : int
        Nombre maximum de brevets à collecter.
    min_year : int, optional
        Filtre : année de priorité/dépôt minimum.

    Retourne
    --------
    List[Dict[str, Any]]
        Brevets au format standardisé du pipeline.
    """
    api_key = os.environ.get("SERPAPI_KEY", "")
    loop = asyncio.get_event_loop()

    def _sync_collect():
        if api_key:
            print(f"[google_patents_collector] Mode SerpAPI activé pour '{query}'")
            return _collect_via_serpapi(query, max_results, min_year, api_key)
        else:
            print(f"[google_patents_collector] Mode scraping direct pour '{query}' (pas de SERPAPI_KEY)")
            return _collect_via_scraping(query, max_results, min_year)

    patents = await loop.run_in_executor(None, _sync_collect)
    print(f"[google_patents_collector] Total: {len(patents)} brevets collectés.")
    return patents
