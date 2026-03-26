# Systrace & Perfetto 分析模式参考

## Systrace 概览

### 格式
- `.systrace` 文件 (文本格式)
- `.html` 文件 (Chrome Tracing HTML格式)
- 包含完整的系统追踪数据

### 抓取命令
```bash
# 使用 systrace.py
python systrace.py -o trace.html sched gfx view wm am app

# 使用 Perfetto (推荐)
adb shell perfetto -c - --txt -o /data/misc/perfetto-traces/trace.pftrace \
  -e 60s sched freq idle am wm gfx view memory
```

## Systrace 关键事件

### UI渲染管线

| 事件 | 描述 | 目标时间 |
|------|------|----------|
| `Choreographer#doFrame` | 帧回调起点 | <16ms |
| `ViewRootImpl#performTraversals` | 布局遍历入口 | <5ms |
| `Measure` | View测量 | <2ms |
| `Layout` | View布局 | <2ms |
| `Sync` | DisplayList同步 | <1ms |
| `Draw` | Canvas绘制 | <8ms |
| `Execute` | 命令执行 | <4ms |
| `Process` | 输入处理 | <12ms |

### SurfaceFlinger

| 事件 | 描述 | 目标时间 |
|------|------|----------|
| `SurfaceFlinger#handleMessageInvalidate` | 帧处理 | <2ms |
| `SurfaceFlinger#onMessageReceived` | 消息接收 | <1ms |
| `SurfaceFlinger#flush` | Buffer出队 | <2ms |

### Input

| 事件 | 描述 | 目标时间 |
|------|------|----------|
| `InputQueue.consumeBatch` | 输入批处理 | <1ms |
| `NativeInputReader` | 原生输入读取 | <2ms |
| `InputDispatcher` | 输入分发 | <2ms |

## Perfetto 概览

### 格式
- `.pftrace` / `.perfetto-trace` - 二进制protobuf
- `.json` - JSON格式 (可读)
- `.prototrace` - Protobuf格式

### 抓取命令
```bash
# Android
adb shell perfetto \
  -c - --txt \
  -o /data/misc/perfetto-traces/trace.pftrace \
  -e 60s \
  sched freq idle am wm gfx view memory power

# iOS
ios perf record --output trace.perfetto-trace
```

### Perfetto SQL 查询

```sql
-- 查看慢帧
SELECT name, dur/1000000 as dur_ms
FROM slice
WHERE name LIKE '%doFrame%' AND dur > 16000000
ORDER BY dur DESC;

-- 查看CPU调度延迟
SELECT
  t.name,
  s.sched_latency/1000000 as latency_ms
FROM sched s
JOIN thread t ON s.thread_id = t.id
WHERE s.sched_latency > 10000000
ORDER BY s.sched_latency DESC;

-- 查看内存分配
SELECT
  name,
  SUM(alloc_size)/1000000 as total_mb
FROM alloc
GROUP BY name
ORDER BY total_mb DESC;
```

## 常见问题模式

### 1. 丢帧 (Frame Drop)

```
症状: doFrame > 16ms
原因:
  - 主线程阻塞
  - 过度绘制
  - 复杂布局
  - GC暂停
```

### 2. 布局抖动 (Layout Thrashing)

```
症状: 短时间内多次 performTraversals
原因:
  - 循环中requestLayout
  - 动画触发布局
  - Adapter.notifyDataSetChanged
```

### 3. 内存分配抖动 (Allocation Churn)

```
症状: 频繁GC_FOR_MALLOC
原因:
  - 循环中创建对象
  - 字符串拼接
  - 集合扩容
```

### 4. 锁竞争 (Lock Contention)

```
症状: 主线程等待锁
证据: "waiting for lock" 在主线程
原因:
  - 单例锁
  - 数据库锁
  - 共享资源竞争
```

### 5. IO阻塞

```
症状: 主线程读写文件/网络
证据: read/write 系统调用耗时
原因:
  - 主线程网络请求
  - 主线程文件IO
  - SQLite查询慢
```

### 6. GC暂停

```
症状: GC事件导致帧延迟
证据: "GC_CONCURRENT" / "GC_FOR_MALLOC" 耗时
原因:
  - 分配速率过高
  - 大对象分配
  - 内存碎片
```

## 分析工具

### 官方工具
1. **Perfetto UI** - https://ui.perfetto.dev (推荐)
2. **Systrace Viewer** - Chrome browser:chrome://tracing
3. **Android Studio Profiler** - CPU/Memory分析

### 分析步骤

1. **确定问题类型**
   - 卡顿? → 查看帧时间
   - 发热? → 查看CPU使用率
   - 耗电? → 查看wakelock和传感器

2. **放大时间范围**
   - 找到问题的精确时间点
   - 放大该时间范围

3. **追踪调用链**
   - 从症状向上追溯原因
   - doFrame → ViewRootImpl → Activity → 你的代码

4. **检查系统状态**
   - CPU频率是否过低
   - 内存是否紧张
   - 是否有其他进程抢占资源

## 阈值参考

| 指标 | 正常 | 警告 | 严重 |
|------|------|------|------|
| 帧时间 | <16ms | 16-32ms | >32ms |
| 丢帧率 | <5% | 5-20% | >20% |
| GC暂停 | <5ms | 5-20ms | >20ms |
| CPU调度延迟 | <5ms | 5-15ms | >15ms |
| IO等待 | <2ms | 2-10ms | >10ms |
| 内存分配速率 | <10MB/s | 10-50MB/s | >50MB/s |
