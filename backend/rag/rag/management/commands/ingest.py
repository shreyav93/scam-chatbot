import hashlib, json
from pathlib import Path
import trafilatura
from django.core.management.base import BaseCommand
from django.utils import timezone
from fastembed import TextEmbedding
from rag.models import Source, Chunk

def chunk_text(text, size=180, overlap=40):
    words = text.split()
    step = size - overlap
    return [" ".join(words[i:i+size]) for i in range(0, max(len(words), 1), step)
            if words[i:i+size]]

class Command(BaseCommand):
    help = "Sync sources.json into the DB, then fetch, chunk and embed changed pages."

    def add_arguments(self, p):
        p.add_argument("--force", action="store_true", help="re-embed even if unchanged")

    def handle(self, *args, **o):
        manifest = json.loads((Path(__file__).parents[2] / "sources.json").read_text())
        urls = {m["url"] for m in manifest}
        for m in manifest:                                   # add / update
            Source.objects.update_or_create(url=m["url"], defaults={
                "title": m["title"], "publisher": m["publisher"], "active": True})
        Source.objects.exclude(url__in=urls).update(active=False)   # removed -> inactive

        model = TextEmbedding("BAAI/bge-small-en-v1.5")
        for s in Source.objects.filter(active=True):
            html = trafilatura.fetch_url(s.url)
            text = trafilatura.extract(html) if html else None
            if not text:
                self.stderr.write(f"SKIP (fetch failed): {s.url}"); continue
            h = hashlib.sha256(text.encode()).hexdigest()
            if h == s.content_hash and not o["force"]:
                self.stdout.write(f"unchanged: {s.title}"); continue
            parts = chunk_text(text)
            vecs = list(model.embed(parts))
            s.chunks.all().delete()
            Chunk.objects.bulk_create(
                Chunk(source=s, position=i, text=t, embedding=v.tolist())
                for i, (t, v) in enumerate(zip(parts, vecs)))
            s.content_hash, s.last_ingested = h, timezone.now()
            s.save()
            self.stdout.write(f"ingested: {s.title} ({len(parts)} chunks)")