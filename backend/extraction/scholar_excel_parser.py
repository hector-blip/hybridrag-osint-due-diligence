"""
scholar_excel_parser.py
=======================
Parseur pour les fichiers Excel issus de Google Scholar.
Supporte les exports semi-manuels (Publish or Perish, Zotero, BibTeX converti,
ou tout fichier Excel avec des colonnes standard Scholar).

Compatible avec les colonnes ajoutées manuellement par l'utilisateur :
- Toute colonne inconnue est préservée dans le champ `extra_metadata`
  afin de ne pas perdre les annotations du directeur de recherche.

Format de sortie standardisé (identique aux autres parseurs) :
{
    "Title": str,
    "Authors": list[str],
    "Affiliations": list[str],
    "Year": int,
    "Abstract": str,
    "Source_URL": str,
    "extra_metadata": dict   ← colonnes supplémentaires ajoutées manuellement
}
"""
import io
import re
import pandas as pd
from typing import List, Dict, Any, Optional


# ─── Correspondances de colonnes connues (insensible à la casse) ─────────────
# Chaque groupe de synonymes correspond à un champ standardisé.
COLUMN_MAP = {
    "title": [
        "title", "titre", "article title", "document title", "paper title",
        "name", "nom", "intitulé"
    ],
    "authors": [
        "authors", "author", "auteurs", "auteur", "full author names",
        "au", "af", "creator", "créateur"
    ],
    "affiliations": [
        "affiliations", "affiliation", "institution", "institutions",
        "organization", "organisations", "address", "addresses",
        "c1", "university", "universities"
    ],
    "year": [
        "year", "année", "pub year", "publication year", "py",
        "date", "published", "publié"
    ],
    "abstract": [
        "abstract", "résumé", "resume", "summary", "description",
        "ab", "excerpt", "extrait"
    ],
    "doi": [
        "doi", "digital object identifier", "di", "doi or weblink", "doi or link", "doi/link"
    ],
    "url": [
        "url", "link", "lien", "source url", "source", "cites",
        "gs_id", "scholar_url", "gsid", "gs url", "doi or weblink", "doi or link", "doi/link", "weblink", "web link"
    ],
    "journal": [
        "journal", "revue", "source", "publication", "periodical",
        "venue", "container-title"
    ],
    "citations": [
        "cites", "cited by", "citations", "citedby", "nb citations",
        "nombre de citations", "citation count", "cité par"
    ],
    "type": [
        "type", "document type", "article type", "genre"
    ],
}

# Champs standardisés « connus » (ne seront pas versés dans extra_metadata)
KNOWN_STANDARD_FIELDS = set(COLUMN_MAP.keys())


def _build_column_index(df: pd.DataFrame) -> Dict[str, str]:
    """
    Construit un index {champ_standardisé: nom_colonne_réelle} 
    et un index {nom_colonne_réelle_lower: nom_colonne_réelle} pour extra_metadata.
    """
    standard_index = {}   # champ_std → colonne_réelle
    all_cols_lower = {}   # col_lower → col_réelle

    for col in df.columns:
        col_lower = str(col).lower().strip()
        all_cols_lower[col_lower] = col

        for std_field, synonyms in COLUMN_MAP.items():
            if std_field not in standard_index:
                if col_lower in synonyms:
                    standard_index[std_field] = col
                    break

    return standard_index, all_cols_lower


def _get_val(row: pd.Series, col_name: Optional[str]) -> Optional[Any]:
    """Récupère une valeur de façon sûre, retourne None si NaN/vide."""
    if col_name is None:
        return None
    val = row.get(col_name)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    sval = str(val).strip()
    return sval if sval else None


def _parse_authors(raw: str) -> List[str]:
    """
    Divise une chaîne d'auteurs en liste.
    Supporte les séparateurs : ' ; ', ' and ', ', ', ' & '.
    """
    if not raw:
        return []
    # Normalize separators
    text = raw.replace(" and ", ";").replace(" & ", ";")
    parts = re.split(r"[;|]", text)
    return [p.strip() for p in parts if p.strip()]


def _parse_affiliations(raw: str) -> List[str]:
    """
    Divise une chaîne d'affiliations en liste unique.
    Les affiliations Google Scholar sont souvent séparées par ' ; '.
    """
    if not raw:
        return []
    parts = re.split(r"[;|]", raw)
    cleaned = []
    seen = set()
    for p in parts:
        p = p.strip()
        if p and p.lower() not in seen:
            cleaned.append(p)
            seen.add(p.lower())
    return cleaned


