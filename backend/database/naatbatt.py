import os
import json
import re

# Resolve the database path relative to this file
DB_PATH = os.path.join(os.path.dirname(__file__), "naatbatt_db.json")

# Load NAATBatt data once on import
_naatbatt_data = []
try:
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "r", encoding="utf-8") as f:
            _naatbatt_data = json.load(f)
    else:
        print(f"Warning: NAATBatt database file not found at {DB_PATH}")
except Exception as e:
    print(f"Error loading NAATBatt database: {e}")

def validate_entity(entity_name: str) -> dict:
    """
    Checks if a given entity name (e.g., 'Tesla Inc', 'Redwood Materials') matches 
    any company or facility in the NAATBatt Lithium-Ion Battery Supply Chain Database.
    
    Returns a dictionary with validation status:
    {
        "is_validated": bool,
        "company": str or None,
        "facility": str or None,
        "location": str or None,
        "segment": str or None,
        "details": str or None,
        "status_label": str
    }
    """
    if not entity_name:
        return {
            "is_validated": False,
            "company": None,
            "facility": None,
            "location": None,
            "segment": None,
            "details": None,
            "status_label": "Unknown"
        }

    # Normalize entity name for matching
    normalized_name = entity_name.strip().lower()
    
    # Remove common corporate suffixes to improve matching (e.g. Inc, Corp, Corporation, Ltd, Co)
    clean_name = re.sub(r'\b(inc|corp|corporation|ltd|co|llc|gmbh)\b', '', normalized_name).strip()
    # Remove punctuation
    clean_name = re.sub(r'[^\w\s-]', '', clean_name).strip()

    for item in _naatbatt_data:
        comp = item["company"]
        fac = item["facility"]
        
        comp_norm = comp.lower()
        # Remove suffixes from DB names too
        comp_clean = re.sub(r'\b(inc|corp|corporation|ltd|co|llc|gmbh)\b', '', comp_norm).strip()
        comp_clean = re.sub(r'[^\w\s-]', '', comp_clean).strip()
        
        # Check if the clean name is a substring of the database company or vice versa
        # Example: clean_name='redwood materials' matches comp_clean='redwood materials'
        # Example: clean_name='tesla battery lab' matches comp_clean='tesla'
        # We check word boundary or containment
        if comp_clean in clean_name or clean_name in comp_clean:
            return {
                "is_validated": True,
                "company": comp,
                "facility": fac,
                "location": item["location"],
                "segment": item["segment"],
                "details": item["details"],
                "status_label": f"NAATBatt: {item['segment']} ({comp} - {item['location']})"
            }

    # If it is a known academic entity or university, return a helpful status
    univ_keywords = ["university", "université", "univ", "institute", "lab", "laboratory", "school", "college", "polytechnic", "mit"]
    if any(kw in normalized_name for kw in univ_keywords):
        return {
            "is_validated": False,
            "company": None,
            "facility": None,
            "location": None,
            "segment": None,
            "details": None,
            "status_label": "Academic Research"
        }

    return {
        "is_validated": False,
        "company": None,
        "facility": None,
        "location": None,
        "segment": None,
        "details": None,
        "status_label": "International / Unlisted"
    }
