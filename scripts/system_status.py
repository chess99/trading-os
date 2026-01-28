#!/usr/bin/env python3
"""
系统状态脚本

快速显示系统状态和关键信息，为Claude实例提供上下文
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))


def print_header():
    """打印系统标题"""
    print("=" * 60)
    print("🏦 Trading OS - 基金管理AI系统")
    print("=" * 60)
    print(f"📅 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 项目路径: {repo_root}")
    print()


def print_system_architecture():
    """打印系统架构"""
    print("🏗️ 系统架构:")
    print("├── Claude Code标准架构")
    print("│   ├── Skills: fund-management, market-analysis")
    print("│   └── Sub-agents: system-architect, fund-manager, research-analyst, risk-manager")
    print("├── Trading OS基础架构")
    print("│   ├── 数据层: DuckDB数据湖 + 多源数据适配")
    print("│   ├── 分析层: 技术分析 + 基本面分析")
    print("│   ├── 决策层: AI投资决策 + 风险管理")
    print("│   └── 执行层: 回测引擎 + 纸交易")
    print()


def print_available_commands():
    """打印可用命令"""
    print("⚡ 快速命令:")
    print("📊 市场分析:")
    print("  python .claude/skills/market-analysis/scripts/market_analysis.py")
    print()
    print("💼 投资组合管理:")
    print("  python .claude/skills/fund-management/scripts/portfolio_metrics.py")
    print("  python .claude/skills/fund-management/scripts/comprehensive_analysis.py")
    print()
    print("🔧 系统维护:")
    print("  python scripts/system_maintenance.py")
    print("  python tests/run_tests.py")
    print()
    print("📈 传统CLI:")
    print("  python -m trading_os agent daily")
    print("  python -m trading_os agent recommend")
    print("  python -m trading_os agent risk")
    print()


def print_role_guidance():
    """打印角色指导"""
    print("🎭 AI角色指导:")
    print()
    print("如果用户需要技术架构和系统开发:")
    print("  👤 角色: 首席技术官(CTO) + 系统架构师")
    print("  🎯 职责: 系统设计、技术决策、代码实现")
    print("  🔧 权限: 修改代码、架构设计、技术选型")
    print()
    print("如果用户需要投资管理和决策:")
    print("  👤 角色: 专业基金经理")
    print("  🎯 职责: 投资决策、风险管理、市场分析")
    print("  📊 权限: 独立投资分析和决策")
    print()
    print("💡 协作原则:")
    print("  - 数据驱动的决策")
    print("  - 风险优先的管理")
    print("  - 主动汇报和专业建议")
    print("  - 重大决策寻求董事长确认")
    print()


def check_system_health():
    """检查系统健康状况"""
    print("🏥 系统健康检查:")

    # 检查关键目录
    critical_paths = [
        (".claude", "Claude配置"),
        ("src/trading_os", "核心代码"),
        ("tests", "测试套件"),
        ("configs", "配置文件")
    ]

    for path, description in critical_paths:
        full_path = repo_root / path
        status = "✅" if full_path.exists() else "❌"
        print(f"  {status} {description}: {path}")

    # 检查关键文件
    critical_files = [
        (".claude/settings.json", "Claude设置"),
        (".claude/CLAUDE.md", "系统身份"),
        ("configs/agent_config.yaml", "Agent配置"),
        (".env.example", "环境变量模板")
    ]

    for file_path, description in critical_files:
        full_path = repo_root / file_path
        status = "✅" if full_path.exists() else "❌"
        print(f"  {status} {description}: {file_path}")

    print()


def print_recent_activity():
    """打印最近活动"""
    print("📋 最近活动:")

    # 检查维护报告
    maintenance_report = repo_root / "artifacts" / "maintenance_report.md"
    if maintenance_report.exists():
        mtime = datetime.fromtimestamp(maintenance_report.stat().st_mtime)
        print(f"  📄 最后维护: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

    # 检查测试状态
    test_runner = repo_root / "tests" / "run_tests.py"
    if test_runner.exists():
        print(f"  🧪 测试套件: 可用")

    print()


def main():
    """主函数"""
    print_header()
    print_system_architecture()
    print_available_commands()
    print_role_guidance()
    check_system_health()
    print_recent_activity()

    print("🚀 系统就绪！请根据用户需求选择合适的角色和工具。")
    print("=" * 60)


if __name__ == '__main__':
    main()
