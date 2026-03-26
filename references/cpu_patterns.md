# CPU 分析模式参考

## 常用工具

1. **Method Tracing** - 精确方法级CPU时间
2. **Systrace** - 系统级性能追踪
3. **CPU Profiler** - Android Studio内置工具
4. **Perfetto** - Google新一代追踪工具

## Trace文件格式

### .trace 文件 (Method Tracing)
```
MethodTracer
  version: 6
  data-file-creation-time: 1234567890
  clock: realtime
  profile: method
  entries: 12345
```

### .systrace 文件
HTML格式，包含JS可交互界面

## 关键指标

| 指标 | 正常值 | 警告值 | 危险值 |
|------|--------|--------|--------|
| 方法执行时间 | <1ms | 1-5ms | >5ms |
| 帧时间 | 16ms | 16-32ms | >32ms |
| CPU使用率 | <50% | 50-80% | >80% |
| GC时间 | <5ms | 5-20ms | >20ms |

## 常见问题模式

### 1. 主线程阻塞
```
Pattern: Main thread blocked for >16ms
Evidence: "main" tid=1 prio=5 Blocked for 23ms
```

### 2. 过度GC
```
Pattern: GC pauses causing frame drops
Evidence: "GC_CONCURRENT" , "GC_FOR_MALLOC"
```

### 3. 方法追踪开销
```
Pattern: Tracing overhead too high
Evidence: "Tracing overhead: 15%"
```

### 4. 锁竞争
```
Pattern: Lock contention on main thread
Evidence: "waiting for lock 0x1234 on thread main"
```

## Systrace 关键标签

- `Choreographer#doFrame` - 帧渲染
- `InputQueue$Hanlder` - 输入处理
- `ViewRootImpl#performTraversals` - 布局遍历
- `RecyclerView#onLayout` - RecyclerView布局
- `SurfaceView` - 硬件加速合成
