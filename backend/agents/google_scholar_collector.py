"""
google_scholar_collector.py
============================
Collecteur Google Scholar via la bibliothèque `scholarly`.

IMPORTANT — Limitations Google Scholar :
- Google Scholar n'a pas d'API officielle.
- `scholarly` fonctionne par scraping web avec délais aléatoires (rate-limiting).
- Google peut bloquer après ~100 requêtes consécutives rapides.
- Pour contourner : utiliser un proxy Tor ou ScraperAPI (optionnel, voir .env).
- Pour un mémoire : le mode direct (sans proxy) suffit pour des batches de 50-200.

Format de sortie standardisé (identique au reste du pipeline) :
{
    "Title": str,
    "Authors": list[str],
    "Affiliations": list[str],
    "Year": int,
    "Abstract": str,
    "Source_URL": str,
}
"""
import asyncio
import time
import random
from typing import List, Dict, Any, Optional

# ── Import conditionnel (scholarly n'est pas toujours installé) ───────────────
try:
    from scholarly import scholarly, ProxyGenerator
    SCHOLARLY_AVAILABLE = True
except ImportError:
    SCHOLARLY_AVAILABLE = False
    print("[google_scholar_collector] AVERTISSEMENT: 'scholarly' non installé. "
          "Lancez: pip install scholarly")


def _setup_proxy_if_configured():
    """
    Configure un proxy si SCHOLAR_PROXY_API_KEY est défini dans .env.
    Utilisé pour éviter les blocages CAPTCHA sur de grands volumes.
    """
    import os
    proxy_key = os.environ.get("SCHOLAR_PROXY_API_KEY", "")
    if proxy_key and SCHOLARLY_AVAILABLE:
        try:
            pg = ProxyGenerator()
            # ScraperAPI est le service le plus fiable pour Scholar
            pg.ScraperAPI(proxy_key)
            scholarly.use_proxy(pg)
            print("[google_scholar_collector] Proxy ScraperAPI configuré.")
        except Exception as e:
            print(f"[google_scholar_collector] Erreur proxy: {e}. Mode direct utilisé.")


def _extract_article(pub: dict, fallback_year: int = 2020) -> Optional[Dict[str, Any]]:
    """
    Convertit un résultat brut de `scholarly` au format standardisé du pipeline.
    """
    bib = pub.get("bib", {})

    title = bib.get("title", "").strip()
    if not title:
        return None

    # Auteurs
    authors_raw = bib.get("author", "")
    if isinstance(authors_raw, list):
        authors_list = [str(a).strip() for a in authors_raw if a]
    else:
        # Format "Dupont, A and Martin, B and ..."
        parts = str(authors_raw).replace(" and ", ";").split(";")
        authors_list = [p.strip() for p in parts if p.strip()]

    # Affiliations — scholarly ne retourne pas toujours les affiliations
    # On les reconstruit à partir de l'info auteur si disponible
    affiliations_list = []
    author_details = pub.get("author_info", [])
    if author_details:
        for ad in author_details:
            affil = ad.get("affiliation", "")
            if affil and affil not in affiliations_list:
                affiliations_list.append(affil)

    # Année
    year_raw = bib.get("pub_year", str(fallback_year))
    try:
        pub_year = int(str(year_raw).strip()[:4])
    except (ValueError, TypeError):
        pub_year = fallback_year

    # Résumé
    abstract = bib.get("abstract", "").strip()
    if not abstract:
        abstract = "Résumé non disponible depuis Google Scholar."
    abstract = abstract[:1500]

    # URL
    pub_url = pub.get("pub_url", "")
    eprint_url = pub.get("eprint_url", "")
    source_url = pub_url or eprint_url or "https://scholar.google.com"

    return {
        "Title": title,
        "Authors": authors_list,
        "Affiliations": affiliations_list,
        "Year": pub_year,
        "Abstract": abstract,
        "Source_URL": source_url,
    }


async def collect_google_scholar(
    query: str,
    max_results: int = 50,
    min_year: Optional[int] = None,
    rate_limit_seconds: float = 3.0
) -> List[Dict[str, Any]]:
    """
    Collecte des articles depuis Google Scholar via `scholarly`.

    Paramètres
    ----------
    query : str
        Requête de recherche (mots-clés en anglais recommandés).
    max_results : int
        Nombre maximum d'articles à collecter (défaut 50, max 200 conseillé).
    min_year : int, optional
        Filtre : année de publication minimum.
    rate_limit_seconds : float
        Délai de base entre requêtes (+ aléatoire ±1s). Défaut : 3.0s.

    Retourne
    --------
    List[Dict[str, Any]]
        Articles au format standardisé du pipeline.
    """
    if not SCHOLARLY_AVAILABLE:
        print("[google_scholar_collector] scholarly non disponible. Retour liste vide.")
        return []

    _setup_proxy_if_configured()

    articles: List[Dict[str, Any]] = []
    loop = asyncio.get_event_loop()

    def _sync_collect():
        """Exécuté dans un thread pool (scholarly est synchrone)."""
        collected = []
        try:
            print(f"[google_scholar_collector] Recherche Scholar: '{query}' (max {max_results})")
            search_gen = scholarly.search_pubs(query)

            for i, pub in enumerate(search_gen):
                if i >= max_results:
                    break

                # Filtre par année si demandé
                try:
                    pub_year = int(pub.get("bib", {}).get("pub_year", 0))
                except (ValueError, TypeError):
                    pub_year = 0

                if min_year and pub_year and pub_year < min_year:
                    continue

                article = _extract_article(pub, fallback_year=min_year or 2020)
                if article:
                    collected.append(article)

                # Rate limiting pour éviter les blocages CAPTCHA
                sleep_time = rate_limit_seconds + random.uniform(0.5, 1.5)
                time.sleep(sleep_time)

                if (i + 1) % 10 == 0:
                    print(f"[google_scholar_collector] {len(collected)} articles collectés...")

        except Exception as e:
            print(f"[google_scholar_collector] Erreur durant la collecte: {e}")

        print(f"[google_scholar_collector] Total: {len(collected)} articles collectés pour '{query}'")
        return collected

    # Exécuter la fonction synchrone dans un thread pour ne pas bloquer FastAPI async
    articles = await loop.run_in_executor(None, _sync_collect)
    return articles
