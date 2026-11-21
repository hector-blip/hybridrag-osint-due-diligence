import io
import re
import pandas as pd
from typing import List, Dict, Any

def parse_wos_affiliations(c1_text: str) -> List[str]:
    """
    Parses the Web of Science C1 (Author Addresses) field.
    Example: "[Smith, J.] MIT, Cambridge, MA USA; [Doe, A.] Stanford Univ, Stanford, CA USA"
    Returns: ['MIT, Cambridge, MA USA', 'Stanford Univ, Stanford, CA USA']
    """
    if not c1_text or pd.isna(c1_text):
        return []
    
    c1_str = str(c1_text)
    affiliations = []
    
    # Check if we have bracketed authors
    if "[" in c1_str and "]" in c1_str:
        # Regex to match address part after bracket
        # Matches: [author names] Address here
        matches = re.findall(r'\]\s*([^;]+)', c1_str)
        for m in matches:
            addr = m.strip()
            if addr:
                affiliations.append(addr)
    else:
        # Fallback to simple split by semicolon
        parts = c1_str.split(";")
        for p in parts:
            addr = p.strip()
            if addr:
                affiliations.append(addr)
                
    # Further clean affiliations (extracting institutional names where possible)
    cleaned_affils = []
    for aff in affiliations:
        # Just clean trailing/leading spaces and duplicate commas
        cleaned = re.sub(r'\s+', ' ', aff).strip()
        if cleaned:
            cleaned_affils.append(cleaned)
            
    return list(set(cleaned_affils))

def parse_wos_authors(au_text: str) -> List[str]:
    """
    Parses the Web of Science AU (Authors) field.
    Example: "Smith, John; Doe, Jane"
    Returns: ['Smith, John', 'Doe, Jane']
    """
    if not au_text or pd.isna(au_text):
        return []
    
    au_str = str(au_text)
    authors = []
    parts = au_str.split(";")
    for p in parts:
        author = p.strip()
        if author:
            authors.append(author)
    return authors

def parse_wos_file(file_content: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Parses Web of Science exported files (TXT/TSV, CSV, or XLSX).
    Returns a list of structured article dictionaries:
    [
        {
            "Title": str,
            "Authors": list[str],
            "Affiliations": list[str],
            "Year": int,
            "Abstract": str,
            "Source_URL": str
        }
    ]
    """
    articles = []
    df = None
    
    try:
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            # Excel parser
            df = pd.read_excel(io.BytesIO(file_content))
        elif filename.endswith(".csv"):
            # CSV parser
            df = pd.read_csv(io.BytesIO(file_content))
        else:
            # Assume Tab-delimited (TXT or TSV)
            # Clarivate WoS TSV files often have headers on line 1 or 2, and might have a 'FN Web of Science' line
            content_str = file_content.decode("utf-8", errors="ignore")
            lines = content_str.splitlines()
            
            # Dynamically search for the header line (usually starts with 'PT' and contains tabs)
            skiprows = 0
            for idx, line in enumerate(lines):
                parts = line.split("\t")
                if len(parts) > 1 and (parts[0] == "PT" or "TI" in parts or "Title" in parts):
                    skiprows = idx
                    break
                
            df = pd.read_csv(io.StringIO(content_str), sep="\t", skiprows=skiprows)
            
    except Exception as e:
        print(f"Error reading file {filename} with pandas: {e}")
        return []

    if df is None or df.empty:
        return []

    # Map column headers to WoS Tag keys (case-insensitive)
    col_mapping = {}
    for col in df.columns:
        col_lower = str(col).lower().strip()
        col_mapping[col_lower] = col

    # Helper to retrieve column content by tags or full names
    def get_col_val(row, tags: List[str]):
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower in col_mapping:
                val = row[col_mapping[tag_lower]]
                if pd.notna(val):
                    return val
        return None

    for _, row in df.iterrows():
        # Retrieve fields using common WoS tags or human-readable equivalents
        title = get_col_val(row, ["TI", "Title", "Document Title", "Article Title"])
        authors_raw = get_col_val(row, ["AU", "AF", "Authors", "Full Author Names", "Author"])
        c1_raw = get_col_val(row, ["C1", "Addresses", "Author Addresses", "Affiliations", "Affiliation"])
        year = get_col_val(row, ["PY", "Year", "Publication Year"])
        abstract = get_col_val(row, ["AB", "Abstract"])
        doi = get_col_val(row, ["DI", "DOI", "Digital Object Identifier"])
        ut = get_col_val(row, ["UT", "Accession Number", "WoS ID"])

        if not title:
            continue

        # Parse and format the data fields
        authors_list = parse_wos_authors(authors_raw) if authors_raw else []
        affiliations_list = parse_wos_affiliations(c1_raw) if c1_raw else []
        
        # Ensure year is integer
        try:
            pub_year = int(year) if year else 2020
        except ValueError:
            pub_year = 2020

        # Construct fallback source URL
        source_url = f"https://doi.org/{doi}" if doi else (f"https://gateway.webofknowledge.com/gateway/Gateway.cgi?GWVersion=2&SrcApp=PARTNER_APP&SrcAuth=LinksAMR&KeyUT={ut}&DestLinkType=FullRecord&DestApp=ALL_WOS" if ut else "https://webofscience.com")

        abstract_text = str(abstract) if abstract else "Abstract non fourni. Se fier au titre."

        articles.append({
            "Title": str(title).strip(),
            "Authors": authors_list,
            "Affiliations": affiliations_list,
            "Year": pub_year,
            "Abstract": abstract_text[:1500], # Truncate to limit tokens
            "Source_URL": source_url
        })

    return articles
