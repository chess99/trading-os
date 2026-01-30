"""
账户管理器

统一管理模拟账户和真实账户
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

from .simulation_account import SimulationAccount

logger = logging.getLogger(__name__)


class AccountManager:
    """
    账户管理器

    功能:
    1. 管理多个账户
    2. 提供统一的账户访问接口
    3. 支持模拟账户和真实账户
    4. 账户持久化和恢复
    """

    def __init__(self, data_dir: Path):
        """
        初始化账户管理器

        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = data_dir / "accounts"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.accounts: Dict[str, SimulationAccount] = {}
        self._load_all_accounts()

        logger.info(f"账户管理器初始化完成，数据目录: {self.data_dir}")

    def create_simulation_account(
        self,
        account_id: str,
        initial_cash: float,
        fee_rate: float = 0.0003,
        min_fee: float = 5.0,
        overwrite: bool = False
    ) -> SimulationAccount:
        """
        创建模拟账户

        Args:
            account_id: 账户ID
            initial_cash: 初始资金
            fee_rate: 手续费率
            min_fee: 最低手续费
            overwrite: 是否覆盖已存在的账户

        Returns:
            模拟账户实例
        """
        if account_id in self.accounts and not overwrite:
            logger.warning(f"账户已存在: {account_id}")
            return self.accounts[account_id]

        account = SimulationAccount(
            account_id=account_id,
            initial_cash=initial_cash,
            data_dir=self.data_dir,
            fee_rate=fee_rate,
            min_fee=min_fee
        )

        self.accounts[account_id] = account
        account.save()

        logger.info(f"创建模拟账户: {account_id}, 初始资金: {initial_cash:,.2f}")
        return account

    def get_account(self, account_id: str) -> Optional[SimulationAccount]:
        """
        获取账户

        Args:
            account_id: 账户ID

        Returns:
            账户实例，如果不存在返回None
        """
        return self.accounts.get(account_id)

    def list_accounts(self) -> Dict[str, dict]:
        """
        列出所有账户

        Returns:
            账户信息字典
        """
        return {
            account_id: {
                'account_id': account.account_id,
                'account_type': account.account_type.value,
                'initial_cash': account.initial_cash,
                'current_cash': account.get_cash(),
                'created_at': account.created_at.isoformat(),
                'last_update': account.last_update.isoformat()
            }
            for account_id, account in self.accounts.items()
        }

    def save_all_accounts(self) -> None:
        """保存所有账户"""
        for account in self.accounts.values():
            account.save()
        logger.info(f"已保存 {len(self.accounts)} 个账户")

    def _load_all_accounts(self) -> None:
        """加载所有账户"""
        if not self.data_dir.exists():
            return

        # 查找所有账户文件
        account_files = list(self.data_dir.glob("*.json"))
        account_files = [
            f for f in account_files
            if not f.name.endswith('_transactions.jsonl')
            and not f.name.endswith('_snapshots.jsonl')
        ]

        for account_file in account_files:
            account_id = account_file.stem
            account = SimulationAccount.load(account_id, self.data_dir)
            if account:
                self.accounts[account_id] = account

        logger.info(f"加载了 {len(self.accounts)} 个账户")


def get_default_account_manager() -> AccountManager:
    """
    获取默认账户管理器

    Returns:
        账户管理器实例
    """
    from pathlib import Path
    data_dir = Path.cwd() / "data"
    return AccountManager(data_dir)


def initialize_default_simulation_account(
    initial_cash: float = 500000.0,
    overwrite: bool = False
) -> SimulationAccount:
    """
    初始化默认模拟账户

    Args:
        initial_cash: 初始资金，默认50万
        overwrite: 是否覆盖已存在的账户

    Returns:
        模拟账户实例
    """
    manager = get_default_account_manager()
    account = manager.create_simulation_account(
        account_id="default_simulation",
        initial_cash=initial_cash,
        overwrite=overwrite
    )

    logger.info(
        f"默认模拟账户已初始化: "
        f"账户ID={account.account_id}, "
        f"初始资金={initial_cash:,.2f}"
    )

    return account


def get_default_simulation_account() -> Optional[SimulationAccount]:
    """
    获取默认模拟账户

    Returns:
        模拟账户实例，如果不存在返回None
    """
    manager = get_default_account_manager()
    account = manager.get_account("default_simulation")

    if account is None:
        logger.warning("默认模拟账户不存在，请先初始化")
        return None

    return account
