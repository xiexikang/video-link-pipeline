# VLP Web UI 视觉方案

| 项 | 说明 |
| --- | --- |
| 版本 | Draft v0.2 |
| 关联 | [web-local-dev-plan.md](./web-local-dev-plan.md) |
| 技术栈 | React + Vite，dev port **5550** |
| 设计方法 | 遵循 `frontend-design` skill：主题驱动、避免 AI 模板审美 |
| 布局策略 | **Mobile-first 自适应**——320px 手机至 ultrawide 桌面同一套 UI，非单独 H5 页 |

---

## 1. 设计定位

### 1.1 主题锚点

**产品**：本机视频链接处理流水线的 Web 控制台（`video-link-pipeline` / `vlp`）。

**用户**：在自己电脑上跑 CLI 的开发者或创作者——熟悉命令行，需要「少开文件夹、少记参数」，但仍要看到与 `manifest.json` 一致的真实状态。

**页面唯一职责（各页）**：

| 页面 | 单一职责 |
| --- | --- |
| 任务看板 | 快速扫一眼所有 job 走到哪一步 |
| 任务详情 | 读懂一条 pipeline 发生了什么、产物在哪 |
| 新建任务 | 用表单代替记 CLI flags |
| 环境诊断 | 确认本机 prerequisites 是否就绪 |

**视觉隐喻**：**本地信号台（Local Signal Desk）**——不是 SaaS 仪表盘，而是贴在你 `output/` 文件夹旁边的监视器：暗色工作台、清晰的状态灯、等宽路径、横向信号流。灵感来自广播控台指示灯、时间码、波形，而非通用「数据统计后台」。

### 1.2 刻意回避的默认审美

以下三种 AI 常见默认**不采用**（除非 brief 明确要求）：

- 暖奶油底 + 高对比衬线 + 赤陶 accent
- 纯黑底 + 荧光绿/朱红单 accent
- 报纸式细线 + 零圆角 + 密集分栏

---

## 2. Design Tokens

### 2.1 色彩

命名语义与 pipeline 阶段绑定，便于组件复用。

| Token | Hex | 用途 |
| --- | --- | --- |
| `base` | `#13151A` | 页面背景 |
| `surface` | `#1C1F26` | 侧栏、顶栏 |
| `elevated` | `#252932` | 卡片、表格行 hover |
| `border` | `#343A46` | 分隔线、输入框边框 |
| `text-primary` | `#E8EAED` | 标题、正文 |
| `text-secondary` | `#9AA3B2` | 辅助说明、时间戳 |
| `text-muted` | `#6B7280` | 占位、禁用 |
| `accent` | `#E5A023` | **签名色**：运行中、焦点、主 CTA（磷光琥珀，像控台 RUN 灯） |
| `signal-ok` | `#4EC9A0` | 阶段成功、done |
| `signal-warn` | `#E5A023` | 警告、复用已有产物 |
| `signal-fail` | `#E06C75` | 失败、error_code |
| `signal-skip` | `#5C6370` | 跳过阶段 |
| `signal-idle` | `#3D4450` | 未开始 |

**accent 使用纪律**：全页只有「运行态 + 主按钮 + 当前导航项」三处高饱和琥珀；成功/失败用 signal 色，不抢签名色。

### 2.2 字体

| 角色 | 字体 | 用途 |
| --- | --- | --- |
| Display | **Syne** 600/700 | 页面标题、job 标题、空状态 headline |
| Body | **Source Sans 3** 400/500/600 | 正文、按钮、表单 label |
| Utility | **IBM Plex Mono** 400/500 | URL、路径、error_code、时间戳、manifest 字段名 |

**Type scale**（rem；根字号随断点微调，见 §4.3）：

