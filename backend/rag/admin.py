from django.contrib import admin
from .models import Source

@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("title", "publisher", "category", "channel", "active", "last_ingested")
    list_filter = ("publisher", "category", "channel", "active")