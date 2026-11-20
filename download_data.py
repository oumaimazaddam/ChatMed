import json
import pathlib
import re
import sys
import time
import httpx

API = "https://api.fda.gov/drug/label.json"
OUT = pathlib.Path("data")
MAX_CHARS = 8000  # longueur maximale d'une section

# (nom FDA en anglais, nom de fichier, nom affiché)
DRUGS = [
    # Douleur, fièvre, inflammation
    ("acetaminophen", "paracetamol", "Paracétamol (acetaminophen)"),
    ("ibuprofen", "ibuprofene", "Ibuprofène (ibuprofen)"),
    ("naproxen", "naproxene", "Naproxène (naproxen)"),
    ("diclofenac", "diclofenac", "Diclofénac (diclofenac)"),
    ("aspirin", "aspirine", "Aspirine (aspirin)"),
    ("celecoxib", "celecoxib", "Célécoxib (celecoxib)"),
    ("meloxicam", "meloxicam", "Méloxicam (meloxicam)"),
    # Anti-infectieux
    ("amoxicillin", "amoxicilline", "Amoxicilline (amoxicillin)"),
    ("azithromycin", "azithromycine", "Azithromycine (azithromycin)"),
    ("ciprofloxacin", "ciprofloxacine", "Ciprofloxacine (ciprofloxacin)"),
    ("doxycycline", "doxycycline", "Doxycycline (doxycycline)"),
    ("cephalexin", "cefalexine", "Céfalexine (cephalexin)"),
    ("clarithromycin", "clarithromycine", "Clarithromycine (clarithromycin)"),
    ("metronidazole", "metronidazole", "Métronidazole (metronidazole)"),
    ("levofloxacin", "levofloxacine", "Lévofloxacine (levofloxacin)"),
    ("nitrofurantoin", "nitrofurantoine", "Nitrofurantoïne (nitrofurantoin)"),
    ("clindamycin", "clindamycine", "Clindamycine (clindamycin)"),
    ("fluconazole", "fluconazole", "Fluconazole (fluconazole)"),
    ("acyclovir", "aciclovir", "Aciclovir (acyclovir)"),
    ("oseltamivir", "oseltamivir", "Oseltamivir (oseltamivir)"),
    ("ivermectin", "ivermectine", "Ivermectine (ivermectin)"),
    ("albendazole", "albendazole", "Albendazole (albendazole)"),
    ("hydroxychloroquine", "hydroxychloroquine", "Hydroxychloroquine (hydroxychloroquine)"),
    # Cœur et vaisseaux
    ("amlodipine", "amlodipine", "Amlodipine (amlodipine)"),
    ("lisinopril", "lisinopril", "Lisinopril (lisinopril)"),
    ("atorvastatin", "atorvastatine", "Atorvastatine (atorvastatin)"),
    ("losartan", "losartan", "Losartan (losartan)"),
    ("metoprolol", "metoprolol", "Métoprolol (metoprolol)"),
    ("bisoprolol", "bisoprolol", "Bisoprolol (bisoprolol)"),
    ("simvastatin", "simvastatine", "Simvastatine (simvastatin)"),
    ("rosuvastatin", "rosuvastatine", "Rosuvastatine (rosuvastatin)"),
    ("furosemide", "furosemide", "Furosémide (furosemide)"),
    ("hydrochlorothiazide", "hydrochlorothiazide", "Hydrochlorothiazide (hydrochlorothiazide)"),
    ("clopidogrel", "clopidogrel", "Clopidogrel (clopidogrel)"),
    ("warfarin", "warfarine", "Warfarine (warfarin)"),
    ("carvedilol", "carvedilol", "Carvédilol (carvedilol)"),
    ("enalapril", "enalapril", "Énalapril (enalapril)"),
    ("valsartan", "valsartan", "Valsartan (valsartan)"),
    ("spironolactone", "spironolactone", "Spironolactone (spironolactone)"),
    ("digoxin", "digoxine", "Digoxine (digoxin)"),
    # Diabète et thyroïde
    ("metformin", "metformine", "Metformine (metformin)"),
    ("glimepiride", "glimepiride", "Glimépiride (glimepiride)"),
    ("sitagliptin", "sitagliptine", "Sitagliptine (sitagliptin)"),
    ("levothyroxine", "levothyroxine", "Lévothyroxine (levothyroxine)"),
    # Digestif
    ("omeprazole", "omeprazole", "Oméprazole (omeprazole)"),
    ("pantoprazole", "pantoprazole", "Pantoprazole (pantoprazole)"),
    ("esomeprazole", "esomeprazole", "Ésoméprazole (esomeprazole)"),
    ("famotidine", "famotidine", "Famotidine (famotidine)"),
    ("ondansetron", "ondansetron", "Ondansétron (ondansetron)"),
    ("loperamide", "loperamide", "Lopéramide (loperamide)"),
    ("metoclopramide", "metoclopramide", "Métoclopramide (metoclopramide)"),
    # Respiratoire, allergies, corticoïdes
    ("albuterol", "salbutamol", "Salbutamol (albuterol)"),
    ("montelukast", "montelukast", "Montélukast (montelukast)"),
    ("cetirizine", "cetirizine", "Cétirizine (cetirizine)"),
    ("loratadine", "loratadine", "Loratadine (loratadine)"),
    ("fexofenadine", "fexofenadine", "Fexofénadine (fexofenadine)"),
    ("prednisone", "prednisone", "Prednisone (prednisone)"),
    ("prednisolone", "prednisolone", "Prednisolone (prednisolone)"),
    ("dexamethasone", "dexamethasone", "Dexaméthasone (dexamethasone)"),
    # Neurologie et psychiatrie
    ("sertraline", "sertraline", "Sertraline (sertraline)"),
    ("fluoxetine", "fluoxetine", "Fluoxétine (fluoxetine)"),
    ("escitalopram", "escitalopram", "Escitalopram (escitalopram)"),
    ("amitriptyline", "amitriptyline", "Amitriptyline (amitriptyline)"),
    ("gabapentin", "gabapentine", "Gabapentine (gabapentin)"),
    ("levetiracetam", "levetiracetam", "Lévétiracétam (levetiracetam)"),
    ("carbamazepine", "carbamazepine", "Carbamazépine (carbamazepine)"),
    # Autres
    ("allopurinol", "allopurinol", "Allopurinol (allopurinol)"),
    ("colchicine", "colchicine", "Colchicine (colchicine)"),
    ("tamsulosin", "tamsulosine", "Tamsulosine (tamsulosin)"),
    ("finasteride", "finasteride", "Finastéride (finasteride)"),
    ("sildenafil", "sildenafil", "Sildénafil (sildenafil)"),
    ("alendronate", "alendronate", "Alendronate (alendronate)"),
]

