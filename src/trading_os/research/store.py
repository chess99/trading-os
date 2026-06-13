from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ResearchRun:
    run_id: str
    recipe: str
    path: Path
    inputs: dict[str, Any]


class ResearchStore:
    """Local research store backed by Parquet datasets and run artifacts.

    The store is intentionally dataset-oriented instead of workflow-oriented:
    recipes can reuse the same universe, quote, fundamental, factor, news, and
    bar caches without forcing a full-market refresh before every task.
    """

    def __init__(self, root: Path) -> None:
        try:
            import pandas as pd
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("ResearchStore requires pandas and pyarrow") from exc
        self._pd = pd
        self.root = root
        self.datasets = root / "datasets"
        self.runs = root / "runs"
        self.datasets.mkdir(parents=True, exist_ok=True)
        self.runs.mkdir(parents=True, exist_ok=True)

    def write_universe(
        self,
        df: Any,
        *,
        as_of: date,
        source: str,
        provenance: dict[str, Any] | None = None,
        freshness_policy: str = "daily",
    ) -> Path:
        return self._write_snapshot_dataset(
            "universe_snapshot",
            df,
            as_of=as_of,
            source=source,
            provenance=provenance,
            freshness_policy=freshness_policy,
        )

    def get_universe(self, *, as_of: date) -> Any:
        return self._read_latest_snapshot("universe_snapshot", as_of=as_of, key="symbol")

    def write_quote_snapshot(
        self,
        df: Any,
        *,
        as_of: date,
        source: str,
        provenance: dict[str, Any] | None = None,
        freshness_policy: str = "daily",
    ) -> Path:
        return self._write_snapshot_dataset(
            "quote_snapshot",
            df,
            as_of=as_of,
            source=source,
            provenance=provenance,
            freshness_policy=freshness_policy,
        )

    def get_quote_snapshot(self, *, as_of: date) -> Any:
        return self._read_latest_snapshot("quote_snapshot", as_of=as_of, key="symbol")

    def write_provider_health(self, records: list[dict[str, Any]]) -> Path:
        df = self._normalize_frame(records)
        if df.empty:
            return self._dataset_path("provider_health", "empty")
        if "recorded_at" not in df.columns:
            df["recorded_at"] = datetime.now(timezone.utc).isoformat()
        partition = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
        return self._write_dataset("provider_health", df, partition)

    def get_provider_health(self) -> Any:
        return self._read_dataset("provider_health")

    def write_fundamentals(
        self,
        df: Any,
        *,
        as_of: date,
        source: str,
        provenance: dict[str, Any] | None = None,
        freshness_policy: str = "quarterly",
    ) -> Path:
        return self._write_snapshot_dataset(
            "fundamentals",
            df,
            as_of=as_of,
            source=source,
            provenance=provenance,
            freshness_policy=freshness_policy,
        )

    def get_fundamentals(self, symbols: list[str] | None = None, *, as_of: date) -> Any:
        df = self._read_latest_snapshot("fundamentals", as_of=as_of, key="symbol")
        if symbols is not None and not df.empty:
            df = df[df["symbol"].isin(symbols)].reset_index(drop=True)
        return df

    def write_estimates(
        self, df: Any, *, as_of: date, source: str, provenance: dict[str, Any] | None = None
    ) -> Path:
        return self._write_snapshot_dataset(
            "estimates", df, as_of=as_of, source=source, provenance=provenance
        )

    def get_estimates(self, symbols: list[str] | None = None, *, as_of: date) -> Any:
        df = self._read_latest_snapshot("estimates", as_of=as_of, key="symbol")
        if symbols is not None and not df.empty:
            df = df[df["symbol"].isin(symbols)].reset_index(drop=True)
        return df

    def write_news(
        self, df: Any, *, as_of: date, source: str, provenance: dict[str, Any] | None = None
    ) -> Path:
        return self._write_snapshot_dataset(
            "news", df, as_of=as_of, source=source, provenance=provenance
        )

    def get_news(self, symbols: list[str] | None = None, *, as_of: date) -> Any:
        df = self._read_latest_snapshot("news", as_of=as_of, key="symbol")
        if symbols is not None and not df.empty:
            df = df[df["symbol"].isin(symbols)].reset_index(drop=True)
        return df

    def write_factors(
        self, df: Any, *, as_of: date, source: str, provenance: dict[str, Any] | None = None
    ) -> Path:
        return self._write_snapshot_dataset(
            "factors", df, as_of=as_of, source=source, provenance=provenance
        )

    def write_bars(
        self,
        df: Any,
        *,
        source: str,
        provenance: dict[str, Any] | None = None,
        freshness_policy: str = "on_demand",
    ) -> Path:
        out = self._normalize_frame(df)
        if out.empty:
            return self._dataset_path("bars", "empty")
        out["ts"] = self._pd.to_datetime(out["ts"], utc=True)
        out["source"] = source
        out["fetched_at"] = datetime.now(timezone.utc).isoformat()
        out["provenance"] = json.dumps(provenance or {}, ensure_ascii=False)
        out["freshness_policy"] = freshness_policy
        partition = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
        return self._write_dataset("bars", out, partition)

    def get_bars(self, symbols: list[str], *, start: date, end: date) -> Any:
        df = self._read_dataset("bars")
        if df.empty:
            return df
        df["ts"] = self._pd.to_datetime(df["ts"], utc=True)
        start_ts = self._pd.Timestamp(start, tz="UTC")
        end_ts = self._pd.Timestamp(end, tz="UTC")
        df = df[df["symbol"].isin(symbols)]
        df = df[(df["ts"] >= start_ts) & (df["ts"] < end_ts)]
        return df.sort_values(["symbol", "ts"]).reset_index(drop=True)

    def start_run(self, recipe: str, *, inputs: dict[str, Any]) -> ResearchRun:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"{stamp}-{recipe}-{uuid4().hex[:8]}"
        path = self.runs / run_id
        (path / "tables").mkdir(parents=True, exist_ok=True)
        (path / "charts").mkdir(parents=True, exist_ok=True)
        return ResearchRun(run_id=run_id, recipe=recipe, path=path, inputs=inputs)

    def write_run_artifacts(
        self,
        run: ResearchRun,
        *,
        manifest: dict[str, Any],
        trace_lines: list[str],
        report: str,
        tables: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "run_id": run.run_id,
            "recipe": run.recipe,
            "inputs": run.inputs,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            **manifest,
        }
        run.path.mkdir(parents=True, exist_ok=True)
        (run.path / "manifest.json").write_text(
            json.dumps(_jsonable(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (run.path / "trace.md").write_text("\n".join(trace_lines).rstrip() + "\n", encoding="utf-8")
        (run.path / "report.md").write_text(report, encoding="utf-8")
        for name, table in (tables or {}).items():
            df = self._normalize_frame(table)
            table_path = run.path / "tables" / f"{name}.csv"
            table_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(table_path, index=False)

    def _write_snapshot_dataset(
        self,
        dataset: str,
        df: Any,
        *,
        as_of: date,
        source: str,
        provenance: dict[str, Any] | None,
        freshness_policy: str = "daily",
    ) -> Path:
        out = self._normalize_frame(df)
        out["as_of"] = as_of.isoformat()
        out["source"] = source
        out["fetched_at"] = datetime.now(timezone.utc).isoformat()
        out["provenance"] = json.dumps(provenance or {}, ensure_ascii=False)
        out["freshness_policy"] = freshness_policy
        return self._write_dataset(dataset, out, as_of.isoformat())

    def _read_latest_snapshot(self, dataset: str, *, as_of: date, key: str) -> Any:
        df = self._read_dataset(dataset)
        if df.empty:
            return df
        df = df[df["as_of"] <= as_of.isoformat()]
        if df.empty:
            return df.reset_index(drop=True)
        df = df.sort_values(["as_of", "fetched_at"])
        return df.groupby(key, as_index=False).tail(1).sort_values(key).reset_index(drop=True)

    def _dataset_path(self, dataset: str, partition: str) -> Path:
        return self.datasets / dataset / f"{partition}.parquet"

    def _write_dataset(self, dataset: str, df: Any, partition: str) -> Path:
        path = self._dataset_path(dataset, partition)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        return path

    def _read_dataset(self, dataset: str) -> Any:
        files = sorted((self.datasets / dataset).glob("*.parquet"))
        if not files:
            return self._pd.DataFrame()
        return self._pd.concat([self._pd.read_parquet(path) for path in files], ignore_index=True)

    def _normalize_frame(self, data: Any) -> Any:
        if data is None:
            return self._pd.DataFrame()
        if isinstance(data, self._pd.DataFrame):
            return data.copy()
        return self._pd.DataFrame(data)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value
