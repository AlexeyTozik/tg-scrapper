# tg-scrapper

## Requirements

- Python `3.13`
- [`uv`](https://docs.astral.sh/uv/)

The project is pinned to Python `3.13` via `.python-version` and `pyproject.toml`. `uv run ...` will create or reuse a local `.venv` with Python 3.13 automatically.

## Setup

```bash
uv sync
uv run pre-commit install
```

Create `.env` from the tracked example when you want to use LLM summarization:

```bash
cp .env.example .env
```

## Export Telegram Messages

Set Telegram API credentials:

```bash
export TG_API_ID=...
export TG_API_HASH=...
```

If the session file is not authorized yet, the first run will ask for phone number, login code, and 2FA password if enabled.

Run the exporter:

```bash
uv run python main.py \
  --channel -1002294812084 \
  --session ./session_name.session \
  --out messages.jsonl \
  --state messages.state.json
```

`--channel` accepts a public username, invite link, numeric channel id, or Telegram peer id like `-100...`.

Quick smoke test:

```bash
uv run python main.py \
  --channel -1002294812084 \
  --session ./session_name.session \
  --out /tmp/messages.smoke.jsonl \
  --state /tmp/messages.smoke.state.json \
  --max-messages 1
```

## Build Embeddings

`embed_messages.py` reads `messages.jsonl` and writes embeddings to `message_embeddings.jsonl`.

The script now respects `--model`, `--cache-dir`, and `--offline`. You can point it either at a Hugging Face model id or at a local model directory.

Download and save the model once:

```bash
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small', device='cpu').save('./models/multilingual-e5-small')"
```

Run embedding generation:

```bash
uv run python embed_messages.py \
  --input messages.jsonl \
  --output message_embeddings.jsonl \
  --state message_embeddings.state.json \
  --model ./models/multilingual-e5-small \
  --offline \
  --device cpu
```

Device notes:

- macOS / Apple Silicon: use `--device cpu` or try `--device mps`
- Linux with NVIDIA CUDA: use `--device cuda`

Quick smoke test:

```bash
uv run python embed_messages.py \
  --input messages.jsonl \
  --output /tmp/message_embeddings.smoke.jsonl \
  --state /tmp/message_embeddings.smoke.state.json \
  --model ./models/multilingual-e5-small \
  --offline \
  --device cpu \
  --max-messages 1
```

## Summarize Grouped JSONL

`summarize_jsonl.py` reads grouped JSONL rows such as `days.jsonl` or `threads.jsonl` and writes one summary per top-level row into `*_summary.jsonl`.

Required `.env` keys:

```dotenv
OPENROUTER_API_KEY=
```

OpenRouter example for daily summaries:

```bash
uv run python summarize_jsonl.py \
  --model 'openai/gpt-oss-120b:free' \
  --input-file days.jsonl
```

OpenRouter example for thread summaries:

```bash
uv run python summarize_jsonl.py \
  --model 'openai/gpt-oss-120b:free' \
  --input-file threads.jsonl
```

Custom endpoint example with `--base-url`:

```bash
uv run python summarize_jsonl.py \
  --model 'openai/gpt-oss-120b:free' \
  --base-url https://openrouter.ai/api/v1 \
  --input-file days.jsonl
```

Notes:

- If `--output-file` is omitted, the script writes `<input_stem>_summary.jsonl`, for example `days_summary.jsonl`.
- Resume is enabled by default. If the output file already exists, the script appends only missing keys.
- Use `--overwrite` to rebuild the output file from scratch.
- `--base-url` defaults to `https://openrouter.ai/api/v1`, so you only need to pass it when targeting another compatible endpoint.
- The default prompt template lives in `prompts/summarize_group.txt`.
