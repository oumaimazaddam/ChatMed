import json
import pathlib
import sys

from app.rag import col, embed

DATA = pathlib.Path("data")
CATALOGUE = DATA / "catalogue.json"
BATCH = 16
CHUNK_SIZE = 800
OVERLAP = 150

# Cartographie des sections FDA/Catalogue vers le français
SECTION_TITLES = {
    "boxed_warning": "Mise en garde encadrée",
    "indications_and_usage": "Indications",
    "purpose": "Indication",
    "contraindications": "Contre-indications",
    "do_not_use": "Ne pas utiliser / Contre-indications",
    "ask_doctor": "Avis médical nécessaire",
    "ask_doctor_or_pharmacist": "Avis médical ou pharmaceutique",
    "warnings": "Mises en garde",
    "warnings_and_cautions": "Mises en garde et précautions",
    "precautions": "Précautions d'emploi",
    "stop_use": "Arrêt et consultation",
    "when_using": "Pendant l'utilisation",
    "pregnancy_or_breast_feeding": "Grossesse et allaitement",
    "use_in_specific_populations": "Populations particulières",
    "drug_interactions": "Interactions médicamenteuses",
    "adverse_reactions": "Effets indésirables",
    "dosage_and_administration": "Posologie",
    "overdosage": "Surdosage",
}


def clean(text: str) -> str:
    import re
    return re.sub(r"\s+", " ", text).strip()


def split(text: str, size: int = CHUNK_SIZE, overlap: int = OVERLAP):
    """Découpe en morceaux de ~`size` caractères, en coupant sur un espace."""
    start, n = 0, len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            cut = text.rfind(" ", start, end)
            if cut > start + size // 2:
                end = cut
        yield text[start:end].strip()
        if end >= n:
            break
        start = max(end - overlap, start + 1)


def alias_text(entry: dict) -> str:
    """Noms arabes et marques (ajoutés par add_aliases.py). Ils sont écrits dans chaque morceau indexé,
    pour retrouver le bon médicament quand le patient écrit « باراسيتامول » ou « Doliprane »."""
    parts = []
    arabic = entry.get("noms_arabes", [])
    brands = entry.get("noms_commerciaux", [])
    if arabic:
        parts.append("بالعربية: " + "، ".join(arabic))
    if brands:
        parts.append("Marques : " + ", ".join(brands))
    return " | ".join(parts)


def drug_documents(name: str, entry: dict):
    """Génère (id, document, métadonnées) pour un médicament du catalogue."""
    drug = entry.get("nom_affiche", name)
    aliases = alias_text(entry)
    docs, metas = [], []

    for section_key, text in entry.get("sections", {}).items():
        # Utiliser le titre français s'il existe pour aider le modèle d'embedding
        section_title = SECTION_TITLES.get(section_key, section_key)
        prefix = f"{drug} ({aliases}) — {section_title} : " if aliases else f"{drug} — {section_title} : "

        for chunk in split(clean(text)):
            if len(chunk) < 50:
                continue
            docs.append(prefix + chunk)
            metas.append({
                "drug": drug,  # inchangé : utilisé pour les sources affichées et pour le contrôle « DEJA »
                "section": section_key,
                "section_title": section_title,
                "source": "catalogue.json",
            })
    return docs, metas


def main():
    args = sys.argv[1:]
    force = "--force" in args
    wanted = [a.lower() for a in args if not a.startswith("--")]

    if not CATALOGUE.exists():
        print(f"Aucun fichier {CATALOGUE}. Lance python download_data.py d'abord.")
        return

    with open(CATALOGUE, encoding="utf-8") as f:
        catalogue = json.load(f)

    if wanted:
        catalogue = {n: e for n, e in catalogue.items() if n.lower() in wanted}
        force = True
    if not catalogue:
        print("Aucun médicament à traiter dans le catalogue.")
        return

    total = 0
    for i, (name, entry) in enumerate(sorted(catalogue.items()), start=1):
        drug_label = entry.get("nom_affiche", name)
        label = f"[{i}/{len(catalogue)}] {drug_label}"

        # Un médicament est considéré "déjà en base" si au moins un de ses morceaux existe
        if not force and not wanted and col.get(where={"drug": drug_label}, limit=1)["ids"]:
            print(f"DEJA   {label}")
            continue

        try:
            docs, metas = drug_documents(name, entry)
            if not docs:
                print(f"VIDE   {label} (sections vides ?)")
                continue

            ids = [f"{drug_label}-{j}" for j in range(len(docs))]

            # Supprimer l'ancienne version du médicament avant de réinsérer
            col.delete(where={"drug": drug_label})

            for j in range(0, len(docs), BATCH):
                col.add(
                    ids=ids[j:j + BATCH],
                    documents=docs[j:j + BATCH],
                    metadatas=metas[j:j + BATCH],
                    embeddings=embed(docs[j:j + BATCH])
                )
            total += len(docs)
            print(f"OK     {label} : {len(docs)} morceaux")
        except Exception as e:  # noqa: BLE001
            print(f"ERREUR {label} : {e}")

    print("Total de morceaux ajoutés :", total)
    print("Total de morceaux en base :", col.count())


if __name__ == "__main__":
    main()