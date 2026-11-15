"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from rag.views import ask
from rag import developer_views


def health(request):
    return JsonResponse({"message": "React is connected to Django!"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health),
    path("api/ask/", ask),
    path("api/developer/login/", developer_views.developer_login),
    path("api/developer/logout/", developer_views.developer_logout),
    path("api/developer/status/", developer_views.developer_status),
    path("api/developer/sources/", developer_views.get_sources),
    path("api/developer/stats/", developer_views.get_dashboard_stats),
    path("api/developer/csrf/", developer_views.developer_csrf),
    path("api/developer/sources/", developer_views.get_sources),
    path("api/developer/sources/add/", developer_views.create_source),
    path("api/developer/sources/<int:source_id>/", developer_views.update_source),
    path("api/developer/stats/", developer_views.get_dashboard_stats),
    path("api/developer/ingest/", developer_views.run_ingestion),

]
