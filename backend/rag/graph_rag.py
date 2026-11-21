import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from backend.database.neo4j_client import graph_db

def ask_graph_rag(query: str) -> dict:
    """
    Retrieves the knowledge graph state and uses an LLM to answer the user's querying.
    """
    if not graph_db.driver:
        return {"answer": "Erreur : Base de données Neo4j non connectée. Modèle GraphRAG indisponible.", "sources": []}

    # 1. Graph Retrieval (Extraction du graphe de connaissances Neo4j)
    # Pour le prototype, on extrait une large vue des relations récentes. En production, on utiliserait un retriever Cypher spécifique.
    cypher = """
    MATCH (s)-[r]->(o)
    RETURN labels(s)[0] AS s_type, s.id AS subject, 
           type(r) AS relation, 
           labels(o)[0] AS o_type, o.id AS object, 
           r.justification AS justification, r.source AS source
    LIMIT 200
    """
    
    records = []
    with graph_db.driver.session() as session:
        result = session.run(cypher)
        for record in result:
            records.append(record)
            
    if not records:
        return {"answer": "La base Graphe est vide. Veuillez d'abord valider et ingérer (Étape 2) les auteurs issus des articles.", "sources": []}

    # 2. Context Formulation (Traduction du graphe en texte structuré)
    context_lines = []
    sources_set = set()
    for rec in records:
        line = f"Le profil {rec['subject']} ({rec['s_type']}) est lié par '{rec['relation']}' à l'entité {rec['object']} ({rec['o_type']}). Justification trouvée extraite des documents : {rec['justification']}"
        context_lines.append(line)
        if rec['source'] and rec['source'] != "unknown":
            sources_set.add(rec['source'])
            
    context_str = "\n".join(context_lines)

    # 3. Generation via LLM (Interrogation du modèle GPT)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"answer": f"OPENAI_API_KEY manquante. RAG local simulé. Contexte brut extrait de la base : {len(records)} relations trouvées. Relatifs aux sources ci-jointes.", "sources": list(sources_set)}

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Tu es un expert analyste en Due Diligence Scientifique et un assistant IA opérant sur un Knowledge Graph (RAG).\n"
                   "Réponds à la question de l'utilisateur UNIQUEMENT en te basant sur le 'Contexte Graphe' ci-dessous.\n"
                   "Ne formule aucune hypothèse externe. Si l'information n'existe pas dans le contexte, déclare que le réseau actuel ne permet pas de l'affirmer.\n"
                   "Mentionne explicitement les noms des institutions (laboratoires) et les concepts d'expertise quand tu parles d'un auteur.\n"
                   "Contexte Graphe Neo4j restructuré:\n{context}"),
        ("human", "{question}")
    ])
    
    chain = prompt | llm
    res = chain.invoke({"context": context_str, "question": query})

    return {"answer": res.content, "sources": list(sources_set)}
