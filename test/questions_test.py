# questions_test.py

QUESTIONS = {
    "factuel": [
        "Quelle est l'affiliation principale des chercheurs travaillant sur les anodes silicium-carbone ?",
        "Quels auteurs ont publié dans Nature sur le recyclage des batteries lithium-ion ?",
        "Dans quel journal a été publié l'article sur le recyclage direct des matériaux de batteries lithium-ion en 2026 ?",
        "Quelles institutions sont affiliées aux recherches sur les électrolytes solides ?",
        "Qui sont les chercheurs les plus actifs sur la récupération des matériaux cathode LFP ?",
        "Quelle est l'organisation partenaire citée dans les recherches sur l'économie circulaire des batteries EV ?",
        "Quels financeurs soutiennent les recherches sur les batteries à état solide ?",
        "Quels auteurs sont affiliés à l'Argonne National Laboratory dans ce corpus ?",
        "Dans quelle plage d'années se concentrent les publications sur le cobalt et les chaînes d'approvisionnement ?",
        "Quelle institution est associée à la Faraday Institution dans le corpus ?"
    ],
    "relationnel": [
        "Quels chercheurs collaborent avec des institutions spécialisées en génie chimique sur le recyclage LFP ?",
        "Quelles organisations partenaires sont associées aux recherches sur la régénération des cathodes ?",
        "Quels liens existent entre les institutions académiques et les initiatives de durabilité des batteries ?",
        "Quels chercheurs partagent une expertise sur les matériaux critiques et les chaînes d'approvisionnement EV ?",
        "Quelles institutions travaillent conjointement sur la récupération du lithium et du cobalt ?",
        "Quels partenariats de financement sont associés aux recherches sur l'économie circulaire des batteries ?",
        "Quels auteurs publient à la fois sur le recyclage des cathodes et sur les systèmes en boucle fermée ?",
        "Quels liens existe-t-il entre les programmes de recherche en durabilité et les fabricants de batteries EV ?",
        "Quelles institutions de recherche sont les plus connectées dans le réseau de collaboration du corpus ?",
        "Quels chercheurs sont à l'intersection des thématiques recyclage et matériaux à état solide ?"
    ],
    "sensemaking": [
        "Quelles sont les tendances dominantes dans le corpus sur le recyclage des batteries lithium-ion entre 2019 et 2026 ?",
        "Quels clusters thématiques émergent de l'analyse du corpus sur les matériaux de batteries ?",
        "Comment évolue la concentration des recherches sur les matériaux critiques (cobalt, lithium) sur la période 2019–2026 ?",
        "Quels sont les principaux défis identifiés dans le corpus concernant la durabilité des chaînes d'approvisionnement EV ?",
        "Quelles technologies de récupération des cathodes sont les plus représentées dans la littérature récente ?",
        "Quel est le positionnement des institutions académiques vs industrielles dans le corpus de recherche sur les batteries ?",
        "Quelles sont les lacunes de recherche identifiables dans ce corpus sur les systèmes de recyclage en boucle fermée ?",
        "Comment les partenariats de financement structurent-ils la production scientifique sur les batteries EV ?",
        "Quels signaux faibles de transfert technologie-industrie sont détectables dans le corpus 2024–2026 ?",
        "Quelle est la structure du réseau de collaboration scientifique dans le domaine du recyclage des batteries ?"
    ]
}

print(f"Total questions : {sum(len(v) for v in QUESTIONS.values())}")
for cat, qs in QUESTIONS.items():
    print(f"  {cat} : {len(qs)} questions")