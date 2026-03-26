# UI/Frame 分析模式参考

## 常用工具

1. **GPU呈现模式分析** - 开发者选项
2. **Systrace** - 帧渲染分析
3. **Layout Inspector** - 布局检查
4. **Perfetto** - Google追踪工具

## GPU 渲染分析

### 柱状图颜色含义

| 颜色 | 含义 | 理想值 |
|------|------|--------|
| 蓝色(更新) | 上传像素到GPU | <2.4ms |
| 紫色(测量) | Measure/Layout | <4.5ms |
| 红色(绘制) | Canvas绘制 | <4.5ms |
| 黄色(转换) | View变换 | <2.9ms |
| 绿色(调度) | Choreographer调度 | <0.6ms |
| 橙色(同步) | 命令同步到GPU | <0.5ms |

### 帧时间目标
- **60 FPS**: 每帧 ≤16.67ms
- **90 FPS**: 每帧 ≤11.11ms
- **120 FPS**: 每帧 ≤8.33ms

## 关键阈值

| 指标 | 正常值 | 警告值 | 危险值 |
|------|--------|--------|--------|
| 帧时间 | <16ms | 16-32ms | >32ms |
| 丢帧率 | <10% | 10-30% | >30% |
| 过度绘制 | <2x | 2-3x | >3x |
| 层级深度 | <10层 | 10-15层 | >15层 |

## Systrace 关键阶段

```
ViewRootImpl.performTraversals:
  ├─ RELAYOUT - 重新布局
  ├─ DISPATCH - 分发事件
  ├─ NOTIFY - 通知输入
  ├─ INPUT - 输入处理
  ├─ TRAVERSAL - 遍历绘制
  │   ├─ PRE - 预处理
  │   ├─ MEASURE - 测量
  │   ├─ LAYOUT - 布局
  │   └─ DRAW - 绘制
  └─ SYNC - 同步
```

## 常见问题模式

### 1. 丢帧 (Jank)
```
Pattern: 帧时间超过16ms
Evidence: "Choreographer: missed frame #123 (46ms)"
```

### 2. 过度绘制
```
Pattern: 同一像素被绘制多次
Evidence: "Overdraw: 4.5x"
Cause: 不必要的背景、不可见元素
```

### 3. 复杂布局
```
Pattern: 嵌套层级过深
Evidence: "Layout depth: 18 levels"
```

### 4. 布局抖动
```
Pattern: 频繁requestLayout
Evidence: "requestLayout called 100 times in one frame"
```

### 5. 滚动卡顿
```
Pattern: RecyclerView滚动不流畅
Evidence: "RecyclerView: 23ms per frame during scroll"
```

### 6. Bitmap加载过慢
```
Pattern: 图片解码阻塞UI
Evidence: "BitmapFactory.decode: 45ms"
```

## 过度绘制来源

1. **不必要的背景**
   - Activity背景
   - CardView背景
   - ListView item背景

2. **不可见元素**
   - GONE但仍绘制的View
   - 透明但仍绘制的View

3. **重复绘制**
   - 自定义View的onDraw过于复杂
   - ClipRect未使用

## Layout Inspector 关键指标

| 指标 | 理想值 | 问题值 |
|------|--------|--------|
| 视图总数 | <50 | >200 |
| 最大层级 | <10 | >20 |
| 测量次数/帧 | 1-2 | >10 |
| 布局次数/帧 | 1-2 | >5 |

## 优化建议

### 减少过度绘制
1. 移除不必要的背景
2. 使用ClipRect裁剪
3. 使用ViewStub延迟加载
4. 使用merge减少层级

### 优化布局性能
1. 使用ConstraintLayout减少嵌套
2. 使用RecyclerView替代ListView
3. 避免在onDraw中创建对象
4. 使用HardwareLayer加速

### 优化滚动性能
1. 使用setHasFixedSize
2. 使用DiffUtil
3. 图片使用三级缓存
4. 避免在滑动回调中做重操作
