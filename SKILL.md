---
name: android-perf-analyzer
description: "Analyzes Android performance log files (CPU, Memory, Battery, Network, UI) to identify performance issues. Activates when user asks to analyze Android performance logs, debug performance problems, or find causes of Android lag/jank/battery drain."
---

# Android Performance Analyzer

> Analyzes Android performance logs to identify the root causes of performance problems

## When to Use This Skill

Activate this skill when the user:
- Provides an Android performance log zip file for analysis
- Asks to analyze CPU, Memory, Battery, or Network performance
- Reports Android lag, jank, freeze, battery drain, or app slowdown
- Wants to debug startup time issues or UI rendering problems
- Says: "分析Android性能日志", "Android性能问题排查", "为什么手机卡顿"

## Workflow Overview

```
Phase 1: Log Extraction
  ├─ Create temp directory
  ├─ Extract zip file contents
  └─ Inventory available log files
      ↓
Phase 2: Log Categorization & Parsing
  ├─ CPU logs (traces, systrace, method profiling)
  ├─ Memory logs (meminfo, GC logs, hprof, allocation logs)
  ├─ Battery logs (battery historian, wakelock, batterystats)
  ├─ Network logs (network traffic, bandwidth)
  ├─ Startup logs (boot traces, app startup timing)
  └─ UI logs (frame timeline, layout inspect, gfx info)
      ↓
Phase 3: Issue Detection
  ├─ CPU: High CPU usage, excessive method tracing overhead
  ├─ Memory: Memory leaks, excessive GC, OOM
  ├─ Battery: Wakelock issues, background drain
  ├─ Network: Excessive traffic, inefficient transfers
  ├─ Startup: Slow initialization, heavy dex loading
  └─ UI: Jank frames, overdraw, layout complexity
      ↓
Phase 4: Report Generation
  └─ Output ranked list of issues with severity and recommendations
```

## Phase 1: Log Extraction

### Step 1.1: Create Temp Directory

```bash
TEMP_DIR=$(mktemp -d)
echo "Created temp directory: $TEMP_DIR"
```

### Step 1.2: Extract Zip File

```bash
unzip -o "$LOG_FILE_PATH" -d "$TEMP_DIR"
```

### Step 1.3: Inventory Log Files

```bash
find "$TEMP_DIR" -type f | sort
```

Common log file patterns:
- `*.trace` - Method traces (CPU profiling)
- `*.systrace` - Systrace HTML files
- `*.html`, `*.htm` - Systrace HTML format
- `*.pftrace`, `*.perfetto-trace` - Perfetto trace files
- `*.prototrace` - Perfetto protobuf traces
- `*.hprof` - Heap dumps
- `meminfo*` - Memory info files
- `batterystats*` - Battery statistics
- `*.json` - Perfetto JSON traces
- `*.txt` - Logcat or other text logs
- `*boot*` - Startup logs
- `*network*` - Network logs

## Phase 2: Log Categorization & Parsing

### 2.0 Systrace Analysis (HTML格式)

**Files to look for:**
- `*.systrace` - Systrace文件
- `*.html`, `*.htm` - Systrace HTML格式
- `trace.html` - 常见的Systrace输出名

**Systrace关键事件:**

| 事件名 | 含义 | 正常值 | 警告值 | 危险值 |
|--------|------|--------|--------|--------|
| `Choreographer#doFrame` | 帧渲染 | <16ms | 16-32ms | >32ms |
| `ViewRootImpl.performTraversals` | 布局遍历 | <5ms | 5-10ms | >10ms |
| `Measure` | 测量阶段 | <2ms | 2-4ms | >4ms |
| `Layout` | 布局阶段 | <2ms | 2-4ms | >4ms |
| `Draw` | 绘制阶段 | <8ms | 8-12ms | >12ms |
| `SurfaceView` | Surface合成 | <8ms | 8-16ms | >16ms |
| `Input` | 输入处理 | <4ms | 4-8ms | >8ms |

**Detection Script:**
```bash
grep -E "(doFrame|performTraversals|SurfaceView|input)" "$TEMP_DIR"/*.html 2>/dev/null | head -50
```

### 2.0.1 Systrace 分析模式

**丢帧分析:**
- 计算 doFrame >16ms 的事件比例
- 丢帧率 >30% = Critical
- 丢帧率 >10% = High
- 丢帧率 >5% = Medium

**阶段分解:**
- Measure >4ms: 检查自定义View.measure
- Layout >4ms: 检查复杂布局或高度自定义View
- Draw >8ms: 检查canvas操作或过深绘制缓存

### 2.0 Perfetto Analysis (JSON/PB格式)

**Files to look for:**
- `*.pftrace` - Perfetto trace
- `*.perfetto-trace` - Perfetto trace
- `*.prototrace` - Protobuf格式
- `*.json` - Perfetto JSON格式

**Perfetto 关键追踪:**

