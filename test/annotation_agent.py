"""
annotation_agent.py
═══════════════════
Agent LLM automatisé pour l'annotation des triplets du gold standard.
Annote les 180 triplets (V/I/U) avec justification, puis calcule le Kappa
de Cohen entre l'annotation de l'agent et celle d'un expert humain.

Utilisation :
    python annotation_agent.py --input triplets_836f4fe7.csv
    python annotation_agent.py --input triplets_836f4fe7.csv --kappa annotations_expert.csv
    python annotation_agent.py --input triplets_836f4fe7.csv --batch-size 20

Dépendances :
    pip install openai pandas scikit-learn openpyxl tqdm
"""

import argparse
import json
import os
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
from sklearn.metrics import cohen_kappa_score
from tqdm import tqdm

# ── Configuration ─────────────────────────────────────────────────────────────
#OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "TON_API_KEY")
MODEL          = "gpt-4o-mini"
TEMPERATURE    = 0          # Reproductibilité maximale
MAX_TOKENS     = 400
BATCH_SLEEP    = 1.0        # Pause entre batches (rate limiting)

# Mapping des codes vers des entiers pour le calcul du Kappa
CODE_MAP = {"V": 0, "I": 1, "U": 2}


# ── Prompt système ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Tu es un expert en analyse de publications scientifiques dans le domaine des matériaux de batteries (lithium-ion, état solide, recyclage, anodes silicium).

Ton rôle est d'annoter des triplets relationnels extraits automatiquement par un pipeline LLM à partir d'un corpus de 1 066 articles scientifiques (2019–2026).

Un triplet est de la forme : [Sujet] —[RELATION]→ [Objet]

Les cinq types de relations sont :
- AFFILIÉ_À : un chercheur est membre d'une institution
- A_POUR_EXPERTISE : un chercheur travaille sur un domaine ou sujet
- PARTENAIRE_DE : un chercheur collabore avec une organisation ou financeur
- TRAVAILLE_SUR : un chercheur mène des recherches sur un sujet spécifique
- PUBLIÉ_DANS : un article a été publié dans un journal

Pour chaque triplet, tu dois évaluer si la relation est correcte selon les critères suivants :

V (VALIDE) : Le triplet est factuellement correct ET explicitement soutenu par la justification fournie ou le texte source. La relation est réelle et vérifiable.

I (INVALIDE) : Le triplet est incorrect, mal formulé, ou inventé par le LLM (hallucination). La relation ne correspond pas au texte source, ou est une inférence erronée.

U (UNCERTAIN) : Tu ne peux pas trancher avec certitude. L'information est ambiguë, partiellement vraie, ou non vérifiable avec les éléments fournis.

RÈGLES STRICTES :
1. Réponds UNIQUEMENT en JSON, sans aucun texte avant ou après.
2. Le champ "code" doit être exactement "V", "I" ou "U" (majuscule, un seul caractère).
3. Le champ "justification" doit expliquer brièvement (1-2 phrases) pourquoi tu attribues ce code.
4. Ne jamais inventer d'informations non présentes dans les données fournies.
5. En cas de doute entre V et I, préférer U plutôt que de risquer une erreur.

Format de réponse obligatoire :
{"code": "V", "justification": "Raison concise de la décision."}"""

# ── Prompt utilisateur ─────────────────────────────────────────────────────────
def build_user_prompt(row: dict) -> str:
    return f"""Annote ce triplet :

SUJET    : {row.get('subject', 'N/A')}
RELATION : {row.get('relation', 'N/A')}
OBJET    : {row.get('object', 'N/A')}

JUSTIFICATION (extraite automatiquement du texte source) :
{row.get('justification', 'Non disponible')}

SOURCE : {row.get('source_url', 'Non disponible')}
SCORE DE CONFIANCE DU PIPELINE : {row.get('confidence', 'N/A')}

