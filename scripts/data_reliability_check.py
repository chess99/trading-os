#!/usr/bin/env python3
"""
数据可靠性检查工具

快速检查系统数据可靠性状态，确保没有使用模拟数据
"""

import sys
from pathlib import Path

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))


def check_code_for_mock_data():
    """检查代码中是否存在模拟数据使用"""
    print("🔍 检查代码中的模拟数据使用...")

    # 危险的模拟数据标识
    dangerous_patterns = [
        "fallback_mock",
        "fallback_simulation",
        "fallback_default",
        "mock_data",
        "降级到模拟数据",
        "使用模拟数据",
        "current_price.*150.0",  # 常见的硬编码价格
        "current_price.*300.0",
    ]

    issues_found = []

    # 检查关键文件
    key_files = [
        "src/trading_os/agents/cli_integration.py",
        "src/trading_os/agents/skills/market_analysis.py",
        ".claude/skills/market-analysis/scripts/market_analysis.py",
        ".claude/skills/fund-management/scripts/portfolio_metrics.py"
    ]

    for file_path in key_files:
        full_path = repo_root / file_path
        if full_path.exists():
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                for i, line in enumerate(content.split('\n'), 1):
                    for pattern in dangerous_patterns:
                        if pattern.lower() in line.lower():
                            issues_found.append({
                                "file": file_path,
                                "line": i,
                                "content": line.strip(),
                                "pattern": pattern
                            })
            except Exception as e:
                print(f"❌ 无法检查文件 {file_path}: {e}")

    if issues_found:
        print(f"❌ 发现 {len(issues_found)} 个潜在的模拟数据使用:")
        for issue in issues_found:
            print(f"  📁 {issue['file']}:{issue['line']}")
            print(f"     模式: {issue['pattern']}")
            print(f"     内容: {issue['content']}")
            print()
        return False
    else:
        print("✅ 代码检查通过，未发现模拟数据使用")
        return True


def check_data_lake_status():
    """检查数据湖状态"""
    print("📊 检查数据湖状态...")

    try:
        from trading_os.agents.data_validation import DataIntegrityChecker

        checker = DataIntegrityChecker(repo_root)
        status = checker.check_data_lake_status()

        if status["data_lake_available"]:
            print(f"✅ 数据湖连接正常")
            print(f"📈 可用股票: {status['total_symbols']}")

            if status["total_symbols"] == 0:
                print("⚠️  警告: 数据湖为空，需要添加数据")
                return False

            # 检查数据时效性
            if status.get("last_update"):
                from datetime import datetime, timedelta
                try:
                    last_update = status["last_update"]
                    if isinstance(last_update, str):
                        last_update = datetime.fromisoformat(last_update.replace('Z', '+00:00'))

                    age = datetime.now().replace(tzinfo=last_update.tzinfo) - last_update
                    if age > timedelta(days=7):
                        print(f"⚠️  警告: 数据过期 ({age.days} 天前)")
                        return False
                    else:
                        print(f"✅ 数据时效性良好 (最后更新: {age.days} 天前)")
                except Exception as e:
                    print(f"⚠️  无法验证数据时效性: {e}")

            return True
        else:
            print(f"❌ 数据湖连接失败: {status.get('error', '未知错误')}")
            return False

    except Exception as e:
        print(f"❌ 数据湖检查失败: {e}")
        return False


def test_data_validation():
    """测试数据验证功能"""
    print("🧪 测试数据验证功能...")

    try:
        from trading_os.agents.data_validation import MarketDataValidator

        # 测试拒绝模拟数据
        mock_data = {
            "data_source": "fallback_mock",
            "prices": {"AAPL": {"current_price": 150.0}}
        }

        try:
            MarketDataValidator.validate_market_data(mock_data)
            print("❌ 数据验证器未能拒绝模拟数据")
            return False
        except Exception:
            print("✅ 数据验证器正确拒绝了模拟数据")
            return True

    except Exception as e:
        print(f"❌ 数据验证测试失败: {e}")
        return False


def main():
    """主函数"""
    print("🛡️  数据可靠性检查")
    print("=" * 50)

    all_checks_passed = True

    # 执行所有检查
    checks = [
        ("代码模拟数据检查", check_code_for_mock_data),
        ("数据湖状态检查", check_data_lake_status),
        ("数据验证功能测试", test_data_validation)
    ]

    for check_name, check_func in checks:
        print(f"\n🔍 {check_name}")
        print("-" * 30)

        try:
            result = check_func()
            if not result:
                all_checks_passed = False
        except Exception as e:
            print(f"❌ {check_name}失败: {e}")
            all_checks_passed = False

    print("\n" + "=" * 50)
    if all_checks_passed:
        print("✅ 所有数据可靠性检查通过")
        print("🎯 系统可以安全用于投资分析")
    else:
        print("❌ 数据可靠性检查失败")
        print("⚠️  请修复上述问题后再使用系统")
        print("📖 详见: docs/DATA_RELIABILITY_STANDARDS.md")

    return 0 if all_checks_passed else 1


if __name__ == '__main__':
    sys.exit(main())