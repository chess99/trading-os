# 账户系统集成指南

**版本**: 1.0
**日期**: 2026-01-30
**状态**: ✅ 设计完成,待实施

---

## 🎯 目标

建立统一的账户接口,支持:
1. **模拟账户** (已完成) - 用于测试和开发
2. **真实账户** (待对接) - 对接真实交易平台

---

## 📋 系统架构

### 当前架构

```
AccountManager (账户管理器)
    ├── SimulationAccount (模拟账户) ✅
    └── RealAccount (真实账户) ⏳
```

### 目标架构

```
AccountManager (账户管理器)
    ├── BaseAccount (抽象基类)
    │   ├── SimulationAccount (模拟账户) ✅
    │   ├── RealAccount (真实账户接口)
    │   │   ├── TonghuashunAccount (同花顺)
    │   │   ├── FutunnAccount (富途)
    │   │   └── XueqiuAccount (雪球)
    │   └── PaperAccount (纸上交易)
    └── AccountFactory (账户工厂)
```

---

## 🔧 统一账户接口

### BaseAccount 抽象接口

所有账户类型必须实现以下接口:

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime

class BaseAccount(ABC):
    """账户抽象基类"""

    @property
    @abstractmethod
    def account_id(self) -> str:
        """账户ID"""
        pass

    @property
    @abstractmethod
    def account_type(self) -> AccountType:
        """账户类型"""
        pass

    @abstractmethod
    def get_cash(self) -> float:
        """获取可用现金"""
        pass

    @abstractmethod
    def get_positions(self) -> Dict[str, Position]:
        """获取所有持仓"""
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        """获取指定股票持仓"""
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
        """买入股票"""
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
        """卖出股票"""
        pass

    @abstractmethod
    def get_total_value(self, prices: Optional[Dict[str, float]] = None) -> float:
        """获取账户总值"""
        pass

    @abstractmethod
    def get_summary(self, prices: Optional[Dict[str, float]] = None) -> dict:
        """获取账户摘要"""
        pass

    @abstractmethod
    def save(self) -> None:
        """保存账户状态"""
        pass
```

---

## 📱 真实账户对接

### 对接方案

#### 方案A: 同花顺 (推荐)

**优势**:
- 用户基数大
- 功能完善
- 有模拟交易功能
- API相对成熟

**API类型**:
- 同花顺iFind API (收费)
- 同花顺Level-2 API (收费)
- 第三方封装库 (easytrader)

**实施步骤**:
1. 研究同花顺API文档
2. 注册开发者账号
3. 申请API权限
4. 实现TonghuashunAccount类
5. 测试模拟交易
6. 逐步切换到真实交易

#### 方案B: 富途证券

**优势**:
- API文档完善
- 支持港股、美股、A股
- 有完整的Python SDK (futu-api)
- 模拟交易环境完善

**实施步骤**:
1. 注册富途账号
2. 下载FutuOpenD
3. 安装futu-api: `pip install futu-api`
4. 实现FutunnAccount类
5. 测试模拟交易

#### 方案C: 雪球

**优势**:
- 社区活跃
- 数据丰富
- 有组合跟踪功能

**限制**:
- 官方API较少
- 主要用于数据获取
- 交易功能有限

### 推荐方案

**短期**: 使用**easytrader**库对接同花顺模拟交易
- 开源免费
- 支持多个券商
- 社区活跃
- 快速上手

**中期**: 对接**富途证券**
- API完善
- 支持多市场
- 开发友好

**长期**: 根据实际需求选择最合适的券商

---

## 🔐 安全考虑

### 敏感信息管理

**绝不在代码中硬编码**:
- 账户密码
- API密钥
- 交易密码

**推荐方案**:

1. **环境变量**
```bash
export TRADING_ACCOUNT_ID="your_account"
export TRADING_API_KEY="your_api_key"
export TRADING_API_SECRET="your_secret"
```

2. **配置文件** (不提交到git)
```yaml
# config/trading_account.yaml (add to .gitignore)
account:
  broker: "tonghuashun"
  account_id: "your_account"
  api_key: "your_key"
  api_secret: "your_secret"
```

3. **密钥管理服务**
- 使用专业的密钥管理工具
- AWS Secrets Manager
- HashiCorp Vault

### 权限控制

**重要决策需要确认**:
- 大额交易(>10万)
- 高风险操作
- 账户设置变更

**实施方式**:
```python
class RealAccount(BaseAccount):
    def buy(self, symbol, quantity, price, ...):
        # 计算交易金额
        amount = quantity * price

        # 大额交易需要确认
        if amount > 100000:
            if not self.request_approval(
                f"买入 {symbol} x {quantity}, 金额 {amount:,.2f}"
            ):
                logger.warning("交易被拒绝")
                return None

        # 执行交易
        return self._execute_buy(...)
