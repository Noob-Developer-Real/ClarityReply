# ClarityReply

[Add project summary]

## Badges

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.x-092E20?style=for-the-badge&logo=django&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![License](https://img.shields.io/badge/License-[Add%20license]-lightgrey?style=for-the-badge)

## Demo

- Deployment: [Add deployment URL]
- Demo video: [Add demo video]
- Screenshots: [Add screenshots]

## Features

- URL-based social post extraction
- Screenshot-based content extraction
- Editable platform data before reply generation
- Platform-aware reply generation
- Discord and WhatsApp conversation context support
- Copy-to-reply workflow
- Mobile-responsive generated reply cards

## Architecture

[Add architecture diagram]

High-level flow:

```text
Frontend
  -> Django views
  -> Extraction service
  -> ReplyRequest persistence
  -> Reply generation service
  -> JSON response
  -> Frontend rendering
```

## Tech Stack

- Backend: Django
- Frontend: HTML, CSS, JavaScript
- Database: [Add database]
- AI: Google Gemini via `google-genai`
- URL extraction: Anakin URL Scraper
- Deployment: [Add deployment platform]

## Installation

```bash
git clone [Add repository URL]
cd ClarityReply
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

Create a local environment file or configure these variables in your shell/deployment platform:

```bash
SECRET_KEY="[Add Django secret key]"
DEBUG=True
DATABASE_URL="[Add database URL]"
GEMINI_API_KEY="[Add Gemini API key]"
GEMINI_MODEL="gemini-2.5-flash"
ANAKIN_API_KEY="[Add Anakin API key]"
ANAKIN_API_BASE="https://api.anakin.io"
ALLOWED_HOSTS="localhost,127.0.0.1"
```

## Local Development

```bash
python3 manage.py migrate
python3 manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Run checks/tests:

```bash
python3 manage.py check
python3 manage.py test
```

## API Flow

### Extract Content

```text
POST /api/extract/
```

Inputs:

- `source_type`: `url` or `screenshot`
- `url`: required for URL extraction
- `image`: required for screenshot extraction
- `platform`: selected platform

Returns:

- `request_id`
- `platform_data`
- extracted fields such as `platform`, `title`, `summary`, `content`, `author_name`, and `author_username`

### Generate Replies

```text
POST /api/generate-reply/
```

Inputs:

- `request_id` or `post_content`
- `platform`
- editable extracted fields
- reply settings
- optional `previous_messages` for Discord and WhatsApp

Returns:

```json
{
  "variation_1": "",
  "variation_2": "",
  "variation_3": ""
}
```

## Screenshots

[Add screenshots]

## Roadmap

- [Add roadmap item]
- [Add roadmap item]
- [Add roadmap item]

## Contributing

[Add contribution guidelines]

## License

[Add license]
