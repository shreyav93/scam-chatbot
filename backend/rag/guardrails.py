import os
from datetime import datetime, timezone
from django.core.exceptions import ImproperlyConfigured
from django.db.models import F
from .models import UsageCounter

FREE_MODELS = {"gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"}
MAX_INPUT_CHARS, MAX_OUTPUT_TOKENS = 2000, 800

class LimitReached(Exception):
    pass

def _n(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default

def get_model():
    m = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    if m not in FREE_MODELS:
        raise ImproperlyConfigured(f"{m} is not on the free-model allowlist")
    return m

def check_enabled():
    if os.environ.get("LLM_ENABLED", "true").lower() in {"0", "false", "no", "off"}:
        raise LimitReached("The assistant is switched off right now.")

def _bump(key, limit):
    UsageCounter.objects.get_or_create(key=key)
    return UsageCounter.objects.filter(key=key, count__lt=limit).update(count=F("count") + 1) == 1

def reserve_call(visitor):          # call before EVERY Gemini request
    t = datetime.now(timezone.utc)
    for key, lim, msg in [
        (f"min:{t:%Y%m%d%H%M}", _n("LIMIT_PER_MINUTE", 5), "We're busy. Try again in a minute."),
        (f"ip:{visitor}:{t:%Y%m%d}", _n("LIMIT_PER_VISITOR_DAY", 20), "Daily question limit reached."),
        (f"day:{t:%Y%m%d}", _n("LIMIT_PER_DAY", 100), "Daily limit reached. Try tomorrow."),
    ]:
        if not _bump(key, lim):
            raise LimitReached(msg)