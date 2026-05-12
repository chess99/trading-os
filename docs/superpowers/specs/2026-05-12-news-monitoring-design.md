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
skill 调用 get_stock_news(symbol, date)
    → cache.py 检查 news_cache.db
        → 命中（fetched_at < 24h）: 直接返回
        → 未命中: fetcher.py 拉取 → 写入缓存 → 返回
```

## Data Model

```python
@dataclass
class NewsItem:
    symbol: str | None   # None = 市场级新闻（财联社电报）
    title: str
    content: str
    source: str          # "eastmoney" | "cctv" | "cls_telegraph"
    pub_time: datetime
    sentiment: str       # "positive" | "negative" | "neutral"
    importance: str      # "high" | "medium" | "low"
    url: str = ""
    fetched_at: datetime = field(default_factory=datetime.now)
```

`sentiment` 和 `importance` 在 fetch 时用关键词词典本地打分，不调 LLM。

## Fetch Layer (`fetcher.py`)

两个独立函数：

```python
def fetch_stock_news(symbol: str, limit: int = 20) -> list[NewsItem]:
    # ak.stock_news_em("600000")
    # 失败时静默返回空列表，不抛异常

def fetch_cls_telegraph(limit: int = 50) -> list[NewsItem]:
    # GET https://www.cls.cn/nodeapi/telegraphList
    # 失败时 fallback 到 ak.news_cctv()
```

数据源：
- **个股新闻**：`ak.stock_news_em`（东方财富），symbol 格式为 6 位数字（"600000"）
- **市场新闻**：财联社电报 `cls.cn/nodeapi/telegraphList`，失败时 fallback 到 `ak.news_cctv`

Anti-crawl：
- AKShare 沿用项目已有的 User-Agent 风格（参考 `eastmoney_source.py`），失败静默
- 财联社：Browser headers + 30s timeout，fallback 到 AKShare CCTV 接口

## Cache Layer (`cache.py`)

**Schema:**

```sql
CREATE TABLE news_cache (
    id          INTEGER PRIMARY KEY,
    symbol      TEXT,           -- NULL 表示市场级新闻
    title       TEXT NOT NULL,
    content     TEXT,
    source      TEXT,
    pub_time    TEXT,           -- ISO8601
    sentiment   TEXT,
    importance  TEXT,
    url         TEXT,
    fetched_at  TEXT NOT NULL   -- ISO8601，TTL 判断依据
);
CREATE INDEX idx_symbol_fetched ON news_cache(symbol, fetched_at);
CREATE UNIQUE INDEX idx_dedup ON news_cache(symbol, title);
```

**TTL：24 小时。** `fetched_at` 距现在 < 24h 则缓存有效，否则重新 fetch 并 `INSERT OR REPLACE`。

## Public Interface (`service.py`)

```python
def get_stock_news(symbol: str, date: date | None = None, limit: int = 20) -> list[NewsItem]:
    """给定标的，返回 date 前 7 天内的新闻。date 为 None 时取今天。"""

def get_market_news(date: date | None = None, limit: int = 30) -> list[NewsItem]:
    """财联社电报 + CCTV 财经，不绑定标的。"""

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

## Future: Phase B（主动推送）

基建层建好后，推送层只需：
1. 定时任务（cron/launchd）调用 `get_stock_news` + `get_market_news`
2. 判断 `importance == "high"` 的新闻
3. 推送到微信企业号 Webhook 或 Telegram Bot

推送层不修改 `news/` 模块，在外部编排即可。
