"""
services/extract_content.py
=============================

Content extraction service for ClarityReply.

Two extraction paths, both writing straight onto a `ReplyRequest` instance:

1. SCREENSHOT  -> OCR via Gemini 2.5 Flash (vision)        -> req.ocr_text
2. URL         -> Anakin Universal URL Scraper             -> title, content,
                                                                summary, author_*,
                                                                likes/comments/shares

Supports any link Anakin can reach, with extra normalization for the
platforms you listed: LinkedIn, Twitter/X, Instagram, YouTube. Generic
sites (blogs, news, Reddit, etc.) are parsed from whatever structured data
(JSON-LD) or visible text Anakin's own `cleanedHtml` contains.

IMPORTANT — actual Anakin response shape:
    Anakin's `/v1/scrape` job result does NOT return `html`, `markdown`, or
    `generatedJson`. A completed job looks exactly like this:

        {
          "id": "...",
          "status": "completed",
          "url": "...",
          "jobType": "url_scraper",
          "country": "us",
          "cached": false,
          "createdAt": "...",
          "completedAt": "...",
          "durationMs": 6960,
          "cleanedHtml": "<div>...</div>"
        }

    `cleanedHtml` is the ONLY field with page content — a cleaned-up,
    rendered DOM snippet (no `<head>`, no OpenGraph/meta tags). Because of
    that, the old "AI generatedJson -> OpenGraph meta-tag regex -> markdown"
    fallback chain never actually had anything to fall back to and has been
    removed. Anakin's `cleanedHtml` is now the single source of truth for
    every platform; there is no secondary scraper or external fallback.

Docs referenced:
    https://anakin.io/docs/api-reference/url-scraper

Install:
--------
    pip install google-genai requests beautifulsoup4 --break-system-packages

Settings (settings.py):
------------------------
    GEMINI_API_KEY = "your-key-here"
    GEMINI_MODEL = "gemini-2.5-flash"     # optional override
    ANAKIN_API_KEY = "ak-your-key-here"
    ANAKIN_API_BASE = "https://api.anakin.io"  # optional override

Usage:
------
    from .models import ReplyRequest
    from .services.extract_content import ContentExtractionService

    req = ReplyRequest.objects.get(pk=1)
    service = ContentExtractionService()
    service.extract_and_save(req)   # branches on req.source_type automatically

    print(req.title, req.content, req.author_name)
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings

from google import genai
from google.genai import types

from core.models import ReplyRequest

logger = logging.getLogger("clarityreply.extraction")


# ==========================================================================
# 1. OCR EXTRACTION (Gemini 2.5 Flash, vision)
# ==========================================================================

class OCRExtractor:
    """
    Extracts text from a screenshot image using Gemini 2.5 Flash's vision
    capability. Used when ReplyRequest.source_type == "screenshot".
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", None)
        self.model = model or getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set in settings.py")
        self.client = genai.Client(api_key=self.api_key)

    def _load_image_bytes(self, image_source: str) -> tuple[bytes, str]:
        """
        image_source can be:
          - a local file path
          - a URL
          - a data URI / raw base64 string
        Returns (bytes, mime_type).
        """
        if image_source.startswith("data:"):
            header, b64data = image_source.split(",", 1)
            mime_type = header.split(";")[0].replace("data:", "") or "image/png"
            return base64.b64decode(b64data), mime_type

        if image_source.startswith("http://") or image_source.startswith("https://"):
            resp = requests.get(image_source, timeout=20)
            resp.raise_for_status()
            mime_type = resp.headers.get("Content-Type", "image/png").split(";")[0]
            return resp.content, mime_type

        # local file path
        mime_type, _ = mimetypes.guess_type(image_source)
        mime_type = mime_type or "image/png"
        with open(image_source, "rb") as f:
            return f.read(), mime_type

    def extract_text(self, image_source: str) -> str:
        """
        Returns the raw extracted text from the screenshot, reading
        top-to-bottom in natural reading order (preserving comment/post
        structure as best as possible).
        """
        image_bytes, mime_type = self._load_image_bytes(image_source)

        prompt = (
            "Extract ALL visible text from this screenshot, exactly as written. "
            "Read in natural top-to-bottom, left-to-right order, preserving the "
            "structure of posts/comments/replies (e.g. keep usernames attached "
            "to their message, keep nested replies indented or clearly separated). "
            "Do not summarize, translate, or fix typos. Do not include your own "
            "commentary — output ONLY the extracted text."
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt,
            ],
            config=types.GenerateContentConfig(temperature=0.0),
        )
        return (response.text or "").strip()

    def extract_and_save(self, req: ReplyRequest, image_source: Optional[str] = None) -> ReplyRequest:
        """
        Runs OCR and saves the result to req.ocr_text. If req.content is
        empty, also copies the OCR text into req.content so downstream
        reply generation has something to work with.
        """
        source = image_source or req.url
        if not source:
            raise ValueError("No image_source provided and req.url is empty.")

        text = self.extract_text(source)
        req.ocr_text = text
        content_was_empty = not req.content
        if not req.content:
            req.content = text

        update_fields = ["ocr_text", "updated_at"]
        if content_was_empty:
            update_fields.append("content")
        req.save(update_fields=update_fields)
        return req


