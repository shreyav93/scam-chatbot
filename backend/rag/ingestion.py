import csv
import hashlib
import io
import os

from django.db import transaction
from django.utils import timezone
from pypdf import PdfReader

from .models import Chunk, Source
from .service import _embedder   # shared, cached model (loads on first use)

ALLOWED = {".pdf", ".txt", ".csv"}
MAX_BYTES = 5 * 1024 * 1024


def chunk_text(text: str, chunk_size: int = 250, overlap: int = 40):
  """Splits text into overlapping chunks (250 words fits the embedding model's limit)."""
  words = text.split()
  chunks = []
  for i in range(0, len(words), chunk_size - overlap):
    chunks.append(" ".join(words[i : i + chunk_size]))
    if i + chunk_size >= len(words):
      break
  return chunks


def ingest_document(title, publisher, url, text, category="", channel=""):
  """Hashes content, embeds chunks, then swaps them in atomically."""
  text = text.strip()
  if not text:
    raise ValueError("No readable text found.")
  content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

  text_chunks = chunk_text(text)
  vectors = list(_embedder().embed(text_chunks))   # slow step first, outside the transaction

  with transaction.atomic():
    source, _ = Source.objects.update_or_create(
        url=url,
        defaults={
            "title": title,
            "publisher": publisher,
            "category": category,
            "channel": channel,
            "content_hash": content_hash,
            "last_ingested": timezone.now(),
        },
    )
    source.chunks.all().delete()
    Chunk.objects.bulk_create(
        Chunk(source=source, position=i, text=t, embedding=v.tolist())
        for i, (t, v) in enumerate(zip(text_chunks, vectors))
    )
  return source


def extract_text(data: bytes, ext: str) -> str:
  """Turns an uploaded file's bytes into plain text."""
  if ext == ".pdf":
    try:
      reader = PdfReader(io.BytesIO(data))
      return "\n\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
      raise ValueError("Could not read this PDF (it may be encrypted or corrupted).")
  text = data.decode("utf-8", errors="ignore")
  if ext == ".csv":
    return "\n".join(", ".join(row) for row in csv.reader(io.StringIO(text)))
  return text


def ingest_upload(cleaned):
  """Takes form.cleaned_data: a file OR pasted text, then hands off to ingest_document."""
  uploaded = cleaned.get("file")
  if uploaded:
    ext = os.path.splitext(uploaded.name)[1].lower()
    if ext not in ALLOWED:
      raise ValueError("Only PDF, TXT, and CSV files are allowed.")
    if uploaded.size > MAX_BYTES:
      raise ValueError("File is too large (5 MB max).")
    text = extract_text(uploaded.read(), ext)
  else:
    text = cleaned["raw_text"]
  return ingest_document(
      title=cleaned["title"],
      publisher=cleaned["publisher"],
      url=cleaned["url"],
      text=text,
      category=cleaned.get("category", ""),
      channel=cleaned.get("channel", ""),
  )