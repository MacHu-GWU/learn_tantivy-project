"""
s01_02_search.py — 实验组 S01：Ngram Only
搜索演示：验证 ngram 子串搜索、全词搜索、fuzzy 搜索三种模式的实测行为。

Run: ../../.venv/bin/python s01_02_search.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import tantivy

# analyzer 配置与 INDEX_DIR 都由 s01_01_index 持有，此处直接 import
from s01_01_index import ANALYZER_NAME, INDEX_DIR, build_ngram_analyzer

if TYPE_CHECKING:
    from shared import HitResult


def open_index() -> tantivy.Index:
    # Index.open() 从磁盘加载已有索引，路径必须包含之前 commit() 生成的文件
    index = tantivy.Index.open(str(INDEX_DIR))
    # tantivy 不持久化 tokenizer 配置，每次 open 后必须重新注册
    index.register_tokenizer(ANALYZER_NAME, build_ngram_analyzer())
    return index


def search(index: tantivy.Index, query_str: str, top_k: int = 5) -> list[HitResult]:
    searcher: tantivy.Searcher = index.searcher()
    query: tantivy.Query = index.parse_query(query_str, ["title"])
    results: tantivy.SearchResult = searcher.search(query, limit=top_k)

    hits: list[HitResult] = []
    for score, addr in results.hits:
        doc: tantivy.Document = searcher.doc(addr)
        hits.append({
            "score": round(score, 4),
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

    print("=" * 60)
    print("【1】Ngram 子串搜索（✅ 正常工作）")
    print("=" * 60)
    # parse_query 用同一个 ngram analyzer 分析 query string，
    # 生成 2-6 字符子串 token，再做 OR 匹配。
    # 只要 query 字符串是某个 title 的子串，就能命中。
    for q in ["async", "pyt", "fast", "rust", "pandas"]:
        print_results(q, search(index, q))

    print()
    print("=" * 60)
    print("【2】完整单词 / 全文搜索（⚠️ 能命中，但机制仍是 ngram）")
    print("=" * 60)
    # 结论：title 字段只注册了 ngram_2_6，没有独立的全文字段。
    # parse_query 用同一个 ngram analyzer 分析 query，
    # "asyncio"（7字符）→ "as","asy","asyn","async","asynci","sy",... 的 OR 查询。
    # 能命中，且由于这些 ngram 只集中在一篇文档里，BM25 分数反而很高（实测 61.39）。
    # ⚠️  无词边界感知：搜"python"也会命中含"pythonic"/"cpython"的文档。
    for q in ["asyncio", "python", "documentation"]:
        print_results(q, search(index, q))

    print()
    print("=" * 60)
    print("【3】Fuzzy 搜索（❌ 在纯 ngram 字段上完全无效，返回 0 结果）")
    print("=" * 60)
    # parse_query 遇到 "pythn~1" 时，先用 ngram analyzer 分词，
    # 得到 "py","pyt","pyth","pythn" 这些短 token，再对每个 token 做 fuzzy。
    # fuzzy 是为"词级别"索引设计的，ngram 把每个字符位置都拆成 token，
    # fuzzy 的语义在这里完全失效 → 实测三个 query 均返回 0 结果。
    # ngram 本身已覆盖拼写容错（"pythn" 的子串 "pyt"/"pyth" 直接命中），
    # 无需也不应在 ngram 字段上叠加 fuzzy。
    for q in [
        "pythn~1",      # 拼写错误：pythn → python
        "algoritm~1",   # 拼写错误：algoritm → algorithm
        "serach~1",     # 拼写错误：serach → search
    ]:
        print_results(q, search(index, q))


if __name__ == "__main__":
    main()
