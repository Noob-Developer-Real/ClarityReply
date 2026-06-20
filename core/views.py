"""
core/views.py

ClarityReply Django Views
Uses:
- ReplyRequest
- ContentExtractionService
- ClarityReplyService
- apply_platform_preset

No DRF required.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from http import HTTPStatus
from typing import Any, Dict

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.http import JsonResponse, HttpRequest
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from core.models import ReplyRequest
from core.services.extract_description import ContentExtractionService, detect_platform
from core.services.reply import ClarityReplyService
from core.common.platform_presets import apply_platform_preset

logger = logging.getLogger("clarityreply.extraction")


# ============================================================
# Constants
# ============================================================

PLATFORM_TEMPLATES = [
    "linkedin",
    "twitter",
    "instagram",
    "youtube",
    "reddit",
    "facebook",
    "discord",
    "whatsapp",
    "tiktok",
    "custom",
]

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

URL_VALIDATOR = URLValidator()


# ============================================================
# Helpers
# ============================================================

def success_response(
    payload: Dict[str, Any],
    status_code: int = HTTPStatus.OK,
) -> JsonResponse:
    body = {"success": True}
    body.update(payload)
    return JsonResponse(body, status=status_code)


def error_response(
    message: str,
    status_code: int = HTTPStatus.BAD_REQUEST,
) -> JsonResponse:
    return JsonResponse(
        {
            "success": False,
            "error": message,
        },
        status=status_code,
    )


def parse_request_data(request: HttpRequest) -> Dict[str, Any]:
    """
    Supports:
    - application/json
    - multipart/form-data
    - form-urlencoded
    """

    content_type = request.content_type or ""

    if "application/json" in content_type:
        if not request.body:
            return {}

        try:
            return json.loads(request.body.decode("utf-8"))
        except Exception as exc:
            raise ValidationError(
                f"Invalid JSON payload: {exc}"
            )

    return request.POST.dict()


def validate_url(url: str) -> None:
    try:
        URL_VALIDATOR(url)
    except ValidationError:
        raise ValidationError("Invalid URL.")


def build_platform_data(req: ReplyRequest) -> Dict[str, Any]:
    return {
        "platform": req.platform,
        "url": req.url,
        "title": req.title,
        "content": req.content,
        "summary": req.summary,
        "author_name": req.author_name,
        "author_username": req.author_username,
        "author_headline": req.author_headline,
        "likes": req.likes,
        "comments": req.comments,
        "shares": req.shares,
        "ocr_text": req.ocr_text,
    }


def debug_reply_request_values(req: ReplyRequest) -> Dict[str, Any]:
    return {
        "id": req.id,
        "platform": req.platform,
        "source_type": req.source_type,
        "url": req.url,
        "title": req.title,
        "content": req.content,
        "summary": req.summary,
        "author_name": req.author_name,
        "author_username": req.author_username,
        "author_headline": req.author_headline,
        "likes": req.likes,
        "comments": req.comments,
        "shares": req.shares,
        "ocr_text": req.ocr_text,
    }


# ============================================================
# Home
# ============================================================

@method_decorator(csrf_exempt, name="dispatch")
class HomeView(View):

    def get(self, request: HttpRequest):
        return render(request, "core/index.html")


# ============================================================
# Templates
# ============================================================

@method_decorator(csrf_exempt, name="dispatch")
class TemplateListView(View):

    def get(self, request: HttpRequest) -> JsonResponse:
        return success_response(
            {
                "templates": PLATFORM_TEMPLATES,
            }
        )


# ============================================================
# Extract Content
# ============================================================

@method_decorator(csrf_exempt, name="dispatch")
class ExtractContentView(View):

    def post(self, request: HttpRequest) -> JsonResponse:

        temp_file_path = None

        try:
            data = parse_request_data(request)

            source_type = (
                data.get("source_type", "")
                .strip()
                .lower()
            )
            logger.warning(
                "[EXTRACT][STEP 1] Incoming request payload source_type=%r url=%r platform=%r",
                source_type,
                data.get("url"),
                data.get("platform"),
            )

            if source_type not in {"url", "screenshot"}:
                return error_response(
                    "source_type must be 'url' or 'screenshot'."
                )

            platform = (
                data.get("platform", "custom")
                .strip()
                .lower()
            )

            extraction_service = ContentExtractionService()

            # ===================================================
            # URL
            # ===================================================

            if source_type == "url":

                url = (
                    data.get("url", "")
                    .strip()
                )

                if not url:
                    return error_response(
                        "url is required."
                    )

                validate_url(url)
                detected_platform = detect_platform(url)
                if detected_platform != "generic" and detected_platform != platform:
                    logger.warning(
                        "[EXTRACT][STEP 1] Platform overridden from payload platform=%r to detected platform=%r for url=%r",
                        platform,
                        detected_platform,
                        url,
                    )
                    platform = detected_platform

                req = ReplyRequest.objects.create(
                    platform=platform,
                    source_type="url",
                    url=url,
                    content="",
                )
                logger.warning("[EXTRACT][STEP 2] ReplyRequest created request_id=%s", req.id)

                req = extraction_service.extract_and_save(req)

            # ===================================================
            # Screenshot
            # ===================================================

            else:

                image = request.FILES.get("image")

                if not image:
                    return error_response(
                        "image file is required."
                    )

                if image.content_type not in ALLOWED_IMAGE_TYPES:
                    return error_response(
                        "Unsupported image type."
                    )

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".png"
                ) as temp_file:

                    for chunk in image.chunks():
                        temp_file.write(chunk)

                    temp_file_path = temp_file.name

                req = ReplyRequest.objects.create(
                    platform=platform,
                    source_type="screenshot",
                    content="",
                )
                logger.warning("[EXTRACT][STEP 2] ReplyRequest created request_id=%s", req.id)

                req = extraction_service.ocr_extractor.extract_and_save(
                    req,
                    image_source=temp_file_path,
                )

            apply_platform_preset(req)
            logger.warning(
                "[EXTRACT][STEP 7] Before final save model values=%s",
                debug_reply_request_values(req),
            )
            req.save()
            persisted_req = ReplyRequest.objects.get(pk=req.pk)
            logger.warning(
                "[EXTRACT][STEP 7] After final save/requery model values=%s",
                debug_reply_request_values(persisted_req),
            )

            platform_data = build_platform_data(persisted_req)
            response_payload = {
                "request_id": persisted_req.id,
                "platform_present_data": platform_data,
                "platform_present": platform_data,
                "platform_data": platform_data,
            }
            logger.warning("[EXTRACT][STEP 8] Final JSON response=%s", response_payload)
            return success_response(response_payload)

        except ValidationError as exc:
            logger.warning("[EXTRACT][VALIDATION] Request validation failed: %s", exc)
            return error_response(
                str(exc),
                HTTPStatus.BAD_REQUEST,
            )

        except Exception as exc:
            logger.exception("[EXTRACT][ERROR] Extraction failed")
            return error_response(
                f"Extraction failed: {exc}",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception:
                    pass


# ============================================================
# Generate Reply
# ============================================================

@method_decorator(csrf_exempt, name="dispatch")
class GenerateReplyView(View):

    def post(self, request: HttpRequest) -> JsonResponse:

        try:

            data = parse_request_data(request)

            request_id = data.get("request_id")

            if request_id:

                try:
                    req = ReplyRequest.objects.get(
                        id=request_id
                    )
                except ReplyRequest.DoesNotExist:
                    return error_response(
                        "Request not found."
                    )

            else:

                post_content = (
                    data.get("post_content", "")
                    .strip()
                )

                if not post_content:
                    return error_response(
                        "post_content is required."
                    )

                platform = (
                    data.get("platform", "custom")
                    .strip()
                    .lower()
                )

                req = ReplyRequest.objects.create(
                    platform=platform,
                    source_type="text",
                    content=post_content,
                )

            # ===================================================
            # Editable frontend fields
            # ===================================================

            editable_fields = [
                "title",
                "content",
                "summary",
                "author_name",
                "author_username",
                "author_role",
                "author_company",
                "author_headline",
                "topic",
                "subtopic",
                "industry",
                "post_type",
                "post_intent",
                "sentiment",
                "emotion",
                "audience_type",
                "formality_level",
                "conversation_summary",
                "latest_message",
            ]

            for field in editable_fields:

                if field in data:
                    setattr(
                        req,
                        field,
                        data.get(field),
                    )

            previous_messages = (
                data.get("previous_messages", "")
                .strip()
            )
            conversation_platform = (
                data.get("selected_template")
                or data.get("platform")
                or req.platform
                or ""
            ).strip().lower()
            if previous_messages and conversation_platform in {"discord", "whatsapp"}:
                req.conversation_summary = previous_messages
                req.latest_message = req.content or data.get("post_content", "") or req.latest_message
                req.conversation_history = [
                    {
                        "role": "previous_messages",
                        "message": previous_messages,
                    }
                ]

            selected_template = (
                data.get(
                    "selected_template",
                    req.platform,
                )
                .strip()
                .lower()
            )

            if (
                selected_template
                and selected_template
                not in PLATFORM_TEMPLATES
            ):
                return error_response(
                    "Invalid template."
                )

            if selected_template != "custom":
                req.platform = selected_template

            if "reply_goal" in data:
                req.reply_goal = data["reply_goal"]

            if "reply_style" in data:
                req.reply_style = data["reply_style"]

            if "reply_length" in data:
                req.reply_length = data["reply_length"]

            if "emoji_level" in data:
                req.emoji_level = int(
                    data["emoji_level"]
                )

            if "creativity_level" in data:
                req.creativity_level = int(
                    data["creativity_level"]
                )

            apply_platform_preset(req)

            req.save()

            reply_service = ClarityReplyService()

            reply_service.generate_and_save(req)

            return success_response(
                {
                    "request_id": req.id,
                    "variation_1": req.professional_reply,
                    "variation_2": req.friendly_reply,
                    "variation_3": req.engaging_reply,
                }
            )

        except ValidationError as exc:

            return error_response(
                str(exc),
                HTTPStatus.BAD_REQUEST,
            )

        except Exception as exc:

            return error_response(
                f"Reply generation failed: {exc}",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
