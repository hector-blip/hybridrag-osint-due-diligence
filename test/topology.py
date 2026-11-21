"""
topologie.py
════════════
Calcule les métriques topologiques du graphe de connaissances Neo4j
et produit les chiffres pour remplir le tableau 4.15 du mémoire.

Utilisation :
    python topologie.py
    python topologie.py --uri bolt://localhost:7687 --password TONPASS
    python topologie.py --export metriques_graphe.json

Dépendances :
    pip install neo4j python-dotenv
"""

import argparse
import json
import os
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")


def run_query(session, query, params=None):
    result = session.run(query, params or {})
    return [dict(r) for r in result]


def compute_metrics(driver):
    metrics = {}

    with driver.session() as s:

        # ── Compter les nœuds par type ─────────────────────────
        for label in ["Researcher", "Institution", "Organization", "Topic", "Article"]:
            res = s.run(f"MATCH (n:{label}) RETURN count(n) AS n").single()
            metrics[f"n_{label.lower()}"] = res["n"] if res else 0

        # ── Compter les relations par type ──────────────────────
        for rel in ["AFFILIÉ_À", "PARTENAIRE_DE", "A_POUR_EXPERTISE",
                    "TRAVAILLE_SUR", "PUBLIÉ_DANS", "A_PUBLIÉ"]:
            res = s.run(f"MATCH ()-[r:`{rel}`]->() RETURN count(r) AS n").single()
            metrics[f"rel_{rel}"] = res["n"] if res else 0

        # ── Total nœuds et relations ────────────────────────────
        res = s.run("MATCH (n) RETURN count(n) AS n").single()
        metrics["total_nodes"] = res["n"] if res else 0

        res = s.run("MATCH ()-[r]->() RETURN count(r) AS n").single()
        metrics["total_relations"] = res["n"] if res else 0

        # ── Densité du graphe ───────────────────────────────────
        # D = 2E / (N × (N-1)) pour graphe non orienté
        N = metrics["total_nodes"]
        E = metrics["total_relations"]
        metrics["density"] = round(2 * E / (N * (N - 1)), 6) if N > 1 else 0

        # ── Degré moyen ─────────────────────────────────────────
        res = s.run("""
            MATCH (n)
            OPTIONAL MATCH (n)-[r]-()
            WITH n, count(r) AS degree
            RETURN avg(degree) AS avg_degree, max(degree) AS max_degree
        """).single()
        metrics["avg_degree"] = round(res["avg_degree"] or 0, 3)
        metrics["max_degree"] = res["max_degree"] or 0

        # ── Top 10 nœuds par centralité de degré ───────────────
        res = run_query(s, """
            MATCH (n)
            OPTIONAL MATCH (n)-[r]-()
            WITH n, count(r) AS degree, labels(n)[0] AS label
            ORDER BY degree DESC
            LIMIT 10
            RETURN
                coalesce(n.name, n.title, 'N/A') AS name,
                label,
                degree
        """)
        metrics["top_nodes_by_degree"] = res

        # ── Chercheur le plus connecté ──────────────────────────
        res = s.run("""
            MATCH (r:Researcher)
            OPTIONAL MATCH (r)-[rel]-()
            WITH r, count(rel) AS degree
            ORDER BY degree DESC LIMIT 1
            RETURN r.name AS name, degree
        """).single()
        if res:
            metrics["top_researcher"] = res["name"]
            metrics["top_researcher_degree"] = res["degree"]

        # ── Institution la plus connectée ───────────────────────
        res = s.run("""
            MATCH (i:Institution)
            OPTIONAL MATCH (i)-[rel]-()
            WITH i, count(rel) AS degree
            ORDER BY degree DESC LIMIT 1
            RETURN i.name AS name, degree
        """).single()
        if res:
            metrics["top_institution"] = res["name"]
            metrics["top_institution_degree"] = res["degree"]

        # ── Composantes connexes (approximation) ────────────────
        # Neo4j Community ne supporte pas gds — approche manuelle
        try:
            res = s.run("""
                MATCH (n)
                WITH collect(id(n)) AS all_nodes
                RETURN size(all_nodes) AS total
            """).single()
            # Heuristique : compter les nœuds isolés (degré 0)
            res_isolated = s.run("""
                MATCH (n)
                WHERE NOT (n)--()
                RETURN count(n) AS isolated
            """).single()
            metrics["isolated_nodes"] = res_isolated["isolated"] if res_isolated else 0
            metrics["connected_nodes"] = N - metrics["isolated_nodes"]
            metrics["note_composantes"] = "GDS non disponible — nœuds isolés calculés manuellement"
        except Exception as e:
            metrics["isolated_nodes"] = "N/A"
            metrics["note_composantes"] = str(e)

        # ── Topics les plus fréquents (mots-clés dominants) ─────
        res = run_query(s, """
            MATCH (t:Topic)
            OPTIONAL MATCH (t)<-[r:A_POUR_EXPERTISE]-()
            WITH t, count(r) AS freq
            ORDER BY freq DESC LIMIT 10
            RETURN t.name AS topic, freq
        """)
        metrics["top_topics"] = res

        # ── Clustering coefficient approximatif ─────────────────
        # Chercheurs qui partagent une institution
        res = s.run("""
            MATCH (r1:Researcher)-[:AFFILIÉ_À]->(i:Institution)<-[:AFFILIÉ_À]-(r2:Researcher)
            WHERE id(r1) < id(r2)
            RETURN count(*) AS shared_institution_pairs
        """).single()
        metrics["shared_institution_pairs"] = res["shared_institution_pairs"] if res else 0

    return metrics


