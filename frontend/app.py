import streamlit as st
import requests
import pandas as pd
from streamlit_agraph import agraph, Node, Edge, Config

API_BASE_URL = "http://127.0.0.1:8000"

# Configuration globale de la page
st.set_page_config(page_title="Scientific Due Diligence V9", layout="wide", page_icon="")

# CSS Personnalisé pour un look premium
st.markdown("""
<style>
    /* Masquer le menu hamburger par défaut et le footer Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Donner un style moderne aux boutons principaux */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }

    /* Cartes de métriques visuellement séparées */
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        color: #636EFA;
    }

    /* Badges de source */
    .source-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
        margin-right: 4px;
    }
    .badge-scholar { background: #4285F4; color: white; }
    .badge-books   { background: #34A853; color: white; }
    .badge-patents { background: #EA4335; color: white; }
    .badge-wos     { background: #FF6600; color: white; }
    .badge-openalex{ background: #636EFA; color: white; }
</style>
""", unsafe_allow_html=True)

# En-tête principal
st.title(" Scientific Due Diligence")
st.markdown("### Prototype OSINT & Knowledge Graph")
st.divider()

# Gestion des états de session
if "mission_id" not in st.session_state:
    st.session_state["mission_id"] = None
if "mission_status" not in st.session_state:
    st.session_state["mission_status"] = None

# Barre latérale : Menu stylisé
st.sidebar.title("Workflow d'Investigation")
page = st.sidebar.radio("Navigation", [
    "1. Mission Configuration",
    "2. Validation Humaine",
    "3. Graph Dashboard & RAG"
])

# Indicateur de source active
if st.session_state.get("mission_id"):
    st.sidebar.divider()
    st.sidebar.caption(f"Mission active : `{st.session_state['mission_id'][:8]}...`")

# Module de recherche rapide NAATBatt dans la barre latérale
if page == "2. Validation Humaine":
    st.sidebar.divider()
    st.sidebar.markdown("### Validation NAATBatt (NLR)")
    st.sidebar.markdown("Recherche manuelle d'installations dans la base de données de la chaîne de valeur nord-américaine.")
    search_q = st.sidebar.text_input("Vérifier un acteur/usine", placeholder="Ex: Redwood, Tesla, Albemarle...")
    if search_q:
        import json
        import os
        db_path = os.path.join("backend", "database", "naatbatt_db.json")
        if os.path.exists(db_path):
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    naatbatt_list = json.load(f)
                results = [item for item in naatbatt_list if search_q.lower() in item["company"].lower() or search_q.lower() in item["facility"].lower()]
                if results:
                    st.sidebar.success(f"{len(results)} installation(s) trouvée(s) :")
                    for r in results:
                        st.sidebar.markdown(f"**{r['company']}** - *{r['facility']}* ({r['location']})")
                        st.sidebar.caption(f"Segment : {r['segment']}\n\n{r['details']}")
                        st.sidebar.markdown("---")
                else:
                    st.sidebar.info("Aucun acteur correspondant dans la base NAATBatt locale.")
            except Exception as e:
                st.sidebar.error(f"Erreur base NAATBatt : {e}")
        else:
            st.sidebar.error("Base NAATBatt introuvable.")


