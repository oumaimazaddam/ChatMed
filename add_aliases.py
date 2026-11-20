"""
add_aliases.py - Ajoute les noms arabes et les noms commerciaux aux médicaments de data/catalogue.json

Pourquoi : les notices FDA sont en anglais. Un patient qui écrit « باراسيتامول » ou « Doliprane » doit
retrouver la fiche « acetaminophen ». Ce script ajoute deux champs à chaque médicament :
    "noms_arabes"       : noms en arabe (dénomination commune)
    "noms_commerciaux"  : marques courantes (internationales / France)

Utilisation (depuis le dossier du projet) :
    python add_aliases.py
Le script est sans danger : il crée data/catalogue.backup.json avant de modifier le fichier,
et on peut le relancer autant de fois qu'on veut.

À FAIRE VALIDER par un pharmacien : orthographe arabe et marques vendues en Tunisie.
Ajoute tes marques tunisiennes directement dans le dictionnaire ALIASES ci-dessous.
"""
import json
import shutil
import sys
from pathlib import Path

CATALOGUE = Path("data/catalogue.json")
BACKUP = Path("data/catalogue.backup.json")

# clé = nom FDA utilisé dans download_data.py : (noms arabes, noms commerciaux)
ALIASES = {
    # Douleur, fièvre, inflammation
    "acetaminophen": (["باراسيتامول", "بارسيتامول", "أسيتامينوفين", "دوليبران", "بانادول"],
                      ["Doliprane", "Efferalgan", "Panadol", "Dafalgan"]),
    "ibuprofen": (["إيبوبروفين", "ايبوبروفين", "أدفيل", "نوروفين"], ["Advil", "Nurofen", "Brufen"]),
    "naproxen": (["نابروكسين"], ["Apranax", "Naprosyn"]),
    "diclofenac": (["ديكلوفيناك", "فولتارين"], ["Voltarène", "Voltaren"]),
    "aspirin": (["أسبرين", "اسبيرين", "حمض أسيتيل الساليسيليك"], ["Aspégic", "Kardégic", "Aspirine"]),
    "celecoxib": (["سيليكوكسيب"], ["Celebrex"]),
    "meloxicam": (["ميلوكسيكام"], ["Mobic"]),
    # Anti-infectieux
    "amoxicillin": (["أموكسيسيلين", "اموكسيسيلين"], ["Clamoxyl", "Amoxil"]),
    "azithromycin": (["أزيثروميسين", "ازيثروميسين"], ["Zithromax"]),
    "ciprofloxacin": (["سيبروفلوكساسين"], ["Ciflox", "Cipro"]),
    "doxycycline": (["دوكسيسيكلين"], ["Vibramycine"]),
    "cephalexin": (["سيفاليكسين"], ["Keforal"]),
    "clarithromycin": (["كلاريثروميسين"], ["Zeclar", "Biaxin"]),
    "metronidazole": (["ميترونيدازول"], ["Flagyl"]),
    "levofloxacin": (["ليفوفلوكساسين"], ["Tavanic"]),
    "nitrofurantoin": (["نيتروفورانتوين"], ["Furadantine"]),
    "clindamycin": (["كليندامايسين"], ["Dalacine"]),
    "fluconazole": (["فلوكونازول"], ["Triflucan", "Diflucan"]),
    "acyclovir": (["أسيكلوفير", "اسيكلوفير"], ["Zovirax"]),
    "oseltamivir": (["أوسيلتاميفير"], ["Tamiflu"]),
    "ivermectin": (["إيفرمكتين", "ايفرمكتين"], ["Stromectol"]),
    "albendazole": (["ألبيندازول"], ["Zentel"]),
    "hydroxychloroquine": (["هيدروكسي كلوروكين"], ["Plaquenil"]),
    # Cœur et vaisseaux
    "amlodipine": (["أملوديبين", "املوديبين"], ["Amlor", "Norvasc"]),
    "lisinopril": (["ليسينوبريل"], ["Zestril"]),
    "atorvastatin": (["أتورفاستاتين", "اتورفاستاتين"], ["Tahor", "Lipitor"]),
    "losartan": (["لوسارتان"], ["Cozaar"]),
    "metoprolol": (["ميتوبرولول"], ["Lopressor", "Seloken"]),
    "bisoprolol": (["بيسوبرولول"], ["Cardensiel", "Concor"]),
    "simvastatin": (["سيمفاستاتين"], ["Zocor"]),
    "rosuvastatin": (["روسوفاستاتين"], ["Crestor"]),
    "furosemide": (["فوروسيميد"], ["Lasilix", "Lasix"]),
    "hydrochlorothiazide": (["هيدروكلوروثيازيد"], ["Esidrex"]),
    "clopidogrel": (["كلوبيدوغريل"], ["Plavix"]),
    "warfarin": (["وارفارين"], ["Coumadine"]),
    "carvedilol": (["كارفيديلول"], ["Kredex", "Coreg"]),
    "enalapril": (["إينالابريل"], ["Renitec"]),
    "valsartan": (["فالسارتان"], ["Tareg", "Diovan"]),
    "spironolactone": (["سبيرونولاكتون"], ["Aldactone"]),
    "digoxin": (["ديجوكسين", "ديغوكسين"], ["Digoxine Nativelle", "Lanoxin"]),
    # Diabète et thyroïde
    "metformin": (["ميتفورمين"], ["Glucophage"]),
    "glimepiride": (["غليميبيريد", "جليميبيريد"], ["Amarel", "Amaryl"]),
    "sitagliptin": (["سيتاغليبتين"], ["Januvia"]),
    "levothyroxine": (["ليفوثيروكسين"], ["Levothyrox", "Synthroid"]),
    # Digestif
    "omeprazole": (["أوميبرازول", "اوميبرازول"], ["Mopral", "Losec"]),
    "pantoprazole": (["بانتوبرازول"], ["Inipomp", "Pantoloc"]),
    "esomeprazole": (["إيزوميبرازول", "إسوميبرازول"], ["Inexium", "Nexium"]),
    "famotidine": (["فاموتيدين"], ["Pepcid"]),
    "ondansetron": (["أوندانسيترون"], ["Zophren"]),
    "loperamide": (["لوبيراميد"], ["Imodium"]),
    "metoclopramide": (["ميتوكلوبراميد"], ["Primperan"]),
    # Respiratoire, allergies, corticoïdes
    "albuterol": (["سالبوتامول", "فنتولين"], ["Ventoline", "Ventolin"]),
    "montelukast": (["مونتيلوكاست"], ["Singulair"]),
    "cetirizine": (["سيتيريزين"], ["Zyrtec"]),
    "loratadine": (["لوراتادين"], ["Clarityne", "Claritin"]),
    "fexofenadine": (["فيكسوفينادين"], ["Telfast"]),
    "prednisone": (["بريدنيزون"], ["Cortancyl"]),
    "prednisolone": (["بريدنيزولون"], ["Solupred"]),
    "dexamethasone": (["ديكساميثازون"], ["Dectancyl", "Decadron"]),
    # Neurologie et psychiatrie
    "sertraline": (["سيرترالين"], ["Zoloft"]),
    "fluoxetine": (["فلوكسيتين"], ["Prozac"]),
    "escitalopram": (["إسيتالوبرام", "اسيتالوبرام"], ["Seroplex", "Lexapro"]),
    "amitriptyline": (["أميتريبتيلين"], ["Laroxyl", "Elavil"]),
    "gabapentin": (["غابابنتين", "جابابنتين"], ["Neurontin"]),
    "levetiracetam": (["ليفيتيراسيتام"], ["Keppra"]),
    "carbamazepine": (["كاربامازيبين"], ["Tegretol"]),
    # Autres
    "allopurinol": (["ألوبورينول"], ["Zyloric", "Zyloprim"]),
    "colchicine": (["كولشيسين"], ["Colchimax", "Colcrys"]),
    "tamsulosin": (["تامسولوسين"], ["Omix", "Flomax"]),
    "finasteride": (["فيناسترايد"], ["Proscar"]),
    "sildenafil": (["سيلدينافيل"], ["Viagra"]),
    "alendronate": (["أليندرونات"], ["Fosamax"]),
}


def main():
    if not CATALOGUE.exists():
        sys.exit(f"{CATALOGUE} introuvable : lance d'abord python download_data.py")
    shutil.copy(CATALOGUE, BACKUP)
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))

    updated, missing = 0, []
    for name, entry in catalogue.items():
        if name in ALIASES:
            arabic, brands = ALIASES[name]
            entry["noms_arabes"] = arabic
            entry["noms_commerciaux"] = brands
            updated += 1
        else:
            missing.append(name)

    CATALOGUE.write_text(json.dumps(catalogue, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{updated}/{len(catalogue)} médicaments mis à jour (sauvegarde : {BACKUP})")
    if missing:
        print("Sans noms arabes (à ajouter dans ALIASES) :", ", ".join(missing))


if __name__ == "__main__":
    main()