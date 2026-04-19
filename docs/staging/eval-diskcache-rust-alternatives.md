# 评估: diskcache 的 Rust 替代方案

**评估日期:** 2026-04-19  
**场景:** sayt (search as you type) 的 query 结果缓存, 基于 query string 做 key, 搜索结果做 value

---

## 结论 (先说结论)

**不需要替换 diskcache.** 现有 Rust + Python binding 的方案性能优势在 SAYT 这个场景下几乎无法体现, 且引入了更大的依赖复杂度.

---

## 现有 Rust KV 方案盘点

### rocksdict (唯一成熟选项)

- PyPI: `rocksdict`, 最新版 v0.3.29 (2025年12月发布), 积极维护
- 底层: Facebook RocksDB (LSM-tree 引擎), 通过 PyO3 绑定
- API: 类 dict 接口, 支持 Pickle 序列化任意 Python 对象
- 预编译 wheels: macOS/Linux/Windows, x86-64 和 ARM64 均有
- **问题**: RocksDB 是重量级依赖, 部署复杂度远高于 diskcache

### redb

- PyPI: `redb` v0.5.0, 最后更新 2022年8月
- 每周下载量仅 34 次, Python binding 实际已弃坑
- **结论: 不可用**

### sled

- 无可用的 Python binding (PyPI 上的 `sled` 包是无关的 async scheduler)
- sled 与 PyO3 存在 GIL deadlock 问题 (spacejam/sled#1184)
- **结论: 不可用**

---

## 性能分析

### diskcache (SQLite 后端) 实测延迟

| 操作 | 中位数 | P90 |
|------|--------|-----|
| Get  | ~12 µs | ~17 µs |
| Set  | ~69 µs | ~94 µs |

注: 高并发下 Set 的 P99 会飙到 21ms, 但 SAYT 场景是单用户单线程.

### RocksDB vs SQLite 架构对比

| 维度 | SQLite (diskcache) | RocksDB (rocksdict) |
|------|--------------------|---------------------|
| 存储引擎 | B-tree | LSM-tree |
| 写入优势 | 单线程写入快 | 高并发写入快 |
| 读取延迟 | 单线程小 value 很快 | 相当或略慢 (LSM 层级查找) |
| 并发优势 | 差 | 强 |
| 依赖大小 | 极小 (内置 SQLite) | 大 (需要 RocksDB 库) |

### SAYT 场景特征

- **访问模式**: 单用户, 单线程, 小 value (搜索结果 JSON)
- **读多写少**: query cache 命中率高时以读为主
- **并发**: 基本没有

这正好是 SQLite 擅长的场景, RocksDB 的优势完全无法体现.

---

## 瓶颈在哪里?

在 SAYT + Alfred 场景下, 真正的延迟来源:

1. **Python 进程冷启动** (~40-400ms, 视调用方式)
2. **tantivy index 加载** (首次打开, 通常 <10ms)
3. **搜索本身** (<1ms)
4. **diskcache 读取** (~12 µs)

diskcache 的 12 µs 读取延迟在整个链路里微不足道. 替换它对用户体验零影响.

---

## 最终建议

| 场景 | 建议 |
|------|------|
| 当前 SAYT 缓存 | 保持 diskcache, 无需替换 |
| 如果将来有高并发写入需求 | 考虑 rocksdict |
| 如果想减少依赖 | 可以考虑直接用 sqlite3 标准库替代 diskcache |

**替换 diskcache 的唯一合理理由**: 如果场景变成多进程并发写入, 且 diskcache 的 SQLite 锁竞争成为瓶颈. 当前 SAYT 场景不存在这个问题.
