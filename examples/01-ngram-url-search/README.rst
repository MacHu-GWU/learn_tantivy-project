tantivy POC — Ngram URL 标题搜索
==================================

目标
----

验证 tantivy（Rust 全文搜索引擎的 Python binding）能否用 **Ngram（2-6字符）**
对中短文本做子串搜索，并摸清 ngram 字段上全词搜索与 fuzzy 搜索的边界，
作为替换 Whoosh 的前置评估。

目录结构
--------

::

    01-ngram-url-search/
    ├── data/
    │   └── urls.json                        # 测试数据：30 条 URL + Title（各组复用）
    ├── shared.py                            # 通用 helper：路径、load_urls()、HitResult、reset_index()
    │
    ├── s01_01_index.py                      # [S01] 建索引：纯 ngram(2-6) 模式
    ├── s01_02_search.py                     # [S01] 搜索演示：ngram 子串 / 全词 / fuzzy 三种模式
    ├── .tantivy_index_s01_ngram_only/       # [S01] 索引目录（运行后自动生成，dot 开头不进 git）
    │
    └── README.rst                           # 本文件

测试数据长什么样
----------------

``data/urls.json`` 是一个 JSON 数组，每条记录只有两个字段::

    [
      {
        "url": "https://docs.python.org/3/library/asyncio.html",
        "title": "asyncio - Asynchronous I/O"
      },
      ...
    ]

共 30 条，覆盖 Python 标准库、常用框架（FastAPI、SQLAlchemy）、工具链（uv、ruff、mypy）、
搜索引擎（tantivy、Whoosh、Lucene、Elasticsearch）、数据科学（NumPy、pandas、sklearn）等话题，
目的是让 ngram 搜索在各种前缀/子串场景下都有可验证的命中。

索引结构
--------

Schema 只有两个字段：

============  ==============  ============================================
字段           tokenizer       说明
============  ==============  ============================================
``title``     ``ngram_2_6``   用 ngram 分词，stored=True，支持子串搜索
``url``       ``raw``         整体作为一个 token，仅存储，不参与搜索
============  ==============  ============================================

Ngram 原理
----------

``Tokenizer.ngram(min_gram=2, max_gram=6)`` 会把每个字符位置上、
长度在 [2, 6] 之间的所有子串都作为独立 token 写入倒排索引。

以标题 ``"asyncio - Asynchronous I/O"`` 为例，前 20 个 token::

    'as', 'asy', 'asyn', 'async', 'asynci',
    'sy', 'syn', 'sync', 'synci', 'syncio',
    'yn', 'ync', 'ynci', 'yncio', ...

因此搜索 ``"async"``（5字符）、``"pyt"``（3字符）均可命中，**无需输入完整词**。

运行方式
--------

.. code-block:: bash

    cd examples/01-ngram-url-search

    # S01 — 纯 ngram 模式
    # 第一步：建索引（幂等，会先清空旧索引）
    ../../.venv/bin/python s01_01_index.py

    # 第二步：搜索演示（含三种模式验证）
    ../../.venv/bin/python s01_02_search.py

搜索结果按 BM25 分数降序排列，分数越高越相关。

三种搜索模式的实测结论
----------------------

**1. Ngram 子串搜索（✅ 正常工作）**

query 经过同一个 ngram analyzer 分词后做 OR 匹配，任何 ≥2 字符的子串都能命中。
这是本 example 的核心用途。

**2. 完整单词搜索（⚠️ 能命中，但机制仍是 ngram）**

- 搜 ``"asyncio"``（7字符）：parse_query 把它拆成大量 2-6 字符 ngram 再做 OR，
  因这些 ngram 高度集中在一篇文档里，BM25 分数反而很高（实测 61.39）。
- 搜 ``"documentation"``（13字符）：ngram 数量更多，分数异常高（实测 99.9 / 96.8），
  这是 BM25 在 ngram 字段的副作用——query 越长，累积 token 分数越高。
- **无词边界感知**：搜 ``"python"`` 同样命中含 ``"cpython"`` 或 ``"pythonic"`` 的文档。
- 若需要精确全词匹配，需额外加 ``tokenizer_name="default"`` 的字段。

**3. Fuzzy 搜索（❌ 在 ngram 字段上完全无效，返回 0 结果）**

- tantivy parse_query 支持 ``term~N`` 语法，但 fuzzy 作用于"索引里的 term"。
- ngram 字段的 term 都是 2-6 字符片段；``"pythn~1"`` 会先被 ngram 分词再对
  每个短 token 做 Levenshtein 自动机搜索，因 prefix_len 限制等原因找不到匹配。
- 实测 ``pythn~1``、``algoritm~1``、``serach~1`` 均返回 0 结果。
- ngram 本身已覆盖拼写容错（``"pythn"`` 的子串 ``"pyt"``/``"pyth"`` 直接命中），
  **无需也不应在 ngram 字段上叠加 fuzzy**。

关键设计决策
------------

1. **Analyzer 不持久化，但重建几乎零开销**：tantivy 只持久化倒排索引数据，
   不保存 tokenizer 配置。每次 ``Index.open()`` 后必须重新 ``register_tokenizer()``。
   实测 ``build_ngram_analyzer()`` 单次耗时 **0.34 µs**（``Index.open()`` 是 180 µs，
   Python 进程启动是 50–100 ms），完全不需要优化。

2. **DocAddress 不是业务 ID**：``results.hits`` 里的 ``addr`` 是
   ``(segment_ord, doc_id)`` 的物理地址，只在同一 ``Searcher`` 快照内有效，
   跨 commit 后不保证可用。

3. **``TYPE_CHECKING`` 用于零开销注解**：``HitResult`` TypedDict 只出现在函数签名里，
   配合 ``from __future__ import annotations`` 放入 ``if TYPE_CHECKING:`` 块，
   运行时不 import，零开销。
