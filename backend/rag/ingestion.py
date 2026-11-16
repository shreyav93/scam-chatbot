import hashlib
from django.utils import timezone
from fastembed import TextEmbedding
from .models import Chunk, Source

# Shared embedder instance
_embedder = TextEmbedding("BAAI/bge-small-en-v1.5")


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50):
  """Splits text into overlapping chunks."""
  words = text.split()
  chunks = []
  for i in range(0, len(words), chunk_size - overlap):
    chunk_words = words[i : i + chunk_size]
    chunks.append(" ".join(chunk_words))
    if i + chunk_size >= len(words):
      break
  return chunks


def ingest_document(
    title: str,
    publisher: str,
    url: str,
    text: str,
    category: str = "",
    channel: str = "",
):
  """Hashes content for deduplication, creates Source, and bulk inserts embedded Chunks."""
  content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

  # Check for existing source by URL or hash
  source, created = Source.objects.get_or_create(
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

  # If source exists, update metadata and delete existing chunks before re-ingesting
  if not created:
    source.title = title
    source.publisher = publisher
    source.content_hash = content_hash
    source.last_ingested = timezone.now()
    source.save()
    source.chunks.all().delete()

  text_chunks = chunk_text(text)
  embeddings = list(_embedder.embed(text_chunks))

  chunk_objects = [
      Chunk(
          source=source,
          position=idx,
          text=chunk_str,
          embedding=vector.tolist(),
      )
      for idx, (chunk_str, vector) in enumerate(zip(text_chunks, embeddings))
  ]

  Chunk.objects.bulk_create(chunk_objects)
  return source