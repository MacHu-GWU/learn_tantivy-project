"""
s02_search.py - Search the tantivy index by title using ngram queries.

Run: .venv/bin/python examples/s02_search.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import tantivy

from shared import ANALYZER_NAME, INDEX_DIR, build_ngram_analyzer

if TYPE_CHECKING:
    # HitResult 只用于类型注解，from __future__ import annotations 使其在运行时不被求值
    # 因此可以放在 TYPE_CHECKING 块里，避免运行时 import shared 时的循环或额外开销
    from shared import HitResult


def open_index() -> tantivy.Index:
    # Index.open() 从磁盘加载已有索引，路径必须包含之前 commit() 生成的文件
    index = tantivy.Index.open(str(INDEX_DIR))
    # 每次打开索引都需要重新注册 analyzer，tantivy 不持久化 tokenizer 配置
    index.register_tokenizer(ANALYZER_NAME, build_ngram_analyzer())
    return index


def search(index: tantivy.Index, query_str: str, top_k: int = 5) -> list[HitResult]:
    # searcher() 获取当前索引快照的只读搜索器（不受后续写入影响）
    searcher: tantivy.Searcher = index.searcher()
    # parse_query 将字符串解析为 Query 对象；第二个参数限定搜索的字段列表
    query: tantivy.Query = index.parse_query(query_str, ["title"])
    # search() 返回 SearchResult，limit 控制最多返回条数，结果已按 BM25 分数降序排列
    results: tantivy.SearchResult = searcher.search(query, limit=top_k)

    hits: list[HitResult] = []
    # results.hits 是 list[tuple[float, DocAddress]]，已按 score 降序排列
    for score, addr in results.hits:
        # score: float — BM25 相关性分数，越高越相关
        # addr: DocAddress — 文档在索引 segment 内的物理地址（segment_ord + doc_id），
        #        不是业务 ID，只用于从 searcher 取回文档内容，跨 commit 后可能失效
        doc: tantivy.Document = searcher.doc(addr)
        hits.append({
            "score": round(score, 4),
            # doc[field] 返回该字段的值列表（一个文档可含多值），取第一个
            "title": doc["title"][0],
            "url": doc["url"][0],
        })
    return hits


def print_results(query_str: str, hits: list[HitResult]) -> None:
    print(f"\nQuery: {query_str!r}  ({len(hits)} hits)")
    print("-" * 60)
    if not hits:
        print("  (no results)")
    for h in hits:
        print(f"  [{h['score']:.4f}] {h['title']}")
        print(f"           {h['url']}")


def main() -> None:
    index = open_index()

    # Demo queries — these work because ngram 2-6 indexes substrings
    queries = [
        "async",        # partial word match
        "pyt",          # 3-char ngram: matches Python, pytest, etc.
        "fast",         # matches FastAPI, "fast Python"
        "rust",         # matches tantivy (Rust)
        "type",         # matches typing, type hints, type checking
        "search",       # matches multiple search-related docs
        "learn",        # very short, 5-char ngram
        "pandas",       # specific library
    ]

    for q in queries:
        hits = search(index, q)
        print_results(q, hits)


if __name__ == "__main__":
    main()
