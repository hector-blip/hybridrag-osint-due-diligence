import pandas as pd

data = [
    {
        'Title': 'Solid-state electrolytes for next-generation lithium-ion batteries',
        'Authors': 'Zhang, Wei; Liu, Chen; Park, Seung-Hwan',
        'Affiliations': '[Zhang, Wei] MIT, Department of Materials Science, Cambridge, MA USA; [Liu, Chen] Stanford University, Department of Chemistry, Stanford, CA USA; [Park, Seung-Hwan] Samsung SDI R&D Center, Suwon, South Korea',
        'Year': 2023,
        'Abstract': 'We present a novel synthesis method for sulfide-based solid-state electrolytes achieving ionic conductivity of 12 mS/cm at room temperature. The fabricated all-solid-state cells demonstrated exceptional cycle stability over 500 cycles with coulombic efficiency above 99.8%. Our experimental results confirm the superiority of the thiophosphate framework for large-scale battery manufacturing.',
        'DOI': '10.1016/j.joule.2023.01.001',
        'Accession Number': 'WOS:000934521700001'
    },
    {
        'Title': 'High-throughput screening of anode materials for lithium metal batteries',
        'Authors': 'Dupont, Marie; Rossi, Alberto; Chen, Xiaoming',
        'Affiliations': '[Dupont, Marie] CEA LITEN, Grenoble, France; [Rossi, Alberto] Politecnico di Milano, Department of Energy, Milan, Italy; [Chen, Xiaoming] Argonne National Laboratory, Lemont, IL USA',
        'Year': 2022,
        'Abstract': 'Using density functional theory combined with machine learning potentials, we screened over 5000 candidate anode materials for lithium metal batteries. Key findings include three silicon-carbon composite architectures with volumetric expansion below 5%. Experimental validation confirmed a specific capacity of 1850 mAh/g after 300 cycles at C/2 rate.',
        'DOI': '10.1038/s41560-022-01045-7',
        'Accession Number': 'WOS:000812345600002'
    },
    {
        'Title': 'Thermal management systems for EV battery packs: a comparative study',
        'Authors': 'Johnson, Robert A.; Kim, Min-Ji; Okafor, Emmanuel',
        'Affiliations': '[Johnson, Robert A.] University of Michigan, Ann Arbor, MI USA; [Kim, Min-Ji] LG Energy Solution, Battery Research Institute, Seoul, South Korea; [Okafor, Emmanuel] Stellantis, Battery Systems Engineering, Auburn Hills, MI USA',
        'Year': 2023,
        'Abstract': 'This study experimentally compares liquid cooling, phase change materials, and heat pipe systems for 100 kWh EV battery packs. Results show liquid cooling maintains cell temperature within 2 degrees Celsius during fast charging at 350 kW. The proposed hybrid thermal management architecture reduces peak temperature by 18% compared to conventional approaches.',
        'DOI': '10.1016/j.apenergy.2023.120456',
        'Accession Number': 'WOS:000923456700003'
    },
    {
        'Title': 'Recycling of spent lithium-ion batteries: hydrometallurgical process optimization',
        'Authors': 'Garcia, Sofia; Nakamura, Takeshi; Williams, David J.',
        'Affiliations': '[Garcia, Sofia] Redwood Materials, Research Division, Carson City, NV USA; [Nakamura, Takeshi] Tokyo University of Science, Department of Applied Chemistry, Tokyo, Japan; [Williams, David J.] Oak Ridge National Laboratory, Oak Ridge, TN USA',
        'Year': 2022,
        'Abstract': 'We demonstrate an optimized hydrometallurgical process achieving 98.7% recovery of lithium, cobalt, nickel, and manganese from spent NMC811 cathodes. The closed-loop process reduces fresh material consumption by 85% compared to primary mining. Pilot-scale validation at 10 kg/batch confirms industrial scalability with a carbon footprint 60% lower than virgin material production.',
        'DOI': '10.1021/acs.est.2c04567',
        'Accession Number': 'WOS:000834512300004'
    },
    {
        'Title': 'Fast-charging protocols for silicon-graphite composite anodes',
        'Authors': 'Thompson, Emily R.; Leblanc, Jean-Paul; Ferrara, Giulia',
        'Affiliations': '[Thompson, Emily R.] University of Texas at Austin, Walker Department of Mechanical Engineering, Austin, TX USA; [Leblanc, Jean-Paul] CNRS, ICMCB Laboratory, Bordeaux, France; [Ferrara, Giulia] Panasonic Energy, Advanced R&D Center, Osaka, Japan',
        'Year': 2024,
        'Abstract': 'We developed adaptive fast-charging protocols based on real-time electrochemical impedance spectroscopy for silicon-graphite anodes. The protocol achieves 80% state of charge in 12 minutes while limiting lithium plating to undetectable levels. Cycle life testing over 1000 cycles showed only 8% capacity fade, representing a 3x improvement over constant-current fast charging.',
        'DOI': '10.1002/adma.202309876',
        'Accession Number': 'WOS:001012345600005'
    },
    {
        'Title': 'Cathode material degradation mechanisms in NMC811 cells under fast charging',
        'Authors': 'Patel, Ananya; Schneider, Klaus; Yamamoto, Hiroshi',
        'Affiliations': '[Patel, Ananya] Georgia Institute of Technology, School of Materials Science, Atlanta, GA USA; [Schneider, Klaus] Technical University of Munich, Chair of Electrical Energy Storage, Munich, Germany; [Yamamoto, Hiroshi] Panasonic Holdings, Energy Research Division, Osaka, Japan',
        'Year': 2023,
        'Abstract': 'Using synchrotron X-ray diffraction and cryo-electron microscopy, we investigated structural degradation in NMC811 cathodes during high-rate cycling. We identified intergranular cracking and lithium-poor phase formation as primary failure mechanisms. Coating the cathode particles with 2 nm Al2O3 via atomic layer deposition suppressed crack formation and extended cycle life by 40%.',
        'DOI': '10.1002/aenm.202300891',
        'Accession Number': 'WOS:000978654300006'
    },
    {
        'Title': 'Machine learning prediction of battery state of health using electrochemical impedance spectroscopy',
        'Authors': 'Kowalski, Piotr; Fernandez, Carlos; Lee, Ji-Yeon',
        'Affiliations': '[Kowalski, Piotr] Warsaw University of Technology, Faculty of Electrical Engineering, Warsaw, Poland; [Fernandez, Carlos] CIRCE Institute, Zaragoza, Spain; [Lee, Ji-Yeon] SK Innovation, Battery R&D Institute, Daejeon, South Korea',
        'Year': 2024,
        'Abstract': 'We trained a gradient-boosted machine learning model on electrochemical impedance spectroscopy data from 450 aged lithium-ion cells to predict state of health with mean absolute error of 1.3%. The model generalizes across different cell chemistries (NMC, LFP, NCA) without retraining. Real-time integration into a battery management system was validated on a 48V e-bike battery pack.',
        'DOI': '10.1016/j.jpowsour.2024.233102',
        'Accession Number': 'WOS:001056789400007'
    }
]

df = pd.DataFrame(data)
output_path = 'exemple_import_wos.xlsx'
df.to_excel(output_path, index=False)
print(f'Fichier cree : {output_path}')
print(f'Lignes : {len(df)} articles')
print(f'Colonnes : {list(df.columns)}')
print('\nApercu du contenu :')
print(df[['Title', 'Authors', 'Year']].to_string())
