# generate_table_4_2.py
import json
import pandas as pd

with open('ragas_results.json', 'r') as f:
    results = json.load(f)

rows = []
for condition, scores in results.items():
    rows.append({
        "Condition"         : condition,
        "Faithfulness"      : round(scores.get("faithfulness", 0), 3),
        "Answer Relevancy"  : round(scores.get("answer_relevancy", 0), 3),
        "Context Precision" : round(scores.get("context_precision", 0), 3),
        "Context Recall"    : round(scores.get("context_recall", 0), 3),
    })

df = pd.DataFrame(rows)
print("\n── TABLEAU COMPARATIF §4.2 ──")
print(df.to_string(index=False))

# Test de Wilcoxon : C4 vs C1 sur Faithfulness
from scipy.stats import wilcoxon
print("\n── Test de Wilcoxon (C4 vs C1 — Faithfulness) ──")
print("Note : exécuter après avoir collecté les scores individuels par question")
print("Ajouter dans run_ragas.py : sauvegarder les scores par question, pas seulement la moyenne")

df.to_csv('tableau_4_2.csv', index=False)
print("\nTableau sauvegardé dans tableau_4_2.csv")