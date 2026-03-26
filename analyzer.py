#!/usr/bin/env python3
"""
Android Performance Log Analyzer
Analyzes Android performance logs to identify performance issues.
"""

import os
import sys
import json
import re
import zipfile
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

class Severity(Enum):
    CRITICAL = ("🔴", "Critical", "需立即处理")
    HIGH = ("🟠", "High", "建议尽快修复")
    MEDIUM = ("🟡", "Medium", "可考虑优化")
    LOW = ("🟢", "Low", "轻微影响")

@dataclass
class Issue:
    category: str
    severity: Severity
    title: str
    description: str
    evidence: List[str] = field(default_factory=list)
    file_source: str = ""
    recommendation: str = ""

class AndroidPerfAnalyzer:
    """Android性能日志分析器"""

    def __init__(self, log_path: str):
        self.log_path = log_path
        self.temp_dir = None
        self.files: Dict[str, List[str]] = {}
        self.issues: List[Issue] = []

    def extract_zip(self) -> bool:
        """解压zip文件"""
        try:
            self.temp_dir = tempfile.mkdtemp(prefix="android_perf_")
            with zipfile.ZipFile(self.log_path, 'r') as zf:
                zf.extractall(self.temp_dir)
            print(f"[+] Extracted to: {self.temp_dir}")
            return True
        except Exception as e:
            print(f"[-] Extract failed: {e}")
            return False

    def scan_files(self) -> None:
        """扫描所有文件"""
        for root, _, files in os.walk(self.temp_dir):
            for f in files:
                path = os.path.join(root, f)
                rel_path = os.path.relpath(path, self.temp_dir)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                        content = fp.readlines()
                    self.files[rel_path] = content
                except:
                    self.files[rel_path] = []

    def search_pattern(self, pattern: str, files: Optional[List[str]] = None) -> List[Tuple[str, int, str]]:
        """搜索模式"""
        results = []
        targets = files or list(self.files.keys())
        regex = re.compile(pattern, re.IGNORECASE)

        for filename in targets:
            if filename not in self.files:
                continue
            for i, line in enumerate(self.files[filename]):
                if regex.search(line):
                    results.append((filename, i + 1, line.strip()))
        return results

    def analyze_cpu(self) -> None:
        """分析CPU相关问题"""
        print("\n[*] Analyzing CPU...")

        # High CPU usage patterns
        patterns = [
            (r'MethodTracer.*?overhead.*?(\d+)%', 'High tracing overhead', Severity.MEDIUM),
            (r'DoFrame.*?(\d+)ms.*?>\s*16ms', 'Frame time exceeded 16ms', Severity.HIGH),
            (r'Choreographer.*?missed.*?frame', 'Missed frame detected', Severity.HIGH),
            (r'performTraversals.*?(\d+)ms', 'Layout traversal slow', Severity.MEDIUM),
            (r'input.*?latency.*?(\d+)ms', 'Input latency detected', Severity.MEDIUM),
        ]

        for pattern, title, severity in patterns:
            results = self.search_pattern(pattern)
            if results:
                for fname, line_num, line in results[:5]:
                    self.issues.append(Issue(
                        category="CPU",
                        severity=severity,
                        title=title,
                        description=f"Found in {fname}:{line_num}",
                        evidence=[line],
                        file_source=fname
                    ))

    def analyze_memory(self) -> None:
        """分析内存相关问题"""
        print("[*] Analyzing Memory...")

        patterns = [
            (r'GC_[A-Z_]+.*?(\d+)ms.*?>\s*20ms', 'Long GC pause', Severity.HIGH),
            (r'GC_CONCURRENT', 'Frequent concurrent GC', Severity.MEDIUM),
            (r'GC_FOR_MALLOC', 'Allocation-triggered GC', Severity.MEDIUM),
            (r'Bitmap.*?(\d+)MB', 'Large bitmap allocation', Severity.MEDIUM),
            (r'meminfo.*?total.*?(\d+)MB.*?free.*?(\d+)MB', 'Memory usage check', Severity.LOW),
            (r'native.*?allocated.*?(\d+)MB', 'Native memory high', Severity.HIGH),
            (r'OOM|OutOfMemoryError', 'OOM error detected', Severity.CRITICAL),
            (r'LeakCanary.*?retained', 'Memory leak detected', Severity.HIGH),
        ]

        for pattern, title, severity in patterns:
            results = self.search_pattern(pattern)
            if results:
                for fname, line_num, line in results[:5]:
                    self.issues.append(Issue(
                        category="Memory",
                        severity=severity,
                        title=title,
                        description=f"Found in {fname}:{line_num}",
                        evidence=[line],
                        file_source=fname
                    ))

    def analyze_battery(self) -> None:
        """分析电池相关问题"""
        print("[*] Analyzing Battery...")

        patterns = [
            (r'Wakelock.*?held.*?(\d+)min', 'Wakelock held too long', Severity.HIGH),
            (r'PARTIAL_WAKE_LOCK', 'Partial wakelock detected', Severity.MEDIUM),
            (r'GPS.*?active.*?(\d+)min', 'GPS持续开启', Severity.HIGH),
            (r'Sensor.*?accelerometer.*?(\d+)min', 'Accelerometer overuse', Severity.MEDIUM),
            (r'background.*?data.*?(\d+)MB', 'High background data usage', Severity.MEDIUM),
            (r'JobScheduler.*?(\d+)\s*jobs', 'Too many background jobs', Severity.LOW),
        ]

        for pattern, title, severity in patterns:
            results = self.search_pattern(pattern)
            if results:
                for fname, line_num, line in results[:5]:
                    self.issues.append(Issue(
                        category="Battery",
                        severity=severity,
                        title=title,
                        description=f"Found in {fname}:{line_num}",
                        evidence=[line],
                        file_source=fname
                    ))

    def analyze_network(self) -> None:
        """分析网络相关问题"""
        print("[*] Analyzing Network...")

        patterns = [
            (r'bytes.*?(\d+)KB/s', 'High bandwidth usage', Severity.MEDIUM),
            (r'download.*?(\d+)MB', 'Large download detected', Severity.LOW),
            (r'upload.*?(\d+)MB', 'Large upload detected', Severity.LOW),
            (r'retry.*?(\d+)\s*times', 'Network retry detected', Severity.LOW),
            (r'DNS.*?slow.*?(\d+)ms', 'DNS lookup slow', Severity.LOW),
        ]

        for pattern, title, severity in patterns:
            results = self.search_pattern(pattern)
            if results:
                for fname, line_num, line in results[:5]:
                    self.issues.append(Issue(
                        category="Network",
                        severity=severity,
                        title=title,
                        description=f"Found in {fname}:{line_num}",
                        evidence=[line],
                        file_source=fname
                    ))

    def analyze_startup(self) -> None:
        """分析启动相关问题"""
        print("[*] Analyzing Startup...")

        patterns = [
            (r'Process.*?start.*?(\d+)ms', 'Process start slow', Severity.HIGH),
            (r'onCreate.*?(\d+)ms', 'Application.onCreate slow', Severity.HIGH),
            (r'dex2oat.*?(\d+)ms', 'DEX loading slow', Severity.MEDIUM),
            (r'ContentProvider.*?init.*?(\d+)ms', 'ContentProvider init slow', Severity.MEDIUM),
            (r'cold.*?start.*?(\d+)ms', 'Cold start slow', Severity.HIGH),
        ]

        for pattern, title, severity in patterns:
            results = self.search_pattern(pattern)
            if results:
                for fname, line_num, line in results[:5]:
                    self.issues.append(Issue(
                        category="Startup",
                        severity=severity,
                        title=title,
                        description=f"Found in {fname}:{line_num}",
                        evidence=[line],
                        file_source=fname
                    ))

    def analyze_ui(self) -> None:
        """分析UI相关问题"""
        print("[*] Analyzing UI...")

        patterns = [
            (r'Draw.*?(\d+)ms.*?>\s*8ms', 'Draw phase slow', Severity.MEDIUM),
            (r'Execute.*?(\d+)ms.*?>\s*4ms', 'Execute phase slow', Severity.MEDIUM),
            (r'Process.*?(\d+)ms.*?>\s*12ms', 'Process phase slow', Severity.HIGH),
            (r'jank|drop.*?frame', 'Frame drop detected', Severity.HIGH),
            (r'missed.*?VSYNC', 'VSYNC missed', Severity.HIGH),
            (r'overdraw.*?(\d+)x', 'Overdraw detected', Severity.LOW),
            (r'requestLayout.*?\d+\s*times', 'Excessive requestLayout', Severity.MEDIUM),
            (r'Invalidate', 'View invalidated frequently', Severity.LOW),
        ]

        for pattern, title, severity in patterns:
            results = self.search_pattern(pattern)
            if results:
                for fname, line_num, line in results[:5]:
                    self.issues.append(Issue(
                        category="UI",
                        severity=severity,
                        title=title,
                        description=f"Found in {fname}:{line_num}",
                        evidence=[line],
                        file_source=fname
                    ))

    def generate_report(self) -> str:
        """生成分析报告"""
        # Sort issues by severity
        severity_order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]
        self.issues.sort(key=lambda x: severity_order.index(x.severity))

        report = []
        report.append("# 📊 Android 性能分析报告")
        report.append(f"\n**分析文件**: {self.log_path}")
        report.append(f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"\n**发现文件数**: {len(self.files)}")
        report.append(f"**发现问题数**: {len(self.issues)}")

        # Group by severity
        for severity in severity_order:
            category_issues = [i for i in self.issues if i.severity == severity]
            if not category_issues:
                continue

            emoji, name, desc = severity.value
            report.append(f"\n\n## {emoji} {name} ({desc})")

            for i, issue in enumerate(category_issues, 1):
                report.append(f"\n### {i}. {issue.title}")
                report.append(f"**分类**: {issue.category}")
                report.append(f"**文件**: {issue.file_source}")
                report.append(f"**描述**: {issue.description}")

                if issue.evidence:
                    report.append("\n**证据**:")
                    for ev in issue.evidence[:3]:
                        report.append(f"```\n{ev}\n```")

                if issue.recommendation:
                    report.append(f"\n**建议**: {issue.recommendation}")

        # Summary
        report.append("\n\n---\n## 📈 问题统计")
        categories = {}
        for issue in self.issues:
            categories[issue.category] = categories.get(issue.category, 0) + 1

        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            report.append(f"- **{cat}**: {count} 个问题")

        return "\n".join(report)

    def analyze(self) -> str:
        """执行完整分析"""
        print(f"\n[+] Analyzing: {self.log_path}")

        if not self.extract_zip():
            return "[-] Failed to extract zip file"

        print("[*] Scanning files...")
        self.scan_files()
        print(f"[+] Found {len(self.files)} files")

        # Run all analyzers
        self.analyze_cpu()
        self.analyze_memory()
        self.analyze_battery()
        self.analyze_network()
        self.analyze_startup()
        self.analyze_ui()

        print(f"[+] Found {len(self.issues)} issues")

        # Generate report
        return self.generate_report()

def main():
    parser = argparse.ArgumentParser(description='Android Performance Analyzer')
    parser.add_argument('log_file', help='Path to performance log zip file')
    parser.add_argument('-o', '--output', help='Output report to file')
    parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')

    args = parser.parse_args()

    if not os.path.exists(args.log_file):
        print(f"[-] File not found: {args.log_file}")
        sys.exit(1)

    analyzer = AndroidPerfAnalyzer(args.log_file)
    report = analyzer.analyze()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"[+] Report saved to: {args.output}")
    else:
        print(report)

if __name__ == '__main__':
    import tempfile
    main()
