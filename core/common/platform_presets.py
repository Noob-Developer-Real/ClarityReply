"""
services/platform_presets.py
==============================

Ideal-use-case presets per platform — sensible defaults for reply_goal,
reply_style, reply_length, emoji_level, creativity_level, formality_level,
and audience_type, so callers don't have to guess sane values for every
ReplyRequest.

These map directly onto fields in models.ReplyRequest:
    reply_goal, reply_style, reply_length, emoji_level (0-100),
    creativity_level (0-100), formality_level, audience_type

Usage:
------
    from .services.platform_presets import apply_platform_preset
    from .models import ReplyRequest

    req = ReplyRequest.objects.create(
        platform="LinkedIn",
        source_type="url",
        url="https://linkedin.com/posts/...",
        content="",
    )
    apply_platform_preset(req)   # fills in goal/style/length/emoji/creativity
    req.save()

Or just look up a preset without touching a model instance:

    from .services.platform_presets import get_preset
    preset = get_preset("discord")
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Optional

from core.models import ReplyRequest


@dataclass
class PlatformPreset:
    audience_type: str
    formality_level: str          # casual | neutral | formal
    reply_goal: str                # engage | network | support | inform | entertain | convert
    reply_style: str                # short human description of voice
    reply_length: str               # short | medium | long
    emoji_level: int                # 0-100
    creativity_level: int           # 0-100
    notes: str = ""                 # why this preset, for humans reading the code

    def to_dict(self) -> Dict:
        return asdict(self)


# --------------------------------------------------------------------------
# The "ideal" preset per platform
# --------------------------------------------------------------------------

PLATFORM_PRESETS: Dict[str, PlatformPreset] = {

    "linkedin": PlatformPreset(
        audience_type="Professionals, recruiters, founders, B2B decision-makers",
        formality_level="formal",
        reply_goal="network",
        reply_style="Professional, thoughtful, value-driven, credible",
        reply_length="medium",
        emoji_level=10,
        creativity_level=35,
        notes="LinkedIn rewards substance and credibility over cleverness. "
              "Low emoji, no slang, light networking angle.",
    ),

    "twitter": PlatformPreset(
        audience_type="General public, niche communities, fast scrollers",
        formality_level="casual",
        reply_goal="engage",
        reply_style="Witty, sharp, conversational, opinionated — punchy not corporate",
        reply_length="short",
        emoji_level=20,
        creativity_level=70,
        notes="X/Twitter rewards personality and brevity. Reward = engagement, "
              "so the reply should be quotable, not safe.",
    ),
    "x": None,  # alias, resolved at lookup time

    "reddit": PlatformPreset(
        audience_type="Topic-specific community members, skeptical of marketing",
        formality_level="casual",
        reply_goal="inform",
        reply_style="Authentic, direct, no corporate language, adds real value or opinion",
        reply_length="medium",
        emoji_level=0,
        creativity_level=40,
        notes="Reddit instantly downvotes anything that smells like a brand or "
              "an ad. Zero emojis, no enthusiasm-speak, sound like a normal user.",
    ),

    "discord": PlatformPreset(
        audience_type="Community members, often a shared interest/server topic",
        formality_level="casual",
        reply_goal="engage",
        reply_style="Friendly, casual, natural chat tone — like talking to a friend in a group chat",
        reply_length="short",
        emoji_level=50,
        creativity_level=60,
        notes="Discord is real-time chat, not a publishing platform. Keep it loose, "
              "use casual phrasing/abbreviations where natural.",
    ),

    "whatsapp": PlatformPreset(
        audience_type="A personal contact or small known group",
        formality_level="casual",
        reply_goal="support",
        reply_style="Warm, personal, like texting a friend — short and human, not polished",
        reply_length="short",
        emoji_level=60,
        creativity_level=30,
        notes="WhatsApp is 1:1 personal context. No marketing tone, no hashtags, "
              "no generic platitudes — sound like you actually know this person.",
    ),

    "youtube": PlatformPreset(
        audience_type="Video viewers, fans, the creator's existing community",
        formality_level="casual",
        reply_goal="support",
        reply_style="Supportive, encouraging, conversational — fuels more discussion",
        reply_length="short",
        emoji_level=30,
        creativity_level=45,
        notes="YouTube comments work best when they react genuinely to the content "
              "and invite others to chime in (good for creator engagement).",
    ),

    "instagram": PlatformPreset(
        audience_type="Visual-first, casual scrollers, often younger/lifestyle audience",
        formality_level="casual",
        reply_goal="engage",
        reply_style="Short, friendly, upbeat, emoji-forward",
        reply_length="short",
        emoji_level=70,
        creativity_level=55,
        notes="Instagram comments are short and emotionally expressive — emojis carry "
              "tone here more than on any other platform.",
    ),

    "facebook": PlatformPreset(
        audience_type="Mixed-age general public, often friends/family or local community groups",
        formality_level="casual",
        reply_goal="support",
        reply_style="Warm, plain-spoken, personable — not overly polished",
        reply_length="medium",
        emoji_level=40,
        creativity_level=30,
        notes="Facebook skews older/more personal than Instagram or Twitter — "
              "keep it warm and straightforward rather than witty.",
    ),

    "tiktok": PlatformPreset(
        audience_type="Younger, fast-scrolling, trend-aware audience",
        formality_level="casual",
        reply_goal="engage",
        reply_style="Playful, trend-aware, very casual, high energy",
        reply_length="short",
        emoji_level=60,
        creativity_level=80,
        notes="TikTok comments reward humor and trend-fluency more than any other "
              "platform — safe/generic replies get buried.",
    ),
}

# Resolve aliases after the dict is built
PLATFORM_PRESETS["x"] = PLATFORM_PRESETS["twitter"]

DEFAULT_PRESET = PlatformPreset(
    audience_type="General audience",
    formality_level="neutral",
    reply_goal="engage",
    reply_style="Clear, friendly, contextually appropriate",
    reply_length="medium",
    emoji_level=20,
    creativity_level=40,
    notes="Fallback used when the platform isn't recognized.",
)


def get_preset(platform: str) -> PlatformPreset:
    """Look up the ideal preset for a platform name (case-insensitive)."""
    if not platform:
        return DEFAULT_PRESET
    key = platform.strip().lower().replace("/", " ").split()[0]
    return PLATFORM_PRESETS.get(key, DEFAULT_PRESET)


def apply_platform_preset(req: ReplyRequest, overwrite: bool = False) -> ReplyRequest:
    """
    Fills in req's preference fields (reply_goal, reply_style, reply_length,
    emoji_level, creativity_level, audience_type, formality_level) from the
    platform preset.

    By default only fills in fields that are currently empty/default, so it
    won't clobber preferences the user already explicitly set. Pass
    overwrite=True to force the preset onto the instance regardless.
    """
    preset = get_preset(req.platform)

    fields_map = {
        "audience_type": preset.audience_type,
        "formality_level": preset.formality_level,
        "reply_goal": preset.reply_goal,
        "reply_style": preset.reply_style,
        "reply_length": preset.reply_length,
        "emoji_level": preset.emoji_level,
        "creativity_level": preset.creativity_level,
    }

    for field, value in fields_map.items():
        current = getattr(req, field, None)
        is_empty = current in (None, "", 0)
        if overwrite or is_empty:
            setattr(req, field, value)

    return req


if __name__ == "__main__":
    # Quick non-Django preview of every preset
    import json as _json

    for platform_key in ["linkedin", "twitter", "reddit", "discord", "whatsapp",
                          "youtube", "instagram", "facebook", "tiktok", "unknown_platform"]:
        preset = get_preset(platform_key)
        print(f"\n=== {platform_key} ===")
        print(_json.dumps(preset.to_dict(), indent=2))