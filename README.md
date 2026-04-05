# 🤖 WhatsApp AI Chatbot Platform

A multi-tenant, production-grade WhatsApp chatbot backend powered by **Google Gemini 2.5 Flash**, **LangChain RAG**, and **Firebase Firestore**. Built with FastAPI, it enables businesses to deploy their own AI-driven WhatsApp assistant trained on custom documents — with full multi-language support, end-to-end encryption, and enterprise-level rate limiting.

---

## 📋 Table of Contents

- [Overview](#overview)
- [The Problem It Solves](#theproblemitsolves)
- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Security](#security)
- [Rate Limiting](#rate-limiting)
- [Multi-Language Support](#multi-language-support)
- [RAG System](#rag-system)
- [Fallback System](#fallback-system)
- [Deployment](#deployment)
- [Contributing](#contributing)

---

## Overview

This platform allows businesses (gyms, restaurants, bakeries, etc.) to register and deploy their own WhatsApp AI chatbot — without writing any AI code. Each business uploads a knowledge document (menu, policies, FAQs), and the RAG system answers their customers' questions automatically via WhatsApp.

The platform supports multiple concurrent business clients, each with their own isolated data, conversation history, and bot configuration.

---

## The Problem It Solves
For local businesses like **Bakeries, and Restaurants**, high-commission delivery platforms (like Zomato or Swiggy) consume **30-40%** of every transaction. This makes it difficult for small to medium-sized businesses to maintain healthy margins while offering online ordering.

### The Solution
This system eliminates the middleman by enabling direct customer-to-business commerce via WhatsApp.

* **Zero Commission:** Businesses retain 100% of their revenue by moving the ordering process from high-fee third-party apps directly to their own WhatsApp backend.
* **Automated Interaction:** Specifically designed handlers for different niches:
    * **Restaurants & Bakeries:** Automated menu browsing, order taking, and inquiry handling.
    * **Gyms:** Membership management and automated responses for fitness-related inquiries.
* **RAG-Powered Intelligence:** Uses Retrieval-Augmented Generation (RAG) to provide accurate, business-specific information to customers instantly.
* **Enterprise-Grade Backend:** Features a robust FastAPI structure with integrated Firebase for data persistence, rate limiting to prevent spam, and secure JWT-based authentication for administrative tasks.
* **Seamless User Experience:** Customers can order items, ask questions, and interact with the brand in the app they already use daily—WhatsApp—without downloading additional software.

---

## Features

### 🧠 AI & Retrieval
- **RAG (Retrieval-Augmented Generation)** using LangChain + FAISS + BM25 ensemble retrieval
- Powered by **Google Gemini 2.5 Flash** for generation and **Google Generative AI Embeddings** for vector search
- **Prompt injection protection** on all user inputs
- Conversation history support per user session
- Per-client document upload and hot-reload into the RAG pipeline

### 🌐 Multi-Language
- Auto-detects **English, Hindi, Gujarati, and Hinglish** from incoming messages
- Translates queries to English before RAG processing, then translates responses back to the user's language
- LRU-cached translations (up to 500 entries) to reduce API calls
- Timeout-protected translation with graceful English fallback

### 🔒 Security & Encryption
- **Fernet symmetric encryption** for all sensitive data at rest (phone numbers, names, tokens)
- **bcrypt password hashing** for client account passwords
- **JWT authentication** for the dashboard API (8-hour sessions)
- Phone number validation and input sanitization on all endpoints
- Security event logging (login attempts, invalid tokens, suspicious activity)
- Message replay attack prevention (messages older than 2.5 minutes are rejected)

### ⚡ Rate Limiting
- Multi-layered: per-minute, per-hour, per-day sliding window counters
- Token bucket algorithm for burst control (120 requests/minute burst)
- Duplicate message detection (30-second cooldown)
- Automatic temporary user blocking on suspicious activity
- Admin endpoints to view stats, unblock, or reset limits

### 🏢 Multi-Tenant
- Each business client has isolated Firestore collections for members, orders, and chat data
- TTL-based RAG bot cache (30-minute TTL, max 100 clients) with LRU eviction
- Renewal reminder system: automated WhatsApp messages sent to members whose plans expire within 3 days

### 📊 Dashboard API
- Business registration and login
- Customer and non-member management
- Order confirmation flow with WhatsApp notifications
- Dashboard statistics (total customers, pending/total orders)
- Payment link management

---

## Architecture

```
WhatsApp Cloud API
        │  (Webhook POST)
        ▼
   FastAPI (app.py)
        │
        ├── Rate Limiter ──────────────────── rate_limiter.py
        │       │
        │       ▼
        ├── Message Extraction & Validation
        │       │
        │       ▼
        ├── Firebase Lookup ───────────────── firebase.py
        │   (phone_id → client_id → client config)
        │       │
        │       ▼
        ├── RAG Cache Manager
        │   (client_id → RAGBot instance)
        │       │
        │       ├── Cache HIT  → return cached bot
        │       └── Cache MISS → fetch doc → build RAGBot ── Rag.py
        │                                         │
        │                                         ├── LangChain Text Splitter
        │                                         ├── FAISS + BM25 Ensemble Retrieval
        │                                         └── Gemini 2.5 Flash (generation)
        │
        ├── EfficientTranslator ───────────── Features.py
        │   (detect lang → translate to EN → process → translate back)
        │
        ├── Fallback Chain ────────────────── fallback.py → basic_fallback.py
        │
        └── send_whatsapp_message()
            (httpx → WhatsApp Graph API v19.0)
```

---

## Project Structure

```
.
├── app.py                  # FastAPI application, all routes, webhook handler, cache manager
├── Rag.py                  # RAGBot class — FAISS+BM25 retrieval, Gemini generation
├── Features.py             # EfficientTranslator — language detection & translation pipeline
├── firebase.py             # Firebase Admin SDK wrapper — CRUD for clients, customers, orders
├── encryption_utils.py     # Fernet encryption, bcrypt hashing, singleton logger, validators
├── rate_limiter.py         # Multi-layer rate limiter (token bucket + sliding window)
├── fallback.py             # Fallback response handler (LLM or basic)
├── basic_fallback.py       # Rule-based keyword chatbot (last-resort fallback)
├── get_secrets.py          # Secret loading utility (env vars / secret manager)
├── handle_all_things.py    # Business-type-specific message handlers (gym, restaurant, bakery)
├── we_are.py               # System prompt / company context injected into RAG
├── static/                 # Frontend assets (index.html, CSS, JS)
├── templates/              # Jinja2 templates
└── requirements.txt
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web Framework | FastAPI |
| AI Model | Google Gemini 2.5 Flash (`langchain-google-genai`) |
| Embeddings | Google Generative AI Embeddings |
| Vector Store | FAISS (`langchain-community`) |
| Keyword Retrieval | BM25 (`langchain-community`) |
| Database | Firebase Firestore (via `firebase-admin`) |
| Encryption | Fernet (`cryptography`) |
| Password Hashing | bcrypt |
| Auth | JWT (`PyJWT`) |
| HTTP Client | httpx (async) |
| Translation | `deep-translator` (Google Translate) |
| Env / Secrets | `python-dotenv`, custom `get_secrets.py` |
| Server | Uvicorn |

---

## Prerequisites

- Python 3.11+
- A **Firebase** project with Firestore enabled and a service account JSON key
- A **WhatsApp Business** account with Cloud API access (Meta Developer Portal)
- A **Google AI Studio** API key (for Gemini and Embeddings)
- A **Fernet key** for data encryption (generate with `cryptography.fernet.Fernet.generate_key()`)

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables (see Configuration below)
cp .env.example .env
# Edit .env with your credentials

# 5. Run the development server
uvicorn app:app --reload --port 8000
```

---

## Configuration

Create a `.env` file in the project root with the following variables:

```env
# Encryption
FERNET_KEY=your_44_char_fernet_key_here

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key

# Firebase
FIREBASE_CREDENTIALS_PATH=/path/to/serviceAccountKey.json

# JWT
JWT_SECRET=your_jwt_secret_key

# Admin API
ADMIN_API_KEY=your_admin_api_key
```

> **Note:** All secrets are loaded via the `get_secrets.py` utility, which supports both plain environment variables and a secret manager. Sensitive values are encrypted with Fernet before being stored in Firestore.

---

## API Reference

### Public Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serve frontend HTML dashboard |
| `GET` | `/health` | Health check |
| `POST` | `/api/login` | Authenticate a business client, returns JWT |
| `POST` | `/api/register` | Register a new business (form data + optional doc upload) |
| `GET/POST` | `/send-reminder` | Trigger renewal reminder WhatsApp messages |

### Authenticated Endpoints (Bearer JWT)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/verify-session` | Validate current JWT session |
| `POST` | `/api/add-customer` | Add a member with plan expiry date |
| `POST` | `/api/add-non-member` | Add a non-member to exclusion list |
| `POST` | `/api/upload-document` | Upload/replace the RAG knowledge document |
| `POST` | `/api/update-payment-link` | Set the payment URL sent in renewal reminders |
| `GET` | `/api/dashboard-stats` | Get total customers, orders, and pending orders |
| `GET` | `/api/confirmed-orders` | List all `confirmed_to_deliver` orders |
| `GET` | `/api/new-orders` | Check if any new unconfirmed orders exist |
| `POST` | `/api/confirm-order/{order_id}` | Confirm an order and notify the customer via WhatsApp |

### Admin Endpoints (X-Admin-Key header)

| Method | Path | Description |
|---|---|---|
| `GET` | `/cache/stats` | RAG cache hit/miss statistics |
| `POST` | `/cache/clear/{client_id}` | Invalidate a specific client's RAG cache |
| `POST` | `/cache/cleanup` | Purge all expired cache entries |
| `GET` | `/rate-limit/stats/{phone_number}` | Rate limit stats for a user |
| `POST` | `/rate-limit/reset/{phone_number}` | Reset all rate limit counters for a user |
| `POST` | `/rate-limit/unblock/{phone_number}` | Manually unblock a temporarily blocked user |
| `GET` | `/rate-limit/global-stats` | Global rate limiting statistics |

### WhatsApp Webhook

| Method | Path | Description |
|---|---|---|
| `GET` | `/webhook` | WhatsApp webhook verification (hub.challenge) |
| `POST` | `/webhook` | Receive and process incoming WhatsApp messages |

---

## Security

### Data Encryption
All personally identifiable information stored in Firestore (names, phone numbers, WhatsApp tokens, API keys) is encrypted using **Fernet symmetric encryption** before writing and decrypted on read. The encryption key is validated on startup for correct format and length.

### Authentication
- Client dashboard sessions use **JWT tokens** (8-hour expiry)
- Admin routes require an `X-Admin-Key` header
- All client IDs are validated against a strict allowlist regex: `^[A-Za-z0-9_-]{8,64}$`

### Input Sanitization
- Phone numbers are validated with a regex before any processing
- All string inputs are sanitized with a maximum length cap
- Prompt injection attempts in user messages are detected and blocked before reaching the LLM

### Webhook Security
- Messages older than 150 seconds are discarded (replay protection)
- Messages with future timestamps are rejected (clock-skew/replay attack prevention)
- Bot's own outgoing messages are automatically filtered out (prevents self-loop)

---

## Rate Limiting

The `RateLimiter` in `rate_limiter.py` applies the following checks in order for every incoming WhatsApp message:

1. **Block check** — Is the user temporarily blocked? Return 429 with retry-after.
2. **Duplicate message** — Same message within 10 seconds? Reject with 30-second cooldown.
3. **Message length** — Over 4,000 characters? Reject.
4. **Burst control** — More than 120 requests in 60 seconds? Reject with 10-second wait.
5. **Token bucket** — Smooth per-minute rate enforced via token refill.
6. **Sliding window (minute)** — Over 300 req/min? Reject.
7. **Sliding window (hour)** — Over 5,000 req/hr? Reject.
8. **Sliding window (day)** — Over 50,000 req/day? Reject.
9. **Suspicious activity** — Over 100 req/min triggers a 120-second auto-block.

User identities for rate limiting are derived from a SHA-256 hash of `client_id:phone_number` — no raw phone numbers are stored in memory.

---

## Multi-Language Support

`EfficientTranslator` in `Features.py` provides the full translation pipeline:

1. **Script detection** — Unicode range analysis distinguishes Devanagari (Hindi) from Gujarati script from Latin.
2. **Hinglish detection** — A curated vocabulary of ~100 transliterated Hindi words, combined with pattern matching (question words, repeated characters, subject-verb combos), identifies Hinglish with high accuracy.
3. **Translation to English** — Uses `deep-translator` (Google Translate) with a 10-second timeout and LRU caching.
4. **Response translation back** — The English LLM response is translated back to the user's detected language before sending.

Supported languages: **English, Hindi (Devanagari), Gujarati, Hinglish (Hindi in Roman script)**.

---

## RAG System

`RAGBot` in `Rag.py` implements a retrieval-augmented generation pipeline:

- **Chunking** — Documents split into 1,000-character chunks with 150-character overlap using `RecursiveCharacterTextSplitter`
- **Dual retrieval** — FAISS vector similarity search combined with BM25 keyword retrieval via `EnsembleRetriever` (top-5 results)
- **LLM** — `ChatGoogleGenerativeAI` with Gemini 2.5 Flash, temperature 0.3, max 500 output tokens
- **Conversation history** — Per-user session history maintained in memory for contextual responses
- **Caching** — `RAGCacheManager` in `app.py` caches initialized `RAGBot` instances per client for 30 minutes (max 100 clients), with LRU eviction and thread-safe access via `threading.Lock`

When a client registers and uploads a document, the RAG bot is initialized the first time a customer messages that business and cached for subsequent requests.

---

## Fallback System

Three-tier graceful degradation:

1. **RAGBot** — Primary response via document retrieval + Gemini generation.
2. **`fallback.py`** — Called when RAG is unavailable; currently delegates to the basic fallback.
3. **`basic_fallback.py`** — Fully offline, rule-based keyword matcher covering greetings, feelings, FAQs, jokes, and motivational responses. Requires zero external dependencies and zero latency.

---

## Deployment

### Docker (recommended)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Google Cloud Run / Render / Railway

1. Set all environment variables as platform secrets.
2. Point your **WhatsApp Cloud API webhook URL** to `https://your-domain/webhook`.
3. Set the webhook **verify token** to match the `WA_Verify_Token` stored for each client in Firestore.

### Renewal Reminders (Cron)

Hit `GET /send-reminder` daily via a cron job or Cloud Scheduler to trigger plan expiry notifications.

---

## Contributing

1. Fork the repository and create a feature branch: `git checkout -b feature/your-feature`
2. Follow the existing code style — all functions should include try/except with `logger.log_error()`
3. Never log raw phone numbers or API keys — use `hash_for_logging()` for identifiers
4. All new Firestore writes of sensitive data must use `encrypt_data()` from `encryption_utils.py`
5. Open a pull request with a clear description of your changes

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.