def print_report(metrics):
    sep = "=" * 60
    print(f"\n{sep}")
    print("MÉTRIQUES TOPOLOGIQUES — GRAPHE DE CONNAISSANCES NEO4J")
    print(f"{sep}")
    print(f"\n── Structure du graphe ──")
    print(f"  Nœuds total               : {metrics.get('total_nodes', 'N/A')}")
    print(f"    Researcher               : {metrics.get('n_researcher', 'N/A')}")
    print(f"    Institution              : {metrics.get('n_institution', 'N/A')}")
    print(f"    Organization             : {metrics.get('n_organization', 'N/A')}")
    print(f"    Topic (mots-clés)        : {metrics.get('n_topic', 'N/A')}")
    print(f"    Article                  : {metrics.get('n_article', 'N/A')}")
    print(f"  Relations total            : {metrics.get('total_relations', 'N/A')}")
    print(f"    AFFILIÉ_À                : {metrics.get('rel_AFFILIÉ_À', 'N/A')}")
    print(f"    PARTENAIRE_DE            : {metrics.get('rel_PARTENAIRE_DE', 'N/A')}")
    print(f"    A_POUR_EXPERTISE         : {metrics.get('rel_A_POUR_EXPERTISE', 'N/A')}")
    print(f"    TRAVAILLE_SUR            : {metrics.get('rel_TRAVAILLE_SUR', 'N/A')}")
    print(f"    PUBLIÉ_DANS              : {metrics.get('rel_PUBLIÉ_DANS', 'N/A')}")

    print(f"\n── Métriques topologiques ──")
    print(f"  Densité du graphe (D)      : {metrics.get('density', 'N/A')}")
    print(f"  Degré moyen                : {metrics.get('avg_degree', 'N/A')}")
    print(f"  Degré maximum              : {metrics.get('max_degree', 'N/A')}")
    print(f"  Nœuds isolés (degré=0)    : {metrics.get('isolated_nodes', 'N/A')}")
    print(f"  Nœuds connectés            : {metrics.get('connected_nodes', 'N/A')}")
    print(f"  Paires chercheurs/inst.    : {metrics.get('shared_institution_pairs', 'N/A')}")

    print(f"\n── Nœuds les plus connectés ──")
    print(f"  Top Researcher : {metrics.get('top_researcher', 'N/A')} "
          f"(degré = {metrics.get('top_researcher_degree', 'N/A')})")
    print(f"  Top Institution: {metrics.get('top_institution', 'N/A')} "
          f"(degré = {metrics.get('top_institution_degree', 'N/A')})")

    print(f"\n── Top 10 nœuds par degré ──")
    for r in metrics.get("top_nodes_by_degree", []):
        print(f"  [{r.get('label','?'):<15}] {r.get('name','?'):<40} degré={r.get('degree','?')}")

    print(f"\n── Top 10 mots-clés (Topics) ──")
    for r in metrics.get("top_topics", []):
        print(f"  {r.get('topic','?'):<45} freq={r.get('freq','?')}")

    print(f"\n{sep}")
    print("VALEURS POUR §4.6 — TABLEAU 4.15")
    print(f"{sep}")
    print(f"  Densité du graphe (D)                    : {metrics.get('density', '[à compléter]')}")
    print(f"  Degré moyen des nœuds                    : {metrics.get('avg_degree', '[à compléter]')}")
    print(f"  Nœud à plus forte centralité de degré    : {metrics.get('top_researcher', '[à compléter]')} (degré = {metrics.get('top_researcher_degree', '?')})")
    print(f"  Nœuds isolés                             : {metrics.get('isolated_nodes', '[à compléter]')}")
    print(f"  Nœuds connectés                          : {metrics.get('connected_nodes', '[à compléter]')}")
    print(f"{sep}\n")


def main():
    parser = argparse.ArgumentParser(description="Métriques topologiques Neo4j — Mémoire UQO")
    parser.add_argument("--uri",      default=NEO4J_URI,      help="URI Neo4j")
    parser.add_argument("--user",     default=NEO4J_USER,     help="Utilisateur Neo4j")
    parser.add_argument("--password", default=NEO4J_PASSWORD, help="Mot de passe Neo4j")
    parser.add_argument("--export",   default=None,           help="Exporter en JSON (ex: metriques.json)")
    args = parser.parse_args()

    from neo4j import GraphDatabase

    print(f"Connexion à {args.uri}...")
    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))

    try:
        driver.verify_connectivity()
        print("Connexion établie.")
    except Exception as e:
        print(f"Erreur de connexion : {e}")
        print("Vérifiez que Neo4j est démarré et que les credentials sont corrects.")
        return

    metrics = compute_metrics(driver)
    driver.close()

    print_report(metrics)

    if args.export:
        # Sérialiser pour JSON (retirer les objets non sérialisables)
        export_data = {k: v for k, v in metrics.items()
                       if isinstance(v, (int, float, str, list, dict, type(None)))}
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        print(f"Métriques exportées : {args.export}")


if __name__ == "__main__":
    main()