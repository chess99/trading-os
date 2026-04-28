"""EastMoney F10 财务数据源。

直接调用东方财富 F10 接口获取季度财务数据（EPS 同比增速、ROE），
无需 BaoStock 账号，无需预缓存，适合实时扫描场景。

主要用途：scan-canslim --live 模式，直接读 parquet + 实时拉取财务数据，
不依赖 fundamental-store 预缓存。
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://emweb.securities.eastmoney.com/",
}
_EM_F10_URL = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew"
_NAME_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

_name_cache: dict[str, str] = {}


def symbol_to_em_code(symbol: str) -> str:
    """将规范格式转换为东方财富代码。

    Examples:
        "SSE:600000"  -> "SH600000"
        "SZSE:000001" -> "SZ000001"
    """
    parts = symbol.split(":")
    if len(parts) != 2:
        return ""
    exchange, ticker = parts
    prefix = "SH" if exchange == "SSE" else "SZ"
    return f"{prefix}{ticker}"


def em_code_to_secucode(em_code: str) -> str:
    """SH600000 -> 600000.SH（东财数据中心格式）。"""
    if len(em_code) < 3:
        return ""
    prefix = em_code[:2]   # SH / SZ
    ticker = em_code[2:]   # 600000
    return f"{ticker}.{prefix}"


def get_stock_name(symbol: str) -> str:
    """获取股票中文名称（带缓存）。失败时返回空字符串。"""
    if symbol in _name_cache:
        return _name_cache[symbol]

    em_code = symbol_to_em_code(symbol)
    if not em_code:
        return ""

    secucode = em_code_to_secucode(em_code)
    try:
        r = requests.get(
            _NAME_URL,
            params={
                "reportName": "RPT_LICO_FN_CPD",
                "columns": "SECURITY_NAME_ABBR",
                "filter": f'(SECUCODE="{secucode}")',
                "pageSize": "1",
                "pageNumber": "1",
            },
            headers=_HEADERS,
            timeout=6,
        )
        name = ""
        if r.ok:
            d = r.json()
            if d.get("result") and d["result"].get("data"):
                name = d["result"]["data"][0].get("SECURITY_NAME_ABBR", "")
        _name_cache[symbol] = name
        return name
    except Exception:
        _name_cache[symbol] = ""
        return ""


def get_financial_data(symbol: str) -> dict[str, Any] | None:
    """从东方财富 F10 获取季度财务数据。

    返回格式：
        {
            "roe_list": [{"period": "2024-09-30", "roe": 17.54}, ...],   # 降序
            "yoy_eps_list": [{"period": "2024-09-30", "yoy_eps": 0.25}, ...],  # 降序
        }

    roe 单位：百分数（17.54 = 17.54%）
    yoy_eps：小数（0.25 = 25%）

    失败返回 None。
    """
    em_code = symbol_to_em_code(symbol)
    if not em_code:
        return None

    try:
        r = requests.get(
            _EM_F10_URL,
            params={"type": "0", "code": em_code},
            headers=_HEADERS,
            timeout=10,
        )
        if r.status_code != 200:
            return None

        result = r.json()
        pages = result.get("pages", 0)
        if not pages:
            return None

        all_data: list[dict] = []
        for page in range(1, min(pages, 4) + 1):
            r2 = requests.get(
                _EM_F10_URL,
                params={"type": "0", "code": em_code, "page": page},
                headers=_HEADERS,
                timeout=10,
            )
            if r2.status_code != 200:
                break
            d = r2.json()
            all_data.extend(d.get("data", []))
            if page >= d.get("pages", 0):
                break
            time.sleep(0.05)

        if not all_data:
            return None

        roe_list = []
        yoy_eps_list = []
        for rec in all_data:
            period = str(rec.get("REPORT_DATE", ""))[:10]
            roe = rec.get("ROEJQ")
            if roe is not None:
                roe_list.append({"period": period, "roe": float(roe)})
            eps_tz = rec.get("EPSJBTZ")
            if eps_tz is not None:
                # EPSJBTZ 是百分数格式（25.0 = 25%），转换为小数
                yoy_eps_list.append({"period": period, "yoy_eps": float(eps_tz) / 100})

        return {"roe_list": roe_list, "yoy_eps_list": yoy_eps_list}

    except Exception as exc:
        log.debug("EastMoney F10 failed for %s: %s", symbol, exc)
        return None
