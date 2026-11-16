from django.shortcuts import redirect, render
from .forms import IngestionForm
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .service import answer
from .guardrails import MAX_INPUT_CHARS, LimitReached
from .ingestion import ingest_document

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
        return JsonResponse({"error": "Could not generate an answer."}, status=502)


def upload_source_view(request):
  if request.method == "POST":
    form = IngestionForm(request.POST, request.FILES)
    if form.is_valid():
      title = form.cleaned_data["title"]
      publisher = form.cleaned_data["publisher"]
      url = form.cleaned_data["url"]
      category = form.cleaned_data.get("category", "")
      channel = form.cleaned_data.get("channel", "")

      text = form.cleaned_data.get("raw_text", "")
      uploaded_file = request.FILES.get("file")

      # Read text from uploaded file if present
      if uploaded_file:
        if uploaded_file.name.endswith(".txt"):
          text = uploaded_file.read().decode("utf-8")
        # Optional: You can add python-docx or pypdf handling here later for PDFs/Word docs

      if text:
        ingest_document(
            title=title,
            publisher=publisher,
            url=url,
            text=text,
            category=category,
            channel=channel,
        )
        return redirect("upload_success")  # Or wherever you want to redirect
  else:
    form = IngestionForm()

  return render(request, "chatbot/upload.html", {"form": form})