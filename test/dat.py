# stats_descriptives.py
import pandas as pd
from collections import Counter

df = pd.read_excel('..\Excel-Data-Abbcari-Battery-materials.xlsx')

# ── 1. Statistiques de base ──────────────────────────────────────
print("=" * 55)
print("STATISTIQUES DESCRIPTIVES DU CORPUS — §4.1")
print("=" * 55)
print(f"Nombre total d'articles ingérés         : {len(df)}")

# ── 2. Distribution par année ────────────────────────────────────
print("\n── Distribution par année ──")
year_counts = df['Year'].value_counts().sort_index()
for year, count in year_counts.items():
    print(f"  {year} : {count} articles")

# ── 3. Journaux ──────────────────────────────────────────────────
journals = df['Journal'].dropna().unique()
print(f"\nNombre de journaux distincts             : {len(journals)}")
print("Top 5 journaux :")
for j, n in df['Journal'].value_counts().head(5).items():
    print(f"  {j[:60]:<60} ({n})")

# ── 4. Auteurs ───────────────────────────────────────────────────
all_authors = []
for val in df['Authors'].dropna():
    for a in str(val).split(','):
        a = a.strip()
        if a:
            all_authors.append(a)

author_counts = Counter(all_authors)
print(f"\nNombre total de mentions d'auteurs       : {len(all_authors)}")
print(f"Nombre d'auteurs uniques                 : {len(author_counts)}")
print("Top 10 auteurs les plus fréquents :")
for author, count in author_counts.most_common(10):
    print(f"  {author:<45} ({count} articles)")

# ── 5. Affiliations ──────────────────────────────────────────────
all_affils = []
for val in df['Affiliations'].dropna():
    for a in str(val).split(','):
        a = a.strip()
        if a:
            all_affils.append(a)

affil_counts = Counter(all_affils)
print(f"\nNombre d'affiliations uniques            : {len(affil_counts)}")
print("Top 10 institutions les plus fréquentes :")
for affil, count in affil_counts.most_common(10):
    print(f"  {affil[:55]:<55} ({count})")

# ── 6. Partenaires / financeurs ──────────────────────────────────
all_partners = []
for val in df['Partners or funding sources'].dropna():
    for p in str(val).split(','):
        p = p.strip()
        if p:
            all_partners.append(p)

partner_counts = Counter(all_partners)
print(f"\nNombre de partenaires/financeurs uniques : {len(partner_counts)}")
print("Top 10 partenaires/financeurs :")
for p, count in partner_counts.most_common(10):
    print(f"  {p[:55]:<55} ({count})")

# ── 7. Mots-clés ─────────────────────────────────────────────────
all_kw = []
for val in df['Key words'].dropna():
    for k in str(val).split(','):
        k = k.strip().lower()
        if k:
            all_kw.append(k)

kw_counts = Counter(all_kw)
print(f"\nNombre de mots-clés uniques              : {len(kw_counts)}")
print("Top 20 mots-clés les plus fréquents :")
for kw, count in kw_counts.most_common(20):
    print(f"  {kw:<45} ({count})")

print("\n" + "=" * 55)
print("Copie ces chiffres dans le tableau §4.1")
print("=" * 55)