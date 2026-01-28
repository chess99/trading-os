#!/usr/bin/env python3
"""
Skills系统测试

测试fund-management和market-analysis技能包
"""

import unittest
import sys
from pathlib import Path
import subprocess

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))


class TestSkillsSystem(unittest.TestCase):
    """Skills系统测试类"""

    def setUp(self):
        """测试设置"""
        self.repo_root = repo_root
        self.skills_dir = self.repo_root / ".claude" / "skills"

    def test_skills_directory_structure(self):
        """测试Skills目录结构"""
        self.assertTrue(self.skills_dir.exists())

        # 检查必要的技能包
        fund_management_dir = self.skills_dir / "fund-management"
        market_analysis_dir = self.skills_dir / "market-analysis"

        self.assertTrue(fund_management_dir.exists())
        self.assertTrue(market_analysis_dir.exists())

    def test_market_analysis_script(self):
        """测试市场分析脚本"""
        script_path = self.skills_dir / "market-analysis" / "scripts" / "market_analysis.py"

        if script_path.exists():
            # 测试脚本是否可以执行（不会实际运行，只检查语法）
            result = subprocess.run([
                sys.executable, "-m", "py_compile", str(script_path)
            ], capture_output=True, text=True)

            self.assertEqual(result.returncode, 0,
                           f"市场分析脚本语法错误: {result.stderr}")
        else:
            self.skipTest("市场分析脚本不存在")

    def test_portfolio_metrics_script(self):
        """测试投资组合指标脚本"""
        script_path = self.skills_dir / "fund-management" / "scripts" / "portfolio_metrics.py"

        if script_path.exists():
            # 测试脚本语法
            result = subprocess.run([
                sys.executable, "-m", "py_compile", str(script_path)
            ], capture_output=True, text=True)

            self.assertEqual(result.returncode, 0,
                           f"投资组合脚本语法错误: {result.stderr}")
        else:
            self.skipTest("投资组合脚本不存在")

    def test_comprehensive_analysis_script(self):
        """测试综合分析脚本"""
        script_path = self.skills_dir / "fund-management" / "scripts" / "comprehensive_analysis.py"

        if script_path.exists():
            # 测试脚本语法
            result = subprocess.run([
                sys.executable, "-m", "py_compile", str(script_path)
            ], capture_output=True, text=True)

            self.assertEqual(result.returncode, 0,
                           f"综合分析脚本语法错误: {result.stderr}")
        else:
            self.skipTest("综合分析脚本不存在")


if __name__ == '__main__':
    unittest.main()
