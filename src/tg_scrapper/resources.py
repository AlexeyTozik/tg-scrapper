from importlib.resources import files
from pathlib import Path


def get_packaged_prompt_text(filename: str) -> str:
    return files("tg_scrapper.prompts").joinpath(filename).read_text(encoding="utf-8")


def read_prompt_text(path: str | None, *, default_filename: str) -> str:
    if path is None:
        return get_packaged_prompt_text(default_filename)
    return Path(path).read_text(encoding="utf-8")