| 名称 | 默认 (≥768px) | 紧凑 (<768px) | 行高 | 字重 |
| --- | --- | --- | --- | --- |
| `display-lg` | 1.75rem | 1.375rem | 1.2 | Syne 700 |
| `display-sm` | 1.25rem | 1.125rem | 1.3 | Syne 600 |
| `body` | 0.9375rem | 0.9375rem | 1.55 | Source Sans 3 400 |
| `body-sm` | 0.8125rem | 0.8125rem | 1.5 | Source Sans 3 400 |
| `mono-sm` | 0.8125rem | 0.75rem | 1.45 | IBM Plex Mono 400 |
| `caption` | 0.75rem | 0.6875rem | 1.4 | Source Sans 3 500 |

长 URL / 路径在窄屏允许 `word-break: break-all` 或单行 truncate + 点击复制，避免撑破布局。

Google Fonts 加载：`Syne`, `Source Sans 3`, `IBM Plex Mono`。

### 2.3 间距与圆角

- 间距基准：**4px**；常用阶梯 8 / 12 / 16 / 24 / 32 / 48
- 圆角：`sm 6px`（badge、chip）· `md 10px`（卡片、输入）· `lg 14px`（预览面板）
- 不用大圆角 pill 风；保持工具感

### 2.4 阴影与边框

- 卡片：`1px solid border`，无 drop shadow（暗色 UI 靠 elevation 色差）
- 焦点环：`0 0 0 2px base, 0 0 0 4px accent`（键盘可访问）

---

## 3. 签名元素（Signature）

**Signal Flow Bar（信号流阶段条）**

任务详情页核心视觉：三段管道 **下载 → 转录 → 摘要**，节点为圆角方块 + 状态灯，段间用 2px 连接线。

- **≥768px**：横向排列（默认）
- **<768px**：纵向 stack，连接线为竖向 2px，节点全宽可点（便于触控）

| 状态 | 节点表现 |
| --- | --- |
| idle | 灰底 + 暗边框 |
| running | 琥珀描边 + 段内 ** subtle 波形 shimmer**（仅当前阶段） |
| done | 绿色实心灯 + 勾 |
| failed | 红色灯 + × |
| skipped | 虚线边框 + 「—」 |

列表页每行左侧 **4px 竖条** 与 runtime 状态同色（queued=琥珀 pulse，succeeded=绿，failed=红），与详情页 signal 语义一致。

**为何选它**：pipeline 的本质是信号流经阶段；比通用 stepper（01/02/03）更贴 manifest 语义，且一处 bold、其余界面克制。

---

## 4. 布局系统

### 4.1 App Shell

```text
┌──────────┬────────────────────────────────────────────┐
│          │  [页面标题]                    [刷新] [新建] │
│  VLP     ├────────────────────────────────────────────┤
│  ─────   │                                            │
│  看板    │              Main Content                  │
│  新建    │                                            │
│  设置    │                                            │
│          │                                            │
│  ─────   │                                            │
│  ● API   │                                            │
└──────────┴────────────────────────────────────────────┘
  200px                   fluid max-width 1200px
```

- **桌面 (≥1024px)**：左侧栏 200px 常驻
- **主区** padding 随断点变化（见 §4.3）；详情页 max-width 960px 居中（阅读型）
- **顶栏** 主区上方：页面标题 + contextual 操作；窄屏收进 overflow 菜单
- **API 状态**：桌面在侧栏底；平板在 icon rail 底；手机在顶栏右侧圆点

### 4.2 断点与布局模式

采用 **mobile-first** CSS（`min-width` 递进）。命名与 Tailwind 默认断点对齐，便于实现。

| Token | 宽度 | 布局模式 | 导航 |
| --- | --- | --- | --- |
| `xs` | 320–479px | 单栏紧凑 | 底部 Tab Bar |
| `sm` | 480–767px | 单栏标准 | 底部 Tab Bar |
| `md` | 768–1023px | 单栏 + 可选 icon rail | 左侧 64px icon rail **或** 底部 Tab（用户可折叠，默认 icon rail） |
| `lg` | 1024–1279px | 侧栏 + 主区 | 左侧 200px 全文字侧栏 |
| `xl` | ≥1280px | 侧栏 + 主区（max 1200px 居中） | 同 lg |

