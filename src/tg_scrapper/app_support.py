import json
import os
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv

JsonObject = dict[str, object]
JsonDict = dict[str, Any]


def load_working_dir_dotenv(
    filename: str = ".env",
    *,
    override: bool = True,
    directory: Path | None = None,
) -> None:
    search_dir = directory or Path.cwd()
    load_dotenv(dotenv_path=search_dir / filename, override=override)


def load_repo_dotenv(filename: str = ".env", *, override: bool = True) -> None:
    load_working_dir_dotenv(filename, override=override)


def get_first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _ensure_json_object(raw: object, context: str) -> JsonObject:
    if not isinstance(raw, dict):
        raise ValueError(f"{context} is not a JSON object")
    return cast(JsonObject, raw)


def iter_jsonl(path: Path, skip_lines: int = 0) -> Iterator[tuple[int, JsonObject]]:
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if line_number <= skip_lines:
                continue

            yield line_number, _ensure_json_object(json.loads(line), f"Line {line_number} in {path}")


def append_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(dict(row), ensure_ascii=False) + "\n")


def load_json_dict(path: Path) -> JsonDict | None:
    if not path.exists():
        return None

    return cast(JsonDict, _ensure_json_object(json.loads(path.read_text(encoding="utf-8")), f"{path}"))


def save_json(path: Path, value: object, *, indent: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=indent), encoding="utf-8")


def get_optional_str(row: Mapping[str, object], key: str) -> str | None:
    value = row.get(key)
    return value if isinstance(value, str) else None


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
