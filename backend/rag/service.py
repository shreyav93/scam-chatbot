import os
import time
from functools import lru_cache

import numpy as np

from . import confidence, guardrails
from .models import Chunk

MIN_SCORE = 0.45   # tune with your test questions


@lru_cache(maxsize=1)
def _embedder():
    from fastembed import TextEmbedding
    return TextEmbedding("BAAI/bge-small-en-v1.5")   # local, free


def retrieve(query, k=4):
    chunks = list(Chunk.objects.filter(source__active=True).select_related("source"))
    if not chunks:
        return []
    m = np.array([c.embedding for c in chunks], dtype=float)
    m /= np.linalg.norm(m, axis=1, keepdims=True)
    q = np.array(next(iter(_embedder().embed([query]))), dtype=float)
    q /= np.linalg.norm(q)
    scores = m @ q
    top = np.argsort(scores)[::-1][:k]
    return [(chunks[i], float(scores[i])) for i in top if scores[i] >= MIN_SCORE]


PROMPT = """You explain possible scams to older adults in plain, short sentences.
Use ONLY the numbered sources. Put the source number after each claim, like [1].
Never say a message is definitely safe or definitely a scam.
Never ask for personal details.
Format exactly:
Warning signs I notice:
- ...
What to do next:
- ...
If the sources do not cover this, say: "My sources don't cover this."
End with one final line, exactly one of:
Source check: agree      (the sources say consistent things about this message)
Source check: partial    (the sources only cover part of this message)
Source check: conflict   (the sources disagree with each other)

SOURCES:
{context}

MESSAGE:
{question}
"""

NO_SOURCE_ANSWER = (
    "I couldn't find guidance on this in my trusted sources. Don't click links or "
    "share information. Contact the company using a phone number you already trust."
)


def generate(prompt, visitor_id):
    from google import genai
    from google.genai import errors, types

    guardrails.check_enabled()
    model = guardrails.get_model()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise guardrails.LimitReached("The assistant isn't configured yet.")
    client = genai.Client(api_key=key)

    for attempt in range(3):
        guardrails.reserve_call(visitor_id)   # counts every attempt
        try:
            r = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=guardrails.MAX_OUTPUT_TOKENS,
                ),
            )
            return r.text or ""
        except errors.APIError as e:
            if e.code in (429, 503):
                if attempt < 2:
                    time.sleep(2 ** attempt * 2)
                    continue
                raise guardrails.LimitReached("We're busy. Try again in a minute.")
            raise


def answer(question, visitor_id="local"):
    hits = retrieve(question)
    if not hits:
        return {"answer": NO_SOURCE_ANSWER, "sources": [], "confidence": confidence.no_support()}

    context = "\n\n".join(
        f"[{i + 1}] ({c.source.publisher}: {c.source.title})\n{c.text}"
        for i, (c, _) in enumerate(hits)
    )
    raw = generate(PROMPT.format(context=context, question=question), visitor_id).strip()
    text, agreement = confidence.split_agreement(raw)
    if not text:
        return {"answer": NO_SOURCE_ANSWER, "sources": [], "confidence": confidence.no_support()}
    if "don't cover this" in text.lower():
        return {"answer": text, "sources": [], "confidence": confidence.no_support()}
    cited = {n for n in confidence.cited_numbers(text) if 1 <= n <= len(hits)}   # ignore invented numbers
    conf, details = confidence.assess(
        question, text, hits,
        embed=lambda texts: list(_embedder().embed(texts)),
        agreement=agreement,
    )
    sources = [
        {"id": i + 1, "title": c.source.title, "publisher": c.source.publisher,
         "url": c.source.url, "snippet": c.text[:300],
         "cited": (i + 1) in cited, **detail}
        for i, ((c, _), detail) in enumerate(zip(hits, details))
    ]
    return {"answer": text, "sources": sources, "confidence": conf}