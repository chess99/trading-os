#!/usr/bin/env python3
"""
配置系统测试

测试配置文件的完整性和有效性
"""

import json
import unittest
from pathlib import Path

import yaml


class TestConfigurationSystem(unittest.TestCase):
    """配置系统测试类"""

    def setUp(self):
        """测试设置"""
        self.repo_root = Path(__file__).parent.parent

    def test_claude_settings_json(self):
        """测试Claude设置文件"""
        settings_path = self.repo_root / ".claude" / "settings.json"

        if settings_path.exists():
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)

            # 检查必要的配置项
            self.assertIn('permissions', settings)
            self.assertIn('env', settings)

            # 检查权限配置
            permissions = settings['permissions']
            self.assertIsInstance(permissions, dict)
            self.assertIn('allow', permissions)
            self.assertIn('ask', permissions)
            self.assertIn('deny', permissions)

            # 检查环境变量配置
            env_vars = settings['env']
            self.assertIsInstance(env_vars, dict)
        else:
            self.skipTest("Claude设置文件不存在")

    def test_agent_config_yaml(self):
        """测试Agent配置文件"""
        config_path = self.repo_root / "configs" / "agent_config.yaml"

        self.assertTrue(config_path.exists(), "Agent配置文件不存在")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 检查必要的Agent配置
        required_agents = ['fund_manager', 'research_analyst', 'risk_manager', 'system_architect']

        for agent in required_agents:
            self.assertIn(agent, config, f"缺少{agent}配置")
            self.assertIsInstance(config[agent], dict)

        # 检查基金经理配置
        fund_manager = config['fund_manager']
        required_fund_params = ['max_single_position', 'max_sector_exposure', 'min_cash_buffer']

        for param in required_fund_params:
            self.assertIn(param, fund_manager, f"基金经理缺少{param}配置")

    def test_env_example_file(self):
        """测试环境变量示例文件"""
        env_example_path = self.repo_root / ".env.example"

        self.assertTrue(env_example_path.exists(), "环境变量示例文件不存在")

        with open(env_example_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查必要的环境变量配置
        required_vars = [
            'TRADING_OS_MODE',
            'LOG_LEVEL',
            'MAX_PORTFOLIO_RISK',
            'BACKTEST_INITIAL_CASH'
        ]

        for var in required_vars:
            self.assertIn(var, content, f"缺少环境变量{var}")

    def test_pyproject_toml(self):
        """测试项目配置文件"""
        pyproject_path = self.repo_root / "pyproject.toml"

        if pyproject_path.exists():
            with open(pyproject_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查基本的项目信息
            self.assertIn('[project]', content)
            self.assertIn('name = "trading-os"', content)
        else:
            self.skipTest("pyproject.toml文件不存在")


if __name__ == '__main__':
    unittest.main()
