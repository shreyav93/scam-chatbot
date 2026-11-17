import hashlib, json
from pathlib import Path
import trafilatura
from django.core.management.base import BaseCommand
from django.utils import timezone
from fastembed import TextEmbedding
from rag.models import Source, Chunk
import requests

def chunk_text(text, size=180, overlap=40):
    words = text.split()
    step = size - overlap
    return [" ".join(words[i:i+size]) for i in range(0, max(len(words), 1), step)
            if words[i:i+size]]

class Command(BaseCommand):
    help = "Sync sources.json into the DB, then fetch, chunk and embed changed pages."

    def add_arguments(self, p):
        p.add_argument("--force", action="store_true",
                    help="re-embed even if unchanged")
        p.add_argument("--source-id", type=int,
                    help="Only ingest a specific source")
    def handle(self, *args, **o):
        manifest = json.loads((Path(__file__).parents[2] / "sources.json").read_text())
        #urls = {m["url"] for m in manifest}
        for m in manifest:
            Source.objects.update_or_create(url=m["url"], defaults={
                "title": m["title"],
                "publisher": m["publisher"],
                "category": m.get("category", ""),
                "channel": m.get("channel", "any"),
                "last_reviewed": m.get("last_reviewed") or None,
                "active": True,
            })
        #Source.objects.exclude(url__in=urls).update(active=False)   # removed -> inactive

        model = TextEmbedding("BAAI/bge-small-en-v1.5")
        sources = Source.objects.filter(active=True)

        if o.get("source_id"):
            sources = sources.filter(id=o["source_id"])

        for s in sources:
            if not s.url:
                self.stdout.write(
                    f"SKIP (no URL; uploaded document): {s.title}"
                )
                continue
            try:
                # r = requests.get(s.url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
                # r.raise_for_status()
                r = requests.get(
                    s.url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/130.0.0.0 Safari/537.36"
                        ),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                    timeout=20,
                )
                r.raise_for_status()
                text = trafilatura.extract(r.text)
            # except requests.RequestException as e:
            #     self.stderr.write(f"SKIP ({e.__class__.__name__}): {s.url}")
            #     continue
            except requests.RequestException as e:
                if isinstance(e, requests.HTTPError):
                    self.stderr.write(
                        f"SKIP (HTTPError {e.response.status_code}): {s.url}"
                    )
                    self.stderr.write(f"Response: {e.response.text[:300]}")
                else:
                    self.stderr.write(f"SKIP ({e}): {s.url}")
                continue
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