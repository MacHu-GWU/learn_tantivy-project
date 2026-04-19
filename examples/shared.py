"""Shared variables and helpers for tantivy POC examples."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TypedDict

from tantivy import Filter, TextAnalyzer, TextAnalyzerBuilder, Tokenizer


class HitResult(TypedDict):
    score: float
    title: str
    url: str


# Paths
EXAMPLES_DIR = Path(__file__).parent
DATA_DIR = EXAMPLES_DIR / "data"
INDEX_DIR = EXAMPLES_DIR / ".tantivy_poc"

URLS_JSON = DATA_DIR / "urls.json"

# Ngram config
NGRAM_MIN = 2
NGRAM_MAX = 6
ANALYZER_NAME = "ngram_2_6"


def build_ngram_analyzer() -> TextAnalyzer:
    """构建 ngram analyzer：Tokenizer.ngram 生成子串 token，Filter.lowercase 统一小写。"""
    return (
        TextAnalyzerBuilder(Tokenizer.ngram(min_gram=NGRAM_MIN, max_gram=NGRAM_MAX))
        .filter(Filter.lowercase())
        .build()
    )


def reset_index() -> None:
    """Delete and recreate the index directory (idempotent reset)."""
    if INDEX_DIR.exists():
        shutil.rmtree(INDEX_DIR)
        print(f"Deleted existing index at {INDEX_DIR}")
    INDEX_DIR.mkdir(parents=True)
    print(f"Created fresh index dir at {INDEX_DIR}")


def load_urls() -> list[dict[str, str]]:
    """Load URL+title records from data/urls.json."""
    with open(URLS_JSON) as f:
        return json.load(f)
