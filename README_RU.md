# Telegram Monitoring Bot For OLX

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Aiogram 3.x](https://img.shields.io/badge/Aiogram-3.x-2CA5E0?style=flat&logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![SQLAlchemy 2.0](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=flat)](https://www.sqlalchemy.org/)
[![curl_cffi](https://img.shields.io/badge/curl__cffi-Chrome120-success?style=flat)](https://github.com/yifeikong/curl_cffi)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

[🇺🇸 Read in English](README.md)

Высокопроизводительный асинхронный сервис мониторинга и лидогенерации объявлений на платформе OLX (поддержка Румынии, Казахстана, Украины, Польши) с мгновенной доставкой уведомлений в Telegram.

Система спроектирована под высокие нагрузки с надежным обходом антифрод-систем AWS WAF и CloudFront, эмуляцией браузерных отпечатков TLS/JA4, сбором через нативный Mobile REST API, дедупликацией на уровне PostgreSQL и балансировщиком категорий по квотам.

## Ключевые архитектурные особенности

- **Сбор через Mobile REST API**: Прямое чтение внутренних мобильных эндпоинтов (`/api/v1/offers/`) исключает накладные расходы на рендеринг тяжелого SSR HTML/DOM, выполняя опрос каталогов за 40 миллисекунд.
- **Обход AWS WAF и CloudFront**: Эмуляция параметров TLS ClientHello, мультиплексирования HTTP/2 и отпечатков JA4 браузеров Chrome 120/124 через `curl_cffi` без блокировок со стороны CDN.
- **Балансировщик категорий (Lead Multiplexer)**: Автоматическая группировка входящего потока по нишам (Автозапчасти, Недвижимость, Электроника, Мода, Спорт, Услуги) с раундовым распределением квот, исключающим перекос ленты в одну категорию.
- **Математическая формула свежести**: Вычисление дельты между временем создания и временем обновления (`bump_delta <= 120s`) и жесткое окно жизни лота (`age <= 30 мин`) отсекают 100% платных коммерческих бампов и поднятий.
- **Раскрытие номеров On-Demand**: Защита от часовых лимитов OLX (6-8 номеров на IP) через интерактивные инлайн-кнопки. Номер запрашивается только при клике пользователя и намертво кэшируется в PostgreSQL (повторные вызовы тратят 0 запросов к OLX).
- **Оригинальные фото Apollo CDN**: Извлечение чистых полноразмерных ссылок CDN без суррогатных параметров масштабирования с двухуровневым fallback на текстовые карточки при задержках Telegram.
- **Транзакционная дедупликация**: Составные B-Tree индексы `(link_id, olx_offer_id)` в PostgreSQL с конструкцией `ON CONFLICT DO NOTHING` гарантируют выборку за O(log N) и отсутствие дублей.
- **Конкурентный чекер с семафором**: Параллельная обработка десятков ссылок через `asyncio.Semaphore` и рандомизированный джиттер без блокировок основного event loop.

## Стек технологий

- **Python 3.12** (Строгая типизация, стандарты PEP 8, асинхронность)
- **Aiogram 3.x** (Асинхронный Telegram UI, FSM, кастомные инлайн-клавиатуры)
- **curl_cffi** (HTTP/2, TLS 1.3, эмуляция браузерных отпечатков Chrome JA4)
- **SQLAlchemy 2.0 & asyncpg** (Асинхронный пул подключений, транзакции, индексы)
- **PostgreSQL 16** (Реляционная база данных в изолированном Docker-контейнере)
- **Selectolax & Lexbor** (Высокоскоростной си-парсер резервного HTML5 DOM)
- **Pydantic Settings & Dotenv** (Валидация переменных окружения и адаптивная маршрутизация прокси)
- **Docker & Docker Compose** (Контейнеризация и оркестрация полного стека одной командой)

## Быстрый старт

### 1. Клонирование и настройка окружения

```bash
git clone https://github.com/HWORK72/Telegram-Monitoring-Bot-For-OLX.git
cd Telegram-Monitoring-Bot-For-OLX
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Настройка файла переменных (`.env`)

Заполни файл `.env` в корне проекта следующими параметрами:

```env
BOT_TOKEN=твой_telegram_токен
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

### 3. Локальный запуск (Разработка)

Запусти контейнер PostgreSQL:

```bash
docker compose up postgres -d
```

Запусти приложение напрямую из терминала:

```bash
python main.py
```

### 4. Развертывание полного стека в Docker

Запусти базу данных и автономный бот в изолированных контейнерах одной командой:

```bash
docker compose up --build -d
```

## Лицензия

MIT License. Разработано и поддерживается [HWORK72](https://github.com/HWORK72).
