# 评估: Alfred Script Filter 冷启动问题

**评估日期:** 2026-04-19  
**场景:** Alfred Script Filter 使用 `uvx ${package_name} --query {query}` 调用 sayt 搜索

---

## 结论 (先说结论)

**当前 `uvx` 方式对普通打字速度是边界可用, 但用固定 venv 直接调用可以低成本解决冷启动问题, 不需要上 daemon 方案.**

---

## 各调用方式冷启动延迟

| 调用方式 | 冷启动延迟 | 说明 |
|----------|------------|------|
| `uvx pkg --query ...` | 150–400ms | uv 需要解析 tool env, 即使已缓存也有 resolution 开销 |
| `uv run --no-sync pkg` | 80–200ms | 跳过 sync, 节省 50–100ms |
| `/path/to/.venv/bin/tool --query ...` | 40–80ms | 仅 Python 解释器启动, 无 uv 开销 |
| 本地 HTTP daemon (curl) | <5ms | 进程常驻, 索引常驻内存 |

---

## Alfred Script Filter 的行为机制

- Alfred **不做 debounce**: 每次按键都触发新的 Script Filter 调用
- 如果上一个脚本还在运行, Alfred 会**取消/忽略**旧的调用并启动新的
- 没有可配置的最小触发间隔

---

## 人类打字速度 vs 冷启动延迟

| 打字速度 | 按键间隔 | uvx 延迟 | 体验 |
|----------|----------|---------|------|
| 慢速 (100 WPM 以下) | ~500ms+ | 150–400ms | 可用, 结果有轻微滞后 |
| 中速 (100–150 WPM) | ~200–300ms | 150–400ms | 边界, 偶尔感觉卡顿 |
| 快速 (>150 WPM) | <200ms | 150–400ms | 明显滞后, 结果跟不上打字 |

注: Alfred 的 Script Filter 场景一般是搜索框输入, 用户注意力在结果列表上, 实际打字速度往往偏慢, 多在慢速区间.

---

## 三种优化方案对比

### 方案一: 直接用固定 venv (推荐)

```bash
# Alfred Script Filter 脚本改为:
~/.local/share/alfred-sayt/venv/bin/my-search-tool --query "{query}"
```

- 冷启动 ~40–80ms, 比 uvx 快 3–5x
- 实现零成本: 只需把 Alfred workflow 里的调用路径从 `uvx` 换成 venv 绝对路径
- 缺点: 需要手动管理 venv (用 `uv pip install` 一次性安装), 不像 uvx 那样自动更新

**这个方案对 SAYT + Alfred 场景已经足够.**

### 方案二: 本地 HTTP daemon (最佳体验)

架构:
```
Alfred Script Filter
  → curl http://localhost:PORT/search?q={query}
  → 常驻 Python 进程 (tantivy index 常驻内存)
  → <5ms 返回结果
```

启动方式选项:
- `launchd` plist (macOS 推荐, 开机自启)
- Alfred workflow 的 "Run Script" 节点在搜索前先检查/启动 daemon
- `uvicorn` 或原生 `http.server`

优点:
- 接近零延迟 (<5ms 全程)
- tantivy index 常驻内存, 无每次加载开销
- 支持更复杂的逻辑 (缓存预热、增量更新等)

缺点:
- 实现复杂度显著增加
- 需要管理进程生命周期
- 端口占用, 进程异常需要处理

### 方案三: 保持 uvx 现状

适合场景: 打字速度慢, 对轻微滞后不敏感, 想保持 uvx 的自动更新便利性.

---

## 核心判断

**是否需要优化取决于你的实际体验感受, 而不是理论延迟数字.**

建议验证方式:
1. 在 Alfred 的 Script Filter 里加一个 `date +%s%N` 计时
2. 正常使用 1–2 天, 看是否感到明显卡顿
3. 如果没有卡顿感, uvx 现状即可; 如果有, 先试固定 venv 方案

**优先级建议:**

```
当前感受不卡 → 维持 uvx 现状
当前感受略卡 → 换固定 venv 调用 (10分钟改动)
追求极致体验 → 本地 HTTP daemon
```

---

## 关于 tantivy 替换 whoosh 的影响

tantivy 本身的搜索延迟 (<1ms) 比 whoosh 快一个数量级, 但这不影响冷启动问题 —— 冷启动瓶颈在 **Python 进程启动 + uv 解析**, 不在搜索本身. 换成 tantivy 后搜索更快, 但整体响应时间仍由冷启动主导.
