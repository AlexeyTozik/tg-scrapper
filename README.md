# tg-scrapper

Локальный CLI-пайплайн для Telegram:

`export messages -> embeddings -> ChromaDB -> RAG answer`

Эмбеддинги и индекс строятся локально. Внешний вызов нужен только для LLM-ответа через OpenRouter.

## Requirements

- Python `3.13`
- [`uv`](https://docs.astral.sh/uv/)
- Telegram API credentials: `TG_API_ID`, `TG_API_HASH`
- OpenRouter API key: `OPENROUTER_API_KEY`

`uv sync` сам подберет нужные `torch` wheels под платформу.

## Setup

```bash
uv sync
cp .env.example .env
```

Заполни `.env`:

```env
OPENROUTER_API_KEY=sk-or-v1-...
TG_API_ID=...
TG_API_HASH=...
```

`.env` в корне репозитория подхватывается автоматически. Можно использовать и shell env.

## Реальный пример канала

Канал из текущей сессии:

- `Talos Linux/Sidero Metal - русскоговорящее сообщество`
- `entity.id=1946286109`
- `peer_id=-1001946286109`

Пример строки из `get_channels.py`:

```text
Talos Linux/Sidero Metal - русскоговорящее сообщество | entity.id=1946286109 | peer_id=-1001946286109
```

Для него в README ниже используются такие пути:

- export: `exports/talos_linux_sidero_ru.jsonl`
- export state: `exports/talos_linux_sidero_ru.state.json`
- embeddings: `exports/talos_linux_sidero_ru.embeddings.jsonl`
- embeddings state: `exports/talos_linux_sidero_ru.embed.state.json`

## Быстрый запуск

Посмотреть доступные каналы:

```bash
uv run python get_channels.py --session ./session_name.session
```

Полный прогон на реальном канале:

```bash
# 1. Выгрузить сообщения
uv run python main.py \
  --channel -1001946286109 \
  --session ./session_name.session \
  --out exports/talos_linux_sidero_ru.jsonl \
  --state exports/talos_linux_sidero_ru.state.json

# 2. Скачать embedding model один раз
uv run python -c "from sentence_transformers import SentenceTransformer; \
  SentenceTransformer('intfloat/multilingual-e5-small', device='cpu') \
    .save('./models/multilingual-e5-small')"

# 3. Посчитать embeddings
uv run python embed_messages.py \
  --input exports/talos_linux_sidero_ru.jsonl \
  --output exports/talos_linux_sidero_ru.embeddings.jsonl \
  --state exports/talos_linux_sidero_ru.embed.state.json \
  --model ./models/multilingual-e5-small --offline --device cpu

# 4. Собрать индекс
uv run python index_messages.py \
  --input 'exports/*.embeddings.jsonl' \
  --chroma-path ./chroma_db

# 5. Задать вопрос
uv run python rag_query.py \
  --question "Какие лучшие практики по Talos Linux и обновлению кластера?" \
  --chroma-path ./chroma_db \
  --chat-ids -1001946286109 \
  --model ./models/multilingual-e5-small --offline --device auto
```

Ответ печатается в stdout и сохраняется в `answers/DD-MM-YYYY-HH-MM-SS.md`.

## Полезные замечания

- `main.py` можно запускать повторно с тем же `--state`: выгрузка продолжится с последнего `id`.
- `main.py` уже настроен на быстрый bulk-export по умолчанию: larger batches, no artificial sleeps, takeout with safe fallback.
- Для быстрого теста можно добавить `--max-messages 1000`.
- `embed_messages.py` и `index_messages.py` используют один и тот же фильтр шума.
- Жестко отбрасываются service messages, пустые/media-only записи и emoji/punctuation-only сообщения.
- Короткие техсообщения и короткие reply-сообщения сохраняются по эвристикам, даже если они короче `--min-chars`.
- Для macOS обычно достаточно `--device cpu` или `--device mps`, для Linux с NVIDIA - `--device cuda`.

## Основные файлы

- `main.py` - экспорт сообщений из Telegram через Telethon
- `get_channels.py` - список каналов и групп в текущей сессии
- `embed_messages.py` - расчет embeddings
- `index_messages.py` - загрузка embeddings в ChromaDB
- `rag_query.py` - поиск по индексу и генерация ответа
- `prompts/` - prompt templates для расширения запроса и финального ответа

Артефакты пишутся в `exports/`, `models/`, `chroma_db/`, `answers/` и `*.state.json`.

## Проверки

```bash
uv run python -m unittest discover tests
uv run ruff check .
uv run mypy .
```
