import os
import numpy as np
from fastembed import TextEmbedding
from google import genai
from .models import Chunk

_embedder = TextEmbedding("BAAI/bge-small-en-v1.5")
_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MIN_SCORE = 0.45   # tune this using test questions (Step 7)

def retrieve(query, k=5):
    chunks = list(Chunk.objects.filter(source__active=True).select_related("source"))
    if not chunks: return []
    M = np.array([c.embedding for c in chunks])
    M /= np.linalg.norm(M, axis=1, keepdims=True)
    q = np.array(next(iter(_embedder.embed([query]))))
    q /= np.linalg.norm(q)
    scores = M @ q
    top = np.argsort(scores)[::-1][:k]
    return [(chunks[i], float(scores[i])) for i in top if scores[i] >= MIN_SCORE]

PROMPT = """You help older adults decide whether a message, call, or email may be a scam.
Use ONLY the numbered sources below. After each claim, cite its source like [1].
Write in short, plain sentences, with no jargon.
Structure: (1) Warning signs you notice in the person's message, (2) What to do next.
Never say a message is definitely safe or definitely a scam; say what looks risky.
Never ask for passwords, account numbers, or other personal details.
If the sources don't cover the question, say so.

SOURCES:
{context}

PERSON'S MESSAGE:
{question}
"""

def answer(question):
    hits = retrieve(question)
    if not hits:
        return {"answer": "I couldn't find guidance on this in my trusted sources. "
                          "If you're worried, don't click links or share information. "
                          "Contact the company directly using a number you already trust.",
                "sources": []}
    context = "\n\n".join(f"[{i+1}] ({c.source.publisher}: {c.source.title})\n{c.text}"
                          for i, (c, _) in enumerate(hits))
    resp = _client.models.generate_content(
        model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=PROMPT.format(context=context, question=question))
    sources = [{"id": i+1, "title": c.source.title, "publisher": c.source.publisher,
                "url": c.source.url, "snippet": c.text[:300]}
               for i, (c, _) in enumerate(hits)]
    return {"answer": resp.text, "sources": sources}