# wilcoxon_test.py
"""
Test de Wilcoxon sur les scores RAGAS par condition.

Priorité de lecture :
  1. CSV par condition (scores par question) → test sur distribution complète
  2. ragas_results.json (scores moyens)      → comparaison simple si CSV absents
"""
import os
import json
import pandas as pd
from scipy.stats import wilcoxon

METRIC    = "faithfulness"
CSV_DIR   = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(CSV_DIR, "ragas_results.json")
CONDITIONS = ["C1_VectorRAG", "C2_GraphRAG", "C3_Hybrid_noHITL", "C4_Hybrid_HITL"]

def load_scores(condition, metric):
    """Charge les scores depuis le CSV si disponible, sinon depuis le JSON."""
    csv_path = os.path.join(CSV_DIR, f"scores_{condition}.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        if metric in df.columns:
            return df[metric].dropna().tolist(), "CSV"
        else:
            print(f"  [WARN] colonne '{metric}' absente de {csv_path}. Colonnes : {list(df.columns)}")
    # Fallback : JSON (score moyen uniquement)
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if condition in data and metric in data[condition]:
            return [data[condition][metric]], "JSON"
    return None, None

# ── Charger les scores pour chaque condition ──────────────────────────────────
scores = {}
for cond in CONDITIONS:
    vals, source = load_scores(cond, METRIC)
    if vals:
        scores[cond] = vals
        print(f"  {cond:<25} → {len(vals):>3} scores chargés depuis {source}")
    else:
        print(f"  {cond:<25} → ⚠ AUCUN score trouvé (CSV absent et JSON manquant)")

print()

# ── Tests de Wilcoxon sur les paires clés ─────────────────────────────────────
PAIRS = [
    ("C4_Hybrid_HITL",    "C1_VectorRAG",     "C4 vs C1 (HITL apporte-t-il un gain ?)"),
    ("C4_Hybrid_HITL",    "C3_Hybrid_noHITL", "C4 vs C3 (impact HITL seul)"),
    ("C3_Hybrid_noHITL",  "C1_VectorRAG",     "C3 vs C1 (hybride vs vector)"),
    ("C2_GraphRAG",       "C1_VectorRAG",     "C2 vs C1 (graph vs vector)"),
]

for a, b, label in PAIRS:
    if a not in scores or b not in scores:
        print(f"  ⚠ Données manquantes pour : {label}")
        continue

    sa, sb = scores[a], scores[b]

    if len(sa) == 1 or len(sb) == 1:
        # Pas assez de données pour un test statistique → comparaison simple
        print(f"\n{label}")
        print(f"  {a}: {sa[0]:.4f}  |  {b}: {sb[0]:.4f}")
        diff = sa[0] - sb[0]
        print(f"  Différence : {diff:+.4f}  (pas assez de données pour Wilcoxon)")
        continue

    # Aligner les longueurs si nécessaire
    n = min(len(sa), len(sb))
    try:
        stat, p = wilcoxon(sa[:n], sb[:n])
        print(f"\n{label}")
        print(f"  Statistique W : {stat:.3f}")
        print(f"  p-value       : {p:.4f}")
        print(f"  Différence significative (α=0.05) : {'✅ OUI' if p < 0.05 else '❌ NON'}")
    except ValueError as e:
        print(f"\n{label} → Wilcoxon impossible : {e}")