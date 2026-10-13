"""All of kb-builder's pages come from the kb app."""

from django.urls import include, path

urlpatterns = [path("", include("kb.urls"))]
