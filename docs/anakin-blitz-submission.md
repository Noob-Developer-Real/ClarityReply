# ClarityReply: Anakin Blitz Submission

**Builder:** Tejasvi Bajaj  
**Competition:** Anakin Blitz  
**Format:** 6-hour hackathon  
**Project:** ClarityReply

## One-Line Summary

ClarityReply helps users extract social post context from URLs or screenshots and generate short, human, platform-aware reply variations.

## Problem Statement

People respond to content across many platforms every day, but each platform has a different communication style.

LinkedIn expects professional and thoughtful replies. Instagram rewards short, natural comments with casual emoji usage. WhatsApp and Discord need awareness of previous messages. Reddit punishes generic brand-like language. YouTube comments should feel supportive and discussion-friendly.

The problem is that most AI reply tools produce generic replies that do not respect platform context. Users also waste time copying post text, cleaning it, identifying the platform, rewriting prompts, and checking whether the final reply sounds natural.

The challenge:

> Build a fast workflow that can extract context from a social post and generate platform-native reply variations with minimal user effort.

## Solution

ClarityReply solves this with a focused extraction-to-reply workflow.

Users can:

- Paste a social post URL.
- Upload a screenshot.
- Extract platform data such as title, content, summary, author, and engagement.
- Add conversation context for Discord and WhatsApp.
- Generate three alternate phrasings of the same reply intent.
- Copy a reply and jump back to the original post when a URL exists.

The generated output intentionally avoids separate personalities such as “Professional Reply,” “Friendly Reply,” and “Engaging Reply.” Instead, ClarityReply returns three variations of the same strategy:

```json
{
  "variation_1": "",
  "variation_2": "",
  "variation_3": ""
}
```

This keeps the reply goal, tone, platform style, and intent consistent while giving the user wording options.

## Why Anakin

Anakin URL Scraper is used to fetch rendered social page content and return `cleanedHtml`. ClarityReply then parses that cleaned HTML for platform-specific fields.

The extraction pipeline uses Anakin for:

- Social URL ingestion.
- Cleaned rendered HTML retrieval.
- Platform-specific downstream parsing.
- Reducing the amount of custom scraping infrastructure needed during a 6-hour build.

## Product Workflow

```text
1. User chooses URL or Screenshot
2. User extracts content
3. Backend detects platform and saves ReplyRequest
4. Extraction service fills structured fields
5. User configures platform/tone/length
6. Gemini generates three reply variations
7. Frontend renders copy-ready reply cards
```

For Discord and WhatsApp:

```text
Previous messages
  +
Latest message
  +
Post content
  =
Context-aware reply prompt
```

## Architecture

```text
Frontend
  |
  | HTML/CSS/JavaScript
  | Extract buttons
  | Platform selector
  | Conversation context
  | Generated reply cards
  v
Django Views
  |
  | ExtractContentView
  | GenerateReplyView
  v
Services
  |
  | ContentExtractionService
  |   |-- URLContentExtractor
  |   |-- OCRExtractor
  |
  | ClarityReplyService
  v
External APIs
  |
  | Anakin URL Scraper
  | Google Gemini
  v
Database
  |
  | ReplyRequest
  v
Django Admin
```

## Core Components

### Frontend

The frontend is a single Django template with static JavaScript and CSS. It handles:

- URL input.
- Screenshot upload.
- Platform selection.
- Conversation context for Discord and WhatsApp.
- Reply generation settings.
- Copy workflow.
- Generated reply rendering.

### Backend Views

`ExtractContentView` handles URL and screenshot extraction.

`GenerateReplyView` handles reply generation from an existing `ReplyRequest` or direct post content.

### Extraction Service

`ContentExtractionService` routes extraction by source type.

URL extraction uses Anakin URL Scraper and platform-specific parsers.

Screenshot extraction uses Gemini vision OCR.

### Reply Service

`ClarityReplyService` builds a focused prompt and asks Gemini to generate only valid JSON with three reply variations.

### Admin

The Django admin page exposes enough operational information to inspect requests, extraction quality, conversation context, engagement fields, and generated replies.

## Platform Handling

Supported platforms:

- LinkedIn
- Twitter/X
- Instagram
- YouTube
- Reddit
- Facebook
- Discord
- WhatsApp
- TikTok
- Custom

Notable platform behavior:

- Instagram replies are short, natural, and emoji-aware.
- Discord and WhatsApp support previous message context.
- YouTube extraction reads JSON-LD and visible cleaned HTML fallbacks.
- Instagram extraction reads embedded SSR JSON payloads for captions and author data.

## Data Model

The project uses the existing `ReplyRequest` model.

Important fields:

- `platform`
- `source_type`
- `url`
- `content`
- `title`
- `summary`
- `author_name`
- `author_username`
- `conversation_summary`
- `latest_message`
- `conversation_history`
- `professional_reply`
- `friendly_reply`
- `engaging_reply`

The three existing reply fields are reused internally as storage for:

- `variation_1`
- `variation_2`
- `variation_3`

No extra migration is required for the variation format.

## API Flow

### Extraction

```text
POST /api/extract/
```

Request:

```json
{
  "source_type": "url",
  "url": "https://example.com/post",
  "platform": "instagram"
}
```

Response:

```json
{
  "success": true,
  "request_id": 1,
  "platform_data": {
    "platform": "instagram",
    "url": "https://example.com/post",
    "title": "",
    "summary": "",
    "content": "",
    "author_name": "",
    "author_username": ""
  }
}
```

### Reply Generation

```text
POST /api/generate-reply/
```

Response:

```json
{
  "success": true,
  "request_id": 1,
  "variation_1": "",
  "variation_2": "",
  "variation_3": ""
}
```

## 6-Hour Build Scope

The project focuses on the core value loop:

- Extract context.
- Preserve structured data.
- Generate useful reply variations.
- Keep platform behavior realistic.
- Provide enough admin visibility for debugging.

Out of scope for the hackathon build:

- Full production deployment hardening.
- Browser extension integration.
- Team accounts.
- Analytics dashboard.
- Long-term reply performance tracking.

## Future Roadmap

- Browser extension for replying directly on social platforms.
- More robust parsers for every supported platform.
- Saved replies and favorites.
- Team workspaces.
- Reply analytics.
- User-level authentication and history.
- Production deployment setup.

## Closing Note

ClarityReply was built by **Tejasvi Bajaj** for **Anakin Blitz** as a 6-hour hackathon project. The goal was to create a practical AI product that demonstrates extraction, structured context handling, and platform-native reply generation in a tight build window.
