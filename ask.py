"""Teste le RAG en ligne de commande, sans l'API.

Usage : python ask.py "Quelles sont les contre-indications du paracétamol ?"
"""
import asyncio
import sys

from app import rag, triage
from app.config import MIN_SCORE, STRONG_SCORE


async def main(question: str):
    kind = triage.classify_message(question)
    if kind != "ok":
        print(f"[règle de sécurité : {kind}]")
        print(triage.MESSAGES[kind])
        return

    chunks = rag.retrieve(question)
    print("Passages trouvés :")
    for c in chunks:
        print(f"  score={c['score']:.2f}  nommé={c['named']}  {c['drug']} | {c['ref']}")

    if not rag.is_confident(chunks):
        print(f"\n[passage refusé : score sous MIN_SCORE={MIN_SCORE}, ou médicament non nommé "
              f"avec un score sous STRONG_SCORE={STRONG_SCORE}]")
        print(triage.NOT_FOUND)
        return

    print("\nRéponse :")
    async for tok in rag.stream_answer(rag.build_messages(question, chunks)):
        print(tok, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "Quelles sont les contre-indications ?"))