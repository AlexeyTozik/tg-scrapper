# tg-scrapper

Локальный Telegram RAG pipeline:

`export -> embeddings -> ChromaDB -> OpenRouter answer`

## Быстрый Старт

```bash
make install
cp .env.example .env
```

Заполни `.env`:

```env
OPENROUTER_API_KEY=sk-or-v1-...
TG_API_ID=...
TG_API_HASH=...
```

Основной сценарий:

```bash
make channels
make export CHANNEL=-1001946286109
make model
make embed
make index
make query "Что обсуждали про Talos?"
```

Повторные `export`, `embed` и `index` продолжают с checkpoint-файлов, а не делают всё заново.

## Настройки

```bash
make export CHANNEL=-1001946286109 SESSION=./session_name.session
make query Q="Что обсуждали про обновление Talos?"
make embed DEVICE=mps
```

Основные артефакты локальные и игнорируются Git: `exports/`, `models/`, `chroma_db/`, `answers/`, `*.state.json`.

## CLI

```bash
tg-scrapper channels --session ./session_name.session
tg-scrapper export --channel -1001946286109 --session ./session_name.session --out exports/talos_linux_sidero_ru.jsonl --state exports/talos_linux_sidero_ru.state.json
tg-scrapper embed --input exports/talos_linux_sidero_ru.jsonl --output exports/talos_linux_sidero_ru.embeddings.jsonl --state exports/talos_linux_sidero_ru.embed.state.json --model ./models/multilingual-e5-small --offline
tg-scrapper index --input exports/talos_linux_sidero_ru.embeddings.jsonl --chroma-path ./chroma_db
tg-scrapper query --question "Что обсуждали про Talos?" --chroma-path ./chroma_db --chat-ids -1001946286109 --model ./models/multilingual-e5-small --offline
```

## Проверки

```bash
make test
```

Код пакета находится в `src/tg_scrapper/`, тесты - в `tests/`.
