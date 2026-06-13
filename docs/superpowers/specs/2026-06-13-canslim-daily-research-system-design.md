# CANSLIM Daily Research System Design

Date: 2026-06-13

## Goal

Build a reliable agent-native CANSLIM daily research system for A-shares.

The system must:

- Run a full A-share CANSLIM screen every trading day.
- Deeply research every strict CANSLIM candidate, not only the top displayed rows.
- Produce final, human-readable operation advice for each candidate.
- Track symbols that have already entered the watchlist.
- Alert when a watched symbol reaches an actionable entry signal.
- Preserve a machine-readable evidence chain for every screen, research report, decision, and alert.

The system is not a live trading executor. It may produce trade-ready advice, but execution still requires explicit user approval and must remain auditable through `RiskManager`, `EventLog`, and run manifests.

## Recommended Approach

Use a hybrid workflow:

- **Daily end-of-day research loop** for full-market screening, deep research, technical confirmation, decisions, watchlist updates, and daily summary.
- **Intraday watchlist alert loop** for symbols already under observation.

Do not build full-market intraday scanning. It is expensive, brittle, and unnecessary for CANSLIM because actionable entry monitoring only needs the current watchlist after the daily research loop has produced valid pivot and invalidation levels.

## Alternatives Considered

### EOD-only system

This is the most stable option. It only needs completed trading-day data and avoids realtime source instability. It misses intraday breakout alerts, which is a core user requirement.

### Full-market realtime system

This can detect every intraday breakout, but it requires a robust realtime market data service, high-frequency polling or push subscriptions, rate limiting, alert deduplication, and much stronger operational monitoring. It is not the right first target for a local research platform.

### Hybrid system

This is the recommended option. Daily full-market work runs on reliable end-of-day data. Intraday work only monitors a small watchlist with explicit pivot, buy-zone, stop-loss, and invalidation rules.

## Current System Gaps

The current repository already has a useful `ResearchStore`, `DataHub`, CANSLIM recipe, run artifacts, and watchlist assets, but it does not yet satisfy the target workflow.

Observed gaps:

- `DataHub` still effectively depends on a single `AkshareResearchProvider` for live refresh.
- `get_estimates()` and `get_news()` read cache only and do not actively fetch missing data.
- `daily_research` currently wraps `canslim_screen` and displays a small subset; it does not deep research all strict candidates.
- Company CANSLIM reports still focus on local deterministic evidence and do not reliably include news, management guidance, institutional sponsorship, peer comparison, or full technical entry confirmation.
- Watchlist state is mostly human-readable Markdown and `pool.json`; it lacks a strict machine-readable state machine for alerts.
- Existing docs describe `artifacts/runs`, while the current store writes recipe runs under `data/research/runs`. The new design must make this boundary explicit.
- Provider failures are not yet represented as first-class evidence with health state, fallback decisions, and conclusion impact.

## Data Source Strategy

### Provider Tiers

`DataHub` should route all data access through a provider router. No recipe should call AkShare, Tushare, BaoStock, EastMoney, Sina, Tencent, RQData, or JQData directly.

Preferred provider tiers:

1. **Primary paid or semi-paid source**
   - Tushare Pro for initial pragmatic coverage.
   - RQData or JQData when stronger point-in-time support, factor research, and historical backtest quality justify the cost.
2. **Free fallback sources**
   - AkShare for broad coverage but not as a single point of truth.
   - BaoStock for historical daily bars and some financial data fallback.
   - Sina, Tencent, and EastMoney for realtime or quote fallback.
3. **Manual or semi-structured fallback**
   - Official exchange announcements, company filings, and selected news search for cases where structured provider coverage is insufficient.

Clash or other proxies are network configuration, not a reliability strategy. A proxy can be used per provider request, but provider failure must still trigger retry, fallback, or explicit degradation.

### Provider Capabilities

Each provider adapter must declare capabilities:

- `universe`
- `quote_snapshot_eod`
- `quote_realtime`
- `bars_daily`
- `bars_minute`
- `fundamentals`
- `financial_statements`
- `business_segments`
- `estimates`
- `institutional_ownership`
- `announcements`
- `news`
- `trading_calendar`