```

---

## 📊 数据同步

### 账户数据同步

**需要同步的数据**:
1. 持仓信息
2. 可用资金
3. 交易记录
4. 账户总值

**同步策略**:
- 实时同步: 交易后立即更新
- 定时同步: 每分钟/每小时更新
- 手动同步: 用户触发更新

### 数据一致性

**确保数据一致**:
```python
class RealAccount(BaseAccount):
    def sync_from_broker(self):
        """从券商同步最新数据"""
        # 获取最新持仓
        positions = self.broker_api.get_positions()

        # 获取最新资金
        cash = self.broker_api.get_cash()

        # 更新本地状态
        self._update_local_state(positions, cash)

        # 记录同步时间
        self.last_sync = datetime.now()
```

---

## 🧪 测试策略

### 测试阶段

**阶段1: 单元测试**
- 测试接口实现
- 模拟各种场景
- 错误处理

**阶段2: 模拟交易测试**
- 使用券商模拟账户
- 测试完整交易流程
- 验证数据同步

**阶段3: 小额真实交易**
- 使用小额资金测试
- 验证系统稳定性
- 积累经验

**阶段4: 正式交易**
- 逐步增加资金
- 持续监控
- 风险控制

### 测试用例

```python
def test_real_account_buy():
    """测试真实账户买入"""
    account = RealAccount(...)

    # 测试正常买入
    tx = account.buy("SSE:600000", 100, 10.0)
    assert tx is not None
    assert tx.quantity == 100

    # 测试资金不足
    tx = account.buy("SSE:600000", 1000000, 10.0)
    assert tx is None

    # 测试持仓更新
    position = account.get_position("SSE:600000")
    assert position.qty >= 100
```

---

## 📝 实施计划

### 短期 (1-2周)

1. **设计统一接口**
   - ✅ 定义BaseAccount抽象类
   - ✅ 文档化接口规范
   - ⏳ 重构SimulationAccount继承BaseAccount

2. **研究对接方案**
   - ⏳ 调研同花顺API
   - ⏳ 调研富途API
   - ⏳ 评估easytrader

3. **搭建测试环境**
   - ⏳ 注册模拟账户
   - ⏳ 配置开发环境
   - ⏳ 编写测试用例

### 中期 (2-4周)

4. **实现真实账户接口**
   - ⏳ 实现RealAccount基类
   - ⏳ 实现具体券商Account
   - ⏳ 数据同步机制

5. **集成测试**
   - ⏳ 模拟交易测试
   - ⏳ 数据同步测试
   - ⏳ 错误处理测试

6. **安全加固**
   - ⏳ 密钥管理
   - ⏳ 权限控制
   - ⏳ 审计日志

### 长期 (1-2月)

7. **小额真实交易**
   - ⏳ 使用小额资金测试
   - ⏳ 监控系统表现
   - ⏳ 优化和改进

8. **逐步扩大规模**
   - ⏳ 增加交易资金
   - ⏳ 扩展交易策略
   - ⏳ 持续优化

---

## 🔗 相关资源

### API文档

- **同花顺**: https://www.10jqka.com.cn/
- **富途**: https://openapi.futunn.com/
- **easytrader**: https://github.com/shidenggui/easytrader

### Python库

```bash
# 富途API
pip install futu-api

# easytrader (支持多券商)
pip install easytrader

# 数据获取
pip install akshare tushare
```

### 示例代码

**富途API示例**:
```python
from futu import *

# 连接FutuOpenD
quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)

# 获取股票报价
ret, data = quote_ctx.get_market_snapshot(['HK.00700'])
if ret == RET_OK:
    print(data)

quote_ctx.close()
```

**easytrader示例**:
```python
import easytrader

# 使用同花顺
user = easytrader.use('ths')

# 登录 (需要配置文件)
user.prepare('ths.json')

# 获取资金
balance = user.balance

# 买入股票
user.buy('162411', price=0.55, amount=100)
```

---

## ⚠️ 风险提示

1. **API稳定性**
   - 券商API可能变更
   - 需要持续维护
   - 准备备用方案

2. **交易风险**
   - 充分测试再上线
   - 小额资金开始
   - 设置止损机制

3. **合规风险**
   - 遵守券商规定
   - 注意交易频率限制
   - 避免违规操作

4. **技术风险**
   - 网络故障
   - 系统bug
   - 数据不一致

---

## 🎉 总结

本指南提供了完整的真实账户对接方案:

✅ 统一的账户接口设计
✅ 多个对接方案对比
✅ 安全和测试策略
✅ 详细的实施计划

**下一步**:
1. 研究选定的券商API
2. 搭建测试环境
3. 实现真实账户接口
4. 充分测试后上线

**系统已经具备对接真实账户的基础!**

---

**Trading OS - 基金管理AI系统**
**为真实投资做好准备!** 🚀
