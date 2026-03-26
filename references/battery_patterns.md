# Battery 分析模式参考

## 常用工具

1. **Battery Historian** - Google电池分析工具
2. **batterystats** - 系统电池统计
3. **Dumpsys** - 系统服务信息
4. **wakelock** - 唤醒锁分析

## Batterystats 关键指标

```
 Batterystats 字段:
 - Uid 0:xxx: 用户应用UID
 - Wake lock: 唤醒锁持有时间
 - Sensor: 传感器使用时间
 - Foreground time: 前台运行时间
 - Background: 后台运行时间
 - Data usage: 网络数据使用
```

## Wakelock 类型

| 类型 | 影响 | 严重程度 |
|------|------|----------|
| PARTIAL_WAKE_LOCK | CPU持续运行 | 🔴 高 |
| SCREEN_DIM_WAKE_LOCK | 屏幕保持唤醒 | 🟠 中 |
| SCREEN_BRIGHT_WAKE_LOCK | 屏幕高亮 | 🟡 低 |
| FULL_WAKE_LOCK | 全部保持 | 🔴 高 |

## 关键阈值

| 指标 | 正常值 | 警告值 | 危险值 |
|------|--------|--------|--------|
| WakeLock持有时间 | <1min/小时 | 1-5min/小时 | >5min/小时 |
| 后台网络使用 | <1MB/小时 | 1-5MB/小时 | >5MB/小时 |
| GPS使用 | <1min/小时 | 1-5min/小时 | >5min/小时 |
| 传感器使用 | <5min/小时 | 5-15min/小时 | >15min/小时 |

## 常见问题模式

### 1. WakeLock泄漏
```
Pattern: WakeLock持有时间过长
Evidence: "Wakelock: foreground=3600000ms"
Cause: 未正确release()
```

### 2. 后台网络过度
```
Pattern: 后台数据使用过大
Evidence: "background data: 50MB in last hour"
Cause: 频繁同步或轮询
```

### 3. 传感器持续使用
```
Pattern: 传感器长时间运行
Evidence: "Sensor: accelerometer 15min active"
Cause: SensorManager未注销
```

### 4. GPS泄漏
```
Pattern: GPS持续开启
Evidence: "GPS: 3000000ms active"
Cause: LocationListener未移除
```

### 5. 频繁JobScheduler
```
Pattern: 后台任务过于频繁
Evidence: "JobScheduler: 50 jobs in last hour"
Cause: 任务调度间隔过短
```

### 6. 同步适配器过度同步
```
Pattern: 同步过于频繁
Evidence: "SyncManager: sync every 15min"
Cause: sync_interval设置不当
```

## Battery Historian 分析

### 时间线视图
- 绿色: 应用在前台
- 蓝色: 部分唤醒锁
- 红色: 满唤醒锁
- 灰色: 设备待命

### 电量消耗排名
1. **屏幕**: 通常占30-40%
2. **WiFi**: 通常占10-20%
3. **应用**: 取决于使用习惯

## 优化建议

1. **使用PARTIAL_WAKE_LOCK替代FULL_WAKE_LOCK**
2. **后台任务使用WorkManager**而非AlarmManager
3. **批量网络请求**减少唤醒次数
4. **GPS使用后及时注销Listener**
5. **使用传感器时设置合适的采样率**
6. **实现GCM网络同步**减少后台网络