```text
Mobile (xs–sm)                 Desktop (lg+)
┌─────────────────────┐        ┌──────┬──────────────────┐
│ ≡  任务        ● API│        │ VLP  │ 任务      [刷新] │
├─────────────────────┤        │ 看板 │                  │
│                     │        │ 新建 │   Main           │
│   Main (pb-safe)    │        │ 设置 │                  │
│                     │        │ ●API │                  │
├─────────────────────┤        └──────┴──────────────────┘
│ 看板  新建  设置     │
└─────────────────────┘
  ↑ bottom tab + safe-area
```

### 4.3 间距与触控（响应式 token）

| Token | xs–sm | md | lg+ |
| --- | --- | --- | --- |
| `--page-px` | 16px | 20px | 24–32px |
| `--page-pb` | 72px + env(safe-area) | 24px | 24px |
| `--touch-min` | 44px | 40px | 36px（桌面可略小，仍 ≥36px） |
| `--sidebar-w` | 0（隐藏） | 64px | 200px |
| `--tabbar-h` | 56px + safe-area | 0 | 0 |
| `html font-size` | 15px | 16px | 16px |

**触控规范**：

- 可点击目标最小 **44×44px**（iOS HIG）；chip、Tab、列表行整行可点
- 相邻可点元素间距 ≥ 8px，避免误触
- 表单输入 `font-size ≥ 16px` on mobile，防止 iOS 自动 zoom
- 支持 `viewport-fit=cover` + `padding-bottom: env(safe-area-inset-bottom)` 适配刘海/Home Indicator

### 4.4 导航自适应

| 断点 | 组件 | 行为 |
| --- | --- | --- |
| xs–sm | `BottomTabBar` | 固定底部 3 项：看板 / 新建 / 设置；当前项琥珀 accent |
| xs–sm | `MobileHeader` | 左：返回（子页）或菜单占位；中：页面标题 truncate；右：API 状态点 |
| md | `IconRail` | 64px 宽，仅图标 + tooltip；hover/focus 显示 label |
| lg+ | `Sidebar` | 200px，图标 + 文字；底部 API 状态 |

**详情页 / 新建页在手机上**：不在 Tab Bar 高亮对应项；`MobileHeader` 左侧显示 **返回** 至看板。

### 4.5 分页面自适应要点

#### 任务看板 `/`

| 断点 | 布局 |
| --- | --- |
| xs–sm | 筛选 chip **横向 scroll**（`overflow-x: auto`，隐藏滚动条）；任务卡片全宽堆叠 |
| md+ | 筛选 chip 换行；列表可为 denser 行或两列卡片（≥1280px 可选双列，仅当 job 数多） |

**任务行 mobile 卡片化**（替代三列 desktop 行）：

```text
┌─────────────────────────────┐
│█ BV1xx-demo-title    Running│
│  bilibili.com/...           │
│  [下载✓] [转录●] [摘要—]     │
│  2 分钟前                    │
└─────────────────────────────┘
```

#### 任务详情 `/jobs/:id`

| 断点 | 布局 |
| --- | --- |
| xs–sm | Signal Flow **纵向**；产物「列表 → 预览」**上下 stack**（预览全宽） |
| md | Signal Flow 横向；产物区 **240px 列表 + fluid 预览** 两栏 |
| lg+ | 同 md，预览区 max-height `min(70vh, 640px)` 内滚动 |

预览 Tab（Phase 3）：xs–sm 用 **横向 scroll tabs**；md+ 常规 tab 条。

#### 新建任务 `/jobs/new`

| 断点 | 布局 |
| --- | --- |
| xs–sm | 任务类型 segmented control 改为 **垂直 radio 卡片列表**（5 项各一行，易点） |
| md+ | 单行 segmented control 或两行 wrap |

