#!/usr/bin/env python3
"""
系统维护脚本

定期检查系统健康状况，清理无用文件，确保仓库整洁
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

# 添加项目路径
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))


class SystemMaintenance:
    """系统维护类"""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.report = []

    def log(self, message: str, level: str = "INFO"):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        self.report.append(log_entry)

    def check_directory_structure(self):
        """检查目录结构完整性"""
        self.log("检查目录结构完整性...")

        required_dirs = [
            ".claude",
            ".claude/skills",
            ".claude/agents",
            "src/trading_os",
            "tests",
            "configs",
            "artifacts",
            "docs"
        ]

        missing_dirs = []
        for dir_path in required_dirs:
            full_path = self.repo_root / dir_path
            if not full_path.exists():
                missing_dirs.append(dir_path)

        if missing_dirs:
            self.log(f"发现缺失目录: {missing_dirs}", "WARNING")
            return False
        else:
            self.log("目录结构检查通过")
            return True

    def check_configuration_files(self):
        """检查配置文件完整性"""
        self.log("检查配置文件完整性...")

        required_configs = [
            ".claude/settings.json",
            ".claude/CLAUDE.md",
            "configs/agent_config.yaml",
            ".env.example",
            "pyproject.toml"
        ]

        missing_configs = []
        for config_path in required_configs:
            full_path = self.repo_root / config_path
            if not full_path.exists():
                missing_configs.append(config_path)

        if missing_configs:
            self.log(f"发现缺失配置文件: {missing_configs}", "WARNING")
            return False
        else:
            self.log("配置文件检查通过")
            return True

    def clean_temporary_files(self):
        """清理临时文件"""
        self.log("清理临时文件...")

        temp_patterns = [
            "**/__pycache__",
            "**/*.pyc",
            "**/*.pyo",
            "**/.DS_Store",
            "**/Thumbs.db",
            "temp/**",
            "tmp/**",
            "**/*.tmp"
        ]

        cleaned_files = []
        for pattern in temp_patterns:
            for file_path in self.repo_root.glob(pattern):
                if file_path.exists():
                    if file_path.is_file():
                        file_path.unlink()
                        cleaned_files.append(str(file_path.relative_to(self.repo_root)))
                    elif file_path.is_dir() and file_path.name in ['__pycache__', 'temp', 'tmp']:
                        import shutil
                        shutil.rmtree(file_path)
                        cleaned_files.append(str(file_path.relative_to(self.repo_root)))

        if cleaned_files:
            self.log(f"清理了 {len(cleaned_files)} 个临时文件/目录")
        else:
            self.log("没有发现需要清理的临时文件")

        return cleaned_files

    def check_code_quality(self):
        """检查代码质量"""
        self.log("检查代码质量...")

        try:
            # 检查Python语法
            result = subprocess.run([
                sys.executable, "-m", "py_compile",
                str(self.repo_root / "src" / "trading_os" / "cli.py")
            ], capture_output=True, text=True)

            if result.returncode == 0:
                self.log("核心代码语法检查通过")
                return True
            else:
                self.log(f"代码语法错误: {result.stderr}", "ERROR")
                return False

        except Exception as e:
            self.log(f"代码质量检查失败: {e}", "ERROR")
            return False

    def run_tests(self):
        """运行测试套件"""
        self.log("运行测试套件...")

        try:
            result = subprocess.run([
                sys.executable, str(self.repo_root / "tests" / "run_tests.py")
            ], capture_output=True, text=True, cwd=str(self.repo_root))

            if result.returncode == 0:
                self.log("所有测试通过")
                return True
            else:
                self.log(f"测试失败: {result.stderr}", "ERROR")
                return False

        except Exception as e:
            self.log(f"测试运行失败: {e}", "ERROR")
            return False

    def check_git_status(self):
        """检查Git状态"""
        self.log("检查Git状态...")

        try:
            # 检查是否有未提交的更改
            result = subprocess.run([
                "git", "status", "--porcelain"
            ], capture_output=True, text=True, cwd=str(self.repo_root))

            if result.returncode == 0:
                if result.stdout.strip():
                    self.log("发现未提交的更改", "INFO")
                    return False
                else:
                    self.log("工作目录干净")
                    return True
            else:
                self.log(f"Git状态检查失败: {result.stderr}", "ERROR")
                return False

        except Exception as e:
            self.log(f"Git状态检查失败: {e}", "ERROR")
            return False

    def generate_maintenance_report(self):
        """生成维护报告"""
        self.log("生成维护报告...")

        report_path = self.repo_root / "artifacts" / "maintenance_report.md"
        report_path.parent.mkdir(exist_ok=True)

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# 系统维护报告\n\n")
            f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"## 维护日志\n\n")

            for entry in self.report:
                f.write(f"- {entry}\n")

        self.log(f"维护报告已保存到: {report_path}")

    def run_full_maintenance(self):
        """运行完整维护流程"""
        self.log("开始系统维护...")

        checks = [
            self.check_directory_structure,
            self.check_configuration_files,
            self.check_code_quality,
            self.run_tests,
            self.check_git_status
        ]

        all_passed = True
        for check in checks:
            if not check():
                all_passed = False

        # 清理临时文件
        self.clean_temporary_files()

        # 生成报告
        self.generate_maintenance_report()

        if all_passed:
            self.log("系统维护完成，所有检查通过", "SUCCESS")
        else:
            self.log("系统维护完成，发现问题需要处理", "WARNING")

        return all_passed


def main():
    """主函数"""
    maintenance = SystemMaintenance(repo_root)
    success = maintenance.run_full_maintenance()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
