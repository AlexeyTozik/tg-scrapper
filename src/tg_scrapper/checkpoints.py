from collections.abc import Mapping
from pathlib import Path

from .app_support import JsonDict, load_json_dict, save_json


def load_checkpoint(path: Path, default: Mapping[str, object]) -> JsonDict:
    state = load_json_dict(path)
    if state is None:
        return dict(default)
    return state


def save_checkpoint(path: Path, value: Mapping[str, object]) -> None:
    save_json(path, dict(value), indent=2)