提交按钮：xs–sm **sticky bottom bar**（在 Tab Bar 上方），全宽「开始任务」；md+ 表单末尾 inline 按钮。

#### 环境诊断 `/settings`

| 断点 | 布局 |
| --- | --- |
| xs–sm | 卡片 **单列** stack |
| md | 2 列 grid |
| lg+ | 2×2 grid，max-width 960px |

### 4.6 内容溢出与可访问性

- 表格型数据（若后续扩展）：`<768px` 改为卡片，不横向滚整张表（除非 mono 日志预览 intentional）
- 视频预览：宽度 `100%`，`aspect-ratio: 16/9`；竖屏手机高度受 `max-height: 50vh` 限制
- 图片/长代码块：`overflow-x: auto` + `-webkit-overflow-scrolling: touch`
- 尊重 `prefers-reduced-motion`（见 §7）
- 键盘导航：Tab 顺序与视觉顺序一致；侧栏 / Tab Bar 均可用方向键（实现阶段 optional）

### 4.7 实现约定

```html
<!-- index.html -->
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
```

```css
/* mobile-first 示例 */
.app-main {
  padding-inline: var(--page-px);
  padding-bottom: var(--page-pb);
  min-height: 100dvh; /* 动态视口，避免 mobile 地址栏跳动 */
}

@media (min-width: 768px) {
  :root {
    --page-px: 20px;
    --page-pb: 24px;
    --tabbar-h: 0px;
  }
}

@media (min-width: 1024px) {
  :root {
    --page-px: 24px;
    --sidebar-w: 200px;
  }
}
```

React 层：`useMediaQuery('(min-width: 768px)')` 仅用于 **Signal Flow 方向、Segmented vs Radio** 等结构性分支；间距优先纯 CSS。

---

## 5. 组件规范

### 5.1 状态 Badge

| runtime | 样式 |
| --- | --- |
| queued | 琥珀底 15% opacity + 琥珀字 |
| running | 琥珀字 + 左侧 pulse 点 |
| succeeded | 绿底 15% + 绿字 |
| failed | 红底 15% + 红字 |

文案：sentence case——`Running`、`Succeeded`、`Failed`，不用全大写。

### 5.2 任务列表行

**Desktop（≥768px）**——紧凑行：

```text
│█│  BV1xx-demo-title                    Running
│ │  bilibili.com/video/BV...             3 阶段 · 2 分钟前
│ │  [下载 ✓] [转录 ●] [摘要 —]
```

**Mobile（<768px）**——全宽卡片，整卡可点（min-height 44px 触控区）：

```text
┌─────────────────────────────┐
│█ BV1xx-demo-title    Running│
│  bilibili.com/...           │
│  [下载✓] [转录●] [摘要—]     │
│  2 分钟前                    │
└─────────────────────────────┘
```

- 左竖条 `█` = runtime 色
- 标题 Syne display-sm；URL mono-sm（desktop truncate，mobile 可换行或复制）
- 迷你阶段 chip 复用 signal 色；窄屏 chip 可换行

### 5.3 诊断面板

- 默认折叠；有 `warning_details` 或 `error_code` 时自动展开
- 每条诊断：`mono-sm` 显示 code，下方 `body-sm` 显示 hint
- 不用红色大横幅；失败信息用左边框 3px `signal-fail`

### 5.4 表单（新建任务）

- 任务类型：
  - **≥768px**：横向 **segmented control** 五选一
  - **<768px**：**垂直 radio 卡片**（每项 min-height 52px，标题 + 一行说明）
- 高级选项折叠区标题：「下载与浏览器选项」
- 主按钮：「开始任务」琥珀实心
  - **<768px**：sticky bottom bar，全宽，位于 Tab Bar 上方
  - **≥768px**：表单末尾 inline
- 输入框 mobile `font-size: 16px`；禁用态 `text-muted` 底

### 5.5 产物预览 Tab（Phase 3）

