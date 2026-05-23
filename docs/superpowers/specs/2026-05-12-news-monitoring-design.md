# News Monitoring Design

**Date:** 2026-05-12  
**Status:** Approved

## Problem

trading-os 目前没有新闻数据层。自选池标的分析（elder-screen、canslim-position-monitor、value-position-monitor）和日常工作流日报缺乏新闻背景，无法解释量价异动、无法监控核心假设是否被新公告否定。

## Goals

- **Phase A（本期）**：建立新闻基建层，集成进日常工作流。
- **Phase B（后续）**：在基建层之上加主动推送（微信/Telegram），不在本期实现。

## Non-Goals

- 实时新闻监控后台进程
- 主动推送通知
- 新闻作为硬门控（不因负面新闻自动阻止买入）
- Tushare 新闻（付费 + 额外积分，不引入）

## Architecture

### New Module: `src/trading_os/news/`

```
src/trading_os/news/
    __init__.py       # 导出 get_stock_news, get_market_news, format_news_for_prompt
    models.py         # NewsItem dataclass
    fetcher.py        # AKShare + 财联社 fetch 逻辑
    cache.py          # SQLite 读写，24h TTL
    service.py        # 对外唯一接口
```

缓存文件：`data/news_cache.db`（gitignored）

### Data Flow

```
skill 调用 get_stock_news(symbol)
    → cache.py 检查 news_cache.db
        → 命中（fetched_at >= now_utc - 24h）: 直接返回
        → 未命中: fetcher.py 拉取（strip symbol prefix） → 写入缓存 → 返回
```

## Data Model

```python
@dataclass
class NewsItem:
    symbol: str          # '__MARKET__' = 市场级新闻（财联社电报）
    title: str
    content: str
    source: str          # "eastmoney" | "cls_telegraph"
    pub_time: datetime
    sentiment: str       # "positive" | "negative" | "neutral"
    importance: str      # "high" | "medium" | "low"
    url: str = ""
    fetched_at: datetime = field(default_factory=datetime.now)
```

`symbol` 使用 sentinel `'__MARKET__'` 表示市场级新闻（不能用 `None`，SQLite UNIQUE 索引对 NULL 不去重）。

`sentiment` 和 `importance` 在 fetch 时用关键词词典本地打分，不调 LLM。

## Fetch Layer (`fetcher.py`)

两个独立函数：

```python
def fetch_stock_news(symbol: str, limit: int = 10) -> list[NewsItem]:
    # symbol 必须先从 "SSE:600000" 剥离为 "600000"
    # ak.stock_news_em("600000") — 实际最多返回 10 条（akshare 内部 pageSize=10 硬编码）
    # 失败时静默返回空列表，不抛异常

def fetch_cls_telegraph(limit: int = 20) -> list[NewsItem]:
    # GET https://www.cls.cn/nodeapi/telegraphList — 返回最近 20 条，无日期过滤，无翻页
    # 失败时静默返回空列表（不 fallback 到 ak.news_cctv，CCTV 是电视文字稿，不是金融新闻）
```

数据源：
- **个股新闻**：`ak.stock_news_em`（东方财富），**fetcher 内部必须剥离交易所前缀**（`"SSE:600000"` → `"600000"`）。注意 akshare 对该接口 `pageSize` 硬编码为 10，`limit` 默认值与此对齐。
- **市场新闻**：财联社电报 `cls.cn/nodeapi/telegraphList`，只返回当前最近条目，无历史查询能力。CLS 失败时**不 fallback 到 `ak.news_cctv`**（CCTV 接口返回电视文字稿，不适合金融分析）；直接返回空列表。

Anti-crawl：
- AKShare 沿用项目已有的 User-Agent 风格（参考 `eastmoney_source.py`），失败静默
- 财联社：Browser headers + 30s timeout

## Cache Layer (`cache.py`)

**Schema:**

```sql
CREATE TABLE news_cache (
    id          INTEGER PRIMARY KEY,
    symbol      TEXT    NOT NULL,   -- '__MARKET__' 表示市场级新闻，不用 NULL（NULL 破坏 UNIQUE 去重）
    title       TEXT    NOT NULL,
    content     TEXT,
    source      TEXT,
    pub_time    TEXT,               -- ISO8601 UTC
    sentiment   TEXT,
    importance  TEXT,
    url         TEXT,
    fetched_at  TEXT    NOT NULL    -- ISO8601 UTC with +00:00 suffix，TTL 判断依据
);
CREATE INDEX idx_symbol_fetched ON news_cache(symbol, fetched_at);
CREATE UNIQUE INDEX idx_dedup ON news_cache(symbol, title);
```

