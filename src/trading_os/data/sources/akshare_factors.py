"""
AkShare因子数据获取模块

使用akshare获取真实的股票基本面数据、技术指标、行业分类等
严格禁止使用模拟数据!
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class AkshareFactorSource:
    """
    AkShare因子数据源

    提供:
    - 股票基本信息(名称、行业、市值等)
    - 估值因子(PE、PB、PS等)
    - 财务因子(ROE、ROA、负债率等)
    - 技术因子(动量、波动率等)
    - 股票池(A股全市场)
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        初始化数据源

        Args:
            cache_dir: 缓存目录,用于存储获取的数据
        """
        try:
            import akshare as ak
            self.ak = ak
        except ImportError as e:
            raise RuntimeError(
                "akshare is required. Install with: pip install akshare"
            ) from e

        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

        # 缓存
        self._stock_info_cache: Optional[pd.DataFrame] = None
        self._stock_list_cache: Optional[pd.DataFrame] = None
        self._cache_time: Optional[datetime] = None

        logger.info("AkShare因子数据源初始化完成")

    def get_a_stock_list(self) -> pd.DataFrame:
        """
        获取A股股票列表

        Returns:
            DataFrame包含:
            - symbol: 股票代码(6位)
            - name: 股票名称
            - exchange: 交易所(SSE/SZSE)
            - market: 市场(主板/创业板/科创板等)

        Raises:
            RuntimeError: 如果数据获取失败
        """
        # 检查缓存(缓存1小时)
        if (self._stock_list_cache is not None and
            self._cache_time is not None and
            datetime.now() - self._cache_time < timedelta(hours=1)):
            logger.info("使用缓存的股票列表")
            return self._stock_list_cache

        try:
            logger.info("获取A股股票列表...")

            # 获取沪深A股列表
            df = self.ak.stock_info_a_code_name()

            if df is None or df.empty:
                raise RuntimeError("获取股票列表失败: 返回空数据")

            # 标准化列名
            df = df.rename(columns={
                'code': 'symbol',
                'name': 'name'
            })

            # 添加交易所信息
            def get_exchange(code: str) -> str:
                if code.startswith('6'):
                    return 'SSE'
                elif code.startswith(('0', '3')):
                    return 'SZSE'
                else:
                    return 'UNKNOWN'

            df['exchange'] = df['symbol'].apply(get_exchange)

            # 添加市场信息
            def get_market(code: str) -> str:
                if code.startswith('688'):
                    return '科创板'
                elif code.startswith('300'):
                    return '创业板'
                elif code.startswith('6'):
                    return '沪市主板'
                elif code.startswith('0'):
                    return '深市主板'
                elif code.startswith('002'):
                    return '中小板'
                else:
                    return '其他'

            df['market'] = df['symbol'].apply(get_market)

            # 缓存
            self._stock_list_cache = df
            self._cache_time = datetime.now()

            logger.info(f"成功获取 {len(df)} 只A股股票")
            return df

        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            raise RuntimeError(f"无法获取股票列表: {e}") from e

    def get_stock_basic_info(self, symbol: str) -> Dict:
        """
        获取股票基本信息

        Args:
            symbol: 股票代码(6位数字)

        Returns:
            包含股票基本信息的字典:
            - name: 股票名称
            - industry: 所属行业
            - market_cap: 总市值
            - float_market_cap: 流通市值
            - pe_ratio: 市盈率
            - pb_ratio: 市净率
            - ps_ratio: 市销率
            - total_shares: 总股本
            - float_shares: 流通股本
        """
        try:
            logger.info(f"获取股票基本信息: {symbol}")

            # 获取实时行情(包含估值数据)
            df = self.ak.stock_zh_a_spot_em()
            stock_data = df[df['代码'] == symbol]

            if stock_data.empty:
                raise ValueError(f"未找到股票: {symbol}")

            row = stock_data.iloc[0]

            # 获取个股信息
            try:
                detail = self.ak.stock_individual_info_em(symbol=symbol)
                industry = detail[detail['item'] == '行业']['value'].values[0] if not detail.empty else "未知"
                total_shares = float(detail[detail['item'] == '总股本']['value'].values[0]) if not detail.empty else 0
                float_shares = float(detail[detail['item'] == '流通股']['value'].values[0]) if not detail.empty else 0
            except Exception as e:
                logger.warning(f"获取详细信息失败: {e}")
                industry = "未知"
                total_shares = 0
                float_shares = 0

            info = {
                'symbol': symbol,
                'name': row['名称'],
                'industry': industry,
                'market_cap': float(row['总市值']),
                'float_market_cap': float(row['流通市值']),
                'pe_ratio': float(row['市盈率-动态']) if row['市盈率-动态'] != '-' else 0,
                'pb_ratio': float(row['市净率']) if row['市净率'] != '-' else 0,
                'ps_ratio': 0,  # akshare实时行情不提供PS,需要从财务数据计算
                'total_shares': total_shares,
                'float_shares': float_shares,
                'last_update': datetime.now()
            }

            logger.info(f"成功获取 {symbol} 基本信息")
            return info

        except Exception as e:
            logger.error(f"获取股票基本信息失败 {symbol}: {e}")
            raise RuntimeError(f"无法获取股票信息: {symbol}") from e

    def get_stock_financial_indicators(self, symbol: str) -> Dict:
        """
        获取股票财务指标

        Args:
            symbol: 股票代码(6位数字)

        Returns:
            财务指标字典:
            - roe: 净资产收益率
            - roa: 总资产收益率
            - gross_margin: 毛利率
            - net_margin: 净利率
            - debt_ratio: 资产负债率
            - current_ratio: 流动比率
            - revenue_growth: 营收增长率
            - profit_growth: 利润增长率
        """
        try:
            logger.info(f"获取财务指标: {symbol}")

            # 获取主要财务指标
            df = self.ak.stock_financial_analysis_indicator(symbol=symbol)

            if df is None or df.empty:
                raise ValueError(f"未找到财务数据: {symbol}")

            # 使用最新一期数据
            latest = df.iloc[0]

            indicators = {
                'roe': float(latest['净资产收益率']) / 100 if '净资产收益率' in latest else 0,
                'roa': float(latest['总资产净利率']) / 100 if '总资产净利率' in latest else 0,
                'gross_margin': float(latest['销售毛利率']) / 100 if '销售毛利率' in latest else 0,
                'net_margin': float(latest['销售净利率']) / 100 if '销售净利率' in latest else 0,
                'debt_ratio': float(latest['资产负债率']) / 100 if '资产负债率' in latest else 0,
                'current_ratio': float(latest['流动比率']) if '流动比率' in latest else 0,
                'revenue_growth': 0,  # 需要对比历史数据计算
                'profit_growth': 0,   # 需要对比历史数据计算
                'report_date': latest['日期'],
                'last_update': datetime.now()
            }

            # 计算增长率(对比去年同期)
            if len(df) >= 5:  # 至少有5个季度的数据
                try:
                    # 营收增长率(同比)
                    current_revenue = float(latest['营业总收入'])
                    yoy_revenue = float(df.iloc[4]['营业总收入'])  # 去年同期
                    if yoy_revenue > 0:
                        indicators['revenue_growth'] = (current_revenue - yoy_revenue) / yoy_revenue

                    # 利润增长率(同比)
                    current_profit = float(latest['净利润'])
                    yoy_profit = float(df.iloc[4]['净利润'])
                    if yoy_profit > 0:
                        indicators['profit_growth'] = (current_profit - yoy_profit) / yoy_profit
                except Exception as e:
                    logger.warning(f"计算增长率失败: {e}")

            logger.info(f"成功获取 {symbol} 财务指标")
            return indicators

        except Exception as e:
            logger.error(f"获取财务指标失败 {symbol}: {e}")
            raise RuntimeError(f"无法获取财务指标: {symbol}") from e

    def get_stock_technical_indicators(
        self,
        symbol: str,
        period: str = "daily",
        days: int = 120
    ) -> Dict:
        """
        获取股票技术指标

        Args:
            symbol: 股票代码(6位数字)
            period: 周期(daily/weekly/monthly)
            days: 计算天数

        Returns:
            技术指标字典:
            - momentum_1m: 1月动量
            - momentum_3m: 3月动量
            - momentum_6m: 6月动量
            - volatility: 波动率(年化)
            - turnover_rate: 平均换手率
            - avg_volume: 平均成交量
            - avg_amount: 平均成交额
        """
        try:
            logger.info(f"获取技术指标: {symbol}")

            # 获取历史行情
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

            df = self.ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=""
            )

            if df is None or df.empty:
                raise ValueError(f"未找到历史数据: {symbol}")

            # 计算收益率
            df['return'] = df['收盘'].pct_change()

            # 计算动量(累计收益率)
            momentum_1m = (df['收盘'].iloc[-1] / df['收盘'].iloc[-20] - 1) if len(df) >= 20 else 0
            momentum_3m = (df['收盘'].iloc[-1] / df['收盘'].iloc[-60] - 1) if len(df) >= 60 else 0
            momentum_6m = (df['收盘'].iloc[-1] / df['收盘'].iloc[-120] - 1) if len(df) >= 120 else 0

            # 计算波动率(年化)
            volatility = df['return'].std() * np.sqrt(252) if len(df) > 1 else 0

            # 平均换手率
            avg_turnover = df['换手率'].mean() if '换手率' in df.columns else 0

            # 平均成交量和成交额
            avg_volume = df['成交量'].mean()
            avg_amount = df['成交额'].mean()

            indicators = {
                'momentum_1m': momentum_1m,
                'momentum_3m': momentum_3m,
                'momentum_6m': momentum_6m,
                'volatility': volatility,
                'turnover_rate': avg_turnover,
                'avg_volume': avg_volume,
                'avg_amount': avg_amount,
                'last_update': datetime.now()
            }

            logger.info(f"成功获取 {symbol} 技术指标")
            return indicators

        except Exception as e:
            logger.error(f"获取技术指标失败 {symbol}: {e}")
            raise RuntimeError(f"无法获取技术指标: {symbol}") from e

    def get_complete_stock_factors(self, symbol: str) -> Dict:
        """
        获取股票完整因子数据

        整合基本信息、财务指标、技术指标

        Args:
            symbol: 股票代码(6位数字)

        Returns:
            完整因子数据字典
        """
        try:
            logger.info(f"获取完整因子数据: {symbol}")

            # 获取各类数据
            basic_info = self.get_stock_basic_info(symbol)
            financial = self.get_stock_financial_indicators(symbol)
            technical = self.get_stock_technical_indicators(symbol)

            # 整合
            factors = {
                **basic_info,
                **financial,
                **technical,
                'last_update': datetime.now()
            }

            logger.info(f"成功获取 {symbol} 完整因子数据")
            return factors

        except Exception as e:
            logger.error(f"获取完整因子数据失败 {symbol}: {e}")
            raise RuntimeError(f"无法获取因子数据: {symbol}") from e

    def get_industry_classification(self) -> pd.DataFrame:
        """
        获取行业分类

        Returns:
            DataFrame包含:
            - symbol: 股票代码
            - name: 股票名称
            - industry: 行业
            - sector: 板块
        """
        try:
            logger.info("获取行业分类...")

            # 获取东方财富行业分类
            df = self.ak.stock_board_industry_name_em()

            if df is None or df.empty:
                raise RuntimeError("获取行业分类失败")

            logger.info(f"成功获取 {len(df)} 个行业分类")
            return df

        except Exception as e:
            logger.error(f"获取行业分类失败: {e}")
            raise RuntimeError(f"无法获取行业分类: {e}") from e

    def batch_get_stock_factors(
        self,
        symbols: List[str],
        max_workers: int = 5
    ) -> Dict[str, Dict]:
        """
        批量获取股票因子数据

        Args:
            symbols: 股票代码列表
            max_workers: 最大并发数

        Returns:
            {symbol: factors} 字典
        """
        logger.info(f"批量获取 {len(symbols)} 只股票的因子数据...")

        results = {}
        failed = []

        for i, symbol in enumerate(symbols, 1):
            try:
                logger.info(f"处理 {i}/{len(symbols)}: {symbol}")
                factors = self.get_complete_stock_factors(symbol)
                results[symbol] = factors
            except Exception as e:
                logger.error(f"获取 {symbol} 失败: {e}")
                failed.append(symbol)

            # 避免请求过快
            import time
            time.sleep(0.5)

        logger.info(
            f"批量获取完成: "
            f"成功{len(results)}只, 失败{len(failed)}只"
        )

        if failed:
            logger.warning(f"失败列表: {failed}")

        return results


def get_default_factor_source() -> AkshareFactorSource:
    """获取默认的因子数据源"""
    cache_dir = Path("data/cache/factors")
    return AkshareFactorSource(cache_dir=cache_dir)
