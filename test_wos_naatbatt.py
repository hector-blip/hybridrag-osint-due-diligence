import os
import sys

# Ensure backend can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.extraction.wos_parser import parse_wos_file
from backend.database.naatbatt import validate_entity

def test_wos_parsing():
    print("Testing Web of Science parsing...")
    test_file_path = "wos_test_export.txt"
    if not os.path.exists(test_file_path):
        print(f"Error: {test_file_path} not found.")
        return False
        
    with open(test_file_path, "rb") as f:
        content = f.read()
        
    articles = parse_wos_file(content, test_file_path)
    print(f"Parsed {len(articles)} articles.")
    for idx, art in enumerate(articles):
        print(f"\nArticle {idx+1}:")
        print(f"  Title: {art['Title']}")
        print(f"  Authors: {art['Authors']}")
        print(f"  Affiliations: {art['Affiliations']}")
        print(f"  Year: {art['Year']}")
        print(f"  Source: {art['Source_URL']}")
        
    if len(articles) != 2:
        print("Error: Expected 2 articles parsed.")
        return False
    return True

def test_naatbatt_matching():
    print("\nTesting NAATBatt matching...")
    test_cases = [
        ("Redwood Materials", True, "Downstream"),
        ("Tesla Inc.", True, "Midstream"),
        ("MIT Battery Lab", False, "Academic"),
        ("Stanford University", False, "Academic"),
        ("Random Unlisted Biotech", False, "Unlisted")
    ]
    
    passed = True
    for name, expected_val, desc in test_cases:
        res = validate_entity(name)
        print(f"Entity: '{name}' -> Label: '{res['status_label']}' (is_validated={res['is_validated']})")
        if res["is_validated"] != expected_val:
            print(f"  FAILED: expected is_validated={expected_val}")
            passed = False
            
    return passed

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        
    p_ok = test_wos_parsing()
    m_ok = test_naatbatt_matching()
    if p_ok and m_ok:
        print("\nAll tests passed successfully! ✅")
    else:
        print("\nSome tests failed. ❌")
        sys.exit(1)