**TTL：24 小时。** 判断逻辑：`fetched_at >= (now_utc - 24h)` 则缓存有效，直接返回；否则重新 fetch 并 `INSERT OR REPLACE`。

**注意**：
- `fetched_at` 必须存储为 UTC ISO8601 带时区（`datetime.now(timezone.utc).isoformat()`），与 EventLog 一致，避免 TEXT 比较时时区混用
- SQLite UNIQUE 索引对 NULL 不去重（每个 NULL 视为不同值），市场新闻必须用 `'__MARKET__'` sentinel 而非 NULL

## Public Interface (`service.py`)

```python
def get_stock_news(symbol: str, limit: int = 10) -> list[NewsItem]:
    """给定标的，返回最近新闻（最多 10 条，受 akshare 上限限制）。
    注：ak.stock_news_em 无日期过滤，始终返回当前最新条目。不支持历史查询。"""

def get_market_news(limit: int = 20) -> list[NewsItem]:
    """财联社电报，不绑定标的。返回当前最近条目（无历史查询能力）。"""

def format_news_for_prompt(items: list[NewsItem]) -> str:
    """格式化为 Markdown 供 skill prompt 注入。"""
```

调用方只使用这三个函数，缓存和 fetch 逻辑透明。

## Skill Integration

新闻不改变 skill 的判断框架，只在相关步骤追加"📰 近期新闻"段落供参考。**新闻是 context，不是门控。**

| Skill | 注入位置 | 新闻类型 |
|---|---|---|
| `elder-screen` | "异常量价"判断后，附近 3 天新闻作背景参考 | `get_stock_news` |
| `canslim-position-monitor` | "核心假设验证"步骤，检查有无负面公告 | `get_stock_news` |
| `value-position-monitor` | "逻辑止损条件"检查，扫描护城河相关新闻 | `get_stock_news` |
| `daily-workflow` | 日报末尾增加"近期市场动态"一栏 | `get_market_news` |

## File Changes

```
新增:
  src/trading_os/news/__init__.py
  src/trading_os/news/models.py
  src/trading_os/news/fetcher.py
  src/trading_os/news/cache.py
  src/trading_os/news/service.py

运行时生成（gitignored）:
  data/news_cache.db

.gitignore 追加:
  data/news_cache.db
```

## Design Decisions

- **不用 MongoDB**：零额外依赖，SQLite 与现有 EventLog 一致
- **不用 Tushare**：付费 + 额外积分，不适合基础数据源
- **财联社电报**：A 股实时资讯最快来源，go-stock 已有完整爬虫实现可参考
- **情感分析本地化**：参考 go-stock 的金融关键词词典，不调 LLM，避免延迟和成本
- **失败静默**：新闻不影响核心分析流程，fetch 失败返回空列表，skill 正常继续
- **symbol sentinel 而非 NULL**：SQLite UNIQUE 索引对 NULL 不去重，市场新闻用 `'__MARKET__'` 哨兵值
- **去掉 `date` 参数**：`ak.stock_news_em` 和 CLS 电报均无历史查询能力，暴露无法实现的参数会误导调用方
- **不 fallback 到 `news_cctv`**：CCTV 接口返回电视文字稿，不是金融新闻，不适合作为市场新闻 fallback
- **`fetched_at` 用 UTC ISO8601+00:00**：与 EventLog 一致，避免 TEXT 比较时时区混用导致 TTL 误判

## Required Tests

关键路径测试（必须在合并前通过）：

| Test | 验证内容 |
|---|---|
| `test_ttl_returns_cached_when_fresh` | fetched_at=now-1h → 第二次调用零网络请求 |
| `test_ttl_refetches_when_stale` | fetched_at=now-25h → 触发重新 fetch |
| `test_market_news_no_row_growth` | 连续两次 get_market_news → DB 行数不变 |
| `test_market_sentinel_symbol` | 市场新闻 DB 行 symbol='__MARKET__'，不是 NULL |
| `test_symbol_strip_sse` | get_stock_news("SSE:600000") → ak.stock_news_em 被调用时参数为 "600000" |
| `test_symbol_strip_szse` | get_stock_news("SZSE:000001") → 参数为 "000001" |
| `test_fetched_at_utc_format` | 存入 DB 的 fetched_at 符合 `\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00` |
| `test_format_news_for_prompt_empty` | items=[] → 返回空字符串，不抛异常 |
| `test_format_news_for_prompt_truncation` | 10 条长内容 → 输出 < 4000 字符 |

## Future: Phase B（主动推送）

基建层建好后，推送层只需：
1. 定时任务（cron/launchd）调用 `get_stock_news` + `get_market_news`
2. 判断 `importance == "high"` 的新闻
3. 推送到微信企业号 Webhook 或 Telegram Bot

推送层不修改 `news/` 模块，在外部编排即可。