def _build_url(doi: Optional[str], url: Optional[str]) -> str:
    """Construit l'URL source avec ordre de priorité DOI > URL directe."""
    if doi:
        doi = doi.strip()
        # Si c'est déjà une URL complète
        if doi.startswith(("http://", "https://")):
            return doi
        
        # Si c'est un DOI brut
        doi_clean = doi
        for prefix in ["https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"]:
            if doi_clean.lower().startswith(prefix):
                doi_clean = doi_clean[len(prefix):]
                break
        return f"https://doi.org/{doi_clean}"
    if url:
        return url.strip()
    return "https://scholar.google.com"


def parse_scholar_excel(file_content: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Parse un fichier Excel ou CSV issu de Google Scholar (export semi-manuel
    depuis Publish or Perish, Zotero, ou tout outil compatible Scholar).

    Gère aussi les fichiers BibTeX convertis en Excel/CSV.

    Paramètres
    ----------
    file_content : bytes
        Contenu binaire du fichier.
    filename : str
        Nom du fichier (pour détecter l'extension).

    Retourne
    --------
    List[Dict[str, Any]]
        Liste d'articles au format standardisé du pipeline.
    """
    articles: List[Dict[str, Any]] = []

    # ── Chargement ────────────────────────────────────────────────────────────
    try:
        if filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_content), dtype=str)
        elif filename.lower().endswith(".csv"):
            # Essai UTF-8 puis latin-1 (encodages courants des exports Scholar)
            try:
                df = pd.read_csv(io.BytesIO(file_content), dtype=str, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(io.BytesIO(file_content), dtype=str, encoding="latin-1")
        else:
            # TSV ou TXT
            content_str = file_content.decode("utf-8", errors="ignore")
            df = pd.read_csv(io.StringIO(content_str), sep="\t", dtype=str)
    except Exception as e:
        print(f"[scholar_excel_parser] Erreur de lecture du fichier '{filename}': {e}")
        return []

    if df is None or df.empty:
        print(f"[scholar_excel_parser] Fichier vide : '{filename}'")
        return []

    # Nettoyage des noms de colonnes (trim whitespace)
    df.columns = [str(c).strip() for c in df.columns]

    # ── Indexation des colonnes ───────────────────────────────────────────────
    standard_idx, all_cols_lower = _build_column_index(df)

    # Colonnes supplémentaires (non-standard) = annotations manuelles du directeur
    known_col_names_lower = set()
    for std_field, synonyms in COLUMN_MAP.items():
        if std_field in standard_idx:
            known_col_names_lower.add(standard_idx[std_field].lower().strip())

    extra_columns = [
        col for col in df.columns
        if col.lower().strip() not in known_col_names_lower
    ]

    if extra_columns:
        print(f"[scholar_excel_parser] Colonnes supplémentaires détectées (annotations manuelles): {extra_columns}")

    # ── Parcours des lignes ───────────────────────────────────────────────────
    skipped = 0
    for _, row in df.iterrows():
        title = _get_val(row, standard_idx.get("title"))
        if not title or title.lower() in ("title", "titre", "nan"):
            skipped += 1
            continue

        # Auteurs
        authors_raw = _get_val(row, standard_idx.get("authors"))
        authors_list = _parse_authors(authors_raw) if authors_raw else []

        # Affiliations
        affil_raw = _get_val(row, standard_idx.get("affiliations"))
        affiliations_list = _parse_affiliations(affil_raw) if affil_raw else []

        # Année
        year_raw = _get_val(row, standard_idx.get("year"))
        try:
            # Extrait 4 chiffres de n'importe quel format de date
            match = re.search(r"\b(19|20)\d{2}\b", str(year_raw or ""))
            pub_year = int(match.group()) if match else 2020
        except (ValueError, AttributeError):
            pub_year = 2020

        # Résumé
        abstract_raw = _get_val(row, standard_idx.get("abstract"))
        abstract = str(abstract_raw)[:1500] if abstract_raw else "Résumé non disponible."

        # URL / DOI
        doi_raw = _get_val(row, standard_idx.get("doi"))
        url_raw = _get_val(row, standard_idx.get("url"))
        source_url = _build_url(doi_raw, url_raw)

        # Journal
        journal = _get_val(row, standard_idx.get("journal"))

        # Métadonnées additionnelles (colonnes non standard / annotations manuelles)
        extra_meta: Dict[str, str] = {}
        for extra_col in extra_columns:
            val = _get_val(row, extra_col)
            if val:
                extra_meta[extra_col] = val

        articles.append({
            "Title": title.strip(),
            "Authors": authors_list,
            "Affiliations": affiliations_list,
            "Year": pub_year,
            "Abstract": abstract,
            "Source_URL": source_url,
            "Journal": journal or "",
            "extra_metadata": extra_meta,   # conserve les annotations du directeur
        })

    print(f"[scholar_excel_parser] {len(articles)} articles parsés ({skipped} lignes ignorées) depuis '{filename}'")
    return articles
