import json
import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import IngestionForm
from .guardrails import MAX_INPUT_CHARS, LimitReached
from .ingestion import ingest_upload
from .service import answer

logger = logging.getLogger(__name__)


@csrf_exempt   # fine for local dev; use proper CSRF/CORS handling when deploying
@require_POST
def ask(request):
    try:
        body = json.loads(request.body)
        q = body.get("question", "") if isinstance(body, dict) else ""
        q = q.strip() if isinstance(q, str) else ""
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    if not q or len(q) > MAX_INPUT_CHARS:
        return JsonResponse({"error": "Please enter a shorter, non-empty message."}, status=400)
    try:
        return JsonResponse(answer(q, request.META.get("REMOTE_ADDR", "unknown")))
    except LimitReached as e:
        return JsonResponse({"error": str(e)}, status=429)
    except Exception:
        logger.exception("Chatbot answer generation failed")
        return JsonResponse({"error": "Could not generate an answer."}, status=502)


def upload_source_view(request):
    result = error = None
    if request.method == "POST":
        form = IngestionForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                source = ingest_upload(form.cleaned_data)
                result = f"Saved '{source.title}' ({source.chunks.count()} chunks)."
            except ValueError as e:
                error = str(e)
    else:
        form = IngestionForm()
    return render(request, "chatbot/upload.html",
                  {"form": form, "result": result, "error": error})