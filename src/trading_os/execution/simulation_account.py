"""
模拟交易账户系统

提供与真实账户隔离的模拟交易环境，用于策略测试和AI决策
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from enum import Enum

from .models import Order, OrderSide, OrderStatus, Fill, Position
from .portfolio import Portfolio

logger = logging.getLogger(__name__)


class AccountType(str, Enum):
    """账户类型"""
    SIMULATION = "SIMULATION"  # 模拟账户
    PAPER = "PAPER"           # 纸上交易
    LIVE = "LIVE"             # 真实账户


@dataclass
class Transaction:
    """交易记录"""
    transaction_id: str
    timestamp: datetime
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    fee: float
    amount: float  # 交易金额
    cash_before: float
    cash_after: float
    reason: str = ""  # 交易理由

    def to_dict(self) -> dict:
        """转换为字典"""
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        d['side'] = self.side.value
        return d


@dataclass
class AccountSnapshot:
    """账户快照"""
    timestamp: datetime
    cash: float
    positions: Dict[str, Position]
    total_value: float
    total_pnl: float
    total_return: float

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'cash': self.cash,
            'positions': {
                symbol: {
                    'symbol': pos.symbol,
                    'qty': pos.qty,
                    'avg_price': pos.avg_price,
                    'entry_ts': pos.entry_ts.isoformat() if pos.entry_ts else None
                }
                for symbol, pos in self.positions.items()
            },
            'total_value': self.total_value,
            'total_pnl': self.total_pnl,
            'total_return': self.total_return
        }


class SimulationAccount:
    """
    模拟交易账户

    功能:
    1. 独立的虚拟本金管理
    2. 完整的交易记录
    3. 持仓和盈亏计算
    4. 账户快照和历史
    5. 与真实账户完全隔离
    """

    def __init__(
        self,
        account_id: str,
        initial_cash: float,
        data_dir: Path,
        fee_rate: float = 0.0003,  # A股默认手续费0.03%
        min_fee: float = 5.0,       # 最低手续费5元
    ):
        """
        初始化模拟账户

        Args:
            account_id: 账户ID
            initial_cash: 初始资金
            data_dir: 数据存储目录
            fee_rate: 手续费率
            min_fee: 最低手续费
        """
        self.account_id = account_id
        self.account_type = AccountType.SIMULATION
        self.initial_cash = float(initial_cash)
        self.fee_rate = fee_rate
        self.min_fee = min_fee

        # 账户状态
        self.portfolio = Portfolio.with_cash(initial_cash)
        self.created_at = datetime.now()
        self.last_update = datetime.now()

        # 交易历史
        self.transactions: List[Transaction] = []
        self.snapshots: List[AccountSnapshot] = []

        # 数据持久化
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.account_file = self.data_dir / f"{account_id}.json"
        self.transactions_file = self.data_dir / f"{account_id}_transactions.jsonl"
        self.snapshots_file = self.data_dir / f"{account_id}_snapshots.jsonl"

        logger.info(
            f"创建模拟账户: {account_id}, "
            f"初始资金: {initial_cash:,.2f}, "
            f"手续费率: {fee_rate:.4%}"
        )

    def get_cash(self) -> float:
        """获取当前现金"""
        return self.portfolio.cash

    def get_positions(self) -> Dict[str, Position]:
        """获取当前持仓"""
        return self.portfolio.positions.copy()

    def get_position(self, symbol: str) -> Optional[Position]:
        """获取指定股票的持仓"""
        return self.portfolio.position(symbol)

    def get_total_value(self, prices: Dict[str, float]) -> float:
        """
        获取账户总价值

        Args:
            prices: 当前价格字典 {symbol: price}
        """
        return self.portfolio.equity(prices)

    def get_total_pnl(self, prices: Dict[str, float]) -> float:
        """
        获取总盈亏

        Args:
            prices: 当前价格字典
        """
        total_value = self.get_total_value(prices)
        return total_value - self.initial_cash

    def get_total_return(self, prices: Dict[str, float]) -> float:
        """
        获取总收益率

        Args:
            prices: 当前价格字典
        """
        total_pnl = self.get_total_pnl(prices)
        return total_pnl / self.initial_cash if self.initial_cash > 0 else 0.0

    def calculate_fee(self, amount: float) -> float:
        """
        计算交易手续费

        Args:
            amount: 交易金额
        """
        fee = amount * self.fee_rate
        return max(fee, self.min_fee)

    def buy(
        self,
        symbol: str,
        quantity: float,
        price: float,
        reason: str = ""
    ) -> Optional[Transaction]:
        """
        买入股票

        Args:
            symbol: 股票代码
            quantity: 数量
            price: 价格
            reason: 买入理由

        Returns:
            交易记录，如果失败返回None
        """
        # A股买入必须是100股的整数倍
        if quantity % 100 != 0:
            logger.warning(f"买入数量必须是100的整数倍: {quantity}")
            quantity = int(quantity / 100) * 100
            if quantity == 0:
                logger.error("买入数量不足100股")
                return None

        # 计算交易金额和手续费
        amount = quantity * price
        fee = self.calculate_fee(amount)
        total_cost = amount + fee

        # 检查资金是否充足
        if total_cost > self.portfolio.cash:
            logger.error(
                f"资金不足: 需要 {total_cost:,.2f}, "
                f"可用 {self.portfolio.cash:,.2f}"
            )
            return None

        # 创建成交记录
        fill = Fill(
            order_id=f"SIM_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            ts=datetime.now(),
            symbol=symbol,
            side=OrderSide.BUY,
            qty=quantity,
            price=price,
            fee=fee,
            slippage_bps=0.0
        )

        # 更新投资组合
        cash_before = self.portfolio.cash
        self.portfolio.apply_fill(fill)
        cash_after = self.portfolio.cash

        # 创建交易记录
        transaction = Transaction(
            transaction_id=fill.order_id,
            timestamp=fill.ts,
            symbol=symbol,
            side=OrderSide.BUY,
            quantity=quantity,
            price=price,
            fee=fee,
            amount=amount,
            cash_before=cash_before,
            cash_after=cash_after,
            reason=reason
        )

        self.transactions.append(transaction)
        self.last_update = datetime.now()

        # 持久化交易记录
        self._save_transaction(transaction)

        logger.info(
            f"买入成功: {symbol} x {quantity} @ {price:.2f}, "
            f"金额: {amount:,.2f}, 手续费: {fee:.2f}, "
            f"剩余现金: {cash_after:,.2f}"
        )

        return transaction

    def sell(
        self,
        symbol: str,
        quantity: float,
        price: float,
        reason: str = ""
    ) -> Optional[Transaction]:
        """
        卖出股票

        Args:
            symbol: 股票代码
            quantity: 数量
            price: 价格
            reason: 卖出理由

        Returns:
            交易记录，如果失败返回None
        """
        # 检查持仓
        position = self.portfolio.position(symbol)
        if position is None or position.qty < quantity:
            available_qty = position.qty if position else 0
            logger.error(
                f"持仓不足: {symbol}, "
                f"需要 {quantity}, 可用 {available_qty}"
            )
            return None

        # A股卖出必须是100股的整数倍（最后不足100股可以一次性卖出）
        if quantity % 100 != 0 and quantity != position.qty:
            logger.warning(f"卖出数量必须是100的整数倍或全部卖出: {quantity}")
            quantity = int(quantity / 100) * 100
            if quantity == 0:
                logger.error("卖出数量不足100股")
                return None

        # 计算交易金额和手续费
        amount = quantity * price
        fee = self.calculate_fee(amount)
        # A股卖出还需要缴纳印花税0.1%
        stamp_tax = amount * 0.001
        total_fee = fee + stamp_tax
        proceeds = amount - total_fee

        # 创建成交记录
        fill = Fill(
            order_id=f"SIM_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            ts=datetime.now(),
            symbol=symbol,
            side=OrderSide.SELL,
            qty=quantity,
            price=price,
            fee=total_fee,
            slippage_bps=0.0
        )

        # 更新投资组合
        cash_before = self.portfolio.cash
        self.portfolio.apply_fill(fill)
        cash_after = self.portfolio.cash

        # 创建交易记录
        transaction = Transaction(
            transaction_id=fill.order_id,
            timestamp=fill.ts,
            symbol=symbol,
            side=OrderSide.SELL,
            quantity=quantity,
            price=price,
            fee=total_fee,
            amount=amount,
            cash_before=cash_before,
            cash_after=cash_after,
            reason=reason
        )

        self.transactions.append(transaction)
        self.last_update = datetime.now()

        # 持久化交易记录
        self._save_transaction(transaction)

        logger.info(
            f"卖出成功: {symbol} x {quantity} @ {price:.2f}, "
            f"金额: {amount:,.2f}, 手续费: {total_fee:.2f}, "
            f"现金: {cash_after:,.2f}"
        )

        return transaction

    def take_snapshot(self, prices: Dict[str, float]) -> AccountSnapshot:
        """
        创建账户快照

        Args:
            prices: 当前价格字典
        """
        snapshot = AccountSnapshot(
            timestamp=datetime.now(),
            cash=self.portfolio.cash,
            positions=self.portfolio.positions.copy(),
            total_value=self.get_total_value(prices),
            total_pnl=self.get_total_pnl(prices),
            total_return=self.get_total_return(prices)
        )

        self.snapshots.append(snapshot)
        self._save_snapshot(snapshot)

        return snapshot

    def get_summary(self, prices: Dict[str, float]) -> dict:
        """
        获取账户摘要

        Args:
            prices: 当前价格字典
        """
        total_value = self.get_total_value(prices)
        total_pnl = self.get_total_pnl(prices)
        total_return = self.get_total_return(prices)

        # 计算持仓市值
        position_value = total_value - self.portfolio.cash

        # 持仓详情
        positions_detail = []
        for symbol, pos in self.portfolio.positions.items():
            current_price = prices.get(symbol, 0.0)
            market_value = pos.qty * current_price
            cost = pos.qty * pos.avg_price
            pnl = market_value - cost
            pnl_ratio = pnl / cost if cost > 0 else 0.0

            positions_detail.append({
                'symbol': symbol,
                'quantity': pos.qty,
                'avg_price': pos.avg_price,
                'current_price': current_price,
                'cost': cost,
                'market_value': market_value,
                'pnl': pnl,
                'pnl_ratio': pnl_ratio,
                'weight': market_value / total_value if total_value > 0 else 0.0
            })

        # 按持仓市值排序
        positions_detail.sort(key=lambda x: x['market_value'], reverse=True)

        return {
            'account_id': self.account_id,
            'account_type': self.account_type.value,
            'created_at': self.created_at.isoformat(),
            'last_update': self.last_update.isoformat(),
            'initial_cash': self.initial_cash,
            'current_cash': self.portfolio.cash,
            'position_value': position_value,
            'total_value': total_value,
            'total_pnl': total_pnl,
            'total_return': total_return,
            'position_count': len(self.portfolio.positions),
            'transaction_count': len(self.transactions),
            'positions': positions_detail
        }

    def _save_transaction(self, transaction: Transaction) -> None:
        """保存交易记录"""
        try:
            with open(self.transactions_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(transaction.to_dict(), ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"保存交易记录失败: {e}")

    def _save_snapshot(self, snapshot: AccountSnapshot) -> None:
        """保存账户快照"""
        try:
            with open(self.snapshots_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(snapshot.to_dict(), ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"保存账户快照失败: {e}")

    def save(self) -> None:
        """保存账户状态"""
        try:
            account_data = {
                'account_id': self.account_id,
                'account_type': self.account_type.value,
                'initial_cash': self.initial_cash,
                'current_cash': self.portfolio.cash,
                'fee_rate': self.fee_rate,
                'min_fee': self.min_fee,
                'created_at': self.created_at.isoformat(),
                'last_update': self.last_update.isoformat(),
                'positions': {
                    symbol: {
                        'symbol': pos.symbol,
                        'qty': pos.qty,
                        'avg_price': pos.avg_price,
                        'entry_ts': pos.entry_ts.isoformat() if pos.entry_ts else None
                    }
                    for symbol, pos in self.portfolio.positions.items()
                }
            }

            with open(self.account_file, 'w', encoding='utf-8') as f:
                json.dump(account_data, f, ensure_ascii=False, indent=2)

            logger.info(f"账户状态已保存: {self.account_file}")
        except Exception as e:
            logger.error(f"保存账户状态失败: {e}")

    @classmethod
    def load(cls, account_id: str, data_dir: Path) -> Optional[SimulationAccount]:
        """
        加载账户

        Args:
            account_id: 账户ID
            data_dir: 数据目录
        """
        account_file = data_dir / f"{account_id}.json"

        if not account_file.exists():
            logger.warning(f"账户文件不存在: {account_file}")
            return None

        try:
            with open(account_file, 'r', encoding='utf-8') as f:
                account_data = json.load(f)

            # 创建账户实例
            account = cls(
                account_id=account_data['account_id'],
                initial_cash=account_data['initial_cash'],
                data_dir=data_dir,
                fee_rate=account_data.get('fee_rate', 0.0003),
                min_fee=account_data.get('min_fee', 5.0)
            )

            # 恢复现金
            account.portfolio.cash = account_data['current_cash']

            # 恢复持仓
            for symbol, pos_data in account_data.get('positions', {}).items():
                entry_ts = None
                if pos_data.get('entry_ts'):
                    entry_ts = datetime.fromisoformat(pos_data['entry_ts'])

                account.portfolio.positions[symbol] = Position(
                    symbol=pos_data['symbol'],
                    qty=pos_data['qty'],
                    avg_price=pos_data['avg_price'],
                    entry_ts=entry_ts
                )

            # 恢复时间戳
            account.created_at = datetime.fromisoformat(account_data['created_at'])
            account.last_update = datetime.fromisoformat(account_data['last_update'])

            logger.info(f"账户加载成功: {account_id}")
            return account

        except Exception as e:
            logger.error(f"加载账户失败: {e}")
            return None
