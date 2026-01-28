#!/usr/bin/env python3
"""
测试运行器

统一执行所有测试并生成报告
"""

import unittest
import sys
from pathlib import Path

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

def run_all_tests():
    """运行所有测试"""
    # 直接导入测试模块
    test_modules = [
        'test_agent_system',
        'test_cli_integration',
        'test_skills',
        'test_configuration'
    ]

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 加载每个测试模块
    for module_name in test_modules:
        try:
            module = __import__(module_name, fromlist=[''])
            suite.addTests(loader.loadTestsFromModule(module))
        except ImportError as e:
            print(f"警告: 无法导入测试模块 {module_name}: {e}")
            continue

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出结果摘要
    print("\n" + "="*60)
    print("测试结果摘要:")
    print(f"总测试数: {result.testsRun}")
    print(f"失败数: {len(result.failures)}")
    print(f"错误数: {len(result.errors)}")
    print(f"跳过数: {len(result.skipped)}")

    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('\\n')[-2]}")

    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split('\\n')[-2]}")

    print("="*60)

    # 返回是否所有测试都通过
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
