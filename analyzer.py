#!/usr/bin/env python3
"""
Android Performance Log Analyzer
Analyzes Android performance logs to identify performance issues.
Supports: method traces, systrace, perfetto, meminfo, batterystats, gfx info, etc.
"""

import os
import sys
import json
import re
import zipfile
import argparse
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

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

@dataclass
class SystraceEvent:
    """Systrace事件"""
    name: str
    tid: int
    dur: int  # nanoseconds
    ts: int   # nanoseconds
    cat: str = ""

@dataclass
class PerfettoTrack:
    """Perfetto轨道"""
    name: str
    track_id: int
    process_name: str = ""

class SystraceAnalyzer:
    """Systrace HTML格式分析器"""

    def __init__(self, content: str):
        self.content = content
        self.events: List[SystraceEvent] = []
        self.frames: List[Dict[str, Any]] = []
        self._parse()

    def _parse(self) -> None:
        """解析Systrace HTML内容"""
        # Systrace HTML中的trace事件在 <script> 标签内
        script_match = re.search(r'<script[^>]*>\s*(\{.*?\}|\[.*?\])\s*</script>',
                                  self.content, re.DOTALL)

        if script_match:
            try:
                # 尝试解析JSON格式的trace数据
                data = json.loads(script_match.group(1))
                self._parse_trace_data(data)
            except json.JSONDecodeError:
                # 回退到正则解析
                self._parse_text_format()

        # 解析帧数据 (Chrome Tracing format)
        self._parse_frames()

    def _parse_trace_data(self, data: Any) -> None:
        """解析trace数据"""
        if isinstance(data, dict) and 'traceEvents' in data:
            for event in data.get('traceEvents', []):
                if event.get('ph') in ('B', 'E', 'X'):  # Begin, End, Complete
                    self.events.append(SystraceEvent(
                        name=event.get('name', ''),
                        tid=event.get('tid', 0),
                        dur=int(event.get('dur', 0)),
                        ts=int(event.get('ts', 0)),
                        cat=event.get('cat', '')
                    ))

    def _parse_text_format(self) -> None:
        """解析文本格式的Systrace"""
        # 支持 "进程名 线程名 优先级 时间戳 时间差 标签" 格式
        pattern = r'\|\s*(\d+)\s+\d+\s+\d+\s+\d+\s+(\d+)\s+\d+\s+(\S+)\s+(.+)'
        for match in re.finditer(pattern, self.content):
            tid, dur, name, detail = match.groups()
            self.events.append(SystraceEvent(
                name=name,
                tid=int(tid),
                dur=int(dur),
                ts=0,
                cat=detail
            ))

    def _parse_frames(self) -> None:
        """解析帧数据"""
        # 查找 Choreographer#doFrame 事件
        for event in self.events:
            if 'doFrame' in event.name or 'Choreographer' in event.name:
                frame_time_ms = event.dur / 1_000_000
                self.frames.append({
                    'name': event.name,
                    'dur_ms': frame_time_ms,
                    'ts': event.ts,
                    'dropped': frame_time_ms > 16.67
                })

    def analyze(self) -> List[Issue]:
        """分析Systrace数据"""
        issues = []

        # 1. 分析帧时间
        slow_frames = [f for f in self.frames if f['dropped']]
        if slow_frames:
            avg_time = sum(f['dur_ms'] for f in self.frames) / len(self.frames) if self.frames else 0
            max_time = max((f['dur_ms'] for f in self.frames), default=0)
            dropped_rate = len(slow_frames) / len(self.frames) * 100 if self.frames else 0

            if dropped_rate > 30:
                issues.append(Issue(
                    category="UI",
                    severity=Severity.CRITICAL,
                    title="严重丢帧",
                    description=f"丢帧率: {dropped_rate:.1f}%, 平均帧时间: {avg_time:.1f}ms, 最大: {max_time:.1f}ms",
                    evidence=[f"慢帧: {f['dur_ms']:.1f}ms" for f in slow_frames[:5]],
                    recommendation="检查主线程阻塞、过度绘制或复杂布局"
                ))
            elif dropped_rate > 10:
                issues.append(Issue(
                    category="UI",
                    severity=Severity.HIGH,
                    title="中度丢帧",
                    description=f"丢帧率: {dropped_rate:.1f}%, 平均帧时间: {avg_time:.1f}ms",
                    evidence=[f"慢帧: {f['dur_ms']:.1f}ms" for f in slow_frames[:3]],
                    recommendation="优化布局层级或减少主线程工作"
                ))

        # 2. 分析关键阶段耗时
        phase_events = {
            'DoFrame': [], 'performTraversals': [], 'input': [],
            'ViewRootImpl': [], 'SurfaceView': []
        }

        for event in self.events:
            for phase_name in phase_events:
                if phase_name in event.name:
                    phase_events[phase_name].append(event)

        # 检查 DoFrame 耗时
        for event in phase_events['DoFrame']:
            dur_ms = event.dur / 1_000_000
            if dur_ms > 32:
                issues.append(Issue(
                    category="UI",
                    severity=Severity.HIGH,
                    title="DoFrame严重超时",
                    description=f"帧渲染耗时: {dur_ms:.1f}ms (目标: <16.67ms)",
                    evidence=[f"{event.name}: {dur_ms:.1f}ms"],
                    recommendation="检查onDraw和display list执行"
                ))
            elif dur_ms > 16:
                issues.append(Issue(
                    category="UI",
                    severity=Severity.MEDIUM,
                    title="DoFrame超时",
                    description=f"帧渲染耗时: {dur_ms:.1f}ms",
                    evidence=[f"{event.name}: {dur_ms:.1f}ms"],
                    recommendation="优化绘制操作"
                ))

        # 检查 performTraversals 耗时
        for event in phase_events['performTraversals']:
            dur_ms = event.dur / 1_000_000
            if dur_ms > 10:
                issues.append(Issue(
                    category="UI",
                    severity=Severity.MEDIUM,
                    title="布局遍历耗时",
                    description=f"performTraversals耗时: {dur_ms:.1f}ms",
                    evidence=[f"{event.name}: {dur_ms:.1f}ms"],
                    recommendation="检查自定义View.measure/layout实现"
                ))

        # 3. 分析SurfaceView合成
        for event in phase_events['SurfaceView']:
            dur_ms = event.dur / 1_000_000
            if dur_ms > 16:
                issues.append(Issue(
                    category="UI",
                    severity=Severity.HIGH,
                    title="SurfaceView合成延迟",
                    description=f"SurfaceView更新耗时: {dur_ms:.1f}ms",
                    evidence=[f"{event.name}: {dur_ms:.1f}ms"],
                    recommendation="考虑使用TextureView替代"
                ))

        # 4. 分析输入延迟
        for event in phase_events['input']:
            dur_ms = event.dur / 1_000_000
            if dur_ms > 16:
                issues.append(Issue(
                    category="CPU",
                    severity=Severity.MEDIUM,
                    title="输入处理延迟",
                    description=f"输入事件处理耗时: {dur_ms:.1f}ms",
                    evidence=[f"{event.name}: {dur_ms:.1f}ms"],
                    recommendation="检查input filter实现"
                ))

        # 5. 统计各阶段平均耗时
        phase_stats = {}
        for phase_name, events in phase_events.items():
            if events:
                avg_dur = sum(e.dur for e in events) / len(events) / 1_000_000
                phase_stats[phase_name] = avg_dur

        if phase_stats:
            # 检查测量/布局/绘制分布
            traversal_events = [e for e in self.events if 'performTraversals' in e.name]
            if traversal_events:
                measure_time = sum(e.dur for e in self.events
                                  if 'Measure' in e.name) / 1_000_000
                layout_time = sum(e.dur for e in self.events
                                 if 'Layout' in e.name) / 1_000_000
                draw_time = sum(e.dur for e in self.events
                               if 'Draw' in e.name) / 1_000_000

                if draw_time > 8:
                    issues.append(Issue(
                        category="UI",
                        severity=Severity.MEDIUM,
                        title="绘制阶段耗时较长",
                        description=f"Draw阶段平均: {draw_time:.1f}ms",
                        evidence=[f"目标: <8ms"],
                        recommendation="减少自定义View绘制复杂度，使用hardware加速"
                    ))

        return issues


