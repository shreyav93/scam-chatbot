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
from rag.views import upload_source_view
from django.views.generic import RedirectView


def health(request):
    return JsonResponse({"message": "React is connected to Django!"})


urlpatterns = [
    path("", RedirectView.as_view(url="/upload/", permanent=False)),
    path("admin/", admin.site.urls),
    path("upload/", upload_source_view, name="upload_source"),
    path("api/health/", health),
    path("api/ask/", ask),
]
