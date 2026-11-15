
import json
from functools import wraps

from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .models import Source, Chunk
from io import StringIO
import re

from django.core.management import call_command


def developer_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required."}, status=401)

        if not request.user.is_staff:
            return JsonResponse({"error": "Developer access required."}, status=403)

        return view_func(request, *args, **kwargs)

    return wrapper


def parse_json(request):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None


def serialize_source(source):
    return {
        "id": source.id,
        "title": source.title,
        "publisher": source.publisher,
        "url": source.url,
        "category": source.category,
        "channel": source.channel,
        "last_reviewed": (
            source.last_reviewed.isoformat()
            if source.last_reviewed else None
        ),
        "active": source.active,
        "last_ingested": (
            source.last_ingested.isoformat()
            if source.last_ingested else None
        ),
        "chunk_count": source.chunks.count(),
    }


@ensure_csrf_cookie
@require_GET
def developer_csrf(request):
    return JsonResponse({"message": "CSRF cookie set."})


@require_POST
def developer_login(request):
    data = parse_json(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    user = authenticate(
        request,
        username=data.get("username", ""),
        password=data.get("password", "")
    )

    if user is None:
        return JsonResponse(
            {"error": "Invalid username or password."},
            status=401
        )

    if not user.is_staff:
        return JsonResponse(
            {"error": "Developer access required."},
            status=403
        )

    login(request, user)

    return JsonResponse({
        "success": True,
        "username": user.username
    })


@require_POST
@developer_required
def developer_logout(request):
    logout(request)
    return JsonResponse({"success": True})


@require_GET
def developer_status(request):
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False})

    return JsonResponse({
        "authenticated": True,
        "is_developer": request.user.is_staff,
        "username": request.user.username
    })


# DATASET MANAGEMENT

@require_GET
@developer_required
def get_sources(request):
    sources = Source.objects.all().order_by("publisher", "title")

    return JsonResponse({
        "sources": [serialize_source(source) for source in sources]
    })


@require_POST
@developer_required
def create_source(request):
    data = parse_json(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    required_fields = ["title", "publisher", "url"]

    for field in required_fields:
        if not isinstance(data.get(field), str) or not data[field].strip():
            return JsonResponse(
                {"error": f"{field.capitalize()} is required."},
                status=400
            )

    title = data["title"].strip()
    publisher = data["publisher"].strip()
    url = data["url"].strip()

    if len(title) > 300 or len(publisher) > 100:
        return JsonResponse({"error": "Title or publisher is too long."}, status=400)

    try:
        URLValidator()(url)
    except ValidationError:
        return JsonResponse({"error": "Please enter a valid URL."}, status=400)

    try:
        source = Source.objects.create(
            title=title,
            publisher=publisher,
            url=url,
            category=str(data.get("category", "")).strip(),
            channel=str(data.get("channel", "any")).strip(),
            active=True,
        )
    except IntegrityError:
        return JsonResponse(
            {"error": "A source with this URL already exists."},
            status=409
        )

    return JsonResponse({
        "success": True,
        "source": serialize_source(source),
        "message": "Source added successfully. Run ingestion to make its content available to the chatbot."
    }, status=201)


@require_http_methods(["PATCH", "PUT"])
@developer_required
def update_source(request, source_id):
    try:
        source = Source.objects.get(id=source_id)
    except Source.DoesNotExist:
        return JsonResponse({"error": "Source not found."}, status=404)

    data = parse_json(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    allowed_fields = {
        "title", "publisher", "url", "category",
        "channel", "last_reviewed", "active"
    }

    if not data or not set(data.keys()).issubset(allowed_fields):
        return JsonResponse({"error": "Invalid or empty update."}, status=400)

    for field in ("title", "publisher", "url", "category", "channel"):
        if field in data:
            if not isinstance(data[field], str):
                return JsonResponse({"error": f"{field} must be text."}, status=400)
            setattr(source, field, data[field].strip())

    if not source.title or not source.publisher or not source.url:
        return JsonResponse(
            {"error": "Title, publisher, and URL cannot be empty."},
            status=400
        )

    if len(source.title) > 300 or len(source.publisher) > 100:
        return JsonResponse({"error": "Title or publisher is too long."}, status=400)

    try:
        URLValidator()(source.url)
    except ValidationError:
        return JsonResponse({"error": "Please enter a valid URL."}, status=400)

    if "last_reviewed" in data:
        from datetime import date
        try:
            source.last_reviewed = (
                date.fromisoformat(data["last_reviewed"])
                if data["last_reviewed"] else None
            )
        except (ValueError, TypeError):
            return JsonResponse(
                {"error": "last_reviewed must use YYYY-MM-DD format."},
                status=400
            )

    if "active" in data:
        if not isinstance(data["active"], bool):
            return JsonResponse({"error": "active must be true or false."}, status=400)
        source.active = data["active"]

    url_changed = "url" in data and source.url != Source.objects.get(id=source_id).url

    if url_changed:
        source.content_hash = ""
        source.last_ingested = None
        source.chunks.all().delete()

    try:
        source.save()
    except IntegrityError:
        return JsonResponse(
            {"error": "Another source already uses this URL."},
            status=409
        )

    return JsonResponse({
        "success": True,
        "source": serialize_source(source),
        "message": "Source updated successfully."
    })




# DASHBOARD STATISTICS

@require_GET
@developer_required
def get_dashboard_stats(request):
    return JsonResponse({
        "total_sources": Source.objects.count(),
        "active_sources": Source.objects.filter(active=True).count(),
        "inactive_sources": Source.objects.filter(active=False).count(),
        "total_chunks": Chunk.objects.count(),
    })

# DATA INGESTION

@require_POST
@developer_required
def run_ingestion(request):
    stdout = StringIO()
    stderr = StringIO()

    try:
        call_command(
            "ingest",
            stdout=stdout,
            stderr=stderr,
        )

        output = stdout.getvalue()
        errors = stderr.getvalue()
        lines = output.splitlines()

        ingested = [line for line in lines if line.startswith("ingested:")]
        unchanged = [line for line in lines if line.startswith("unchanged:")]
        skipped = [line for line in lines if line.startswith("SKIP")]

        chunks_created = 0

        for line in ingested:
            match = re.search(r"\((\d+) chunks\)", line)
            if match:
                chunks_created += int(match.group(1))

        return JsonResponse({
            "success": True,
            "message": "Ingestion completed.",
            "sources_ingested": len(ingested),
            "sources_unchanged": len(unchanged),
            "sources_skipped": len(skipped),
            "chunks_created": chunks_created,
            "output": output,
            "errors": errors,
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e),
            "output": stdout.getvalue(),
            "errors": stderr.getvalue(),
        }, status=500)