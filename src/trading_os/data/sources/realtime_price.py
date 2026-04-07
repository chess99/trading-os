"""
实时价格获取模块

提供股票实时价格获取功能,确保交易使用最新价格
"""

from typing import Dict, Optional
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_realtime_price(symbol: str) -> Optional[float]:
    """
    获取股票实时价格

    Args:
        symbol: 股票代码,格式如 "SSE:600000"

    Returns:
        实时价格,如果获取失败返回None

    Raises:
        ValueError: 如果symbol格式不正确
        RuntimeError: 如果数据获取失败
    """
    try:
        import akshare as ak
    except ImportError as e:
        raise RuntimeError(
            "akshare is required. Install with: pip install akshare"
        ) from e

    # 解析symbol
    if ":" not in symbol:
        raise ValueError(f"symbol格式错误,应为'交易所:代码',得到: {symbol}")

    exchange, ticker = symbol.split(":", 1)

    if len(ticker) != 6 or not ticker.isdigit():
        raise ValueError(f"A股代码必须是6位数字,得到: {ticker}")

    try:
        logger.info(f"获取实时价格: {symbol}")

        # 方法1: 使用实时行情接口(东方财富)
        df = ak.stock_zh_a_spot_em()

        if df is None or df.empty:
            raise RuntimeError(f"获取实时行情失败: {symbol}")

        # 查找对应股票
        stock_data = df[df['代码'] == ticker]

        if stock_data.empty:
            raise RuntimeError(f"未找到股票: {symbol}")

        # 获取最新价
        price = float(stock_data.iloc[0]['最新价'])

        logger.info(f"获取实时价格成功: {symbol} = {price:.2f}")
        return price

    except Exception as e:
        logger.error(f"获取实时价格失败 {symbol}: {e}")

        # 降级方案: 使用最新日线数据
        try:
            logger.info(f"尝试降级方案: 使用最新日线数据")
            end_date = datetime.now().strftime('%Y%m%d')
            df = ak.stock_zh_a_hist(
                symbol=ticker,
                period='daily',
                end_date=end_date,
                adjust=''
            )

            if df is not None and not df.empty:
                price = float(df.iloc[-1]['收盘'])
                date = df.iloc[-1]['日期']
                logger.info(f"使用最新日线价格: {symbol} = {price:.2f} (日期: {date})")
                return price

        except Exception as e2:
            logger.error(f"降级方案也失败: {e2}")

        raise RuntimeError(f"无法获取价格: {symbol}") from e


def get_realtime_prices(symbols: list[str]) -> Dict[str, float]:
    """
    批量获取股票实时价格

    Args:
        symbols: 股票代码列表

    Returns:
        价格字典 {symbol: price}
    """
    prices = {}

    for symbol in symbols:
        try:
            price = get_realtime_price(symbol)
            if price is not None:
                prices[symbol] = price
        except Exception as e:
            logger.error(f"获取价格失败 {symbol}: {e}")
            # 继续处理其他股票
            continue

    return prices


def get_stock_realtime_info(symbol: str) -> Optional[Dict]:
    """
    获取股票实时详细信息

    Args:
        symbol: 股票代码,格式如 "SSE:600000"

    Returns:
        包含实时信息的字典,包括:
        - price: 最新价
        - change: 涨跌额
        - change_pct: 涨跌幅(%)
        - volume: 成交量
        - amount: 成交额
        - open: 开盘价
        - high: 最高价
        - low: 最低价
        - prev_close: 昨收价
        - timestamp: 数据时间
    """
    try:
        import akshare as ak
    except ImportError as e:
        raise RuntimeError(
            "akshare is required. Install with: pip install akshare"
        ) from e

    # 解析symbol
    if ":" not in symbol:
        raise ValueError(f"symbol格式错误,应为'交易所:代码',得到: {symbol}")

    exchange, ticker = symbol.split(":", 1)

    try:
        logger.info(f"获取实时详细信息: {symbol}")

        # 获取实时行情
        df = ak.stock_zh_a_spot_em()

        if df is None or df.empty:
            return None

        # 查找对应股票
        stock_data = df[df['代码'] == ticker]

        if stock_data.empty:
            return None

        row = stock_data.iloc[0]

        info = {
            'symbol': symbol,
            'name': row['名称'],
            'price': float(row['最新价']),
            'change': float(row['涨跌额']),
            'change_pct': float(row['涨跌幅']),
            'volume': float(row['成交量']),
            'amount': float(row['成交额']),
            'open': float(row['今开']),
            'high': float(row['最高']),
            'low': float(row['最低']),
            'prev_close': float(row['昨收']),
            'timestamp': datetime.now().isoformat(),
            'source': 'akshare_realtime'
        }

        logger.info(f"获取实时信息成功: {symbol}")
        return info

    except Exception as e:
        logger.error(f"获取实时信息失败 {symbol}: {e}")
        return None


def validate_price_data(symbol: str, price: float, threshold_pct: float = 0.20) -> bool:
    """
    验证价格数据的合理性

    检查价格是否在合理范围内(与昨收价相比)

    Args:
        symbol: 股票代码
        price: 待验证的价格
        threshold_pct: 涨跌幅阈值(默认20%,A股涨跌停限制)

    Returns:
        True if price is valid, False otherwise
    """
    try:
        info = get_stock_realtime_info(symbol)

        if info is None:
            logger.warning(f"无法获取参考价格进行验证: {symbol}")
            return True  # 无法验证时假定有效

        prev_close = info['prev_close']
        change_pct = abs(price - prev_close) / prev_close

        if change_pct > threshold_pct:
            logger.warning(
                f"价格异常: {symbol}, "
                f"当前价={price:.2f}, 昨收={prev_close:.2f}, "
                f"变动={change_pct:.1%}"
            )
            return False

        return True

    except Exception as e:
        logger.error(f"价格验证失败: {e}")
        return True  # 验证失败时假定有效