| 追踪名 | 含义 | 阈值 |
|--------|------|------|
| `sched/sched_switch` | 进程切换 | >10ms延迟 |
| `power/cpu_frequency` | CPU频率 | 低频率持续 |
| `power/gpu_frequency` | GPU频率 | 低频率持续 |
| `vmstat` | 内存状态 | 可用内存低 |
| `android/app/drawn_frames` | 应用帧率 | >16ms/帧 |
| `net/netstack` | 网络栈 | >100ms DNS |
| `power/wakelock` | 电源锁 | >1min持有 |

**Detection Script:**
```bash
grep -E "(sched|frame|wakelock|gc|cpu_frequency)" "$TEMP_DIR"/*.json 2>/dev/null | head -50
```

### 2.0.2 Perfetto 分析模式

**CPU分析:**
- sched_switch延迟 >10ms = High
- CPU频率低 = 检查热节流
- 调度器延迟 = 线程竞争

**内存分析:**
- gc_* 事件频繁 = Medium
- alloc size >1MB = High
- heap grow = 内存泄漏迹象

**渲染分析:**
- drawn_frames >16ms = High
- jank frames >30% = Critical
- SurfaceFlinger延迟 = 显示问题

**电池分析:**
- wakelock >1min = High
- sensor事件 >100/s = Medium
- wifi_scan 频繁 = Low

### 2.1 CPU Log Analysis

**Files to look for:**
- `*.trace` (ART method tracing)
- `*.systrace` (Systrace HTML)
- `CPU_*` files
- `method-trace*`

**Analysis Patterns:**

| Pattern | Indicates | Severity |
|---------|-----------|----------|
| `MethodTr races` sections with >10ms methods | Heavy CPU work | High |
| `SurfaceView` composition delays | UI thread blocked | High |
| `input` latency >16ms | Input handling lag | Medium |
| `DoFrame` >16ms | Frame drop | High |
| `VSYNC` missed | Display issues | High |

**Detection Script:**
```bash
grep -E "(total_time|MethodTracer|overhead|ms)" "$TEMP_DIR"/*.trace 2>/dev/null | head -100
grep -E "(Choreographer|DoFrame|performTraversals)" "$TEMP_DIR"/*.systrace 2>/dev/null | head -50
```

### 2.2 Memory Log Analysis

**Files to look for:**
- `meminfo*`
- `*gc*`
- `*.hprof`
- `*allocation*`
- `*leak*`

**Analysis Patterns:**

| Pattern | Indicates | Severity |
|---------|-----------|----------|
| `Allocations` growing continuously | Memory leak | High |
| `GC_CONCURRENT`频繁触发 | Memory pressure | Medium |
| `GC_FOR_MALLOC` >100ms | Large object allocation | Medium |
| `native allocated`持续增长 | Native memory leak | High |
| `Dalvikvik`内存接近上限 | OOM风险 | Critical |
| `Bitmap`数量过多 | Bitmap泄漏 | Medium |

**Detection Script:**
```bash
grep -E "(total mem|free mem|allocated|GC_|Allocations)" "$TEMP_DIR"/meminfo* 2>/dev/null
grep -E "(Bitmap|Texture|shader)" "$TEMP_DIR"/*hprof* 2>/dev/null | head -50
```

### 2.3 Battery Log Analysis

**Files to look for:**
- `batterystats*`
- `*wakelock*`
- `*battery*`
- `*power*`

**Analysis Patterns:**

| Pattern | Indicates | Severity |
|---------|-----------|----------|
| `Wakelock` held >1min | Background wake lock | High |
| `background` data usage high | Background network | Medium |
| `Sensor`频繁唤醒 | Sensor过度使用 | Medium |
| `GPS`持续开启 | Location泄漏 | High |
| `JobScheduler`频繁 | 定期任务过多 | Low |
| `SyncManager`过度同步 | 同步过于频繁 | Low |

**Detection Script:**
```bash
grep -E "(Wakelock| Wakeup|background|data usage|sensor|gps)" "$TEMP_DIR"/batterystats* 2>/dev/null
grep -E "(PARTIAL_WAKE_LOCK|Full|Wakelock)" "$TEMP_DIR"/*wakelock* 2>/dev/null
```

### 2.4 Network Log Analysis

**Files to look for:**
- `*network*`
- `*net*`
- `*traffic*`
- `*bandwidth*`

**Analysis Patterns:**

| Pattern | Indicates | Severity |
|---------|-----------|----------|
| Large file下载/上传 | 网络使用过大 | Medium |
| 频繁小请求 | 效率低下 | Low |
| 重试请求 | 网络不稳定 | Medium |
| DNS lookup慢 | DNS问题 | Low |

**Detection Script:**
```bash
grep -E "(bytes|KB/s|MB/s|download|upload|retry)" "$TEMP_DIR"/*network* 2>/dev/null | head -50
```

### 2.5 Startup Time Analysis

**Files to look for:**
- `*startup*`
- `*boot*`
- `*launch*`
- `*cold*`
- `*warm*`

**Analysis Patterns:**

| Pattern | Indicates | Severity |
|---------|-----------|----------|
| `Process start` >2000ms | 冷启动慢 | High |
| `dex2oat`耗时过长 | DEX加载慢 | Medium |
| `ContentProvider`初始化慢 | 组件初始化问题 | Medium |
| `Application.onCreate()` >500ms | 应用初始化重 | High |
| `Activity.onResume`延迟 | UI准备慢 | Medium |

