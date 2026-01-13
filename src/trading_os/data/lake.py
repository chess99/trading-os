from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from typing import TYPE_CHECKING

try:
    import duckdb  # type: ignore
except ImportError:  # pragma: no cover
    duckdb = None  # type: ignore

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    pd = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    import duckdb as duckdb_types
    import pandas as pd_types

from .schema import Adjustment, BarColumns, Exchange, Timeframe


@dataclass(frozen=True, slots=True)
class DataLakePaths:
    root: Path

    @property
    def duckdb_path(self) -> Path:
        return self.root / "lake.duckdb"

    @property
    def parquet_dir(self) -> Path:
        return self.root / "parquet"

    @property
    def bars_dir(self) -> Path:
        return self.parquet_dir / "bars"


class LocalDataLake:
    """DuckDB + Parquet local data lake.

    Storage layout:
    - data/lake.duckdb
    - data/parquet/bars/*.parquet
    """

    def __init__(self, root: Path):
        if duckdb is None or pd is None:  # pragma: no cover
            raise RuntimeError(
                "LocalDataLake requires optional dependencies. "
                "Create a Python 3.10–3.12 environment and install: "
                "`pip install -e .[data_lake]`"
            )
        self.paths = DataLakePaths(root=root)
        self.paths.root.mkdir(parents=True, exist_ok=True)
        self.paths.bars_dir.mkdir(parents=True, exist_ok=True)

    def connect(self) -> "duckdb_types.DuckDBPyConnection":
        # duckdb is guaranteed by __init__
        con = duckdb.connect(str(self.paths.duckdb_path))  # type: ignore[union-attr]
        # pragmatic defaults
        con.execute("SET TimeZone='UTC'")
        return con

    def _create_empty_bars_view(self, con: "duckdb_types.DuckDBPyConnection") -> None:
        # DuckDB can't create a parquet view if the glob matches nothing.
        con.execute(
            f"""
            CREATE OR REPLACE VIEW bars AS
            SELECT
              CAST(NULL AS VARCHAR)      AS {BarColumns.symbol},
              CAST(NULL AS VARCHAR)      AS {BarColumns.exchange},
              CAST(NULL AS VARCHAR)      AS {BarColumns.timeframe},
              CAST(NULL AS VARCHAR)      AS {BarColumns.adjustment},
              CAST(NULL AS TIMESTAMPTZ)  AS {BarColumns.ts},
              CAST(NULL AS DOUBLE)       AS {BarColumns.open},
              CAST(NULL AS DOUBLE)       AS {BarColumns.high},
              CAST(NULL AS DOUBLE)       AS {BarColumns.low},
              CAST(NULL AS DOUBLE)       AS {BarColumns.close},
              CAST(NULL AS DOUBLE)       AS {BarColumns.volume},
              CAST(NULL AS DOUBLE)       AS {BarColumns.vwap},
              CAST(NULL AS BIGINT)       AS {BarColumns.trades},
              CAST(NULL AS VARCHAR)      AS {BarColumns.source}
            WHERE 1=0
            """
        )

    def init(self) -> None:
        """Create or refresh views/tables pointing to Parquet datasets."""
        with self.connect() as con:
            files = sorted(self.paths.bars_dir.glob("*.parquet"))
            if not files:
                self._create_empty_bars_view(con)
                return

            con.execute(
                f"""
                CREATE OR REPLACE VIEW bars AS
                SELECT *
                FROM read_parquet('{self.paths.bars_dir.as_posix()}/*.parquet', union_by_name=true)
                """
            )

    def write_bars_parquet(
        self,
        df: "pd_types.DataFrame",
        *,
        exchange: Exchange,
        timeframe: Timeframe,
        adjustment: Adjustment = Adjustment.NONE,
        source: str,
        partition_hint: str | None = None,
    ) -> Path:
        """Append bars to parquet.

        We store as multiple Parquet files (append-only). Downstream queries use DuckDB view `bars`.
        """

        required = [
            BarColumns.symbol,
            BarColumns.ts,
            BarColumns.open,
            BarColumns.high,
            BarColumns.low,
            BarColumns.close,
            BarColumns.volume,
        ]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"bars df missing columns: {missing}")

        out = df.copy()
        # Normalize ts to tz-aware UTC
        if BarColumns.ts in out.columns:
            out[BarColumns.ts] = pd.to_datetime(out[BarColumns.ts], utc=True)  # type: ignore[union-attr]
        out[BarColumns.exchange] = exchange.value
        out[BarColumns.timeframe] = timeframe.value
        out[BarColumns.adjustment] = adjustment.value
        out[BarColumns.source] = source

        # ensure ordering
        cols = [
            BarColumns.symbol,
            BarColumns.exchange,
            BarColumns.timeframe,
            BarColumns.adjustment,
            BarColumns.ts,
            BarColumns.open,
            BarColumns.high,
            BarColumns.low,
            BarColumns.close,
            BarColumns.volume,
            BarColumns.vwap,
            BarColumns.trades,
            BarColumns.source,
        ]
        out = out[[c for c in cols if c in out.columns]]

        suffix = partition_hint or "append"
        path = self.paths.bars_dir / f"bars_{exchange.value}_{timeframe.value}_{adjustment.value}_{suffix}.parquet"
        out.to_parquet(path, index=False)
        return path

    def query_bars(
        self,
        *,
        symbols: Iterable[str] | None = None,
        exchange: Exchange | None = None,
        timeframe: Timeframe = Timeframe.D1,
        adjustment: Adjustment = Adjustment.NONE,
        start: str | None = None,  # ISO date or timestamp
        end: str | None = None,
        limit: int | None = None,
    ) -> "pd_types.DataFrame":
        """Query bars from DuckDB view.

        `start`/`end` are interpreted by DuckDB (ISO strings recommended).
        """
        self.init()
        where: list[str] = [
            f"{BarColumns.timeframe} = ?",
            f"{BarColumns.adjustment} = ?",
        ]
        params: list[object] = [timeframe.value, adjustment.value]

        if exchange is not None:
            where.append(f"{BarColumns.exchange} = ?")
            params.append(exchange.value)
        if symbols is not None:
            syms = list(symbols)
            if syms:
                where.append(f"{BarColumns.symbol} IN ({','.join(['?'] * len(syms))})")
                params.extend(syms)
        if start is not None:
            where.append(f"{BarColumns.ts} >= ?")
            params.append(start)
        if end is not None:
            where.append(f"{BarColumns.ts} <= ?")
            params.append(end)

        sql = f"SELECT * FROM bars WHERE {' AND '.join(where)} ORDER BY {BarColumns.ts}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))

        with self.connect() as con:
            return con.execute(sql, params).df()

