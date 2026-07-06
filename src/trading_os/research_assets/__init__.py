from __future__ import annotations

from .company import AssetValidationError, validate_company_dir

__all__ = [
    "AssetValidationError",
    "build_index",
    "validate_company_dir",
    "write_index",
]


def __getattr__(name: str):
    if name in {"build_index", "write_index"}:
        from .index import build_index, write_index

        return {"build_index": build_index, "write_index": write_index}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