Réponds uniquement en JSON : {{"code": "V/I/U", "justification": "..."}}"""


# ── Fonction d'annotation d'un seul triplet ────────────────────────────────────

def annotate_triplet(client: OpenAI, row: dict, retries: int = 3) -> dict:
    """Appelle l'API OpenAI pour annoter un triplet. Retente en cas d'erreur."""
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                messages=[
                    {"role": "system",  "content": SYSTEM_PROMPT},
                    {"role": "user",    "content": build_user_prompt(row)},
                ]
            )
            raw = response.choices[0].message.content.strip()
            # Nettoyer les éventuels backticks markdown
            raw = raw.replace("```json", "").replace("```", "").strip()
            result = json.loads(raw)

            # Validation du code
            code = result.get("code", "").upper()
            if code not in ("V", "I", "U"):
                raise ValueError(f"Code invalide reçu : {code}")

            return {
                "agent_code":          code,
                "agent_justification": result.get("justification", ""),
                "agent_raw_response":  raw,
                "agent_error":         None,
            }

        except json.JSONDecodeError as e:
            error = f"JSONDecodeError (tentative {attempt+1}): {e}"
        except ValueError as e:
            error = f"ValueError (tentative {attempt+1}): {e}"
        except Exception as e:
            error = f"APIError (tentative {attempt+1}): {e}"
            time.sleep(2 ** attempt)  # Backoff exponentiel

    # Toutes les tentatives ont échoué → marquer comme erreur
    return {
        "agent_code":          "U",   # Fallback conservateur
        "agent_justification": "Erreur d'annotation — réponse invalide après plusieurs tentatives.",
        "agent_raw_response":  "",
        "agent_error":         error,
    }


# ── Calcul du Kappa de Cohen ──────────────────────────────────────────────────
def compute_kappa(df: pd.DataFrame, col_agent: str, col_human: str) -> dict:
  
    valid = df[[col_agent, col_human]].dropna()
    valid = valid[valid[col_agent].isin(["V","I","U"]) & valid[col_human].isin(["V","I","U"])]

    if len(valid) < 10:
        return {"error": f"Trop peu de paires valides : {len(valid)} (minimum 10)"}

    agent_int = [CODE_MAP[c] for c in valid[col_agent]]
    human_int = [CODE_MAP[c] for c in valid[col_human]]

    kappa     = cohen_kappa_score(human_int, agent_int)
    agreement = sum(a == h for a, h in zip(agent_int, human_int)) / len(agent_int)

    # Matrice de contingence
    contingency = {"VV":0,"VI":0,"VU":0,"IV":0,"II":0,"IU":0,"UV":0,"UI":0,"UU":0}
    for a, h in zip(valid[col_agent], valid[col_human]):
        contingency[f"{h}{a}"] += 1

    interpretation = (
        "Accord faible"            if kappa < 0.20 else
        "Accord juste"             if kappa < 0.40 else
        "Accord modéré"            if kappa < 0.60 else
        "Accord substantiel ✓"    if kappa < 0.80 else
        "Accord presque parfait ✓"
    )

    return {
        "n_pairs":         len(valid),
        "kappa":           round(kappa, 4),
        "interpretation":  interpretation,
        "accord_observe":  round(agreement, 4),
        "h2_confirmee":    "OUI" if kappa >= 0.60 else "NON",
        "contingency":     contingency,
    }


# ── Calcul Précision / Rappel / F1 ────────────────────────────────────────────
def compute_prf1(df: pd.DataFrame, col_annotation: str) -> dict:
    """
    Calcule Précision, Rappel, F1 par type de relation.
    Suppose que les triplets avec code V = vrais positifs,
    code I = faux positifs, code U = exclus du calcul P/R/F1.
    """
    results = {}
    relations = df["relation"].unique()

    for rel in relations:
        subset = df[(df["relation"] == rel) & (df[col_annotation].isin(["V", "I"]))]
        tp = len(subset[subset[col_annotation] == "V"])
        fp = len(subset[subset[col_annotation] == "I"])
        # FN = triplets qui auraient dû être extraits mais ne l'ont pas été
        # → Non mesurable sans référence externe ; on rapporte TP/FP uniquement
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        results[rel] = {
            "TP": tp, "FP": fp,
            "precision": round(precision, 4),
            "note": "Rappel non calculable sans référence externe complète"
        }

    # Global
    all_valid = df[df[col_annotation].isin(["V","I"])]
    tp_g = len(all_valid[all_valid[col_annotation] == "V"])
    fp_g = len(all_valid[all_valid[col_annotation] == "I"])
    results["GLOBAL"] = {
        "TP": tp_g, "FP": fp_g,
        "precision": round(tp_g / (tp_g + fp_g), 4) if (tp_g + fp_g) > 0 else 0.0,
        "note": "Rappel non calculable sans référence externe"
    }
    return results


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Agent d'annotation automatisée des triplets")
    parser.add_argument("--input",      required=True, help="Fichier CSV des triplets (triplets_693a8d20.csv)")
    parser.add_argument("--output",     default="annotations_agent.csv", help="Fichier CSV de sortie")
    parser.add_argument("--kappa",      default=None, help="Fichier CSV avec annotations humaines (col 'human_code') pour calculer le Kappa")
    parser.add_argument("--batch-size", type=int, default=20, help="Taille des batches (pause entre chaque)")
    parser.add_argument("--resume",     action="store_true", help="Reprendre une annotation interrompue")
    args = parser.parse_args()

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    df     = pd.read_csv(args.input)
    output_path = Path(args.output)

    # Reprendre si demandé
    if args.resume and output_path.exists():
        done = pd.read_csv(output_path)
        done_ids = set(done["triplet_id"].tolist()) if "triplet_id" in done.columns else set()
        df = df[~df["triplet_id"].isin(done_ids)]
        print(f"Reprise : {len(done_ids)} triplets déjà annotés, {len(df)} restants.")
    else:
        done_ids = set()

    print(f"\n{'='*55}")
    print(f"AGENT D'ANNOTATION — {len(df)} triplets à annoter")
    print(f"Modèle : {MODEL}  |  Température : {TEMPERATURE}")
    print(f"{'='*55}\n")

    results = []
    errors  = 0

    # Traitement par batches
    for batch_start in range(0, len(df), args.batch_size):
        batch = df.iloc[batch_start : batch_start + args.batch_size]

        for _, row in tqdm(batch.iterrows(), total=len(batch),
                           desc=f"Batch {batch_start//args.batch_size + 1}"):
            annotation = annotate_triplet(client, row.to_dict())

            if annotation["agent_error"]:
                errors += 1

            result_row = row.to_dict()
            result_row.update(annotation)
            results.append(result_row)

        # Pause entre batches
        if batch_start + args.batch_size < len(df):
            time.sleep(BATCH_SLEEP)

    # Sauvegarder les résultats
    results_df = pd.DataFrame(results)
    if args.resume and output_path.exists():
        existing = pd.read_csv(output_path)
        results_df = pd.concat([existing, results_df], ignore_index=True)

    results_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    # Statistiques
    print(f"\n{'='*55}")
    print(f"RÉSULTATS D'ANNOTATION")
    print(f"{'='*55}")
    print(f"Total annoté  : {len(results_df)}")
    print(f"Erreurs API   : {errors}")
    print(f"\nDistribution des codes :")
    for code, count in results_df["agent_code"].value_counts().items():
        pct = count / len(results_df) * 100
        print(f"  {code} : {count:4d}  ({pct:.1f}%)")

    # Métriques P/R/F1
    prf1 = compute_prf1(results_df, "agent_code")
    print(f"\nPrécision par relation :")
    for rel, metrics in prf1.items():
        print(f"  {rel:<25} TP={metrics['TP']:3d}  FP={metrics['FP']:3d}  Precision={metrics['precision']:.3f}")

    # Kappa de Cohen (si fichier humain fourni)
    if args.kappa and Path(args.kappa).exists():
        human_df = pd.read_csv(args.kappa)
        if "human_code" not in human_df.columns:
            print(f"\nATTENTION : le fichier {args.kappa} doit contenir une colonne 'human_code'")
        else:
            # Merge sur triplet_id
            merged = results_df.merge(human_df[["triplet_id","human_code"]], on="triplet_id", how="inner")
            kappa_result = compute_kappa(merged, "agent_code", "human_code")
            print(f"\n{'='*55}")
            print(f"KAPPA DE COHEN — Agent vs Expert humain")
            print(f"{'='*55}")
            for k, v in kappa_result.items():
                if k != "contingency":
                    print(f"  {k:<25} : {v}")
            print(f"\nMatrice de contingence (lignes=humain, cols=agent) :")
            print(f"         V      I      U")
            print(f"  V   {kappa_result['contingency']['VV']:5d}  {kappa_result['contingency']['VI']:5d}  {kappa_result['contingency']['VU']:5d}")
            print(f"  I   {kappa_result['contingency']['IV']:5d}  {kappa_result['contingency']['II']:5d}  {kappa_result['contingency']['IU']:5d}")
            print(f"  U   {kappa_result['contingency']['UV']:5d}  {kappa_result['contingency']['UI']:5d}  {kappa_result['contingency']['UU']:5d}")

            # Sauvegarde du rapport JSON
            report = {
                "n_triplets_annotes": len(results_df),
                "distribution_codes": results_df["agent_code"].value_counts().to_dict(),
                "precision_par_relation": prf1,
                "kappa_agent_vs_humain": kappa_result,
            }
            with open("rapport_annotation.json", "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\nRapport complet sauvegardé : rapport_annotation.json")

    print(f"\nAnnotations sauvegardées : {output_path}")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()