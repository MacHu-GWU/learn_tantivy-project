"""
s01_01_index.py — 实验组 S01：Ngram Only
建索引：title 字段仅用 ngram(2-6) tokenizer，不添加全文或 fuzzy 字段。

Run: ../../.venv/bin/python s01_01_index.py
"""

from __future__ import annotations

import tantivy
from tantivy import Filter, TextAnalyzer, TextAnalyzerBuilder, Tokenizer

from shared import EXAMPLES_DIR, load_urls, reset_index

# ── Ngram analyzer 配置（S01 专属） ─────────────────────────────────────────
NGRAM_MIN = 2
NGRAM_MAX = 6
ANALYZER_NAME = "ngram_2_6"

# S01 独立的索引目录，与其他实验组互不干扰
INDEX_DIR = EXAMPLES_DIR / ".tantivy_index_s01_ngram_only"


def build_ngram_analyzer() -> TextAnalyzer:
    """构建 ngram analyzer：Tokenizer.ngram 生成子串 token，Filter.lowercase 统一小写。"""
    return (
        TextAnalyzerBuilder(Tokenizer.ngram(min_gram=NGRAM_MIN, max_gram=NGRAM_MAX))
        .filter(Filter.lowercase())
        .build()
    )


def build_schema() -> tantivy.Schema:
    builder = tantivy.SchemaBuilder()
    # title 字段：用自定义 ngram analyzer 索引，stored=True 使其可从搜索结果还原
    builder.add_text_field("title", stored=True, tokenizer_name=ANALYZER_NAME)
    # url 字段：tokenizer_name="raw" 表示整体作为一个 token，不分词，仅存储
    builder.add_text_field("url", stored=True, tokenizer_name="raw")
    return builder.build()


def build_index() -> tantivy.Index:
    """建索引并返回 Index 对象（供测试或其他脚本复用）。"""
    reset_index(INDEX_DIR)

    schema = build_schema()
    index = tantivy.Index(schema, path=str(INDEX_DIR))
    # 将 analyzer 注册到 index，名称必须与 schema 里 tokenizer_name 一致
    index.register_tokenizer(ANALYZER_NAME, build_ngram_analyzer())

    writer = index.writer()
    docs = load_urls()
    for doc in docs:
        writer.add_document(tantivy.Document(
            title=doc["title"],
            url=doc["url"],
        ))
    writer.commit()
    writer.wait_merging_threads()

    print(f"\nIndexed {len(docs)} documents into {INDEX_DIR}")
    print(f"Ngram range: {NGRAM_MIN}-{NGRAM_MAX} characters")
    return index


def main() -> None:
    build_index()

    # 演示：对样本标题跑一遍 analyzer，直接观察生成的 ngram token
    docs = load_urls()
    sample = docs[0]["title"]
    tokens = build_ngram_analyzer().analyze(sample)
    print(f"\nSample title: {sample!r}")
    print(f"First 20 ngram tokens: {tokens[:20]}")


if __name__ == "__main__":
    main()
