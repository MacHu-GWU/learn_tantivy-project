"""Shared variables and helpers for tantivy POC examples."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TypedDict


class HitResult(TypedDict):
    score: float
    title: str
    url: str


# Paths
EXAMPLES_DIR = Path(__file__).parent
DATA_DIR = EXAMPLES_DIR / "data"

URLS_JSON = DATA_DIR / "urls.json"


def reset_index(index_dir: Path) -> None:
    """Delete and recreate the index directory (idempotent reset)."""
    if index_dir.exists():
        shutil.rmtree(index_dir)
        print(f"Deleted existing index at {index_dir}")
    index_dir.mkdir(parents=True)
    print(f"Created fresh index dir at {index_dir}")


def load_urls() -> list[dict[str, str]]:
    """Load URL+title records from data/urls.json."""
    with open(URLS_JSON) as f:
        return json.load(f)