# -------------------------------------------------------------------------------------
# PAGE 1 : CONFIGURATION — SOURCES ÉLARGIES
# -------------------------------------------------------------------------------------
if page == "1. Mission Configuration":
    st.header("Étape 1 : Définir le besoin de recherche")
    st.markdown("Configurez les paramètres de recherche OSINT. Choisissez la méthode de collecte adaptée à vos besoins.")

    # ─── Sélection du mode via onglets ───────────────────────────────────────
    tab_online, tab_wos, tab_scholar_excel, tab_google = st.tabs([
        " OpenAlex (en ligne)",
        " Import Web of Science",
        " Import Google Scholar (Excel)",
        " Collecte Google (Scholar + Books + Patents)"
    ])

    # ── Onglet 1 : OpenAlex (comportement existant préservé) ─────────────────
    with tab_online:
        st.markdown("#### Collecte via OpenAlex API (arXiv, PubMed, CrossRef...)")
        with st.container(border=True):
            with st.form("mission_form_online"):
                need_description = st.text_area(
                    "Description précise de la technologie / du besoin",
                    placeholder="Ex: solid state battery electrolyte lithium",
                    height=100
                )
                st.markdown("#### Filtres de Données")
                cols = st.columns(2)
                with cols[0]:
                    sources = st.multiselect(
                        "Bases OSINT Cibles",
                        ["arXiv", "PubMed", "Brevets", "OpenAlex"],
                        default=["OpenAlex"]
                    )
                with cols[1]:
                    min_year = st.number_input("Année de publication min.", min_value=1950, max_value=2026, value=2020)

                st.markdown("#### Intelligence Artificielle")
                extraction_rules = st.text_area(
                    "Règles Strictes d'Extraction (Directives LLM)",
                    "Extraire obligatoirement l'affiliation institutionnelle (Université, Labo) de l'auteur.\nL'expérience doit être prouvée expérimentalement dans le résumé de l'article.",
                    height=100
                )
                max_docs = st.slider("Budget de recherche (Max Documents)", 10, 1000, 100)
                st.markdown("<br>", unsafe_allow_html=True)
                submitted = st.form_submit_button(" Lancer l'Agent d'Investigation (OpenAlex)")

                if submitted:
                    rules_list = [r.strip() for r in extraction_rules.split("\n") if r.strip()]
                    payload = {
                        "need_description": need_description,
                        "sources": sources,
                        "min_year": min_year,
                        "extraction_rules": rules_list,
                        "max_documents": max_docs
                    }
                    with st.spinner("Déploiement de l'agent OSINT en cours..."):
                        try:
                            res = requests.post(f"{API_BASE_URL}/api/mission/start", json=payload)
                            if res.status_code == 200:
                                st.session_state["mission_id"] = res.json()["mission_id"]
                                st.session_state["mission_status"] = "started"
                                st.success(f"✅ Mission déployée. ID : `{st.session_state['mission_id']}`")
                                st.info("Passez à l'onglet '2. Validation Humaine' pour suivre le déroulement.")
                            else:
                                st.error("Échec lors du lancement de l'API Mission.")
                        except Exception as e:
                            st.error(f"Impossible de joindre le Backend Uvicorn : {e}")

    # ── Onglet 2 : Import Web of Science (comportement existant préservé) ────
    with tab_wos:
        st.markdown("#### Import d'un fichier export Web of Science")
        st.caption("Formats supportés : `.txt` (tab-délimité), `.tsv`, `.xlsx`, `.xls`, `.csv`")
        with st.container(border=True):
            with st.form("mission_form_wos"):
                uploaded_file = st.file_uploader(
                    "Fichier d'export Web of Science",
                    type=["txt", "tsv", "xlsx", "xls", "csv"]
                )
                need_description = st.text_area(
                    "Description du besoin (pour l'extraction LLM)",
                    placeholder="Ex: solid state battery electrolyte",
                    height=100
                )
                extraction_rules = st.text_area(
                    "Règles d'Extraction LLM",
                    "Extraire obligatoirement l'affiliation institutionnelle de l'auteur.",
                    height=80
                )
                max_docs = st.slider("Max Documents à traiter", 10, 1000, 200, key="wos_max")
                submitted = st.form_submit_button(" Analyser le Fichier Web of Science")

                if submitted:
                    if uploaded_file is None:
                        st.error("Veuillez téléverser un fichier d'export Web of Science.")
                    elif not need_description:
                        st.error("Veuillez décrire le besoin de recherche.")
                    else:
                        with st.spinner("Importation et parsing du fichier WoS..."):
                            try:
                                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                                data = {
                                    "need_description": need_description,
                                    "extraction_rules": extraction_rules,
                                    "max_documents": max_docs
                                }
                                res = requests.post(f"{API_BASE_URL}/api/mission/start-wos", files=files, data=data)
                                if res.status_code == 200:
                                    response_data = res.json()
                                    if response_data.get("status") == "error":
                                        st.error(response_data.get("message"))
                                    else:
                                        st.session_state["mission_id"] = response_data["mission_id"]
                                        st.session_state["mission_status"] = "started"
                                        st.success(f" Mission WoS déployée. ID : `{st.session_state['mission_id']}`")
                                        st.info("Passez à l'onglet '2. Validation Humaine'.")
                                else:
                                    st.error("Échec lors du traitement du fichier.")
                            except Exception as e:
                                st.error(f"Erreur de communication avec le backend : {e}")

    # ── Onglet 3 : Import Google Scholar Excel (NOUVEAU) ─────────────────────
    with tab_scholar_excel:
        st.markdown("#### Import du fichier Excel Google Scholar")
        st.info(
            " **Utilisez cet onglet** pour importer le fichier Excel généré semi-manuellement "
            "depuis Google Scholar (ex : via Publish or Perish, Zotero, ou tout export Scholar). "
            "Les colonnes supplémentaires ajoutées manuellement sont **automatiquement détectées** "
            "et intégrées comme contexte enrichi pour le LLM."
        )

        with st.container(border=True):
            with st.form("mission_form_scholar_excel"):
                uploaded_scholar = st.file_uploader(
                    "Fichier Excel Google Scholar (.xlsx, .csv ou .tsv)",
                    type=["xlsx", "xls", "csv", "tsv", "txt"],
                    key="scholar_excel_upload"
                )

                if uploaded_scholar:
                    # Aperçu du fichier avant envoi
                    try:
                        preview_df = pd.read_excel(uploaded_scholar) if uploaded_scholar.name.endswith(("xlsx", "xls")) else pd.read_csv(uploaded_scholar)
                        st.caption(f" Aperçu : {len(preview_df)} lignes × {len(preview_df.columns)} colonnes")
                        st.dataframe(preview_df.head(3), use_container_width=True)
                        # Réinitialiser le curseur après lecture
                        uploaded_scholar.seek(0)
                    except Exception:
                        pass

                need_description_s = st.text_area(
                    "Description du besoin de recherche (guide l'extraction LLM)",
                    placeholder="Ex: batteries lithium-ion électrolyte solide matériaux",
                    height=100,
                    key="scholar_need"
                )
                extraction_rules_s = st.text_area(
                    "Règles d'Extraction LLM",
                    "Extraire obligatoirement l'affiliation institutionnelle (Université, Labo) de l'auteur.\n"
                    "Tenir compte des annotations manuelles dans les colonnes supplémentaires.",
                    height=100,
                    key="scholar_rules"
                )
                max_docs_s = st.slider(
                    "Nombre maximum d'articles à traiter par le LLM",
                    10, 1000, 200,
                    help="Le fichier peut contenir +1000 articles. Le LLM traitera les N premiers par ordre d'apparition.",
                    key="scholar_max"
                )
                submitted_s = st.form_submit_button(" Importer et Analyser (Google Scholar Excel)")

                if submitted_s:
                    if uploaded_scholar is None:
                        st.error("Veuillez téléverser le fichier Excel Google Scholar.")
                    elif not need_description_s:
                        st.error("Veuillez décrire le besoin de recherche.")
                    else:
                        with st.spinner(f"Parsing du fichier Excel ({uploaded_scholar.name})..."):
                            try:
                                files = {
                                    "file": (
                                        uploaded_scholar.name,
                                        uploaded_scholar.getvalue(),
                                        uploaded_scholar.type or "application/octet-stream"
                                    )
                                }
                                data = {
                                    "need_description": need_description_s,
                                    "extraction_rules": extraction_rules_s,
                                    "max_documents": max_docs_s
                                }
                                res = requests.post(
                                    f"{API_BASE_URL}/api/mission/start-scholar-excel",
                                    files=files,
                                    data=data
                                )
                                if res.status_code == 200:
                                    response_data = res.json()
                                    if response_data.get("status") == "error":
                                        st.error(response_data.get("message"))
                                    else:
                                        st.session_state["mission_id"] = response_data["mission_id"]
                                        st.session_state["mission_status"] = "started"
                                        n_articles = response_data.get("article_count", "?")
                                        st.success(
                                            f" Mission Google Scholar lancée ! "
                                            f"**{n_articles} articles** détectés dans le fichier. "
                                            f"ID : `{st.session_state['mission_id']}`"
                                        )
                                        st.info("Passez à l'onglet '2. Validation Humaine' pour suivre l'extraction LLM.")
                                else:
                                    st.error(f"Erreur backend (HTTP {res.status_code}).")
                            except Exception as e:
                                st.error(f"Erreur de communication avec le backend : {e}")

    # ── Onglet 4 : Collecte en ligne Google multi-sources (NOUVEAU) ──────────
    with tab_google:
        st.markdown("#### Collecte en ligne : Google Scholar + Google Books + Google Patents")

        col_info1, col_info2, col_info3 = st.columns(3)
        with col_info1:
            st.markdown("""
            <div style='background:#4285F4;color:white;padding:12px;border-radius:8px;text-align:center'>
            <b> Google Scholar</b><br>
            <small>Articles scientifiques<br>~17,000 résultats (5 ans)<br>Via scholarly (scraping)</small>
            </div>
            """, unsafe_allow_html=True)
        with col_info2:
            st.markdown("""
            <div style='background:#34A853;color:white;padding:12px;border-radius:8px;text-align:center'>
            <b> Google Books</b><br>
            <small>Ouvrages & manuels<br>API officielle Google<br>Clé API optionnelle</small>
            </div>
            """, unsafe_allow_html=True)
        with col_info3:
            st.markdown("""
            <div style='background:#EA4335;color:white;padding:12px;border-radius:8px;text-align:center'>
            <b> Google Patents</b><br>
            <small>Brevets techniques<br>SerpAPI ou scraping<br>Clé API optionnelle</small>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        with st.container(border=True):
            with st.form("mission_form_google"):
                need_description_g = st.text_area(
                    "Requête de recherche (en anglais recommandé pour Scholar/Patents)",
                    placeholder="Ex: solid state electrolyte lithium battery cathode",
                    height=100,
                    key="google_need"
                )

                st.markdown("#### Sources à activer")
                g_cols = st.columns(3)
                with g_cols[0]:
                    inc_scholar = st.checkbox(" Google Scholar", value=True,
                                              help="Scraping via scholarly (lent, rate-limited)")
                with g_cols[1]:
                    inc_books = st.checkbox(" Google Books", value=True,
                                            help="API officielle Google Books (rapide)")
                with g_cols[2]:
                    inc_patents = st.checkbox(" Google Patents", value=True,
                                              help="SerpAPI ou scraping direct")

                st.markdown("#### Filtres")
                g_cols2 = st.columns(2)
                with g_cols2[0]:
                    min_year_g = st.number_input(
                        "Année minimum", min_value=1950, max_value=2026, value=2019,
                        key="google_year"
                    )
                with g_cols2[1]:
                    max_docs_g = st.slider(
                        "Max documents par source", 10, 200, 50,
                        help="Google Scholar est lent (~3s/article). Limitez à 50 pour une démo.",
                        key="google_max"
                    )

                extraction_rules_g = st.text_area(
                    "Règles d'Extraction LLM",
                    "Extraire obligatoirement l'affiliation institutionnelle (Université, Labo, Entreprise).\n"
                    "Pour les brevets, identifier l'inventeur ET le déposant (assignee).\n"
                    "Pour les livres, identifier l'auteur et l'éditeur.",
                    height=120,
                    key="google_rules"
                )

                if not inc_scholar:
                    st.info(" **Conseil** : Pour Google Scholar, préférez l'onglet 'Import Excel' "
                            "si vous avez le fichier de votre directeur (plus rapide et fiable).")

                submitted_g = st.form_submit_button(" Lancer la Collecte Google Multi-Sources")

                if submitted_g:
                    if not any([inc_scholar, inc_books, inc_patents]):
                        st.error("Sélectionnez au moins une source Google.")
                    elif not need_description_g:
                        st.error("Veuillez saisir une requête de recherche.")
                    else:
                        with st.spinner("Déploiement de la collecte Google multi-sources..."):
                            try:
                                data = {
                                    "need_description": need_description_g,
                                    "extraction_rules": extraction_rules_g,
                                    "max_documents": max_docs_g,
                                    "include_scholar": inc_scholar,
                                    "include_books": inc_books,
                                    "include_patents": inc_patents,
                                    "min_year": min_year_g
                                }
                                res = requests.post(f"{API_BASE_URL}/api/mission/start-google", data=data)
                                if res.status_code == 200:
                                    response_data = res.json()
                                    if response_data.get("status") == "error":
                                        st.error(response_data.get("message"))
                                    else:
                                        st.session_state["mission_id"] = response_data["mission_id"]
                                        st.session_state["mission_status"] = "started"
                                        sources_used = ", ".join(response_data.get("sources", []))
                                        st.success(
                                            f" Mission lancée ! Sources actives : **{sources_used}**\n\n"
                                            f"ID : `{st.session_state['mission_id']}`"
                                        )
                                        if inc_scholar:
                                            st.warning(
                                                " **Google Scholar** nécessite ~3s par article pour éviter les blocages. "
                                                "La collecte peut prendre plusieurs minutes."
                                            )
                                        st.info("Passez à l'onglet '2. Validation Humaine' pour suivre l'avancement.")
                                else:
                                    st.error(f"Erreur backend (HTTP {res.status_code}).")
                            except Exception as e:
                                st.error(f"Erreur de communication avec le backend : {e}")


# -------------------------------------------------------------------------------------
# PAGE 2 : VALIDATION (Human in the loop)
# -------------------------------------------------------------------------------------
elif page == "2. Validation Humaine":
    st.header("Étape 2 : Crible & Contrôle Qualité")
    if not st.session_state["mission_id"]:
        st.warning("Aucune mission en cours. Veuillez démarrer une investigation à l'Étape 1.")
    else:
        m_id = st.session_state["mission_id"]

        try:
            res = requests.get(f"{API_BASE_URL}/api/mission/{m_id}/results")
            if res.status_code == 200:
                data = res.json()
                status = data["status"]

                # Badge de source
                source_label = data.get("source", "")
                if source_label:
                    st.caption(f" Source : **{source_label}**")

                # Jolis badges visuels pour le statut
                if status == "completed":
                    st.success(" Extraction Terminée")
                    triplets = data.get("results", [])

                    if triplets:
                        # Métriques de résumé
                        col1, col2, col3 = st.columns(3)
                        col1.metric(label="Experts Identifiés", value=len(set([t["subject"] for t in triplets])))
                        col2.metric(label="Triplets Générés", value=len(triplets))
                        col3.metric(label="Institutions Croisées NAATBatt",
                                    value=len([t for t in triplets if t.get("object_type") == "Institution"]))

                        st.markdown("#### Revue des résultats (Human-in-the-Loop)")

                        # Alerte explicative sur NAATBatt
                        st.info(
                            "**Validation Clinique & Industrielle :** Les institutions ou entreprises détectées "
                            "comme **'Institution'** ont été automatiquement croisées avec la base de données "
                            "**NAATBatt Lithium-Ion Battery Supply Chain Database (NLR)**. "
                            "Vous pouvez consulter la base complète sur le site officiel de l'"
                            "[NREL/NLR](https://www.nrel.gov/transportation/li-ion-battery-supply-chain-database-access.html)."
                        )

                        df = pd.DataFrame(triplets)
                        if "naatbatt_status" not in df.columns:
                            df["naatbatt_status"] = "Not applicable"

                        df.insert(0, "Validate", True)

                        # Configuration des colonnes pour un rendu premium
                        col_cfg = {
                            "Validate": st.column_config.CheckboxColumn("Valider", default=True),
                            "subject": st.column_config.TextColumn("Sujet (Expert)"),
                            "subject_type": st.column_config.TextColumn("Type Sujet"),
                            "relation": st.column_config.TextColumn("Relation"),
                            "object": st.column_config.TextColumn("Objet (Institution/Skill)"),
                            "object_type": st.column_config.TextColumn("Type Objet"),
                            "justification": st.column_config.TextColumn("Preuve (Extrait)", width="large"),
                            "confidence": st.column_config.NumberColumn("Confiance", format="%.2f"),
                            "source_url": st.column_config.LinkColumn("Source URL"),
                            "naatbatt_status": st.column_config.TextColumn("Validation NAATBatt (NLR)", width="medium"),
                        }

                        edited_df = st.data_editor(
                            df,
                            column_config=col_cfg,
                            num_rows="dynamic",
                            hide_index=True,
                            use_container_width=True
                        )

                        st.markdown("<br>", unsafe_allow_html=True)

                        # Export CSV
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            csv_data = edited_df.to_csv(index=False).encode("utf-8")
                            st.download_button(
                                " Exporter en CSV",
                                data=csv_data,
                                file_name=f"triplets_{m_id[:8]}.csv",
                                mime="text/csv"
                            )
                        with col_btn2:
                            if st.button(" Ingérer la sélection dans Neo4j"):
                                with st.spinner("Ingestion sécurisée vers Neo4j en cours..."):
                                    validated_records = edited_df[edited_df["Validate"] == True].drop("Validate", axis=1).to_dict(orient="records")
                                    ingest_payload = {"mission_id": m_id, "validated_triplets": validated_records}
                                    ingest_res = requests.post(f"{API_BASE_URL}/api/graph/ingest", json=ingest_payload)
                                    if ingest_res.status_code == 200:
                                        st.success(f" {ingest_res.json()['message']}")
                                        st.info("Passez à l'onglet '3. Graph Dashboard' pour explorer les données.")
                                    else:
                                        st.error("Erreur de base de données Graph. Neo4j est-il allumé ?")
                    else:
                        st.warning("Aucun expert n'a pu être trouvé avec un haut score de confiance.")

                elif status == "failed":
                    error_msg = data.get("error", "Erreur réseau inconnue")
                    st.error(f" La mission a échoué (Erreur: {error_msg})")

                else:
                    # En cours de traitement
                    with st.status("Extraction et vérification en cours...", expanded=True):
                        st.write("1. Collecte des documents depuis les sources sélectionnées...")
                        st.write("2. Parsing sémantique avec LLM (GPT-4o-mini)...")
                        st.write("3. Validation NAATBatt des institutions...")

                    if st.button("🔄 Rafraîchir les statuts"):
                        st.rerun()

        except Exception as e:
            st.error(f"Erreur de communication avec le serveur backend : {e}")


# -------------------------------------------------------------------------------------
# PAGE 3 : DASHBOARD ET RAG
# -------------------------------------------------------------------------------------
elif page == "3. Graph Dashboard & RAG":
    st.header("Étape 3 : Cartographie et Interrogation Sémantique")

    tab1, tab2, tab3 = st.tabs([
        "Cartographie Visuelle (Knowledge Graph)",
        " Historique Missions Neo4j",
        " GraphRAG (Chat avec la donnée)"
    ])

    # ── Onglet 1 : Cartographie ───────────────────────────────────────────────
    with tab1:
        m_id = st.session_state.get("mission_id")
        if not m_id:
            st.info(" Aucune mission sélectionnée. Lancez une investigation (Étape 1) "
                    "ou choisissez une mission existante dans l'onglet **Historique Missions Neo4j**.")
        else:
            try:
                # Mode 1 : résultats en mémoire (mission courante de la session)
                res = requests.get(f"{API_BASE_URL}/api/mission/{m_id}/results")
                triplets = []
                if res.status_code == 200 and res.json().get("results"):
                    triplets = res.json()["results"]
                    st.caption(f" Source : **{res.json().get('source', '')}** — données en mémoire")
                else:
                    # Mode 2 : récupération depuis Neo4j (mission historique)
                    res2 = requests.get(f"{API_BASE_URL}/api/graph/mission/{m_id}")
                    if res2.status_code == 200 and res2.json().get("records"):
                        raw = res2.json()["records"]
                        # Reformater au format triplet attendu
                        triplets = [{
                            "subject":      r["subject"],
                            "subject_type": r.get("s_type", "Author"),
                            "relation":     r["relation"],
                            "object":       r["object"],
                            "object_type":  r.get("o_type", "Institution"),
                            "justification": r.get("justification", ""),
                            "confidence":   r.get("confidence", 0.0),
                            "source_url":   r.get("source", ""),
                        } for r in raw]
                        st.caption(f" Données chargées depuis **Neo4j** ({len(triplets)} relations)")

                if triplets:
                    nodes = []
                    edges = []
                    node_ids = set()

                    for t in triplets:
                        subj = t["subject"]
                        obj  = t["object"]

                        if subj not in node_ids:
                            color = "#FF6B6B" if "Author" in t.get("subject_type", "") else "#4ECDC4"
                            nodes.append(Node(id=subj, label=subj, size=25, shape="dot", color=color))
                            node_ids.add(subj)

                        if obj not in node_ids:
                            obj_type = t.get("object_type", "")
                            if "Institution" in obj_type:
                                color, shape = "#FFD166", "triangle"
                            elif "Partner" in obj_type:
                                color, shape = "#F15BB5", "star"
                            elif "Keyword" in obj_type:
                                color, shape = "#9B5DE5", "diamond"
                            elif "Journal" in obj_type:
                                color, shape = "#00BBF9", "square"
                            else:
                                color, shape = "#118AB2", "hexagon"
                            nodes.append(Node(id=obj, label=obj, size=18, shape=shape, color=color))
                            node_ids.add(obj)

                        edges.append(Edge(source=subj, label=t["relation"], target=obj))

                    # Métriques
                    mc1, mc2, mc3 = st.columns(3)
                    mc1.metric("Nœuds", len(nodes))
                    mc2.metric("Relations", len(edges))
                    mc3.metric("ID Mission", m_id[:8] + "...")

                    # Légende
                    leg_cols = st.columns(6)
                    leg_cols[0].markdown("🔴 **Auteurs**")
                    leg_cols[1].markdown("🟡 **Institutions**")
                    leg_cols[2].markdown("🔵 **Concepts**")
                    leg_cols[3].markdown("🟣 **Mots-clés**")
                    leg_cols[4].markdown("💗 **Partenaires**")
                    leg_cols[5].markdown("🔹 **Journaux**")

                    config = Config(
                        width="100%",
                        height=800,
                        directed=True,
                        hierarchical=False,
                        physics={
                            "solver": "forceAtlas2Based",
                            "forceAtlas2Based": {
                                "gravitationalConstant": -200,
                                "centralGravity": 0.01,
                                "springLength": 250,
                                "springConstant": 0.05
                            }
                        }
                    )
                    with st.container(border=True):
                        agraph(nodes=nodes, edges=edges, config=config)
                else:
                    st.warning("Aucun triplet trouvé. Vérifiez que la mission a bien été ingérée dans Neo4j (Étape 2).")

            except Exception as e:
                st.error(f"Impossible d'afficher le composant graphique : {e}")

    # ── Onglet 2 : Historique Missions Neo4j ─────────────────────────────────
    with tab2:
        st.subheader("Missions ingérées dans Neo4j")
        st.markdown("Retrouvez ici **toutes vos ingestions passées**. Sélectionnez une mission pour la visualiser dans la cartographie.")

        col_refresh, col_stats = st.columns([1, 2])

        with col_refresh:
            if st.button(" Actualiser la liste"):
                st.rerun()

        # Statistiques globales du graphe
        try:
            stats_res = requests.get(f"{API_BASE_URL}/api/graph/stats")
            if stats_res.status_code == 200:
                stats = stats_res.json().get("stats", {})
                if stats:
                    with col_stats:
                        stat_cols = st.columns(len(stats))
                        for i, (lbl, cnt) in enumerate(stats.items()):
                            stat_cols[i].metric(lbl, cnt)
        except Exception:
            pass

        st.divider()

        # Liste des missions Neo4j
        try:
            missions_res = requests.get(f"{API_BASE_URL}/api/graph/missions")
            if missions_res.status_code == 200:
                neo4j_missions = missions_res.json().get("missions", [])

                if not neo4j_missions:
                    st.info(" Aucune mission trouvée dans Neo4j. Validez et ingérez des triplets depuis l'Étape 2.")
                    st.markdown("**Requêtes utiles à exécuter directement dans Neo4j Browser :**")
                    st.code("// Voir tous les nœuds du graphe\nMATCH (n)-[r]->(o) RETURN n, r, o LIMIT 200\n\n// Compter les nœuds par type\nMATCH (n) RETURN labels(n)[0] AS type, count(n) AS total\n\n// Voir les relations par mission\nMATCH ()-[r]->() WHERE r.mission_id IS NOT NULL\nRETURN r.mission_id, r.source, count(r) ORDER BY count(r) DESC", language="cypher")
                else:
                    # Construire un tableau des missions
                    missions_df = pd.DataFrame(neo4j_missions)
                    missions_df = missions_df.rename(columns={
                        "mission_id": "Mission ID",
                        "source": "Source",
                        "ingested_at": "Date d'ingestion (UTC)",
                        "relation_count": "Relations"
                    })
                    st.dataframe(missions_df, use_container_width=True, hide_index=True)

                    st.markdown("#### Charger une mission dans la cartographie")
                    mission_options = {
                        f"{m['source']} — {m['mission_id'][:8]}... ({m['relation_count']} rel.)": m["mission_id"]
                        for m in neo4j_missions
                    }
                    selected_label = st.selectbox(
                        "Choisir une mission à visualiser",
                        options=list(mission_options.keys()),
                        key="neo4j_mission_select"
                    )
                    if st.button(" Charger ce graphe dans la Cartographie"):
                        st.session_state["mission_id"] = mission_options[selected_label]
                        st.success(f" Mission chargée ! Allez sur l'onglet **Cartographie Visuelle** pour afficher le graphe.")
                        st.info(f"Mission ID : `{mission_options[selected_label]}`")

                    # Requêtes Neo4j utiles
                    st.divider()
                    st.markdown("####  Requêtes Cypher utiles (Neo4j Browser)")
                    if neo4j_missions:
                        example_id = neo4j_missions[0]["mission_id"]
                        st.code(
                            f"// Voir le graphe d'une mission spécifique\n"
                            f"MATCH (s)-[r]->(o) WHERE r.mission_id = '{example_id}'\n"
                            f"RETURN s, r, o LIMIT 200\n\n"
                            f"// Toutes les missions ingérées\n"
                            f"MATCH ()-[r]->() WHERE r.mission_id IS NOT NULL\n"
                            f"RETURN DISTINCT r.mission_id, r.source, count(r) AS relations ORDER BY relations DESC\n\n"
                            f"// Tous les auteurs du graphe\n"
                            f"MATCH (a:Author) RETURN a.id, a.mission_ids, a.sources LIMIT 100",
                            language="cypher"
                        )
            else:
                st.error("Impossible de joindre l'API backend pour récupérer les missions Neo4j.")
        except Exception as e:
            st.error(f"Erreur de connexion au backend : {e}")
            st.markdown("**Requêtes de diagnostic à lancer dans Neo4j Browser :**")
            st.code(
                "// Voir tout le graphe\nMATCH (n)-[r]->(o) RETURN n, r, o LIMIT 100\n\n"
                "// Compter les nœuds par type\nMATCH (n) RETURN labels(n)[0] AS type, count(n) AS total\n\n"
                "// Voir les missions ingérées\nMATCH ()-[r]->() RETURN DISTINCT r.mission_id, count(r)",
                language="cypher"
            )

    # ── Onglet 3 : GraphRAG ───────────────────────────────────────────────────
    with tab3:
        st.markdown("### Poser une question factuelle (Anti-Hallucination)")
        st.markdown("Le système répondra **uniquement** grâce aux relations préalablement vérifiées dans Neo4j.")

        with st.container(border=True):
            query = st.text_input(
                "Votre Question",
                "Quels auteurs sont affiliés au MIT ?",
                placeholder="Ex: Qui travaille sur les électrolytes solides ?"
            )
            if st.button("🔍 Analyser via GraphRAG"):
                with st.spinner("Parcours du graphe et génération de la réponse..."):
                    res = requests.post(f"{API_BASE_URL}/api/graph/rag", params={"query": query})
                    if res.status_code == 200:
                        st.success(" Réponse d'Intelligence Sémantique :")
                        st.write(res.json()["answer"])
                        sources = res.json().get("sources", [])
                        if sources:
                            with st.expander(" Sources utilisées"):
                                for s in sources:
                                    st.markdown(f"- [{s}]({s})")
                    else:
                        st.error("Échec de la requête vers le moteur RAG.")



