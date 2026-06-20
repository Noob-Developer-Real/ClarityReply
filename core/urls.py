from django.urls import path

from .views import (
    HomeView,
    TemplateListView,
    ExtractContentView,
    GenerateReplyView,
)

app_name = "core"

urlpatterns = [
    # Health Check
    path(
        "",
        HomeView.as_view(),
        name="home",
    ),

    # Templates
    path(
        "templates/",
        TemplateListView.as_view(),
        name="templates",
    ),

    # Extract URL / Screenshot Content
    path(
        "extract/",
        ExtractContentView.as_view(),
        name="extract-content",
    ),

    # Generate Replies
    path(
        "generate-reply/",
        GenerateReplyView.as_view(),
        name="generate-reply",
    ),
]
