tantivy POC — Ngram 搜索验证
==============================

目标
----

验证 tantivy（Rust 全文搜索引擎的 Python binding）能否用 **Ngram（2-6字符）**
对中短文本做子串搜索，作为替换 Whoosh 的前置评估。

目录结构
--------

::

    examples/
    ├── data/
    │   └── urls.json          # 测试数据：30 条 URL + Title
    ├── .tantivy_poc/          # 索引存储目录（运行后自动生成，dot 开头不进 git）
    ├── shared.py              # 共享常量、helper、TypedDict
    ├── s01_index.py           # 建索引
    ├── s02_search.py          # 搜索演示
    └── README.rst             # 本文件

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

因此搜索 ``"async"``（5字符）、``"pyt"``（3字符）、``"ru"``（2字符）
均可命中相应文档，**无需输入完整词**。

运行方式
--------

.. code-block:: bash

    cd examples

    # 第一步：建索引（幂等，会先清空旧索引）
    ../.venv/bin/python s01_index.py

    # 第二步：搜索演示
    ../.venv/bin/python s02_search.py

搜索结果按 BM25 分数降序排列，分数越高越相关。

关键设计决策
------------

1. **Analyzer 不持久化**：tantivy 只持久化倒排索引文件，不保存 tokenizer 配置。
   每次 ``Index.open()`` 之后都必须重新调用 ``register_tokenizer()``，
   否则搜索时无法正确解析 query（``shared.build_ngram_analyzer()`` 统一管理）。

2. **DocAddress 不是业务 ID**：``results.hits`` 返回的 ``addr`` 是
   ``(segment_ord, doc_id)`` 组合，指向文档在索引内部的物理位置，
   只能在同一个 ``Searcher`` 快照内用 ``searcher.doc(addr)`` 取回内容，
   跨 commit 后不保证有效。

3. **``from __future__ import annotations`` + ``TYPE_CHECKING``**：
   ``HitResult`` TypedDict 只出现在函数签名注解里，在 ``s02_search.py``
   中放入 ``if TYPE_CHECKING:`` 块，运行时零开销。