The provider router chooses a provider by capability, configured priority, freshness, health, and quota. The manifest records which provider satisfied each dataset and which providers failed.

### Freshness Rules

Default freshness policy by dataset:

- `universe_snapshot`: daily on trading days, weekly acceptable for fallback if no listing status changes are needed.
- `quote_snapshot`: exact latest completed trading date for daily research.
- `bars_daily`: must cover the required lookback through latest completed trading date.
- `fundamentals`: quarterly, keyed by report period and publish date when available.
- `business_segments`: annual or semiannual, refreshed around financial report releases.
- `estimates`: daily or provider-defined, but always stamped with source and fetch time.
- `news` and `announcements`: hourly to daily depending on workflow.
- `quote_realtime`: intraday only, watchlist scope only.

No daily research run may silently use a stale quote snapshot for the requested completed trading date.

## Trading Calendar

All daily workflows begin by resolving `effective_as_of`.

Rules:

- If the requested date is a trading day after market close, `effective_as_of` is the requested date.
- If the requested date is a trading day before enough EOD data is available, `effective_as_of` is the previous trading day unless the user explicitly requests intraday mode.
- If the requested date is a weekend or holiday, `effective_as_of` is the latest completed trading day.
- The run manifest stores both `requested_as_of` and `effective_as_of`.

This prevents a Saturday run, such as 2026-06-13, from pretending that Saturday market data exists.

## Data Model Additions

Extend `ResearchStore` with these datasets:

- `provider_health`
  - provider name, capability, status, last success, last failure, error category, cooldown.
- `decisions`
  - symbol, date, recipe, decision class, confidence, reasons, required follow-up, source run ids.
- `watchlist_state`
  - symbol, status, source decision, pivot price, buy zone, stop loss, volume baseline, invalidation rules, valid-until date, last review run.
- `alerts`
  - alert id, symbol, trigger type, trigger value, evidence, status, sent destinations, cooldown key, event log id.
- `technical_setups`
  - symbol, setup type, base range, pivot, volume baseline, RS, confirmation status, invalidation level.

Continue storing recipe run evidence under `data/research/runs/{run_id}/`.

Keep human-facing reports under:

- `artifacts/research/`
- `artifacts/watchlist/`

`data/research/runs` is the machine evidence chain. `artifacts/research` and `artifacts/watchlist` are the human operating layer.

## Daily Workflow

The daily recipe should become `daily_canslim_research`.

Inputs:

- `requested_as_of`
- market scope, default full A-share market.
- CANSLIM thresholds.
- strict/provisional handling policy.
- watchlist update policy.
- notification policy.

Steps:

1. Resolve `effective_as_of` using `TradingCalendar`.
2. Run provider health probes for required capabilities.
3. Load or refresh exact-date universe and quote snapshot.
4. Load or refresh fundamentals and financial statement fields needed for CANSLIM.
5. Run full-market CANSLIM screen.
6. Persist full candidate table and displayed candidate table separately.
7. Deep research every strict CANSLIM candidate.
8. For provisional candidates, create a data-gap queue but do not mix them with strict conclusions.
9. Run technical confirmation for every strict candidate and existing watchlist symbol.
10. Produce decisions for strict candidates and watched symbols.
11. Update machine-readable watchlist state.
12. Generate the daily human report.
13. Send daily notification summary if configured.

The workflow must never stop after writing only manifests. The final user-facing output must include the daily report path and a concise summary of actionable decisions.

## CANSLIM Screening Semantics

The screen output must distinguish:

- `all_candidates`: every candidate after scoring.
- `displayed_candidates`: report display subset controlled by `--top`.
- `strict_canslim_candidate`: complete required evidence and passes strict thresholds.
- `provisional_research_queue`: promising but missing required fields or incomplete evidence.

Rules:

- `--top` only limits display, not downstream processing.
- All strict candidates must be deep researched.
- Provisional candidates require data completion before they can become actionable.
- The daily report must state all candidate counts and the display limit.

