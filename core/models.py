from django.db import models


class ReplyRequest(models.Model):
    # Source Information
    platform = models.CharField(max_length=50)
    source_type = models.CharField(max_length=20)  # url, screenshot, text

    # Original Content
    url = models.URLField(blank=True, null=True)
    content = models.TextField()
    title = models.CharField(max_length=500, blank=True, null=True)
    summary = models.TextField(blank=True, null=True)

    # Author Context
    author_name = models.CharField(max_length=255, blank=True, null=True)
    author_username = models.CharField(max_length=255, blank=True, null=True)
    author_role = models.CharField(max_length=255, blank=True, null=True)
    author_company = models.CharField(max_length=255, blank=True, null=True)
    author_headline = models.TextField(blank=True, null=True)

    # Content Analysis
    topic = models.CharField(max_length=255, blank=True, null=True)
    subtopic = models.CharField(max_length=255, blank=True, null=True)
    industry = models.CharField(max_length=255, blank=True, null=True)

    post_type = models.CharField(max_length=100, blank=True, null=True)
    post_intent = models.CharField(max_length=100, blank=True, null=True)

    sentiment = models.CharField(max_length=50, blank=True, null=True)
    emotion = models.CharField(max_length=50, blank=True, null=True)

    audience_type = models.CharField(max_length=100, blank=True, null=True)
    formality_level = models.CharField(max_length=50, blank=True, null=True)

    # Conversation Context
    conversation_summary = models.TextField(blank=True, null=True)
    latest_message = models.TextField(blank=True, null=True)
    conversation_history = models.JSONField(default=list, blank=True)

    # Screenshot/OCR
    ocr_text = models.TextField(blank=True, null=True)

    # Engagement
    likes = models.IntegerField(default=0)
    comments = models.IntegerField(default=0)
    shares = models.IntegerField(default=0)

    # User Preferences
    reply_goal = models.CharField(max_length=100, default="engage")
    reply_style = models.CharField(max_length=100, default="professional")
    reply_length = models.CharField(max_length=50, default="medium")

    emoji_level = models.IntegerField(default=50)
    creativity_level = models.IntegerField(default=50)

    # Generated Output
    professional_reply = models.TextField(blank=True, null=True)
    friendly_reply = models.TextField(blank=True, null=True)
    engaging_reply = models.TextField(blank=True, null=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.platform} - {self.author_name or 'Unknown'}"