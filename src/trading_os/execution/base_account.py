"""
账户抽象基类

定义统一的账户接口,支持模拟账户和真实账户
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime

from .models import Position, OrderType
from .simulation_account import Transaction, AccountType


class BaseAccount(ABC):
    """
    账户抽象基类

    所有账户类型(模拟账户、真实账户)必须实现此接口
    """

    @property
    @abstractmethod
    def account_id(self) -> str:
        """
        账户ID

        Returns:
            账户唯一标识
        """
        pass

    @property
    @abstractmethod
    def account_type(self) -> AccountType:
        """
        账户类型

        Returns:
            SIMULATION(模拟账户) / PAPER(纸上交易) / LIVE(真实账户)
        """
        pass

    @abstractmethod
    def get_cash(self) -> float:
        """
        获取可用现金

        Returns:
            可用现金金额
        """
        pass

    @abstractmethod
    def get_positions(self) -> Dict[str, Position]:
        """
        获取所有持仓

        Returns:
            持仓字典 {symbol: Position}
        """
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        获取指定股票的持仓

        Args:
            symbol: 股票代码

        Returns:
            持仓信息,如果不存在返回None
        """
        pass

    @abstractmethod
    def buy(
        self,
        symbol: str,
        quantity: float,
        price: float,
        order_type: OrderType = OrderType.LIMIT,
        reason: str = ""
    ) -> Optional[Transaction]:
        """
        买入股票

        Args:
            symbol: 股票代码
            quantity: 买入数量
            price: 买入价格
            order_type: 订单类型(限价/市价)
            reason: 买入理由

        Returns:
            交易记录,如果失败返回None
        """
        pass

    @abstractmethod
    def sell(
        self,
        symbol: str,
        quantity: float,
        price: float,
        order_type: OrderType = OrderType.LIMIT,
        reason: str = ""
    ) -> Optional[Transaction]:
        """
        卖出股票

        Args:
            symbol: 股票代码
            quantity: 卖出数量
            price: 卖出价格
            order_type: 订单类型(限价/市价)
            reason: 卖出理由

        Returns:
            交易记录,如果失败返回None
        """
        pass

    @abstractmethod
    def get_total_value(self, prices: Optional[Dict[str, float]] = None) -> float:
        """
        获取账户总值

        Args:
            prices: 当前价格字典 {symbol: price},
                   如果为None则从市场获取最新价格

        Returns:
            账户总值(现金+持仓市值)
        """
        pass

    @abstractmethod
    def get_total_pnl(self, prices: Optional[Dict[str, float]] = None) -> float:
        """
        获取总盈亏

        Args:
            prices: 当前价格字典

        Returns:
            总盈亏金额
        """
        pass

    @abstractmethod
    def get_total_return(self, prices: Optional[Dict[str, float]] = None) -> float:
        """
        获取总收益率

        Args:
            prices: 当前价格字典

        Returns:
            总收益率(百分比)
        """
        pass

    @abstractmethod
    def get_summary(self, prices: Optional[Dict[str, float]] = None) -> dict:
        """
        获取账户摘要

        Args:
            prices: 当前价格字典

        Returns:
            账户摘要信息字典
        """
        pass

    @abstractmethod
    def save(self) -> None:
        """
        保存账户状态

        将账户状态持久化到存储
        """
        pass

    # 可选方法(子类可以选择实现)

    def sync_from_broker(self) -> bool:
        """
        从券商同步最新数据

        仅真实账户需要实现此方法

        Returns:
            同步是否成功
        """
        return True

    def get_orders(self) -> List[dict]:
        """
        获取订单列表

        Returns:
            订单列表
        """
        return []

    def cancel_order(self, order_id: str) -> bool:
        """
        取消订单

        Args:
            order_id: 订单ID

        Returns:
            取消是否成功
        """
        return False

    def get_transactions(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Transaction]:
        """
        获取交易记录

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            交易记录列表
        """
        return []


class AccountError(Exception):
    """账户操作异常"""
    pass


class InsufficientFundsError(AccountError):
    """资金不足异常"""
    pass


class InsufficientPositionError(AccountError):
    """持仓不足异常"""
    pass


class BrokerAPIError(AccountError):
    """券商API异常"""
    pass
