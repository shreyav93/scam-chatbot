"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from rag import developer_views
from rag.views import ask, upload_source_view


def health(request):
    return JsonResponse({"message": "React is connected to Django!"})


urlpatterns = [
    path("", lambda request: JsonResponse({"service": "SeniorShield API"})),
    path("admin/", admin.site.urls),
    path("upload/", upload_source_view, name="upload_source"),
    path("api/health/", health),
    path("api/ask/", ask),
    path("api/developer/login/", developer_views.developer_login),
    path("api/developer/logout/", developer_views.developer_logout),
    path("api/developer/status/", developer_views.developer_status),
    path("api/developer/csrf/", developer_views.developer_csrf),
    path("api/developer/sources/", developer_views.get_sources),
    path("api/developer/sources/add/", developer_views.create_source),
    path("api/developer/sources/<int:source_id>/", developer_views.update_source),
    path("api/developer/stats/", developer_views.get_dashboard_stats),
    path("api/developer/ingest/", developer_views.run_ingestion),
    path("api/developer/sources/upload/",developer_views.upload_source,),
]