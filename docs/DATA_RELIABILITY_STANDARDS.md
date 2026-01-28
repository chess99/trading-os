# 数据可靠性标准

## ⚠️ 关键原则

**这是一个涉及资金的投资系统，数据可靠性是生命线。任何AI在开发和维护此系统时必须严格遵守以下原则。**

## 🚫 严格禁止的行为

### 1. 禁止使用模拟/假数据进行生产分析
```python
# ❌ 绝对禁止
market_data = {
    "prices": {
        "AAPL": {"current_price": 150.0, "change_pct": 0.02}  # 硬编码价格
    }
}

# ❌ 绝对禁止
def get_market_data():
    if data_source_fails:
        return mock_data  # 降级到模拟数据

# ✅ 正确做法
def get_market_data():
    if data_source_fails:
        raise DataValidationError("数据源失败，无法进行分析")
```

### 2. 禁止静默失败和数据降级
```python
# ❌ 绝对禁止
try:
    real_data = fetch_real_data()
except:
    real_data = fallback_mock_data  # 静默使用假数据

# ✅ 正确做法
try:
    real_data = fetch_real_data()
except Exception as e:
    raise RuntimeError(f"数据获取失败: {e}") from e
```

### 3. 禁止跳过数据验证
```python
# ❌ 绝对禁止
def analyze_market(data):
    # 直接使用数据，不验证来源和质量
    return analysis_result

# ✅ 正确做法
def analyze_market(data):
    ensure_data_quality(data)  # 必须先验证
    return analysis_result
```

## ✅ 必须遵守的标准

### 1. 数据源验证
- 所有数据必须标明来源 (`data_source` 字段)
- 禁止使用包含以下标识的数据源：
  - `fallback_mock`
  - `fallback_simulation`
  - `fallback_default`
  - `mock_data`
  - `synthetic` (除非明确用于测试)

### 2. 数据时效性
- 市场数据必须在7天内更新
- 超过7天的数据必须拒绝使用
- 必须验证数据时间戳的有效性

### 3. 数据完整性
- 价格数据不能为空或null
- 必须包含必要的字段 (open, high, low, close, volume)
- 数值必须合理 (价格 > 0, 成交量 >= 0)

### 4. 错误处理标准
- **失败快速**: 发现数据问题立即抛出异常
- **明确错误**: 具体说明什么数据出了什么问题
- **修复指导**: 告诉用户或下一个AI如何解决问题
- **诊断信息**: 提供详细的系统状态信息

## 🔧 强制使用的工具

### 1. 数据验证器
```python
from trading_os.agents.data_validation import ensure_data_quality

def process_market_data(context):
    # 强制验证 - 不可跳过
    ensure_data_quality(context)
    # 继续处理...
```

### 2. 数据状态检查
```bash
# 开发前必须检查数据状态
python -m trading_os agent status
```

### 3. 数据湖状态验证
```python
from trading_os.agents.data_validation import DataIntegrityChecker

checker = DataIntegrityChecker(repo_root)
status = checker.check_data_lake_status()
if not status["data_lake_available"]:
    raise RuntimeError("数据湖不可用")
```

## 📋 开发检查清单

在修改任何涉及数据的代码前，必须确认：

- [ ] 是否使用了真实数据源？
- [ ] 是否添加了数据验证？
- [ ] 是否正确处理了数据获取失败的情况？
- [ ] 是否提供了清晰的错误信息？
- [ ] 是否测试了数据缺失/过期的场景？
- [ ] 是否更新了相关的数据验证逻辑？

## 🚨 紧急情况处理

如果发现系统正在使用不可靠的数据：

1. **立即停止系统运行**
2. **检查数据来源和质量**
3. **修复数据问题**
4. **重新验证系统状态**
5. **记录问题和解决方案**

## 🛡️ 代码审查要求

任何涉及数据处理的代码变更必须：

1. **通过数据验证测试**
2. **包含错误处理测试**
3. **验证数据源标识**
4. **测试数据缺失场景**
5. **更新相关文档**

## 📞 求助指南

如果遇到无法自行解决的数据问题：

1. **运行诊断**: `python -m trading_os agent status`
2. **检查错误日志**: 查看详细的错误信息
3. **联系用户**: 提供具体的问题描述和诊断结果
4. **不要猜测**: 不要尝试绕过或忽略数据问题

## 🎯 目标

**确保每一个投资决策都基于真实、可靠、及时的市场数据，绝不允许因数据问题导致的错误投资决策。**

---

**记住：在金融系统中，一个数据错误可能导致巨大的财务损失。宁可系统停止运行，也不要使用不可靠的数据进行投资分析。**