# ==========================================================================
# 2. URL SCRAPING (Anakin Universal URL Scraper)
# ==========================================================================

def _parse_count(value: Any) -> int:
    """Turns '3', '1.2K', '12,345', etc. into an int. Used for every
    likes/comments/shares/views figure pulled out of cleanedHtml."""
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    text = str(value).lower().replace(",", "").strip()
    if not text:
        return 0
    multiplier = 1
    if text.endswith("k"):
        multiplier, text = 1000, text[:-1]
    elif text.endswith("m"):
        multiplier, text = 1_000_000, text[:-1]
    match = re.match(r"[\d.]+", text)
    if not match:
        return 0
    try:
        return int(float(match.group(0)) * multiplier)
    except ValueError:
        return 0


@dataclass
class AnakinScrapeJob:
    """
    Exact shape of a completed Anakin `/v1/scrape` job. This mirrors what
    Anakin actually returns — NOT a hypothetical richer payload. The only
    content field is `cleaned_html`.
    """
    id: str = ""
    status: str = ""
    url: str = ""
    job_type: str = ""
    country: str = ""
    cached: bool = False
    created_at: str = ""
    completed_at: str = ""
    duration_ms: int = 0
    cleaned_html: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_response(cls, data: Dict[str, Any]) -> "AnakinScrapeJob":
        return cls(
            id=data.get("id", "") or data.get("jobId", "") or "",
            status=data.get("status", "") or "",
            url=data.get("url", "") or "",
            job_type=data.get("jobType", "") or "",
            country=data.get("country", "") or "",
            cached=bool(data.get("cached", False)),
            created_at=data.get("createdAt", "") or "",
            completed_at=data.get("completedAt", "") or "",
            duration_ms=int(data.get("durationMs") or 0),
            cleaned_html=data.get("cleanedHtml", "") or "",
            raw=data,
        )


@dataclass
class ScrapedContent:
    title: str = ""
    content: str = ""
    summary: str = ""
    image_url: str = ""
    author_name: str = ""
    author_username: str = ""
    author_headline: str = ""
    likes: int = 0
    comments: int = 0
    shares: int = 0
    views: int = 0
    job_id: str = ""
    job_status: str = ""
    cached: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


def detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower().replace("www.", "")
    if "linkedin.com" in host:
        return "linkedin"
    if "twitter.com" in host or "x.com" in host:
        return "twitter"
    if "instagram.com" in host:
        return "instagram"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "reddit.com" in host:
        return "reddit"
    if "tiktok.com" in host:
        return "tiktok"
    if "facebook.com" in host:
        return "facebook"
    return "generic"


