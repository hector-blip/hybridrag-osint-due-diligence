"""
google_books_collector.py
==========================
Collecteur Google Books via l'API officielle Google Books API.

Documentation : https://developers.google.com/books/docs/v1/using
Endpoint       : https://www.googleapis.com/books/v1/volumes

Configuration .env :
    GOOGLE_API_KEY=AIza...   (optionnel — augmente les quotas de 10 à 1000 req/jour)
    Sans clé : mode public limité à ~10 requêtes/jour par IP.

Format de sortie standardisé (identique au reste du pipeline) :
{
    "Title": str,
    "Authors": list[str],
    "Affiliations": list[str],     ← toujours [] pour les livres (non disponible)
    "Year": int,
    "Abstract": str,               ← description ou snippet du livre
    "Source_URL": str,
}
"""
import asyncio
import os
import re
from typing import List, Dict, Any, Optional

import requests


GOOGLE_BOOKS_API_URL = "https://www.googleapis.com/books/v1/volumes"


def _extract_year(date_str: Optional[str]) -> int:
    """Extrait une année de 4 chiffres depuis une chaîne de date."""
    if not date_str:
        return 2020
    match = re.search(r"\b(19|20)\d{2}\b", str(date_str))
    return int(match.group()) if match else 2020


def _parse_book(item: dict) -> Optional[Dict[str, Any]]:
    """
    Convertit un résultat brut de l'API Google Books au format standardisé.
    """
    volume_info = item.get("volumeInfo", {})

    title = volume_info.get("title", "").strip()
    if not title:
        return None

    # Sous-titre inclus pour plus de contexte
    subtitle = volume_info.get("subtitle", "")
    if subtitle:
        title = f"{title} : {subtitle}"

    # Auteurs
    authors_list = volume_info.get("authors", [])

    # Résumé / Description
    description = volume_info.get("description", "").strip()
    if not description:
        description = volume_info.get("searchInfo", {}).get("textSnippet", "")
    if not description:
        description = "Description non disponible."
    description = description[:1500]

    # Année
    pub_date = volume_info.get("publishedDate", "")
    pub_year = _extract_year(pub_date)

    # URL de la page Google Books
    canonical_url = volume_info.get("canonicalVolumeLink", "")
    info_link = volume_info.get("infoLink", "")
    source_url = canonical_url or info_link or "https://books.google.com"

    # Identifiants (ISBN, Google Books ID)
    gb_id = item.get("id", "")
    if gb_id and not source_url:
        source_url = f"https://books.google.com/books?id={gb_id}"

    # Catégories / Publisher comme affiliations contextuelles
    publisher = volume_info.get("publisher", "")
    categories = volume_info.get("categories", [])
    affiliations_list = []
    if publisher:
        affiliations_list.append(publisher)

    return {
        "Title": title,
        "Authors": authors_list,
        "Affiliations": affiliations_list,
        "Year": pub_year,
        "Abstract": description,
        "Source_URL": source_url,
    }


async def collect_google_books(
    query: str,
    max_results: int = 40,
    min_year: Optional[int] = None,
    language_restrict: str = ""
) -> List[Dict[str, Any]]:
    """
    Collecte des livres depuis Google Books API.

    Paramètres
    ----------
    query : str
        Requête de recherche.
    max_results : int
        Nombre maximum de livres (max 40 par appel API, pagination automatique).
    min_year : int, optional
        Filtre : année de publication minimum.
    language_restrict : str
        Restreindre à une langue ('fr', 'en', etc.). Vide = toutes langues.

    Retourne
    --------
    List[Dict[str, Any]]
        Livres au format standardisé du pipeline.
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    loop = asyncio.get_event_loop()

    def _sync_collect():
        books = []
        start_index = 0
        batch_size = min(40, max_results)  # API limite à 40 par appel

        while len(books) < max_results:
            params = {
                "q": query,
                "maxResults": min(batch_size, max_results - len(books)),
                "startIndex": start_index,
                "printType": "books",
                "orderBy": "relevance",
            }
            if api_key:
                params["key"] = api_key
            if language_restrict:
                params["langRestrict"] = language_restrict

            try:
                print(f"[google_books_collector] Requête Books API: '{query}' (offset={start_index})")
                resp = requests.get(GOOGLE_BOOKS_API_URL, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"[google_books_collector] Erreur API Google Books: {e}")
                break

            items = data.get("items", [])
            if not items:
                print("[google_books_collector] Aucun résultat supplémentaire.")
                break

            for item in items:
                book = _parse_book(item)
                if not book:
                    continue

                # Filtre par année si demandé
                if min_year and book["Year"] < min_year:
                    continue

                books.append(book)

                if len(books) >= max_results:
                    break

            # Pagination
            total_items = data.get("totalItems", 0)
            start_index += batch_size
            if start_index >= total_items:
                break

        print(f"[google_books_collector] Total: {len(books)} livres collectés pour '{query}'")
        return books

    books = await loop.run_in_executor(None, _sync_collect)
    return books
