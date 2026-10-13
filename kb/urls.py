"""The review app's pages: the overview, setting your name, and one page per question."""

from django.urls import path

from kb import views

urlpatterns = [
    path("", views.overview, name="overview"),
    path("reviewer", views.reviewer, name="reviewer"),
    path("q/<str:qid>", views.question, name="question"),
]
