# Memory 分析模式参考

## 常用工具

1. **meminfo** - 内存分配摘要
2. **GC日志** - 垃圾回收事件
3. **Android Profiler** - Android Studio内存追踪
4. **LeakCanary** - 内存泄漏检测库

## meminfo 关键字段

```
 meminfo解读:
 - Native Heap: C/C++分配的内存
 - Dalvik Heap: Java/Kotlin对象内存
 - Code: 加载的代码(DEX, native libraries)
 - Graphics: GPU内存(纹理, buffers)
 - Stack: 线程栈
 - Others: 系统其他内存
 - Total: 总内存使用
```

## GC 事件类型

| 类型 | 触发条件 | 暂停时间 | 严重程度 |
|------|----------|----------|----------|
| GC_CONCURRENT | 堆达到一定阈值 | <5ms | 低 |
| GC_FOR_MALLOC | 分配新对象但堆不足 | 5-30ms | 中 |
| GC_EXPLICIT | 主动调用System.gc() | 依赖堆大小 | 高 |
| GC_BEFORE_OOM | OOM前最后尝试 | 不确定 | 严重 |

## 关键阈值

| 指标 | 正常值 | 警告值 | 危险值 |
|------|--------|--------|--------|
| 内存使用占比 | <60% | 60-80% | >80% |
| GC频率 | <5次/秒 | 5-10次/秒 | >10次/秒 |
| GC暂停时间 | <5ms | 5-20ms | >20ms |
| 对象分配速率 | <10K/秒 | 10-50K/秒 | >50K/秒 |

## 常见问题模式

### 1. 内存泄漏
```
Pattern: 同一类型对象数量持续增长
Evidence: "LeakCanary: xxx activity objects retained"
```

### 2. 内存抖动
```
Pattern: 频繁GC导致内存上下波动
Evidence: "GC_CONCURRENT" followed by "GC_FOR_MALLOC" repeatedly
```

### 3. 大内存分配
```
Pattern: 单次分配超过1MB的对象
Evidence: "Allocated 2.5MB in java.util.Arrays"
```

### 4. Bitmap泄漏
```
Pattern: Bitmap未回收
Evidence: "Bitmap exceeded 50MB limit"
```

### 5. Native内存泄漏
```
Pattern: native内存持续增长
Evidence: "Native heap: allocated 150MB, freed 10MB"
```

## LeakCanary 泄漏分类

| 类型 | 影响 | 建议 |
|------|------|------|
| Activity泄漏 | 内存持续增长 | 检查static引用, handler延迟消息 |
| Fragment泄漏 | 内存增长 | 检查view引用 |
| Service泄漏 | 资源未释放 | 及时stopService |
| Singleton泄漏 | 全局内存增长 | 检查单例中的Context引用 |

## 优化建议

1. **减少对象分配**: 避免在循环中创建对象
2. **使用对象池**: 复用常用对象
3. **及时释放Bitmap**: bitmap.recycle()
4. **避免内存抖动**: 批量操作, 减少GC次数
5. **使用弱引用**: 缓存使用WeakReference
