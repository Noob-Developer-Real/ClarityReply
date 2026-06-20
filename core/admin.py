from django.contrib import admin
from django.utils.html import format_html
from django.utils.text import Truncator

from core.models import ReplyRequest


@admin.register(ReplyRequest)
class ReplyRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "platform",
        "source_type",
        "title_preview",
        "author_display",
        "content_status",
        "reply_status",
        "engagement_summary",
        "created_at",
    )
    list_filter = (
        "platform",
        "source_type",
        "reply_style",
        "reply_length",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "id",
        "url",
        "title",
        "content",
        "summary",
        "author_name",
        "author_username",
        "conversation_summary",
        "latest_message",
        "professional_reply",
        "friendly_reply",
        "engaging_reply",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "content_preview",
        "ocr_preview",
        "variation_1_preview",
        "variation_2_preview",
        "variation_3_preview",
        "engagement_summary",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 25
    save_on_top = True

    fieldsets = (
        (
            "Source",
            {
                "fields": (
                    "platform",
                    "source_type",
                    "url",
                    "title",
                    "summary",
                    "content",
                    "content_preview",
                )
            },
        ),
        (
            "Author",
            {
                "fields": (
                    "author_name",
                    "author_username",
                    "author_role",
                    "author_company",
                    "author_headline",
                )
            },
        ),
        (
            "Content Analysis",
            {
                "classes": ("collapse",),
                "fields": (
                    "topic",
                    "subtopic",
                    "industry",
                    "post_type",
                    "post_intent",
                    "sentiment",
                    "emotion",
                    "audience_type",
                    "formality_level",
                ),
            },
        ),
        (
            "Conversation Context",
            {
                "classes": ("collapse",),
                "fields": (
                    "conversation_summary",
                    "latest_message",
                    "conversation_history",
                ),
            },
        ),
        (
            "Screenshot / OCR",
            {
                "classes": ("collapse",),
                "fields": (
                    "ocr_text",
                    "ocr_preview",
                ),
            },
        ),
        (
            "Engagement",
            {
                "fields": (
                    "likes",
                    "comments",
                    "shares",
                    "engagement_summary",
                )
            },
        ),
        (
            "Reply Preferences",
            {
                "fields": (
                    "reply_goal",
                    "reply_style",
                    "reply_length",
                    "emoji_level",
                    "creativity_level",
                )
            },
        ),
        (
            "Generated Variations",
            {
                "fields": (
                    "professional_reply",
                    "friendly_reply",
                    "engaging_reply",
                    "variation_1_preview",
                    "variation_2_preview",
                    "variation_3_preview",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="Title")
    def title_preview(self, obj: ReplyRequest) -> str:
        return Truncator(obj.title or obj.content or "Untitled").chars(70)

    @admin.display(description="Author")
    def author_display(self, obj: ReplyRequest) -> str:
        if obj.author_name and obj.author_username:
            return f"{obj.author_name} (@{obj.author_username.lstrip('@')})"
        return obj.author_name or obj.author_username or "Unknown"

    @admin.display(description="Content")
    def content_status(self, obj: ReplyRequest) -> str:
        if obj.content:
            return format_html('<span style="color:#15803d;font-weight:600;">Available</span>')
        if obj.ocr_text:
            return format_html('<span style="color:#a16207;font-weight:600;">OCR only</span>')
        return format_html('<span style="color:#b91c1c;font-weight:600;">Missing</span>')

    @admin.display(description="Replies")
    def reply_status(self, obj: ReplyRequest) -> str:
        count = sum(
            1
            for value in (obj.professional_reply, obj.friendly_reply, obj.engaging_reply)
            if value
        )
        if count == 3:
            return format_html('<span style="color:#15803d;font-weight:600;">3/3 generated</span>')
        if count:
            return format_html('<span style="color:#a16207;font-weight:600;">{}/3 generated</span>', count)
        return format_html('<span style="color:#b91c1c;font-weight:600;">Not generated</span>')

    @admin.display(description="Engagement")
    def engagement_summary(self, obj: ReplyRequest) -> str:
        return f"{obj.likes} likes · {obj.comments} comments · {obj.shares} shares"

    @admin.display(description="Content Preview")
    def content_preview(self, obj: ReplyRequest) -> str:
        return self._preview_block(obj.content)

    @admin.display(description="OCR Preview")
    def ocr_preview(self, obj: ReplyRequest) -> str:
        return self._preview_block(obj.ocr_text)

    @admin.display(description="Variation 1 Preview")
    def variation_1_preview(self, obj: ReplyRequest) -> str:
        return self._preview_block(obj.professional_reply)

    @admin.display(description="Variation 2 Preview")
    def variation_2_preview(self, obj: ReplyRequest) -> str:
        return self._preview_block(obj.friendly_reply)

    @admin.display(description="Variation 3 Preview")
    def variation_3_preview(self, obj: ReplyRequest) -> str:
        return self._preview_block(obj.engaging_reply)

    def _preview_block(self, value: str | None) -> str:
        if not value:
            return format_html('<span style="color:#6b7280;">No data</span>')
        return format_html(
            '<div style="max-width:760px;white-space:pre-wrap;line-height:1.45;">{}</div>',
            Truncator(value).chars(700),
        )


admin.site.site_header = "ClarityReply Admin"
admin.site.site_title = "ClarityReply Admin"
admin.site.index_title = "Workspace Overview"