Tab 顺序：`transcript` · `summary` · `subtitle` · `media` · `keywords`

- **≥768px**：常规 tab 条
- **<768px**：横向 scroll tabs（chip 式，snap scroll）
- 文本区：`elevated` 底 + mono 或 prose（summary max-width 65ch，mobile 100%）
- JSON：`mono-sm` + 可折叠树
- 媒体：`width 100%`，`aspect-ratio 16/9`；mobile `max-height: 50vh`

---

## 6. 分页面视觉说明

### 6.1 任务看板 `/`

**Hero 不做**：看板是工具页，顶部直接是筛选 + 列表。

**结构**：

1. 标题行：「任务」+ 任务计数 caption（mobile 标题可缩小为 display-sm）
2. 筛选 chip：全部 / 成功 / 失败 / 进行中（mobile 横向 scroll）
3. 列表或空状态

**自适应**：详见 §4.5 看板；desktop 行列表 / mobile 卡片 stack。

**空状态**：

- Syne display-sm：「还没有任务」
- body：「用 CLI 跑一个 job，或新建任务开始。」
- 琥珀按钮：「新建任务」（mobile 全宽）

### 6.2 任务详情 `/jobs/:id`

**视觉层级**（上 → 下）：

1. 标题 + runtime Badge + 来源 URL（mono，可点击外链）
2. **Signal Flow Bar**（mobile 纵向 / desktop 横向，见 §3）
3. 诊断面板（条件展开）
4. 产物区：desktop 左 240px 列表 + 右预览；**mobile 上下 stack**
5. `config_effective` 折叠 foot

**运行中**：Signal Flow 当前段 shimmer；desktop 右上角 caption「每 4 秒更新」，mobile 置于阶段条下方居中。

**MobileHeader**：左侧返回看板，标题 truncate 为 job 短名。

### 6.3 新建任务 `/jobs/new`

- 单列表单，max-width 640px（mobile 100% 宽）
- 顶部 body-sm secondary：「选项与 `vlp` CLI 对齐。」
- 提交后 toast：「任务已加入队列」→ 跳转详情

**自适应**：任务类型 mobile 用 radio 卡片；sticky 提交栏见 §5.4。

**内联提示**（琥珀左边框 callout）：

- run + cookies：「提交前请完全关闭 Chrome / Edge。」

### 6.4 环境诊断 `/settings`

- 卡片网格：FFmpeg · Selenium · Cookies · Output 目录
- **xs–sm** 单列 · **md** 2 列 · **lg+** 2×2 grid（max-width 960px）
- 每项：标题 + pass/fail 灯 + doctor 摘要
- 底部：config 来源路径（mono-sm，可横向 scroll）

---

## 7. 动效

| 场景 | 动效 | reduced-motion |
| --- | --- | --- |
| 阶段 running | Signal Flow 段内 1.2s 波形 opacity 循环 | 静态琥珀边框 |
| 列表刷新 | 行 opacity 0.6→1，200ms | 无动画 |
| 路由切换 | main fade 150ms |  instant |
| queued pulse | 侧栏/API 点 2s pulse | 静态琥珀 |

不堆 scroll reveal；工具 UI 以稳定为先。

---

## 8. 文案调性

- Sentence case；动词开头：「开始任务」「刷新列表」
- 错误：「下载失败：primary_http_403」+ hint，不道歉
- 空产物：「还没有 transcript。转录完成后会出现在这里。」
- 不用「提交」「赋能」「一站式」

---

## 9. 与实现的映射

### 9.1 推荐依赖

| 用途 | 库 |
| --- | --- |
| 路由 | `react-router-dom` |
| 图标 | `lucide-react` |
| Markdown 预览 | `react-markdown`（Phase 3） |
| 样式 | **CSS Modules** 或 **Tailwind**（tokens + 断点写入 config / CSS variables） |
| 响应式 | **mobile-first**；Tailwind screens `sm:640` `md:768` `lg:1024` `xl:1280` |
| 视口 hook | 仅结构性分支（Signal Flow 方向、表单控件形态） |

