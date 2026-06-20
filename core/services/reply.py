"""
services/clarity_reply.py
==========================

ClarityReply generation service — Gemini 2.5 Flash edition.

Takes a `ReplyRequest` Django model instance, builds a context-rich prompt
from its fields, calls Gemini, and saves the three generated replies
(professional_reply, friendly_reply, engaging_reply) directly back onto
the model instance.

Install:
--------
    pip install google-genai --break-system-packages

Settings (settings.py):
------------------------
    GEMINI_API_KEY = "your-key-here"
    GEMINI_MODEL = "gemini-2.5-flash"   # optional override

Usage:
------
    from .models import ReplyRequest
    from .services.clarity_reply import ClarityReplyService

    req = ReplyRequest.objects.get(pk=1)
    service = ClarityReplyService()
    service.generate_and_save(req)

    print(req.professional_reply)
    print(req.friendly_reply)
    print(req.engaging_reply)
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict

from django.conf import settings

from google import genai
from google.genai import types

from core.models import ReplyRequest


# --------------------------------------------------------------------------
# Platform rules
# --------------------------------------------------------------------------

PLATFORM_RULES: Dict[str, str] = {
    "linkedin": (
        "Professional, thoughtful, value-driven. Avoid excessive emojis. "
        "Encourage networking."
    ),
    "twitter": "Concise, engaging, conversational. Optimized for visibility.",
    "x": "Concise, engaging, conversational. Optimized for visibility.",
    "reddit": (
        "Authentic, direct, community-focused. Avoid corporate language. "
        "Write like a real redditor, not a brand."
    ),
    "discord": "Casual, friendly, natural conversation style.",
    "whatsapp": "Human, personal, context-aware.",
    "youtube": "Supportive, engagement-focused. Encourage discussion.",
    "instagram": "Short, friendly, emoji-friendly.",
}


def get_platform_rule(platform: str) -> str:
    if not platform:
        return "Match the general tone and norms of the platform."
    key = platform.strip().lower().replace("/", " ").split()[0]
    return PLATFORM_RULES.get(key, "Match the general tone and norms of the platform.")


def _emoji_level_label(level: int) -> str:
    """Model stores emoji_level as 0-100 int; map to a usable instruction."""
    if level <= 10:
        return "none — do not use any emojis."
    if level <= 40:
        return "low — at most 1 emoji, only if natural."
    if level <= 70:
        return "medium — 1-3 emojis where they fit naturally."
    return "high — use emojis liberally and expressively."


def _creativity_level_label(level: int) -> str:
    if level <= 30:
        return "low — keep phrasing safe, clear, conventional."
    if level <= 70:
        return "medium — natural, varied phrasing with some personality."
    return "high — bold, witty, original phrasing while staying relevant."


def _length_label(length: str) -> str:
    return {
        "short": "1-2 sentences",
        "medium": "2-4 sentences",
        "long": "4-6 sentences",
    }.get((length or "medium").lower(), "2-4 sentences")


# --------------------------------------------------------------------------
# Service
# --------------------------------------------------------------------------

class ClarityReplyService:
    """
    Generates platform-aware, persona-aware replies for a ReplyRequest
    instance using Gemini 2.5 Flash, and persists them to the model.
    """

    REQUIRED_TOP_KEYS = {"analysis", "replies"}
    REQUIRED_ANALYSIS_KEYS = {"platform", "topic", "post_type", "emotion", "reply_strategy"}
    REQUIRED_REPLY_KEYS = {"professional_reply", "friendly_reply", "high_engagement_reply"}

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", None)
        self.model = model or getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Add it to settings.py or pass api_key=."
            )
        self.client = genai.Client(api_key=self.api_key)

    # ---------------------------------------------------------------
    # Prompt construction
    # ---------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        return (
            "You are ClarityReply, an expert AI reply generation engine.\n"
            "Your job is to generate highly contextual, human-like replies "
            "optimized for the specific platform and conversation context.\n\n"
            "Rules:\n"
            "- Sound human, never generic or robotic.\n"
            "- Match the platform's norms exactly.\n"
            "- Match the detected sentiment, emotion, and formality level.\n"
            "- Match the requested style, length, emoji level, and creativity level.\n"
            "- Be contextually relevant to the actual content and latest message.\n"
            "- Avoid generic AI wording (no 'great post!', 'I couldn't agree more', "
            "etc. unless genuinely earned by context).\n"
            "- Return ONLY valid JSON matching the exact schema given. No markdown "
            "fences, no commentary, no preamble."
        )

    def _build_user_prompt(self, req: ReplyRequest) -> str:
        platform_rule = get_platform_rule(req.platform)
        length_guide = _length_label(req.reply_length)
        emoji_guide = _emoji_level_label(req.emoji_level)
        creativity_guide = _creativity_level_label(req.creativity_level)

        # conversation_history is a JSONField (list of {role, message} or similar)
        history_str = "N/A"
        if req.conversation_history:
            try:
                history_str = json.dumps(req.conversation_history, ensure_ascii=False)
            except (TypeError, ValueError):
                history_str = str(req.conversation_history)

        content_block = req.content or req.ocr_text or ""

        prompt = f"""
