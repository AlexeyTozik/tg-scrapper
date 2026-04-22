import json
import os
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv

JsonObject = dict[str, object]
JsonDict = dict[str, Any]
REPO_ROOT = Path(__file__).resolve().parent


def load_repo_dotenv(filename: str = ".env", *, override: bool = True) -> None:
    load_dotenv(dotenv_path=REPO_ROOT / filename, override=override)


def get_first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def ensure_json_object(raw: object, context: str) -> JsonObject:
    if not isinstance(raw, dict):
        raise ValueError(f"{context} is not a JSON object")
    return cast(JsonObject, raw)


def read_jsonl(path: Path) -> list[JsonObject]:
    return [row for _, row in iter_jsonl(path)]


def iter_jsonl(path: Path, skip_lines: int = 0) -> Iterator[tuple[int, JsonObject]]:
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if line_number <= skip_lines:
                continue

            yield line_number, ensure_json_object(json.loads(line), f"Line {line_number} in {path}")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, object]], mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(mode, encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(dict(row), ensure_ascii=False) + "\n")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    _write_jsonl(path, rows, "w")


def append_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    _write_jsonl(path, rows, "a")


def load_json_dict(path: Path) -> JsonDict | None:
    if not path.exists():
        return None

    return cast(JsonDict, ensure_json_object(json.loads(path.read_text(encoding="utf-8")), f"{path}"))


def save_json(path: Path, value: object, *, indent: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=indent), encoding="utf-8")


def get_optional_str(row: Mapping[str, object], key: str) -> str | None:
    value = row.get(key)
    return value if isinstance(value, str) else None


def get_required_str(row: Mapping[str, object], key: str) -> str:
    value = get_optional_str(row, key)
    if value is None or not value:
        raise ValueError(f'Field "{key}" is missing or not a non-empty string')
    return value


def get_optional_int(row: Mapping[str, object], key: str) -> int | None:
    value = row.get(key)
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def get_required_int(row: Mapping[str, object], key: str) -> int:
    value = get_optional_int(row, key)
    if value is None:
        raise ValueError(f'Field "{key}" is missing or not an int')
    return value
