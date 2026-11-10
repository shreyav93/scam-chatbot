from django.shortcuts import render
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .service import answer
from .guardrails import MAX_INPUT_CHARS, LimitReached

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