"""
s01_index.py - Build the tantivy index with ngram (2-6) on title field.

Run: .venv/bin/python examples/s01_index.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import tantivy

from shared import ANALYZER_NAME, INDEX_DIR, NGRAM_MAX, NGRAM_MIN, build_ngram_analyzer, load_urls, reset_index

if TYPE_CHECKING:
    pass  # tantivy 在运行时已导入，此处无需额外的类型专用 import


def build_schema() -> tantivy.Schema:
    # 创建 Schema 构造器，tantivy 要求先声明所有字段才能建索引
    builder = tantivy.SchemaBuilder()
    # title 字段：用自定义 ngram analyzer 索引，stored=True 使其可从搜索结果还原
    builder.add_text_field("title", stored=True, tokenizer_name=ANALYZER_NAME)
    # url 字段：tokenizer_name="raw" 表示整体作为一个 token，不分词，仅存储
    builder.add_text_field("url", stored=True, tokenizer_name="raw")
    # 构建并返回最终不可变的 Schema 对象
    return builder.build()


def register_ngram_analyzer(index: tantivy.Index) -> None:
    """Register the ngram tokenizer on the index's tokenizer manager."""
    # 将 analyzer 注册到 index，名称必须与 schema 里 tokenizer_name 一致
    index.register_tokenizer(ANALYZER_NAME, build_ngram_analyzer())


def main() -> None:
    reset_index()

    schema = build_schema()
    # 用 Schema 和磁盘路径创建 Index；路径不存在会报错，reset_index() 已确保目录存在
    index = tantivy.Index(schema, path=str(INDEX_DIR))
    register_ngram_analyzer(index)

    # writer() 返回 IndexWriter，负责写入和提交文档
    writer = index.writer()

    docs = load_urls()
    for doc in docs:
        # 每次 add_document 将文档加入内存缓冲区，尚未落盘
        writer.add_document(tantivy.Document(
            title=doc["title"],
            url=doc["url"],
        ))

    # commit() 将内存缓冲区的文档刷写到磁盘，形成新的 segment
    writer.commit()
    # wait_merging_threads() 等待后台 segment 合并完成，确保索引一致性
    writer.wait_merging_threads()

    print(f"\nIndexed {len(docs)} documents into {INDEX_DIR}")
    print(f"Ngram range: {NGRAM_MIN}-{NGRAM_MAX} characters")

    # 演示：对样本标题跑一遍 analyzer，直接观察生成的 ngram token
    sample = docs[0]["title"]
    # analyze() 返回该文本经过 tokenizer + filters 后的 token 列表
    tokens = build_ngram_analyzer().analyze(sample)
    print(f"\nSample title: {sample!r}")
    print(f"First 20 ngram tokens: {tokens[:20]}")


if __name__ == "__main__":
    main()
