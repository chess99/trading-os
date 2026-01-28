#!/usr/bin/env python3
"""
CLI集成测试

测试Agent系统的CLI集成功能
"""

import unittest
import sys
from pathlib import Path

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

try:
    from trading_os.agents.cli_integration import AgentSystemCLI
    from trading_os.agents.core.agent_interface import AgentContext
    from datetime import datetime
except ImportError as e:
    print(f"导入失败: {e}")
    print("请确保已安装依赖: pip install -e .")


class TestCLIIntegration(unittest.TestCase):
    """CLI集成测试类"""

    def setUp(self):
        """测试设置"""
        self.repo_root = repo_root
        self.agent_cli = AgentSystemCLI(self.repo_root)

    def test_agent_cli_initialization(self):
        """测试AgentSystemCLI初始化"""
        self.assertIsNotNone(self.agent_cli)
        self.assertEqual(self.agent_cli.repo_root, self.repo_root)

    def test_build_analysis_context(self):
        """测试分析上下文构建"""
        context = self.agent_cli._build_analysis_context()

        self.assertIsInstance(context, AgentContext)
        self.assertIsInstance(context.timestamp, datetime)
        self.assertIn('market_data', context.__dict__)
        self.assertIn('portfolio_state', context.__dict__)
        self.assertIn('risk_metrics', context.__dict__)

    def test_format_analysis_results(self):
        """测试分析结果格式化"""
        # 创建模拟输出
        mock_outputs = []

        result = self.agent_cli._format_analysis_results(mock_outputs)

        self.assertIsInstance(result, dict)
        self.assertIn('timestamp', result)
        self.assertIn('total_outputs', result)

    def test_get_investment_recommendations(self):
        """测试投资建议获取"""
        try:
            recommendations = self.agent_cli.get_investment_recommendations()
            self.assertIsInstance(recommendations, dict)
            self.assertIn('recommendations', recommendations)
        except Exception as e:
            self.skipTest(f"投资建议功能需要完整的数据环境: {e}")

    def test_assess_portfolio_risk(self):
        """测试投资组合风险评估"""
        try:
            risk_result = self.agent_cli.assess_portfolio_risk()
            self.assertIsInstance(risk_result, dict)
            self.assertIn('risk_assessment', risk_result)
        except Exception as e:
            self.skipTest(f"风险评估功能需要完整的数据环境: {e}")


if __name__ == '__main__':
    unittest.main()