Generate three reply variants for the following context.

## Source
Platform: {req.platform}
Source Type: {req.source_type}
URL: {req.url or "N/A"}

## Platform Rule
{platform_rule}

## Content
Title: {req.title or "N/A"}
Content: {content_block}
Summary: {req.summary or "N/A"}

## Author Context
Name: {req.author_name or "N/A"}
Username: {req.author_username or "N/A"}
Role: {req.author_role or "N/A"}
Company: {req.author_company or "N/A"}
Headline: {req.author_headline or "N/A"}

## Content Analysis
Topic: {req.topic or "N/A"}
Subtopic: {req.subtopic or "N/A"}
Industry: {req.industry or "N/A"}
Post Type: {req.post_type or "N/A"}
Post Intent: {req.post_intent or "N/A"}
Sentiment: {req.sentiment or "N/A"}
Emotion: {req.emotion or "N/A"}
Audience Type: {req.audience_type or "N/A"}
Formality Level: {req.formality_level or "N/A"}

## Engagement Signals
Likes: {req.likes}  Comments: {req.comments}  Shares: {req.shares}

## Conversation Context
Conversation Summary: {req.conversation_summary or "N/A"}
Conversation History: {history_str}
Latest Message: {req.latest_message or "N/A"}

## User Preferences
Reply Goal: {req.reply_goal}
Reply Style: {req.reply_style}
Reply Length: {req.reply_length} ({length_guide})
Emoji Level: {req.emoji_level}/100 -> {emoji_guide}
Creativity Level: {req.creativity_level}/100 -> {creativity_guide}

## Output Requirements
Generate exactly three replies:
1. professional_reply - polished, credible, respectful of platform norms
2. friendly_reply - warm, approachable, conversational
3. high_engagement_reply - designed to maximize replies/likes/shares while staying authentic

Return ONLY this JSON structure, no markdown fences, no extra text:

{{
  "analysis": {{
    "platform": "",
    "topic": "",
    "post_type": "",
    "emotion": "",
    "reply_strategy": ""
  }},
  "replies": {{
    "professional_reply": "",
    "friendly_reply": "",
    "high_engagement_reply": ""
  }}
}}
""".strip()
        return prompt

    # ---------------------------------------------------------------
    # JSON parsing / validation
    # ---------------------------------------------------------------

    def _extract_json(self, text: str) -> Dict[str, Any]:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError("Model did not return valid JSON:\n" + text)

    def _validate(self, data: Dict[str, Any]) -> None:
        if self.REQUIRED_TOP_KEYS - data.keys():
            raise ValueError(f"Missing top-level keys: {self.REQUIRED_TOP_KEYS - data.keys()}")
        if self.REQUIRED_ANALYSIS_KEYS - data["analysis"].keys():
            raise ValueError(
                f"Missing analysis keys: {self.REQUIRED_ANALYSIS_KEYS - data['analysis'].keys()}"
            )
        if self.REQUIRED_REPLY_KEYS - data["replies"].keys():
            raise ValueError(
                f"Missing reply keys: {self.REQUIRED_REPLY_KEYS - data['replies'].keys()}"
            )

    # ---------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------

    def generate(self, req: ReplyRequest, retries: int = 2) -> Dict[str, Any]:
        """Call Gemini and return the parsed/validated JSON dict (no DB write)."""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(req)

        last_error: Exception | None = None
        for _ in range(retries + 1):
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0.9,
                ),
            )
            text = response.text or ""
            try:
                data = self._extract_json(text)
                self._validate(data)
                return data
            except (ValueError, json.JSONDecodeError) as e:
                last_error = e
                continue

        raise RuntimeError(f"Failed to get valid JSON after {retries + 1} attempts: {last_error}")

    def generate_and_save(self, req: ReplyRequest, retries: int = 2) -> ReplyRequest:
        """
        Generate replies and persist them onto the ReplyRequest instance:
        professional_reply, friendly_reply, engaging_reply. Saves and
        returns the updated instance.
        """
        data = self.generate(req, retries=retries)
        replies = data["replies"]

        req.professional_reply = replies["professional_reply"]
        req.friendly_reply = replies["friendly_reply"]
        req.engaging_reply = replies["high_engagement_reply"]
        req.save(update_fields=["professional_reply", "friendly_reply", "engaging_reply", "updated_at"])
        return req