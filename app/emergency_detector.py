"""
app/emergency_detector.py - Partie Machine Learning de la détection d'urgence (ChatMed)

Rôle : donner une probabilité d'urgence pour les messages que les règles de triage.py ne couvrent pas.
Ce module ne touche PAS à la base de données : l'enregistrement des alertes est fait par app/alerts.py,
appelé depuis app/triage.py (check_and_alert).

Installation : pip install scikit-learn joblib

Commandes :
    python app/emergency_detector.py train   # entraîne et sauvegarde emergency_model.joblib (dans app/)
    python app/emergency_detector.py test    # teste quelques phrases
"""
import re
import sys
import unicodedata
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline

MODEL_PATH = Path(__file__).with_name("emergency_model.joblib")
THRESHOLD = 0.60  # même valeur que ML_ONLY_THRESHOLD dans triage.py


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------- Données d'entraînement
# Pour améliorer le modèle : ajoute des phrases ici (FR, AR, dialecte tunisien), puis relance "train".
URGENT = [
    "j'ai une douleur thoracique très forte",
    "j'ai mal dans la poitrine et mon bras gauche est engourdi",
    "je n'arrive plus à respirer",
    "j'ai du mal à respirer depuis ce matin",
    "mon père s'est évanoui et ne répond plus",
    "j'ai perdu connaissance tout à l'heure",
    "ma mère a le visage qui s'affaisse et elle parle mal",
    "mon enfant fait une convulsion",
    "je crache du sang",
    "j'ai vomi du sang cette nuit",
    "saignement abondant qui ne s'arrête pas",
    "j'ai pris trop de comprimés, je crois que c'est une overdose",
    "mon bébé a avalé des médicaments",
    "mon visage gonfle après avoir pris l'antibiotique",
    "ma gorge gonfle, j'ai du mal à avaler",
    "réaction allergique grave, je suffoque",
    "j'ai des idées suicidaires",
    "je veux mourir",
    "douleur insupportable au ventre depuis une heure",
    "je ressens un serrement dans la poitrine qui irradie dans la mâchoire",
    "mon fils est tout bleu et respire mal",
    "paralysie soudaine du bras droit",
    "je n'arrive plus à parler correctement",
    "j'ai très mal à la poitrine et je transpire beaucoup",
    "il y a du sang dans mes selles en grande quantité",
    "malaise brutal avec palpitations et vertiges",
    "ma femme enceinte saigne beaucoup",
    "crise d'épilepsie, il tremble et ne répond pas",
    "je me sens mourir, le cœur bat trop vite et j'ai mal",
    "douleur atroce dans la tête, la pire de ma vie",
]

NORMAL = [
    "quelles sont les contre-indications du paracétamol ?",
    "puis-je prendre de l'ibuprofène avec du paracétamol ?",
    "j'ai un petit rhume depuis deux jours",
    "j'ai mal à la tête depuis hier, rien de grave",
    "quelle est la posologie de l'amoxicilline ?",
    "comment conserver mes médicaments ?",
    "effets secondaires de l'aspirine",
    "j'ai la gorge un peu irritée",
    "quels aliments éviter avec la metformine ?",
    "est-ce que je peux boire de l'alcool avec cet antibiotique ?",
    "comment prendre rendez-vous avec un médecin ?",
    "j'ai un peu de toux sèche",
    "que faire contre les allergies saisonnières ?",
    "mon enfant a un peu de fièvre à 38",
    "quels sont les bienfaits de la vitamine D ?",
    "j'ai mal au dos après le sport",
    "comment lire une notice de médicament ?",
    "différence entre générique et princeps",
    "j'ai oublié de prendre ma pilule hier soir, que faire ?",
    "est-ce normal d'avoir un peu sommeil avec cet antihistaminique ?",
    "quels sont les symptômes de la grippe ?",
    "comment faire baisser une petite fièvre ?",
    "je veux connaître la composition du doliprane",
    "combien de temps durent les effets de l'ibuprofène ?",
    "puis-je donner du sirop à mon enfant de 5 ans ?",
    "j'ai des douleurs musculaires légères",
    "que contient ce guide de santé sur le diabète ?",
    "j'ai le nez bouché le matin",
    "conseils pour mieux dormir",
    "comment bien se laver les mains ?",
]


# ---------------------------------------------------------------- Entraînement
def build_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(preprocessor=normalize, analyzer="char_wb",
                                  ngram_range=(2, 5), sublinear_tf=True)),
        ("clf", LogisticRegression(C=5, class_weight="balanced", max_iter=1000)),
    ])


def train() -> None:
    X = URGENT + NORMAL
    y = [1] * len(URGENT) + [0] * len(NORMAL)

    # Validation croisée : regarde surtout le RECALL de la classe "urgence"
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    pred = cross_val_predict(build_pipeline(), X, y, cv=cv)
    print(classification_report(y, pred, target_names=["normal", "urgence"]))

    joblib.dump(build_pipeline().fit(X, y), MODEL_PATH)
    print(f"Modèle sauvegardé : {MODEL_PATH}")


# ---------------------------------------------------------------- Prédiction (utilisée par triage.py)
_model = None


def _load_model():
    global _model
    if _model is None:
        if not MODEL_PATH.exists():
            train()
        _model = joblib.load(MODEL_PATH)
    return _model


def check_emergency(text: str) -> dict:
    """Retourne {"urgent": bool, "probability": float}"""
    proba = float(_load_model().predict_proba([text])[0][1])
    return {"urgent": proba >= THRESHOLD, "probability": round(proba, 3)}


if __name__ == "__main__":
    if (sys.argv[1] if len(sys.argv) > 1 else "test") == "train":
        train()
    else:
        for t in ["j'ai un petit mal de tête",
                  "quelles sont les contre-indications du paracétamol ?",
                  "j'ai très mal à la poitrine et je transpire beaucoup",
                  "mon père a perdu connaissance"]:
            print(t, "->", check_emergency(t))