### 9.2 CSS Variables 示例

```css
:root {
  /* 色彩 */
  --vlp-base: #13151A;
  --vlp-surface: #1C1F26;
  --vlp-elevated: #252932;
  --vlp-border: #343A46;
  --vlp-text: #E8EAED;
  --vlp-text-secondary: #9AA3B2;
  --vlp-accent: #E5A023;
  --vlp-ok: #4EC9A0;
  --vlp-fail: #E06C75;
  --vlp-skip: #5C6370;
  /* 字体 */
  --font-display: 'Syne', system-ui, sans-serif;
  --font-body: 'Source Sans 3', system-ui, sans-serif;
  --font-mono: 'IBM Plex Mono', ui-monospace, monospace;
  /* 布局（mobile-first 默认值） */
  --page-px: 16px;
  --page-pb: calc(72px + env(safe-area-inset-bottom, 0px));
  --tabbar-h: calc(56px + env(safe-area-inset-bottom, 0px));
  --sidebar-w: 0px;
  --touch-min: 44px;
}
```

### 9.3 文件结构（设计 → 代码）

```text
web/frontend/src/
├── styles/
│   ├── tokens.css
│   ├── breakpoints.css      # 断点 media queries
│   └── global.css
├── hooks/
│   └── useMediaQuery.ts     # 仅结构性分支
├── components/
│   ├── layout/AppShell.tsx
│   ├── layout/Sidebar.tsx       # lg+
│   ├── layout/IconRail.tsx      # md
│   ├── layout/BottomTabBar.tsx  # xs–sm
│   ├── layout/MobileHeader.tsx  # xs–sm 子页顶栏
│   ├── job/SignalFlowBar.tsx    ← 签名；orientation prop
│   ├── job/StageChip.tsx
│   ├── job/JobRow.tsx           # 内部切换 row / card
│   ├── job/DiagnosticsPanel.tsx
│   ├── job/ArtifactPreview.tsx
│   └── ui/Badge.tsx, Button.tsx, SegmentedControl.tsx, RadioCardGroup.tsx
└── pages/
    ├── JobBoard.tsx
    ├── JobDetail.tsx
    ├── JobNew.tsx
    └── Settings.tsx
```

---

## 10. 自检（frontend-design critique）

| 检查项 | 结论 |
| --- | --- |
| 是否像任意 SaaS 后台？ | 否——暗色信号台 + 管道阶段条贴 pipeline 语义 |
| 是否落入三种 AI 默认？ | 否——未用 cream/serif、纯黑荧光绿、报纸分栏 |
| 签名元素是否唯一且克制？ | 是——仅 Signal Flow Bar 做 shimmer，其余静态 |
| 结构是否服务信息？ | 是——阶段条表顺序；诊断可折叠；无装饰性编号 |
| 开发者是否感到「本地工具」？ | 是——mono 路径、doctor 设置页、CLI 对齐文案 |
| 移动端是否可用？ | 是——320px 起单栏、44px 触控、Tab Bar、纵向 Signal Flow |
| 是否同一套 UI 而非 H5 分叉？ | 是——组件复用，仅布局/密度随断点变化 |

---

## 11. 下一步

1. Phase 0：搭 React + tokens + **响应式 AppShell**（Sidebar / IconRail / BottomTabBar）+ API 连通态
2. Phase 1：看板 + 详情（Signal Flow 横/纵 + 诊断 + 产物列表）
3. Phase 2：新建任务表单（mobile radio 卡片 + sticky 提交）+ 轮询态
4. Phase 3：预览 Tab（scroll tabs）+ Settings 页

**验收建议（自适应）**：在 375px（iPhone SE）、768px（iPad 竖屏）、1280px（桌面）三种宽度手工走通：看板 → 详情 → 新建 → 设置。