## Deep Research Scope

Each strict candidate research packet must cover:

- CANSLIM score breakdown.
- Revenue, earnings, margins, ROE, cash flow, leverage, and trend quality.
- Quarterly continuity and acceleration.
- Business model and main revenue segments.
- Institutional sponsorship or shareholder changes when available.
- 12-month news and announcements.
- Management guidance, capacity, orders, products, and strategic catalysts when available.
- Peer and industry comparison.
- Relative strength and liquidity.
- Base, pivot, buy zone, stop-loss, and invalidation conditions.
- Data limitations and confidence impact.

If a data source fails, the report must not leave the dimension as an unexplained future task. It must name the failed source, fallback source, missing dimension, and how the missing evidence affects confidence.

## Decision Classes

Every strict candidate and watched symbol must end with exactly one current decision:

- `actionable_watch`
  - Fundamentals pass, technical setup is near actionable, and explicit pivot/buy-zone/stop-loss are available.
- `wait_for_breakout`
  - Fundamentals pass, but price/volume confirmation is not yet present.
- `research_only`
  - Interesting but key evidence is incomplete or conflicting.
- `reject`
  - Fails core evidence, has unacceptable risk, or setup is invalidated.

This is advice classification, not an automatic trade instruction.

## Watchlist State Machine

Watchlist state should be machine-readable and generated from decisions.

States:

- `candidate`
- `watching`
- `actionable`
- `invalidated`
- `expired`
- `removed`

Transitions:

- `candidate -> watching`: strict candidate passes deep research and has a valid setup or defined missing condition.
- `watching -> actionable`: pivot/buy-zone and volume confirmation trigger.
- `watching -> invalidated`: price, fundamentals, or event-based invalidation rule triggers.
- `watching -> expired`: valid-until date passes without setup confirmation.
- `invalidated|expired -> removed`: daily review confirms removal.

Each state update records source run id, reasons, and effective date.

## Intraday Alert Monitor

The intraday loop monitors only `watchlist_state` entries that are `watching` or `actionable`.

Supported triggers:

- `near_pivot`
- `breakout_confirmed`
- `volume_confirmed`
- `fell_below_stop`
- `setup_invalidated`
- `news_or_announcement_event`

Alert rules:

- Every trigger has a deterministic condition.
- Every alert has a cooldown key to prevent repeated notifications.
- Every alert writes to `alerts` and `EventLog`.
- Alert evidence links back to watchlist state, quote provider, and latest relevant daily run.
- Failed notification delivery is recorded and retried according to policy.

## Human-Facing Outputs

Daily report path:

`artifacts/research/daily-canslim-YYYYMMDD.md`

Required sections:

- Effective trading date.
- Data sources and degraded capabilities.
- Full candidate counts: all, strict, provisional, displayed.
- New strict candidates.
- Decisions and next actions.
- Watchlist changes.
- Intraday alert levels for active watched symbols.
- Data limitations and confidence impact.
- Links to run manifests and per-symbol research packets.

Watchlist summary:

`artifacts/watchlist/state.json`

Optional human watchlist digest:

`artifacts/watchlist/watchlist-YYYYMMDD.md`

## CLI Shape

Recommended public commands:

```bash
python -m trading_os research daily-canslim --as-of YYYY-MM-DD
python -m trading_os research company SYMBOL --template canslim --as-of YYYY-MM-DD
python -m trading_os alert monitor --mode watchlist
python -m trading_os data provider status
python -m trading_os data provider probe
```

The current `research daily` command can be replaced or redirected during implementation because backward compatibility is not required.

## Configuration

Use environment variables or a local config file that is not committed.

Required config groups:

- Provider credentials: `TUSHARE_TOKEN`, RQData/JQData credentials if used.
- Provider priority and fallback policy.
- Proxy settings per provider: HTTP, HTTPS, SOCKS, timeout.
- Rate limits and circuit breaker cooldown.
- Notification destination: local desktop, Feishu, DingTalk, Telegram, email, or user-selected channel.
- Daily schedule time.
- Intraday monitor interval and trading-session windows.

