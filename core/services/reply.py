"""
services/clarity_reply.py
==========================

ClarityReply generation service — Gemini 2.5 Flash edition.

Takes a `ReplyRequest` Django model instance, builds a focused reply prompt
from its fields, calls Gemini, and saves three alternate phrasings directly
back onto the model instance.

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

    print(req.professional_reply)  # variation_1
    print(req.friendly_reply)      # variation_2
    print(req.engaging_reply)      # variation_3
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
    "instagram": (
        "Short, human, conversational, and native to Instagram. Use natural emoji "
        "placement when it fits. Avoid corporate language, LinkedIn-style phrasing, "
        "generic praise, and AI-sounding comments."
    ),
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
    Generates platform-aware alternate phrasings for a ReplyRequest instance
    using Gemini 2.5 Flash, and persists them to the model.
    """

    REQUIRED_REPLY_KEYS = {"variation_1", "variation_2", "variation_3"}

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
            "You generate short, context-aware social replies.\n"
            "Only generate replies. Do not analyze, explain, summarize, or add meta commentary.\n"
            "Return ONLY valid JSON with exactly these keys: variation_1, variation_2, variation_3."
        )

    def _combined_context(self, req: ReplyRequest) -> str:
        content = req.content or req.ocr_text or ""
        platform = (req.platform or "").strip().lower()
        if platform not in {"discord", "whatsapp"}:
            return content

        pieces = []
        if req.conversation_summary:
            pieces.append(f"Previous messages:\n{req.conversation_summary}")
        if req.latest_message:
            pieces.append(f"Latest message:\n{req.latest_message}")
        if content:
            pieces.append(f"Post content:\n{content}")
        return "\n\n".join(pieces).strip()

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

        content_block = self._combined_context(req)

        prompt = f"""
Generate three alternative phrasings of the same reply strategy.

All three variations must have the same goal, tone, platform style, and intent.
Only change the wording.

Platform: {req.platform}
Title: {req.title or "N/A"}
Summary: {req.summary or "N/A"}
Post Content:
{content_block}

Conversation Summary: {req.conversation_summary or "N/A"}
Conversation History: {history_str}
Latest Message: {req.latest_message or "N/A"}

Platform Style:
{platform_rule}

Reply Goal: {req.reply_goal}
Desired Tone: {req.reply_style}
Reply Length: {req.reply_length} ({length_guide})
Emoji Level: {req.emoji_level}/100 -> {emoji_guide}
Creativity Level: {req.creativity_level}/100 -> {creativity_guide}

Instagram-specific rules when Platform is instagram:
- Keep replies short and human.
- Prefer conversational phrasing like a real Instagram comment.
- Use emojis only where they feel natural.
- Avoid corporate language, generic praise, and LinkedIn tone.
- Do not write phrases like "Great insights. Thanks for sharing."

Return ONLY this JSON structure, no markdown fences, no extra text:

{{
  "variation_1": "",
  "variation_2": "",
  "variation_3": ""
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
        if self.REQUIRED_REPLY_KEYS - data.keys():
            raise ValueError(
                f"Missing reply keys: {self.REQUIRED_REPLY_KEYS - data.keys()}"
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
        professional_reply, friendly_reply, engaging_reply. These existing
        fields store variation_1, variation_2, variation_3 respectively.
        """
        data = self.generate(req, retries=retries)

        req.professional_reply = data["variation_1"]
        req.friendly_reply = data["variation_2"]
        req.engaging_reply = data["variation_3"]
        req.save(update_fields=["professional_reply", "friendly_reply", "engaging_reply", "updated_at"])
        return req
