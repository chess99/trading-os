# input: local data lake bars via duckdb/pandas and UI parameters
# output: tkinter UI with DCA backtest results and optional CSV report
# pos: standalone DCA backtest UI; update this header and `scripts/README.md` on change
from __future__ import annotations

import re
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover
    pd = None  # type: ignore

from trading_os.backtest.dca import (
    DcaConfig,
    DcaFrequency,
    compute_dca_metrics,
    run_dca_backtest,
)
from trading_os.data.lake import LocalDataLake
from trading_os.data.schema import Adjustment, Timeframe
from trading_os.paths import repo_root


class DcaBacktestUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("DCA Backtest")
        self.geometry("1200x700")
        self._build_widgets()

    def _build_widgets(self) -> None:
        root = ttk.Frame(self)
        root.pack(fill=tk.BOTH, expand=True)

        inputs = ttk.LabelFrame(root, text="Inputs")
        inputs.pack(fill=tk.X, padx=10, pady=8)

        self.symbols_var = tk.StringVar(value="SSE:000688")
        self.adjustment_var = tk.StringVar(value="none")
        self.timeframe_var = tk.StringVar(value="1d")
        self.start_var = tk.StringVar(value="2020-01-01")
        self.end_var = tk.StringVar(value="")
        self.use_first_var = tk.BooleanVar(value=False)
        self.annual_var = tk.StringVar(value="120000")
        self.fee_var = tk.StringVar(value="1.0")
        self.slip_var = tk.StringVar(value="2.0")
        self.freq_var = tk.StringVar(value="compare")
        self.fractional_var = tk.BooleanVar(value=True)

        row = 0
        self._add_labeled_entry(
            inputs,
            row,
            "Symbol ids (EXCHANGE:TICKER, comma-separated)",
            self.symbols_var,
            width=60,
        )
        row += 1
        self._add_labeled_entry(inputs, row, "Start date (YYYY-MM-DD)", self.start_var)
        self._add_labeled_entry(inputs, row, "End date (YYYY-MM-DD)", self.end_var, col=2)
        row += 1
        self._add_labeled_option(
            inputs,
            row,
            "Adjustment",
            self.adjustment_var,
            ["none", "qfq", "hfq", "split_div"],
        )
        self._add_labeled_option(inputs, row, "Timeframe", self.timeframe_var, ["1d"], col=2)
        row += 1
        self._add_labeled_entry(inputs, row, "Annual contribution", self.annual_var)
        self._add_labeled_entry(inputs, row, "Fee (bps)", self.fee_var, col=2)
        row += 1
        self._add_labeled_entry(inputs, row, "Slippage (bps)", self.slip_var)
        self._add_labeled_option(
            inputs,
            row,
            "Frequency",
            self.freq_var,
            ["compare", "daily", "weekly", "monthly"],
            col=2,
        )
        row += 1

        ttk.Checkbutton(
            inputs,
            text="Use first available start date",
            variable=self.use_first_var,
        ).grid(row=row, column=0, sticky=tk.W, padx=6, pady=4)
        ttk.Checkbutton(
            inputs,
            text="Allow fractional shares",
            variable=self.fractional_var,
        ).grid(row=row, column=2, sticky=tk.W, padx=6, pady=4)

        run_btn = ttk.Button(inputs, text="Run backtest", command=self._run_backtest)
        run_btn.grid(row=row, column=3, sticky=tk.E, padx=6, pady=4)

        results_frame = ttk.LabelFrame(root, text="Results")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        columns = [
            "symbol",
            "frequency",
            "start",
            "end",
            "invested",
            "final_value",
            "profit",
            "roi",
            "cagr",
            "max_dd",
            "sharpe",
            "xirr",
        ]
        self.tree = ttk.Treeview(results_frame, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=95, anchor=tk.CENTER)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar(value="Ready")
        status = ttk.Label(root, textvariable=self.status_var, anchor=tk.W)
        status.pack(fill=tk.X, padx=10, pady=4)

    def _add_labeled_entry(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        var: tk.StringVar,
        *,
        col: int = 0,
        width: int = 20,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky=tk.W, padx=6, pady=4)
        ttk.Entry(parent, textvariable=var, width=width).grid(
            row=row, column=col + 1, sticky=tk.W, padx=6, pady=4
        )

    def _add_labeled_option(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        var: tk.StringVar,
        options: list[str],
        *,
        col: int = 0,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky=tk.W, padx=6, pady=4)
        ttk.OptionMenu(parent, var, var.get(), *options).grid(
            row=row, column=col + 1, sticky=tk.W, padx=6, pady=4
        )

    def _run_backtest(self) -> None:
        if pd is None:
            messagebox.showerror("Missing dependency", "pandas is required to run this tool.")
            return

        symbols = self._parse_symbols(self.symbols_var.get())
        if not symbols:
            messagebox.showerror("Invalid input", "Please enter at least one symbol id.")
            return

        try:
            adjustment = Adjustment(self.adjustment_var.get())
        except ValueError:
            messagebox.showerror(
                "Invalid input",
                "Adjustment must be one of none/qfq/hfq/split_div.",
            )
            return

        try:
            timeframe = Timeframe(self.timeframe_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Timeframe must be 1d.")
            return

        start = None if self.use_first_var.get() else self.start_var.get().strip() or None
        end = self.end_var.get().strip() or None

        try:
            annual = float(self.annual_var.get())
            fee_bps = float(self.fee_var.get())
            slip_bps = float(self.slip_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Annual contribution/fees must be numbers.")
            return

        freq_choice = self.freq_var.get()
        if freq_choice == "compare":
            freqs = [DcaFrequency.DAILY, DcaFrequency.WEEKLY, DcaFrequency.MONTHLY]
        else:
            try:
                freqs = [DcaFrequency(freq_choice)]
            except ValueError:
                messagebox.showerror(
                    "Invalid input",
                    "Frequency must be daily/weekly/monthly/compare.",
                )
                return

        cfg = DcaConfig(
            annual_contribution=annual,
            fee_bps=fee_bps,
            slippage_bps=slip_bps,
            allow_fractional_shares=bool(self.fractional_var.get()),
        )

        lake = LocalDataLake(repo_root() / "data")
        rows = []
        errors = []

        for symbol in symbols:
            bars = lake.query_bars(
                symbols=[symbol],
                timeframe=timeframe,
                adjustment=adjustment,
                start=start,
                end=end,
                limit=None,
            )
            if bars.empty:
                errors.append(f"No bars found for {symbol}")
                continue

            start_ts = str(pd.to_datetime(bars["ts"].iloc[0]).date())
            end_ts = str(pd.to_datetime(bars["ts"].iloc[-1]).date())

            for freq in freqs:
                res = run_dca_backtest(bars, frequency=freq, config=cfg)
                metrics = compute_dca_metrics(
                    res.equity_curve,
                    periods_per_year=_periods_per_year(freq),
                )
                rows.append(
                    {
                        "symbol": symbol,
                        "frequency": freq.value,
                        "start": start_ts,
                        "end": end_ts,
                        "invested": metrics.total_invested,
                        "final_value": metrics.final_value,
                        "profit": metrics.profit,
                        "roi": metrics.roi,
                        "cagr": metrics.cagr,
                        "max_dd": metrics.max_drawdown,
                        "sharpe": metrics.sharpe,
                        "xirr": metrics.xirr,
                    }
                )

        self._render_results(rows)
        if errors:
            messagebox.showwarning("Data missing", "\n".join(errors))
        if rows:
            self._save_report(rows)

    def _render_results(self, rows: list[dict[str, object]]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in rows:
            values = [
                row["symbol"],
                row["frequency"],
                row["start"],
                row["end"],
                _fmt_money(row["invested"]),
                _fmt_money(row["final_value"]),
                _fmt_money(row["profit"]),
                _fmt_pct(row["roi"]),
                _fmt_pct(row["cagr"]),
                _fmt_pct(row["max_dd"]),
                _fmt_num(row["sharpe"]),
                _fmt_pct(row["xirr"]),
            ]
            self.tree.insert("", tk.END, values=values)
        self.status_var.set(f"Rows: {len(rows)}")

    def _save_report(self, rows: list[dict[str, object]]) -> None:
        if pd is None:
            return
        df = pd.DataFrame(rows)
        out_dir = repo_root() / "artifacts" / "dca_backtest"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"dca_backtest_{stamp}.csv"
        df.to_csv(path, index=False)
        self.status_var.set(f"Saved report: {path}")

    @staticmethod
    def _parse_symbols(text: str) -> list[str]:
        parts = re.split(r"[,\s]+", text.strip())
        return [p for p in parts if p]


def _periods_per_year(freq: DcaFrequency) -> int:
    if freq == DcaFrequency.DAILY:
        return 252
    if freq == DcaFrequency.WEEKLY:
        return 52
    if freq == DcaFrequency.MONTHLY:
        return 12
    raise ValueError(f"unsupported frequency: {freq}")


def _fmt_money(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):,.2f}"


def _fmt_pct(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100:.2f}%"


def _fmt_num(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.3f}"


def main() -> None:
    app = DcaBacktestUI()
    app.mainloop()


if __name__ == "__main__":
    main()
