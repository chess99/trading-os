import pytest
from trading_os.data.sources import akshare_source


def _reset_source_availability():
    """每个测试前重置全局状态"""
    akshare_source._SOURCE_AVAILABILITY["eastmoney"] = None
    akshare_source._SOURCE_AVAILABILITY["sina"] = None
    akshare_source._SOURCE_AVAILABILITY["baostock"] = None


def test_proxy_error_marks_eastmoney_unavailable(monkeypatch):
    """东财 ProxyError 应立即标记 eastmoney 不可用，后续调用直接跳过"""
    _reset_source_availability()
    akshare_source._SOURCE_AVAILABILITY["eastmoney"] = True  # 模拟探测已完成
    akshare_source._SOURCE_AVAILABILITY["sina"] = True

    call_count = {"eastmoney": 0}

    def mock_stock_zh_a_hist(**kwargs):
        call_count["eastmoney"] += 1
        raise Exception("HTTPSConnectionPool: Max retries exceeded (Caused by ProxyError)")

    def mock_stock_zh_a_daily(**kwargs):
        import pandas as pd
        return pd.DataFrame({
            "date": ["2026-05-09"], "open": [10.0], "high": [10.5],
            "low": [9.5], "close": [10.2], "volume": [1000000], "amount": [10000000],
        })

    from trading_os.data.schema import Exchange
    import akshare as ak
    monkeypatch.setattr(ak, "stock_zh_a_hist", mock_stock_zh_a_hist)
    monkeypatch.setattr(ak, "stock_zh_a_daily", mock_stock_zh_a_daily)

    # 第一次调用：东财失败（ProxyError）→ 标记不可用 → 切新浪
    df1, src1 = akshare_source._fetch_with_fallback(
        ak, "600000", Exchange.SSE, "20260509", "20260509", "qfq"
    )
    assert not df1.empty
    assert akshare_source._SOURCE_AVAILABILITY["eastmoney"] is False

    # 第二次调用：应直接跳过东财
    df2, src2 = akshare_source._fetch_with_fallback(
        ak, "600001", Exchange.SSE, "20260509", "20260509", "qfq"
    )
    assert call_count["eastmoney"] == 1  # 只调用了1次，第二只直接跳过


def test_non_proxy_error_does_not_mark_eastmoney_unavailable(monkeypatch):
    """非代理错误（如特定股票停牌）不应标记 eastmoney 全局不可用"""
    _reset_source_availability()
    akshare_source._SOURCE_AVAILABILITY["eastmoney"] = True
    akshare_source._SOURCE_AVAILABILITY["sina"] = True

    def mock_stock_zh_a_hist(**kwargs):
        raise Exception("该股票不存在或已退市")

    def mock_stock_zh_a_daily(**kwargs):
        import pandas as pd
        return pd.DataFrame({
            "date": ["2026-05-09"], "open": [10.0], "high": [10.5],
            "low": [9.5], "close": [10.2], "volume": [1000000], "amount": [10000000],
        })

    import akshare as ak
    monkeypatch.setattr(ak, "stock_zh_a_hist", mock_stock_zh_a_hist)
    monkeypatch.setattr(ak, "stock_zh_a_daily", mock_stock_zh_a_daily)

    from trading_os.data.schema import Exchange
    akshare_source._fetch_with_fallback(ak, "600000", Exchange.SSE, "20260509", "20260509", "qfq")
    # 非代理错误不应标记不可用
    assert akshare_source._SOURCE_AVAILABILITY["eastmoney"] is not False
