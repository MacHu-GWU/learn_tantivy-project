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

    print("=" * 60)
    print("【1】Ngram 子串搜索（正常工作）")
    print("=" * 60)
    # parse_query 用同一个 ngram analyzer 分析 query string，
    # 生成 2-6 字符子串 token，再做 OR 匹配。
    # 只要 query 字符串是某个 title 的子串，就能命中。
    for q in ["async", "pyt", "fast", "rust", "pandas"]:
        print_results(q, search(index, q))

    print()
    print("=" * 60)
    print("【2】完整单词 / 全文搜索（结论：能命中，但机制仍是 ngram）")
    print("=" * 60)
    # 结论：title 字段只注册了 ngram_2_6，没有独立的全文字段。
    # parse_query 用同一个 ngram analyzer 分析 query，
    # "asyncio"（7字符）→ "as","asy","asyn","async","asynci","sy",... 的 OR 查询。
    # 能命中，且由于这些 ngram 只集中在一篇文档里，BM25 分数反而很高（实测 61.39）。
    # "documentation"（13字符）→ 生成大量 ngram，命中 2 篇，分数异常高（99.9 / 96.8），
    # 这是 BM25 在 ngram 字段的副作用：长 query 产生的 token 越多，总分越高。
    # ⚠️  这不是真正的全词匹配：搜"python"也会命中 title 里含"pythonic"/"cpython"的文档，
    # 无法区分"词边界"。若需要精确全词匹配，需额外加 tokenizer_name="default" 的字段。
    for q in ["asyncio", "python", "documentation"]:
        print_results(q, search(index, q))

    print()
    print("=" * 60)
    print("【3】Fuzzy 搜索（结论：在 ngram 字段上完全无效，返回 0 结果）")
    print("=" * 60)
    # tantivy parse_query 支持 Lucene 风格 fuzzy 语法：term~N。
    # ❌ 实测三个 query 全部返回 0 结果，原因分析：
    #
    # parse_query 遇到 "pythn~1" 时，先用 ngram analyzer 分词 →
    # 得到 "py","pyt","pyth","pythn" 这些短 token，再对每个 token 做 fuzzy。
    # tantivy 的 FuzzyTermQuery 要求 term 长度 ≥ min_gram（即 ≥ 2），
    # 但更关键的是：fuzzy 匹配的是索引里已有的 term，而索引里的 term
    # 都是原始 title 的 2-6 字符子串。"pythn"（5字符）做 fuzzy~1 时，
    # 要找编辑距离≤1 的相邻 term，但 tantivy 对 ngram token 的 fuzzy
    # 实现会在词典里做 Levenshtein 自动机搜索 — 这在 ngram 密集的倒排索引里
    # 极大概率因 prefix_len 限制或词典范围问题而找不到匹配项。
    #
    # 核心结论：fuzzy 是为"词级别"索引设计的（一个词 = 一个 token），
    # ngram 把每个字符位置都拆成 token，fuzzy 的语义在这里完全失效。
    # 若要支持拼写容错，ngram 本身已经够用（"pythn" 的子串 "pyt"/"pyth"
    # 直接作为 ngram query 就能命中 python 相关文档）。
    for q in [
        "pythn~1",      # 拼写错误：pythn → python，实测：0 结果（fuzzy 对 ngram 无效）
        "algoritm~1",   # 拼写错误：algoritm → algorithm，实测：0 结果
        "serach~1",     # 拼写错误：serach → search，实测：0 结果
    ]:
        print_results(q, search(index, q))


if __name__ == "__main__":
    main()
