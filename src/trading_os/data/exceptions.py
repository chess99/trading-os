"""Data integrity exceptions for the trading_os data pipeline."""


class DataIntegrityError(ValueError):
    """Raised when incoming data would corrupt an existing symbol's price series.

    Inherits from ValueError so callers can ``except ValueError`` to catch both
    this and ordinary validation errors without needing to import this class.
    """

    def __init__(self, *, symbol: str, expected_range: tuple[float, float], actual_value: float) -> None:
        self.symbol = symbol
        self.expected_range = expected_range
        self.actual_value = actual_value
        lo, hi = expected_range
        super().__init__(
            f"Price continuity check failed for {symbol}: "
            f"existing data median implies range [{lo:.2f}, {hi:.2f}], "
            f"but new data contains {actual_value:.4f}. "
            "This likely means data from a different asset is being written to this symbol. "
            "Use --asset-type to specify the correct asset type."
        )