Secrets must never be written into manifests. Manifests may record provider names and credential presence, not credential values.

## Reliability Requirements

- Provider failure must not crash the entire workflow if another provider can satisfy the same capability.
- If a required capability cannot be satisfied, the run fails explicitly or downgrades the decision class to `research_only`.
- Exact-date quote snapshots are required for daily screening.
- Daily bars must cover the required lookback through `effective_as_of`.
- Fundamental data must be as-of safe. When publish dates are unavailable, the report must state the limitation.
- All cache hits must be explainable by freshness policy and recorded in trace or manifest.
- All external calls must be timeout-bound.

## Testing Plan

Core tests:

- Trading calendar resolves weekend and holiday requested dates to the latest completed trading day.
- `DataHub` does not use stale quote snapshots for exact-date daily research.
- Provider router falls back from a failed primary provider to a healthy secondary provider.
- Provider router records failure reason, fallback provider, and cooldown.
- CANSLIM screen processes all strict candidates downstream regardless of `--top`.
- Daily workflow deep researches every strict candidate.
- Provisional candidates are recorded as a data-gap queue and do not receive actionable decisions.
- Decision board emits exactly one decision class per strict candidate and watched symbol.
- Watchlist state transitions are deterministic and auditable.
- Alert monitor only scans watchlist symbols.
- Alert monitor deduplicates repeated trigger events.
- Daily report includes candidate counts, decisions, watchlist changes, limitations, and manifest links.

Integration tests:

- Run daily workflow with synthetic provider fixtures.
- Simulate provider primary failure and fallback success.
- Simulate stale cache and verify explicit refresh or failure.
- Simulate a watchlist breakout and verify alert + `EventLog` write.

Production smoke tests:

- `python -m trading_os data provider probe`
- `python -m trading_os research daily-canslim --as-of YYYY-MM-DD`
- `python -m trading_os alert monitor --mode watchlist --once`

## Implementation Phases

### Phase 1: Reliable EOD foundation

- Add `TradingCalendar`.
- Add provider capability interfaces and provider router.
- Add Tushare provider as first paid-source adapter.
- Preserve AkShare/BaoStock/Sina/Tencent as fallback adapters.
- Enforce exact-date quote snapshot and bar coverage.
- Add provider health manifests.

### Phase 2: Daily CANSLIM closure

- Replace `daily_research` with `daily_canslim_research`.
- Ensure all strict candidates are deep researched.
- Add decision board and strict/provisional separation.
- Generate daily human report under `artifacts/research`.
- Persist decision records.

### Phase 3: Watchlist state and alerts

- Add `watchlist_state`, `technical_setups`, and `alerts` datasets.
- Add state transitions.
- Add alert monitor for watchlist only.
- Add notification delivery and cooldown.

### Phase 4: Research depth

- Add active news and announcements fetching.
- Add institutional sponsorship data.
- Add peer comparison and industry crowding.
- Add management guidance and catalyst extraction.
- Improve point-in-time handling for fundamentals and estimates.

### Phase 5: Advanced provider and backtest quality

- Add RQData or JQData provider when credentials and cost are accepted.
- Add point-in-time tests for fundamentals.
- Align factor research and backtests with the same provider router and store semantics.

## Non-Goals

- No automatic live trading.
- No full-market intraday scanning in the first implementation.
- No reliance on one free web interface as a primary data source.
- No simulated or invented investment data in production reports.
- No backward compatibility with old daily, scan, lake, or scheduler semantics.

## Open Decisions Before Implementation

These do not block the design, but they affect implementation priority:

- Which paid provider to buy or configure first: Tushare Pro, RQData, or JQData.
- Which notification channel to use first.
- Whether intraday alerting should run as a local long-lived process, a Codex automation, or an external scheduler.

Default implementation assumption:

- Start with Tushare Pro as the first paid provider because it is pragmatic for A-share daily data.
- Use free providers as fallback.
- Build daily EOD closure before intraday alerts.
- Add intraday monitor only for watchlist symbols.