class PerfettoAnalyzer:
    """Perfetto trace格式分析器"""

    def __init__(self, content: str, file_path: str):
        self.content = content
        self.file_path = file_path
        self.events: List[Dict] = []
        self.slices: List[Dict] = []
        self.counters: List[Dict] = []
        self._parse()

    def _parse(self) -> None:
        """解析Perfetto数据"""
        # Perfetto可以是JSON或protobuf格式
        if self.content.strip().startswith('{') or self.content.strip().startswith('['):
            self._parse_json_format()
        else:
            # 二进制protobuf格式 - 尝试解析为文本protobuf
            self._parse_text_format()

    def _parse_json_format(self) -> None:
        """解析JSON格式的Perfetto trace"""
        try:
            data = json.loads(self.content)

            # 提取trace events
            if 'trace' in data:
                trace_data = data['trace']
                if isinstance(trace_data, list):
                    for packet in trace_data:
                        self._process_packet(packet)
                elif isinstance(trace_data, dict):
                    self._process_packet(trace_data)

            # 也支持直接是events数组
            if 'events' in data:
                for event in data['events']:
                    self.events.append(event)

            # 提取slices (ftrace events)
            if 'slices' in data:
                self.slices = data['slices']

            # 提取counters
            if 'counters' in data:
                self.counters = data['counters']

        except json.JSONDecodeError:
            # 可能包含embedded json
            json_match = re.search(r'\{.*"trace".*\}', self.content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    self._process_embedded_trace(data)
                except:
                    pass

    def _process_packet(self, packet: Dict) -> None:
        """处理Perfetto packet"""
        if 'ftraceEvents' in packet:
            for event in packet['ftraceEvents']:
                self.slices.append({
                    'name': event.get('name', ''),
                    'ts': event.get('timestamp', 0),
                    'dur': event.get('duration', 0),
                    'cat': event.get('category', ''),
                    'tid': event.get('tid', 0)
                })

        if 'trackEvent' in packet:
            event = packet['trackEvent']
            self.events.append({
                'name': event.get('name', ''),
                'ts': event.get('timestamp', 0),
                'dur': event.get('duration', 0),
                'cat': event.get('categories', '')
            })

        if 'counters' in packet:
            for counter in packet['counters']:
                self.counters.append(counter)

    def _process_embedded_trace(self, data: Dict) -> None:
        """处理嵌入的trace数据"""
        if 'traceEvents' in data:
            for event in data['traceEvents']:
                self.events.append(event)

    def _parse_text_format(self) -> None:
        """解析文本格式的ftrace"""
        # 尝试解析文本化的trace事件
        lines = self.content.split('\n')
        for line in lines:
            # 跳过元数据行
            if line.startswith('#') or not line.strip():
                continue

            # 尝试解析 JSONL 格式
            if line.strip().startswith('{'):
                try:
                    event = json.loads(line)
                    self.events.append(event)
                except:
                    pass
            else:
                # 尝试解析文本trace格式: name ts dur tid category
                parts = line.split()
                if len(parts) >= 4:
                    self.slices.append({
                        'name': parts[0],
                        'ts': float(parts[1]) if parts[1].replace('.', '').isdigit() else 0,
                        'dur': float(parts[2]) if parts[2].replace('.', '').isdigit() else 0,
                        'cat': parts[3] if len(parts) > 3 else ''
                    })

    def analyze(self) -> List[Issue]:
        """分析Perfetto数据"""
        issues = []

        # 1. 分析CPU调度
        issues.extend(self._analyze_cpu调度())

        # 2. 分析内存分配
        issues.extend(self._analyze_memory_alloc())

        # 3. 分析UI渲染
        issues.extend(self._analyze_rendering())

        # 4. 分析电源状态
        issues.extend(self._analyze_power())

        # 5. 分析网络
        issues.extend(self._analyze_network())

        return issues

    def _analyze_cpu调度(self) -> List[Issue]:
        """分析CPU调度问题"""
        issues = []

        # 查找调度延迟相关事件
        sched_events = [e for e in self.events
                       if 'sched' in str(e.get('name', '')).lower()
                       or 'latency' in str(e.get('name', '')).lower()]

        # 查找wakeup相关
        wakeup_events = [e for e in self.events
                        if 'wakeup' in str(e.get('name', '')).lower()
                        or 'wake' in str(e.get('name', '')).lower()]

        # 分析线程切换
        for event in sched_events[:50]:
            name = event.get('name', '')
            dur = event.get('dur', 0)

            if dur > 10_000_000:  # >10ms
                dur_ms = dur / 1_000_000
                issues.append(Issue(
                    category="CPU",
                    severity=Severity.MEDIUM,
                    title="长调度延迟",
                    description=f"调度延迟: {dur_ms:.1f}ms",
                    evidence=[f"{name}: {dur_ms:.1f}ms"],
                    recommendation="检查CPU负载和调度策略"
                ))

        return issues

    def _analyze_memory_alloc(self) -> List[Issue]:
        """分析内存分配"""
        issues = []

        alloc_events = [e for e in self.events
                       if 'alloc' in str(e.get('name', '')).lower()
                       or 'heap' in str(e.get('name', '')).lower()]

        gc_events = [e for e in self.events
                    if 'gc' in str(e.get('name', '')).lower()
                    or 'GC' in str(e.get('name', ''))]

        # 分析GC模式
        if len(gc_events) > 10:
            issues.append(Issue(
                category="Memory",
                severity=Severity.MEDIUM,
                title="频繁GC",
                description=f"检测到 {len(gc_events)} 个GC事件",
                evidence=[f"GC事件: {e.get('name', 'unknown')}" for e in gc_events[:5]],
                recommendation="检查内存分配模式，避免频繁对象创建"
            ))

        # 分析大内存分配
        for event in alloc_events:
            size = event.get('size', 0) or event.get('bytes', 0)
            if size > 1_000_000:  # >1MB
                size_mb = size / 1_000_000
                issues.append(Issue(
                    category="Memory",
                    severity=Severity.HIGH,
                    title="大内存分配",
                    description=f"分配大小: {size_mb:.1f}MB",
                    evidence=[f"{event.get('name', 'unknown')}: {size_mb:.1f}MB"],
                    recommendation="拆分布局，避免一次性大对象"
                ))

        return issues

    def _analyze_rendering(self) -> List[Issue]:
        """分析渲染问题"""
        issues = []

        # 查找帧渲染相关
        frame_events = [e for e in self.events
                       if 'frame' in str(e.get('name', '')).lower()
                       or 'vsync' in str(e.get('name', '')).lower()
                       or 'doFrame' in str(e.get('name', ''))
                       or 'draw' in str(e.get('name', '')).lower()]

        slow_frames = []
        for event in frame_events:
            dur = event.get('dur', 0)
            if dur > 16_000_000:  # >16ms
                dur_ms = dur / 1_000_000
                slow_frames.append(dur_ms)

        if slow_frames:
            avg = sum(slow_frames) / len(slow_frames)
            max_dur = max(slow_frames)
            dropped_rate = len(slow_frames) / len(frame_events) * 100 if frame_events else 0

            if dropped_rate > 30 or max_dur > 50:
                issues.append(Issue(
                    category="UI",
                    severity=Severity.CRITICAL,
                    title="严重渲染问题",
                    description=f"丢帧率: {dropped_rate:.1f}%, 最大帧时间: {max_dur:.1f}ms",
                    evidence=[f"慢帧: {f:.1f}ms" for f in slow_frames[:5]],
                    recommendation="检查主线程阻塞、overdraw或布局复杂度"
                ))
            elif dropped_rate > 10:
                issues.append(Issue(
                    category="UI",
                    severity=Severity.HIGH,
                    title="渲染丢帧",
                    description=f"丢帧率: {dropped_rate:.1f}%, 平均: {avg:.1f}ms",
                    evidence=[f"慢帧: {f:.1f}ms" for f in slow_frames[:3]],
                    recommendation="优化渲染管线"
                ))

        return issues

    def _analyze_power(self) -> List[Issue]:
        """分析电源问题"""
        issues = []

        # 查找wakelock
        wake_events = [e for e in self.events
                      if 'wake' in str(e.get('name', '')).lower()
                      or 'wakelock' in str(e.get('name', '')).lower()]

        for event in wake_events:
            dur = event.get('dur', 0)
            if dur > 60_000_000:  # >1min
                dur_s = dur / 1_000_000
                issues.append(Issue(
                    category="Battery",
                    severity=Severity.HIGH,
                    title="Wakelock持有过长",
                    description=f"Wakelock持有: {dur_s:.0f}秒",
                    evidence=[f"{event.get('name', 'unknown')}: {dur_s:.0f}s"],
                    recommendation="确保在onPause或后台时释放wakelock"
                ))

        # 查找传感器
        sensor_events = [e for e in self.events
                        if 'sensor' in str(e.get('name', '')).lower()
                        or 'accelerometer' in str(e.get('name', '')).lower()]

        if len(sensor_events) > 100:
            issues.append(Issue(
                category="Battery",
                severity=Severity.MEDIUM,
                title="频繁传感器事件",
                description=f"传感器事件: {len(sensor_events)}次",
                evidence=[f"事件: {sensor_events[0].get('name', 'unknown')}"],
                recommendation="使用合适的采样率，设置传感器禁用"
            ))

        return issues

    def _analyze_network(self) -> List[Issue]:
        """分析网络问题"""
        issues = []

        net_events = [e for e in self.events
                     if 'net' in str(e.get('name', '')).lower()
                     or 'socket' in str(e.get('name', '')).lower()
                     or 'http' in str(e.get('name', '')).lower()
                     or 'dns' in str(e.get('name', '')).lower()]

        # 分析DNS延迟
        dns_events = [e for e in net_events
                     if 'dns' in str(e.get('name', '')).lower()]

        for event in dns_events:
            dur = event.get('dur', 0)
            if dur > 100_000_000:  # >100ms
                issues.append(Issue(
                    category="Network",
                    severity=Severity.LOW,
                    title="DNS查询慢",
                    description=f"DNS耗时: {dur/1_000_000:.0f}ms",
                    evidence=[f"{event.get('name', 'unknown')}: {dur/1_000_000:.0f}ms"],
                    recommendation="考虑DNS缓存或使用HTTP DNS"
                ))

        # 分析连接延迟
        conn_events = [e for e in net_events
                      if 'connect' in str(e.get('name', '')).lower()
                      or 'handshake' in str(e.get('name', '')).lower()]

        for event in conn_events:
            dur = event.get('dur', 0)
            if dur > 500_000_000:  # >500ms
                issues.append(Issue(
                    category="Network",
                    severity=Severity.MEDIUM,
                    title="网络连接慢",
                    description=f"连接耗时: {dur/1_000_000:.0f}ms",
                    evidence=[f"{event.get('name', 'unknown')}: {dur/1_000_000:.0f}ms"],
                    recommendation="检查网络质量或使用连接复用"
                ))

        return issues


class AndroidPerfAnalyzer:
    """Android性能日志分析器"""

    def __init__(self, log_path: str):
        self.log_path = log_path
        self.temp_dir = None
        self.files: Dict[str, List[str]] = {}
        self.raw_files: Dict[str, str] = {}  # 存储原始文件内容
        self.issues: List[Issue] = []
        self.systrace_analyzer: Optional[SystraceAnalyzer] = None
        self.perfetto_analyzer: Optional[PerfettoAnalyzer] = None

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
                        content = fp.read()
                        lines = content.split('\n')
                    self.files[rel_path] = lines
                    self.raw_files[rel_path] = content  # 保存原始内容
                except Exception as e:
                    try:
                        # 二进制文件尝试读取部分内容
                        with open(path, 'rb') as fp:
                            content = fp.read(50000).decode('utf-8', errors='ignore')
                        self.files[rel_path] = content.split('\n')
                        self.raw_files[rel_path] = content
                    except:
                        self.files[rel_path] = []
                        self.raw_files[rel_path] = ""

    def analyze_systrace(self) -> None:
        """分析Systrace文件"""
        print("[*] Analyzing Systrace...")

        systrace_files = []
        for fname in self.raw_files:
            if any(x in fname.lower() for x in ['.systrace', 'systrace', 'trace.html', 'trace.htm']):
                systrace_files.append(fname)
            # HTML文件也可能是systrace
            elif fname.endswith('.html') or fname.endswith('.htm'):
                systrace_files.append(fname)
            # .txt文件可能是systrace text格式
            elif fname.endswith('.txt'):
                content = self.raw_files.get(fname, '')[:1000]
                if any(x in content for x in ['Choreographer', 'doFrame', 'performTraversals', 'SurfaceView']):
                    systrace_files.append(fname)

        for fname in systrace_files:
            content = self.raw_files.get(fname, '')
            if not content:
                continue

            print(f"    [*] Parsing: {fname}")
            try:
                analyzer = SystraceAnalyzer(content)
                issues = analyzer.analyze()

                for issue in issues:
                    issue.file_source = fname
                    self.issues.append(issue)

                if issues:
                    print(f"    [+] Found {len(issues)} issues in {fname}")

            except Exception as e:
                print(f"    [-] Failed to parse {fname}: {e}")

    def analyze_perfetto(self) -> None:
        """分析Perfetto trace文件"""
        print("[*] Analyzing Perfetto...")

        perfetto_files = []
        for fname in self.raw_files:
            if any(x in fname.lower() for x in ['.pftrace', '.perfetto', 'perfetto', '.prototrace']):
                perfetto_files.append(fname)
            # JSON文件可能是perfetto
            elif fname.endswith('.json'):
                content = self.raw_files.get(fname, '')[:500]
                if any(x in content for x in ['traceEvents', 'trace', 'perfetto']):
                    perfetto_files.append(fname)

        for fname in perfetto_files:
            content = self.raw_files.get(fname, '')
            if not content:
                continue

            print(f"    [*] Parsing: {fname}")
            try:
                analyzer = PerfettoAnalyzer(content, fname)
                issues = analyzer.analyze()

                for issue in issues:
                    issue.file_source = fname
                    self.issues.append(issue)

                if issues:
                    print(f"    [+] Found {len(issues)} issues in {fname}")

            except Exception as e:
                print(f"    [-] Failed to parse {fname}: {e}")

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

        # Run Systrace/Perfetto analysis first (most detailed)
        self.analyze_systrace()
        self.analyze_perfetto()

        # Run generic pattern analyzers
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