# (champ openFDA, titre bilingue)
SECTIONS = [
    ("boxed_warning", "Boxed warning / Mise en garde encadrée"),
    ("indications_and_usage", "Indications and usage / Indications"),
    ("purpose", "Purpose / Indication"),
    ("contraindications", "Contraindications / Contre-indications"),
    ("do_not_use", "Do not use / Ne pas utiliser (contre-indications)"),
    ("ask_doctor", "Ask a doctor before use / Demander l'avis d'un médecin"),
    ("ask_doctor_or_pharmacist", "Ask a doctor or pharmacist / Demander l'avis d'un médecin ou pharmacien"),
    ("warnings", "Warnings / Mises en garde"),
    ("warnings_and_cautions", "Warnings and precautions / Mises en garde et précautions"),
    ("precautions", "Precautions / Précautions d'emploi"),
    ("stop_use", "Stop use and ask a doctor / Arrêter et consulter un médecin"),
    ("when_using", "When using this product / Pendant l'utilisation"),
    ("pregnancy_or_breast_feeding", "Pregnancy or breast-feeding / Grossesse et allaitement"),
    ("use_in_specific_populations", "Specific populations, pregnancy / Populations particulières, grossesse"),
    ("drug_interactions", "Drug interactions / Interactions médicamenteuses"),
    ("adverse_reactions", "Adverse reactions / Effets indésirables"),
    ("dosage_and_administration", "Dosage and administration / Posologie et mode d'administration"),
    ("overdosage", "Overdosage / Surdosage"),
]
WANTED = {"indications_and_usage", "contraindications", "warnings", "warnings_and_cautions",
          "adverse_reactions", "drug_interactions", "dosage_and_administration", "do_not_use",
          "ask_doctor", "stop_use"}


def score(label: dict, name: str) -> int:
    """Préfère l'étiquette la plus complète, et un seul principe actif (pas une association)."""
    names = [n.lower() for n in label.get("openfda", {}).get("generic_name", [])]
    return sum(1 for f in WANTED if f in label) + (20 if names == [name.lower()] else 0)


def fetch_label(name: str):
    """Cherche d'abord une étiquette complète (avec contre-indications), sinon n'importe laquelle."""
    queries = [
        f'openfda.generic_name:"{name}" AND _exists_:contraindications',
        f'openfda.generic_name:"{name}"',
    ]
    for q in queries:
        r = httpx.get(API, params={"search": q, "limit": 25}, timeout=60)
        if r.status_code in (400, 404):
            continue
        r.raise_for_status()
        results = r.json().get("results", [])
        if results:
            return max(results, key=lambda lab: score(lab, name))
    return None


def field_text(value) -> str:
    text = " ".join(value) if isinstance(value, list) else str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS].rsplit(" ", 1)[0] + " [...]"


def main():
    args = sys.argv[1:]
    force = "--force" in args
    names = [a.lower() for a in args if not a.startswith("--")]

    catalog = {n: (f, d) for n, f, d in DRUGS}
    if names:
        todo = [(n, *catalog.get(n, (re.sub(r"\W+", "_", n), n.capitalize()))) for n in names]
        force = True
    else:
        todo = DRUGS

    OUT.mkdir(exist_ok=True)
    target = OUT / "catalogue.json"

    # Charger l'ancien catalogue s'il existe (sauf si --force)
    if target.exists() and not force:
        with open(target, encoding="utf-8") as f:
            catalogue = json.load(f)
    else:
        catalogue = {}

    for name, filename, display in todo:
        if name in catalogue:
            print(f"DEJA   {name}")
            continue
        try:
            label = fetch_label(name)
        except httpx.HTTPError as e:
            print(f"ERREUR {name} : {e}")
            continue
        if not label:
            print(f"ABSENT {name}")
            continue

        sections = {}
        for field, title in SECTIONS:
            if field in label:
                sections[field] = field_text(label[field])

        if len(sections) < 3:
            print(f"PEU DE DONNÉES {name} ({len(sections)} sections), ignoré")
            continue

        catalogue[name] = {
            "nom_affiche": display,
            "source": "étiquette officielle FDA (openFDA), langue : anglais",
            "sections": sections,
        }
        print(f"OK     {name} ({len(sections)} sections)")
        time.sleep(0.4)

    # Sauvegarde du fichier unique
    target.write_text(
        json.dumps(catalogue, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Terminé : {len(catalogue)} médicament(s) dans {target}")


if __name__ == "__main__":
    main()