**Detection Script:**
```bash
grep -E "(start|launch|init|create|onCreate|onResume|dex)" "$TEMP_DIR"/*startup* 2>/dev/null | head -50
grep -E "(ProcessStart|activityStart|applicationCreate)" "$TEMP_DIR"/*boot* 2>/dev/null
```

### 2.6 UI/Frame Log Analysis

**Files to look for:**
- `*gfx*`
- `*frame*`
- `*jank*`
- `*drop*`
- `*slow*`
- `*layout*`

**Analysis Patterns:**

| Pattern | Indicates | Severity |
|---------|-----------|----------|
| `Draw` >8ms | Canvas绘制耗时 | Medium |
| `Execute` >4ms | 命令执行慢 | Medium |
| `Process` >12ms | UI线程处理慢 | High |
| 丢帧率 >20% | 严重卡顿 | Critical |
| `Invalidate`频繁 | 过度重绘 | Medium |
| `overdraw` >3x | 过度绘制 | Low |

**Detection Script:**
```bash
grep -E "(Draw|Execute|Process|Prepare|jank|drop|missed)" "$TEMP_DIR"/*gfx* 2>/dev/null | head -50
grep -E "(overdraw|layer|Invalidate|requestLayout)" "$TEMP_DIR"/*layout* 2>/dev/null | head -30
```

## Phase 3: Issue Detection & Severity Ranking

### Severity Levels

| Level | Label | Description |
|-------|-------|-------------|
| Critical | 🔴 | 导致应用崩溃、ANR或严重性能问题 |
| High | 🟠 | 明显影响用户体验，需要尽快修复 |
| Medium | 🟡 | 中等影响，建议优化 |
| Low | 🟢 | 轻微影响，可考虑优化 |

### Issue Categories

1. **CPU问题**
   - 主线程过度工作
   - 频繁GC
   - 过度测量/追踪开销

2. **内存问题**
   - 内存泄漏
   - 内存抖动
   - 大内存分配

3. **电池问题**
   - Wakelock泄漏
   - 后台网络消耗
   - 传感器过度使用

4. **网络问题**
   - 过度网络请求
   - 未压缩传输
   - DNS延迟

5. **启动问题**
   - DEX加载慢
   - 组件初始化慢
   - 阻塞主线程

6. **UI问题**
   - 丢帧
   - 过度绘制
   - 复杂布局

## Phase 4: Report Generation

### Output Template

```markdown
# 📊 Android 性能分析报告

**分析文件**: [文件名]
**分析时间**: [时间戳]

---

## 🔴 Critical Issues (需立即处理)

### 1. [问题名称]
**文件**: [来源文件]
**发现时间**: [时间戳]
**描述**: [问题描述]

**证据**:
```
[相关日志片段]
```

**建议**: [修复方案]

---

## 🟠 High Priority Issues

### 2. [问题名称]
...

---

## 🟡 Medium Priority Issues

### 3. [问题名称]
...

---

## 🟢 Low Priority / Optimizations

### 4. [问题名称]
...

---

## 📈 性能指标摘要

| 指标 | 值 | 状态 |
|------|-----|------|
| CPU使用峰值 | xxx% | 🟠 高 |
| 内存使用峰值 | xxx MB | 🟢 正常 |
| 启动时间 | xxx ms | 🟡 中等 |
| 丢帧率 | xx% | 🔴 严重 |
| 电池消耗 | xxx mAh | 🟢 正常 |

---

## 🎯 Top 3 优化建议

1. **[建议1]**
2. **[建议2]**
3. **[建议3]**

---

**报告生成时间**: [完成时间]
```

## Execution Examples

### Example 1: Basic Performance Log Analysis

**User**: "分析这个性能日志: /tmp/perf_logs.zip"

**AI Response**:
1. Extract zip to temp directory
2. Scan for log files
3. Parse each category (CPU, Memory, Battery, Network, UI)
4. Detect issues using pattern matching
5. Rank by severity
6. Generate formatted report

### Example 2: Specific Issue Investigation

**User**: "这个日志里有什么内存问题?"

**AI Response**:
1. Focus only on memory-related logs
2. Analyze meminfo, GC logs, allocation tracking
3. Identify specific memory issues
4. Provide detailed memory analysis

## Quality Standards

### Validation Checklist
- [ ] All extracted files are accounted for
- [ ] Each issue has supporting evidence from logs
- [ ] Severity ratings are consistent with evidence
- [ ] Recommendations are actionable and specific
- [ ] Report is well-structured and readable

### Error Handling
- Missing log files → Note in report, skip that category
- Corrupted files → Report partial data, continue with others
- Empty zip → Report no data found
- Unsupported format → Suggest correct log collection

## Additional Resources

For reference documentation on Android performance analysis, see:
- `references/cpu_patterns.md` - CPU analysis patterns
- `references/memory_patterns.md` - Memory analysis patterns
- `references/battery_patterns.md` - Battery analysis patterns
- `references/ui_patterns.md` - UI/Frame analysis patterns
