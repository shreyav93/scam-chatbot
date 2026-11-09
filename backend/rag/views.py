from django.shortcuts import render
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .service import answer

@csrf_exempt   # fine for local dev; use proper CSRF/CORS handling when deploying
@require_POST
def ask(request):
    try:
        q = json.loads(request.body).get("question", "").strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    if not q or len(q) > 4000:
        return JsonResponse({"error": "Question missing or too long"}, status=400)
    try:
        return JsonResponse(answer(q))
    except Exception:
        return JsonResponse({"error": "Could not generate an answer"}, status=502)