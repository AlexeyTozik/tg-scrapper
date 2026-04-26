SHELL := /bin/sh
.DEFAULT_GOAL := help

CHANNEL ?= -1001946286109
SESSION ?= ./session_name.session
EXPORT ?= exports/talos_linux_sidero_ru.jsonl
EXPORT_STATE ?= exports/talos_linux_sidero_ru.state.json
EMBEDDINGS ?= exports/talos_linux_sidero_ru.embeddings.jsonl
EMBED_STATE ?= exports/talos_linux_sidero_ru.embed.state.json
INDEX_STATE ?= exports/talos_linux_sidero_ru.index.state.json
CHROMA ?= ./chroma_db
MODEL ?= ./models/multilingual-e5-small
DEVICE ?= cpu
QUERY_ARGS := $(strip $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS)))
Q ?= $(if $(QUERY_ARGS),$(QUERY_ARGS),Что обсуждали про Talos?)

.PHONY: help install channels export embed index query test model

help:
	@printf '%s\n' \
		'Commands:' \
		'  make install' \
		'  make channels' \
		'  make export CHANNEL=-1001946286109' \
		'  make model' \
		'  make embed' \
		'  make index' \
		'  make query "Что обсуждали про Talos?"' \
		'  make query Q="Что обсуждали про Talos?"' \
		'  make test' \
		'' \
		'Useful overrides:' \
		'  CHANNEL SESSION EXPORT EMBEDDINGS CHROMA MODEL DEVICE Q'

install:
	uv sync
	uv run tg-scrapper --help >/dev/null

channels:
	uv run tg-scrapper channels --session "$(SESSION)"

export:
	uv run tg-scrapper export \
		--channel "$(CHANNEL)" \
		--session "$(SESSION)" \
		--out "$(EXPORT)" \
		--state "$(EXPORT_STATE)"

model:
	uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small', device='cpu').save('$(MODEL)')"

embed:
	uv run tg-scrapper embed \
		--input "$(EXPORT)" \
		--output "$(EMBEDDINGS)" \
		--state "$(EMBED_STATE)" \
		--model "$(MODEL)" \
		--offline \
		--device "$(DEVICE)"

index:
	uv run tg-scrapper index \
		--input "$(EMBEDDINGS)" \
		--chroma-path "$(CHROMA)" \
		--state "$(INDEX_STATE)"

query:
	uv run tg-scrapper query \
		--question "$(Q)" \
		--chroma-path "$(CHROMA)" \
		--chat-ids "$(CHANNEL)" \
		--model "$(MODEL)" \
		--offline \
		--device auto

test:
	uv run pre-commit run --all-files
	uv run python -m unittest discover tests

%:
	@:
