# Telegram Monitoring Bot For OLX

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Aiogram 3.x](https://img.shields.io/badge/Aiogram-3.x-2CA5E0?style=flat&logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![SQLAlchemy 2.0](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=flat)](https://www.sqlalchemy.org/)
[![curl_cffi](https://img.shields.io/badge/curl__cffi-Chrome120-success?style=flat)](https://github.com/yifeikong/curl_cffi)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

[🇷🇺 Читать на русском](README_RU.md)

An enterprise-grade, asynchronous real-time classifieds monitoring system and lead-generation engine designed to track, audit, and filter high-liquidity listings across OLX marketplaces (Romania, Kazakhstan, Ukraine, Poland) with zero-latency delivery to Telegram.

Built from the ground up to bypass CloudFront and AWS WAF edge bot protection, neutralize TLS/JA4 browser fingerprint challenges, ingest sub-second Mobile REST API feeds, eliminate duplicate/stale listings via strict mathematical timestamp delta formulas, and balance multi-category leads with on-demand phone extraction.

## Key Architectural Highlights

- **Mobile REST Edge Ingestion**: Bypasses heavy JavaScript/SSR HTML hydration overhead by directly streaming from internal mobile API endpoints (`/api/v1/offers/`), completing full catalog crawls in sub-40ms.
- **AWS WAF & CloudFront Evasion**: Emulates Chrome 120/124 TLS ClientHello, HTTP/2 multiplexing, and JA4 fingerprint parameters through `curl_cffi`, defeating CloudFront anti-bot heuristics without proxy burnout.
- **Lead Multiplexer & Category Balancer**: Groups incoming stream into diverse categories (Automotive, Real Estate, Electronics, Fashion, Home, Jobs) and applies fair round-robin quota limits per batch, preventing single-category feed flooding.
- **Mathematical Freshness & Anti-Bump Engine**: Discards paid commercial bumps and stale reposts by comparing creation timestamps against refresh timestamps (`bump_delta <= 120s`) and strict freshness windows (`age <= 30 min`).
- **On-Demand Phone Extraction & Caching**: Bypasses OLX hourly phone limits (6-8 reveals/10 min) by providing interactive inline buttons. Phone numbers are queried on-demand and cached permanently in PostgreSQL with zero API quota burn on repeated lookups.
- **Ultra-Resilient Media Pipeline**: Resolves Apollo CDN original full-resolution photo assets (`/image`), with double-layer fallback to text messages in case of upstream Telegram CDN latency.
- **Transactional Deduplication**: Leverages PostgreSQL composite B-Tree indexes on `(link_id, olx_offer_id)` with `ON CONFLICT DO NOTHING` statements for O(log N) deduplication under high-throughput concurrency.
- **Bounded Concurrency Poller**: Asynchronous polling engine governed by `asyncio.Semaphore` and randomized jitter intervals, handling hundreds of concurrent target searches with sub-second event loop lag.

## Tech Stack

- **Python 3.12** (Strict typing, PEP 8 compliance, Asyncio task grouping)
- **Aiogram 3.x** (Fully asynchronous Telegram bot framework, FSM, custom inline keyboards)
- **curl_cffi** (HTTP/2 & TLS 1.3 browser impersonation with JA4 fingerprinting)
- **SQLAlchemy 2.0 & asyncpg** (Asynchronous connection pooling, composite indexes, atomic transactions)
- **PostgreSQL 16** (ACID relational persistence in isolated Docker container)
- **Selectolax & Lexbor** (C-based ultra-fast HTML5 fallback parser)
- **Pydantic Settings & Dotenv** (Strict environment schema validation and dynamic proxy routing)
- **Docker & Docker Compose** (Containerized single-command orchestration)

## Quick Start

### 1. Clone Repository & Setup Environment

```bash
git clone https://github.com/HWORK72/Telegram-Monitoring-Bot-For-OLX.git
cd Telegram-Monitoring-Bot-For-OLX
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)

Populate the configuration file located in the project root:

```env
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_IDS=123456789

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433
POSTGRES_DB=olx_monitor
DB_ECHO=false

PROXY_URL=http://127.0.0.1:10809

IGNORE_BUMPED_OFFERS=false
IGNORE_PROMOTED_OFFERS=false
MAX_OFFER_AGE_MINUTES=30
BATCH_OUTPUT_LIMIT=12
MAX_PER_CATEGORY_PER_BATCH=2

MAX_CONCURRENT_CHECKS=5
POLL_INTERVAL_SECONDS=60
POLL_JITTER_SECONDS=5
REQUEST_TIMEOUT=15
CURL_IMPERSONATE=chrome120
LOG_LEVEL=INFO
```

### 3. Standalone Execution (Local Host)

Launch the containerized PostgreSQL database:

```bash
docker compose up postgres -d
```

Run the application orchestrator directly via terminal:

```bash
python main.py
```

### 4. Full Containerized Stack Deployment

Deploy both PostgreSQL and the autonomous background monitor inside Docker:

```bash
docker compose up --build -d
```

## License

MIT License. Designed and maintained by [HWORK72](https://github.com/HWORK72).