class AnakinScraperClient:
    """
    Thin client for Anakin's Universal URL Scraper.
    https://anakin.io/docs/api-reference/url-scraper
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: int = 60):
        self.api_key = api_key or getattr(settings, "ANAKIN_API_KEY", None)
        self.base_url = (base_url or getattr(settings, "ANAKIN_API_BASE", "https://api.anakin.io")).rstrip("/")
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError("ANAKIN_API_KEY not set in settings.py")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def scrape(self, url: str, use_browser: bool = True) -> AnakinScrapeJob:
        """
        Synchronous scrape (single request, full result back). Social
        platforms (LinkedIn, X, Instagram, YouTube) are JS-heavy, so
        use_browser defaults to True for reliability.

        Returns an AnakinScrapeJob — there is no `generateJson` request
        option anymore, since Anakin doesn't return a `generatedJson` field
        to use it with. cleaned_html is the only content Anakin gives back.
        """
        payload = {
            "url": url,
            "useBrowser": use_browser,
        }
        endpoint = f"{self.base_url}/v1/url-scraper"
        logger.warning("[EXTRACT][STEP 3] Anakin request endpoint=%s payload=%s", endpoint, payload)
        resp = requests.post(
            endpoint,
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        logger.warning(
            "[EXTRACT][STEP 3] Anakin response status=%s body=%s",
            resp.status_code,
            resp.text,
        )
        resp.raise_for_status()
        response_json = resp.json()
        logger.warning("[EXTRACT][STEP 5] Raw Anakin response JSON=%s", response_json)
        job = AnakinScrapeJob.from_response(response_json)
        if job.status == "completed":
            return job
        if job.status == "failed":
            raise RuntimeError(f"Anakin scrape job failed: {response_json}")
        if not job.id:
            raise RuntimeError(f"Anakin did not return a job id: {response_json}")

        poll_endpoint = f"{self.base_url}/v1/url-scraper/{job.id}"
        deadline = time.monotonic() + self.timeout

        while time.monotonic() < deadline:
            logger.warning("[EXTRACT][STEP 4] Anakin job polling job id=%s status=%s", job.id, job.status)
            time.sleep(2)
            poll_resp = requests.get(
                poll_endpoint,
                headers=self._headers(),
                timeout=self.timeout,
            )
            logger.warning(
                "[EXTRACT][STEP 4] Anakin poll response status=%s body=%s",
                poll_resp.status_code,
                poll_resp.text,
            )
            poll_resp.raise_for_status()
            poll_json = poll_resp.json()
            logger.warning("[EXTRACT][STEP 5] Raw Anakin poll response JSON=%s", poll_json)
            job = AnakinScrapeJob.from_response(poll_json)

            if job.status == "completed":
                logger.warning("[EXTRACT][STEP 4] Anakin job polling job id=%s status=completed", job.id)
                return job
            if job.status == "failed":
                logger.warning("[EXTRACT][STEP 4] Anakin job polling job id=%s status=failed", job.id)
                raise RuntimeError(f"Anakin scrape job failed: {poll_json}")

        logger.warning("[EXTRACT][STEP 4] Anakin job polling job id=%s status=timeout", job.id)
        raise TimeoutError(f"Anakin scrape job timed out after {self.timeout} seconds: {job.id}")


class URLContentExtractor:
    """
    Scrapes a URL via Anakin and normalizes the result into a
    ScrapedContent object, regardless of platform.

    Every field below is derived ONLY from Anakin's `cleaned_html` — there
    is no OpenGraph/meta-tag regex fallback and no secondary scraping
    service. If Anakin's DOM snapshot doesn't contain a piece of data
    (e.g. a generic site with no JSON-LD and no visible author block),
    that field is simply left blank rather than guessed at.
    """

    def __init__(self, client: Optional[AnakinScraperClient] = None):
        self.client = client or AnakinScraperClient()

    # ---- platform parsers, all operating on cleaned_html only ----------

    def _parse_twitter(self, html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        article = soup.find("article")
        data: Dict[str, Any] = {}
        if not article:
            return data

        # Author name + handle sit in the hover-card-trigger <div> next to
        # the avatar (the avatar link is also a hover-card-trigger, but
        # it's an <a>, so filtering by tag name skips it).
        info_block = article.find("div", attrs={"data-slot": "hover-card-trigger"})
        if info_block:
            links = info_block.find_all("a")
            if len(links) >= 1:
                data["author_name"] = links[0].get_text(strip=True)
            if len(links) >= 2:
                data["author_username"] = links[1].get_text(strip=True).lstrip("@")

        # Tweet body text.
        text_div = article.find("div", attrs={"dir": "auto"})
        if text_div:
            data["content"] = text_div.get_text("", strip=False).strip()

        # First media image, else the avatar.
        photo_link = article.find("a", attrs={"aria-label": "Image"})
        if photo_link and photo_link.find("img"):
            data["image_url"] = photo_link.find("img").get("src", "")
        else:
            avatar_img = article.find("img", alt="user avatar")
            if avatar_img:
                data["image_url"] = avatar_img.get("src", "")

        # Each engagement action button is immediately followed by a
        # sibling button whose aria-label IS the count, e.g.
        # aria-label="Reply" then a sibling with aria-label="3".
        def count_after(label: str) -> int:
            btn = article.find("button", attrs={"aria-label": label})
            if not btn:
                return 0
            sib = btn.find_next_sibling("button")
            if not sib:
                return 0
            return _parse_count(sib.get("aria-label"))

        data["comments"] = count_after("Reply")
        data["likes"] = count_after("Like")
        data["shares"] = count_after("Repost")

        # Views render as "<num> Views" text in the timestamp row.
        for a in article.find_all("a"):
            txt = a.get_text(" ", strip=True)
            if txt.endswith("Views"):
                m = re.match(r"([\d,.]+[KkMm]?)", txt)
                if m:
                    data["views"] = _parse_count(m.group(1))
                break

        data["title"] = (data.get("content") or "")[:80]
        return data

    def _parse_linkedin(self, html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        data: Dict[str, Any] = {}

        h1 = soup.find("h1")
        if h1:
            data["title"] = h1.get_text(strip=True)

        commentary = soup.find(attrs={"data-test-id": "main-feed-activity-card__commentary"})
        reshare_commentary = soup.find(attrs={"data-test-id": "feed-reshare-content__commentary"})
        if commentary and commentary.get_text(strip=True):
            data["content"] = commentary.get_text("\n", strip=True)
        elif reshare_commentary:
            data["content"] = reshare_commentary.get_text("\n", strip=True)

        actor = soup.find("a", attrs={"data-tracking-control-name": "public_post_feed-actor-name"})
        if actor:
            data["author_name"] = actor.get_text(strip=True)

        # LinkedIn's reaction <a> carries the count directly as an
        # attribute: data-num-reactions="8".
        reactions_link = soup.find("a", attrs={"data-num-reactions": True})
        if reactions_link:
            data["likes"] = _parse_count(reactions_link.get("data-num-reactions"))

        img = soup.find("img", attrs={"data-delayed-url": True})
        if img:
            data["image_url"] = img.get("data-delayed-url", "")

        return data

    def _parse_youtube(self, html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        data: Dict[str, Any] = {}

        obj = None
        for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
            if tag.string and '"VideoObject"' in tag.string:
                try:
                    obj = json.loads(tag.string)
                except json.JSONDecodeError:
                    obj = None
                break
        if not obj:
            return data

        data["title"] = obj.get("name", "")
        data["content"] = obj.get("description", "")
        data["summary"] = obj.get("description", "")
        data["author_name"] = obj.get("author", "")
        thumbs = obj.get("thumbnailUrl") or []
        if thumbs:
            data["image_url"] = thumbs[0]

        for stat in obj.get("interactionStatistic", []) or []:
            itype = stat.get("interactionType", "")
            count = _parse_count(stat.get("userInteractionCount"))
            if itype.endswith("WatchAction"):
                data["views"] = count
            elif itype.endswith("LikeAction"):
                data["likes"] = count
            elif itype.endswith("CommentAction"):
                data["comments"] = count

        return data

    def _parse_generic(self, html: str) -> Dict[str, Any]:
        """
        Last resort for sites without a dedicated parser above (blogs,
        news, Reddit, etc). Tries JSON-LD Article-style structured data
        first (still inside Anakin's cleaned_html — no extra request is
        made), then falls back to visible text.
        """
        soup = BeautifulSoup(html, "html.parser")
        data: Dict[str, Any] = {}

        for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
            if not tag.string:
                continue
            try:
                obj = json.loads(tag.string)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, list):
                obj = next((o for o in obj if isinstance(o, dict)), {})
            obj_type = str(obj.get("@type", "")) if isinstance(obj, dict) else ""
            if obj_type in ("Article", "NewsArticle", "BlogPosting"):
                data["title"] = obj.get("headline", "") or data.get("title", "")
                data["summary"] = obj.get("description", "") or data.get("summary", "")
                author = obj.get("author")
                if isinstance(author, dict):
                    data["author_name"] = author.get("name", "")
                elif isinstance(author, str):
                    data["author_name"] = author
                image = obj.get("image")
                if isinstance(image, dict):
                    data["image_url"] = image.get("url", "")
                elif isinstance(image, str):
                    data["image_url"] = image
                break

        if not data.get("title"):
            h1 = soup.find("h1")
            if h1:
                data["title"] = h1.get_text(strip=True)

        if not data.get("content"):
            body_text = soup.get_text("\n", strip=True)
            data["content"] = body_text

        return data

    def extract(self, url: str) -> ScrapedContent:
        platform = detect_platform(url)
        job = self.client.scrape(url)
        html = job.cleaned_html
        logger.warning(
            "[EXTRACT][STEP 4] Anakin job state used for parsing job id=%r status=%r cleanedHtml_length=%s",
            job.id,
            job.status,
            len(html or ""),
        )

        if platform == "twitter":
            parsed = self._parse_twitter(html)
        elif platform == "linkedin":
            parsed = self._parse_linkedin(html)
        elif platform == "youtube":
            parsed = self._parse_youtube(html)
        elif platform == "instagram":
            # Instagram's public DOM is close enough to Twitter's caption
            # layout for the same dir="auto" text-block heuristic to work;
            # if it doesn't find anything it just returns an empty dict.
            parsed = self._parse_twitter(html)
        else:
            parsed = self._parse_generic(html)

        scraped = ScrapedContent(
            title=(parsed.get("title") or "").strip(),
            content=(parsed.get("content") or "").strip(),
            summary=(parsed.get("summary") or "").strip(),
            image_url=(parsed.get("image_url") or "").strip(),
            author_name=(parsed.get("author_name") or "").strip(),
            author_username=(parsed.get("author_username") or "").strip(),
            author_headline=(parsed.get("author_headline") or "").strip(),
            likes=int(parsed.get("likes") or 0),
            comments=int(parsed.get("comments") or 0),
            shares=int(parsed.get("shares") or 0),
            views=int(parsed.get("views") or 0),
            job_id=job.id,
            job_status=job.status,
            cached=job.cached,
            raw=job.raw,
        )
        logger.warning(
            "[EXTRACT][STEP 6] Parsed data title=%r content=%r author_name=%r likes=%r comments=%r shares=%r",
            scraped.title,
            scraped.content,
            scraped.author_name,
            scraped.likes,
            scraped.comments,
            scraped.shares,
        )
        return scraped


# ==========================================================================
# 3. UNIFIED SERVICE — branches on source_type and saves to ReplyRequest
# ==========================================================================

class ContentExtractionService:
    """
    Single entry point: inspects req.source_type and runs the right
    extraction path, saving all results onto the ReplyRequest instance.
    """

    def __init__(
        self,
        ocr_extractor: Optional[OCRExtractor] = None,
        url_extractor: Optional[URLContentExtractor] = None,
    ):
        self._ocr_extractor = ocr_extractor
        self._url_extractor = url_extractor

    @property
    def ocr_extractor(self) -> OCRExtractor:
        if self._ocr_extractor is None:
            self._ocr_extractor = OCRExtractor()
        return self._ocr_extractor

    @property
    def url_extractor(self) -> URLContentExtractor:
        if self._url_extractor is None:
            self._url_extractor = URLContentExtractor()
        return self._url_extractor

    def extract_and_save(self, req: ReplyRequest) -> ReplyRequest:
        source_type = (req.source_type or "").lower()

        if source_type == "screenshot":
            return self.ocr_extractor.extract_and_save(req)

        if source_type == "url":
            if not req.url:
                raise ValueError("source_type is 'url' but req.url is empty.")

            scraped = self.url_extractor.extract(req.url)

            req.title = req.title or scraped.title
            req.content = req.content or scraped.content
            req.summary = req.summary or scraped.summary
            req.author_name = req.author_name or scraped.author_name
            req.author_username = req.author_username or scraped.author_username
            req.author_headline = req.author_headline or scraped.author_headline
            req.likes = scraped.likes or req.likes
            req.comments = scraped.comments or req.comments
            req.shares = scraped.shares or req.shares

            update_fields = [
                "title", "content", "summary",
                "author_name", "author_username", "author_headline",
                "likes", "comments", "shares", "updated_at",
            ]

            # Optional fields — only written if the model actually has them,
            # so this doesn't break installs that haven't migrated yet.
            if hasattr(req, "views"):
                req.views = scraped.views or getattr(req, "views", 0)
                update_fields.append("views")
            if hasattr(req, "scrape_job_id"):
                req.scrape_job_id = scraped.job_id
                update_fields.append("scrape_job_id")
            if hasattr(req, "scrape_cached"):
                req.scrape_cached = scraped.cached
                update_fields.append("scrape_cached")

            logger.warning(
                "[EXTRACT][STEP 7] Before extraction save model values=%s",
                {
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
                    "update_fields": update_fields,
                },
            )
            req.save(update_fields=update_fields)
            persisted_req = ReplyRequest.objects.get(pk=req.pk)
            logger.warning(
                "[EXTRACT][STEP 7] After extraction save/requery model values=%s",
                {
                    "id": persisted_req.id,
                    "platform": persisted_req.platform,
                    "source_type": persisted_req.source_type,
                    "url": persisted_req.url,
                    "title": persisted_req.title,
                    "content": persisted_req.content,
                    "summary": persisted_req.summary,
                    "author_name": persisted_req.author_name,
                    "author_username": persisted_req.author_username,
                    "author_headline": persisted_req.author_headline,
                    "likes": persisted_req.likes,
                    "comments": persisted_req.comments,
                    "shares": persisted_req.shares,
                },
            )
            return persisted_req

        # source_type == "text" (or unset) — nothing to extract, content
        # was already provided directly.
        return req
