---
author: myjin2
updated: 2026-05-10
---

# 组件交互规范

> 触发场景：使用表单/表格/弹窗/反馈等组件、编写页面交互逻辑时查阅。

---

## 反模式优先级判定

`design-spec/examples/*.examples.vue` 中所有 ❌ 反模式都带优先级标签 `[BLOCKING] / [STRONG] / [SOFT]`。统一判定标准：

| 优先级 | 判定 | 典型场景 |
|--------|------|---------|
| **BLOCKING** | **名单越界** / 功能直接断裂 / a11y 直接破坏 | 使用名单外的 type 值（`type="success"`）、宽度越界（`width="480px"`）、不写 `v-model`、不写 `prop`、`<span>` 替代 `<el-button>`、使用被禁的属性（`circle`、`stripe`） |
| **STRONG** | 引入视觉 bug / 隐式依赖被破坏 / 间距乱码 | 间距叠加（gap + margin）、icon 贴文字（裸 svg 不走 #icon 插槽）、纯图标不加 `.btn-icon-square`（80×32 长方形）、基线错位（`<el-button link>` 与 `<span>` 混排）、覆盖全局清零规则 |
| **SOFT** | 偏离最佳实践但功能正常 | 缺 `aria-busy` / `aria-label`、硬编码 `style="height: 40px"` 替代 `size` 属性、`rules` 不带 `trigger`、表单不加 `ref` |

**使用方判读建议**：
- BLOCKING 反模式应被 lint / CR 严格阻断
- STRONG 反模式发现后应立即修复
- SOFT 反模式可纳入下一轮代码改进，不阻塞发布

---

## 基础交互规范

组件使用惯例参考 **Ant Design 设计规范**，包括但不限于：

- **表单**：必填项标红星号在左侧，校验信息在字段下方展示。两种标签布局：

| 布局 | 适用场景 |
|------|---------|
| 顶部标签 `label-position="top"` | 表单为主的整页/半页（创建页、编辑页）；侧抽屉；多列并排表单 |
| 右侧文字标签 `label-position="right"` + `label-width` | 弹窗内表单；页面局部表单区域（筛选、设置项）。label 文字右对齐紧贴 input，配对关系最强 |

> **注意**：`label-position="left"`（label 在左、文字左对齐）**不在设计系统推荐清单**——同一系统内只用 `top` / `right` 两种，避免视觉切换割裂。

- **表格**：操作列固定在最右侧，超过 3 个操作使用"更多"收纳；**不使用 stripe（斑马纹）**，通过 hover 行高亮区分行


| 宽度 | 适用场景 | 内容特征 |
|------|---------|---------|
| 400px | 确认提示、单字段输入、简短信息 | 单列、1\~3 个表单项或纯文本 |
| 640px | 常规表单、详情预览 | 单列多字段表单、中等信息量 |
| 800px | 复杂表单、内嵌表格/列表 | 双列表单、表格选择器、富内容 |
- **反馈**：操作成功使用轻量 Message 提示，危险操作前需 Popconfirm 或 Modal 二次确认

---

## 本项目补充规范

### 按钮图标（icon + 文字）

统一使用 Lucide 图标库，`stroke-width: 2`，`currentColor` 继承按钮色。**图标必须通过 `#icon` 插槽传递**，不使用 EP 的 `:icon` 属性（属性方式只能传组件构造函数，无法精确指定 `:size` / `:stroke-width`，与 input 前后缀图标同理）。

```vue
<!-- ✅ 推荐：#icon 插槽 + Lucide -->
<el-button type="primary">
  <template #icon><Search :size="16" :stroke-width="2" /></template>
  搜索
</el-button>

<!-- ❌ 禁止：把 <svg> / Lucide 组件直接塞 default slot -->
<el-button type="primary">
  <Search /> 搜索
</el-button>
<!-- 后果：button.scss 中 .el-icon + span { margin-inline-start: 6px } 不触发，icon 和文字贴在一起 -->

<!-- ❌ 禁止：用 :icon 属性 -->
<el-button type="primary" :icon="Search">搜索</el-button>
<!-- 后果：无法控制 size / stroke-width，与设计令牌不一致 -->
```

### 纯图标按钮（只有 icon，没有文字）

**触发条件**：按钮内只有 icon 且无任何文字标签时，必须加 `class="btn-icon-square"`。

**理由**：所有 `el-button` 默认强制 `min-width: 80px`（见 `button.scss` 的 min-width 强制段），单 icon 按钮不加 `.btn-icon-square` 会变成 80×32 的长方形。`.btn-icon-square` 在 `:not(.btn-icon-square)` 排除列表里，用它即可解除 80px 约束并提供等宽等高方形样式。

```vue
<!-- ✅ 推荐：纯图标必须用 .btn-icon-square -->
<el-button type="primary" class="btn-icon-square">
  <template #icon><Pencil :size="16" :stroke-width="2" /></template>
</el-button>

<!-- ❌ 禁止：使用 circle 属性（视觉与本设计系统不符） -->
<el-button type="primary" :icon="Pencil" circle />

<!-- ❌ 禁止：纯图标按钮不加 .btn-icon-square -->
<el-button type="primary">
  <template #icon><Pencil :size="16" :stroke-width="2" /></template>
</el-button>
<!-- 后果：被 min-width: 80px 撑开成长方形 -->
```

### 输入框图标

输入框的前后缀图标统一使用 **Lucide 图标 + `#prefix` / `#suffix` 插槽**，不使用 EP 的 `:prefix-icon` / `:suffix-icon` 属性（属性方式无法精确控制尺寸和 stroke-width）。

```vue
<!-- ✅ 推荐：slot 方式，显式指定尺寸 -->
<el-input placeholder="搜索">
  <template #prefix><Search :size="16" :stroke-width="2" /></template>
</el-input>

<!-- ❌ 禁止：prop 方式 -->
<el-input :prefix-icon="Search" placeholder="搜索" />
```

| 属性 | Default / Large | Small |
|------|----------------|-------|
| `:size` | `16`（CSS 兜底值） | `14`（CSS 兜底值） |
| `:stroke-width` | `2` | `2` |

> **自动缩放**：`el-theme/components/input.scss` 已通过 CSS 将 slot 内 Lucide SVG 的 `width` / `height` 覆盖为 rem 值（`1rem` / `0.875rem`），切换字号档位（S/M/L/XL）时图标自动等比缩放。模板中的 `:size` 仅作为 CSS 未加载时的兜底。

**常用图标对照表**：

| 场景 | 图标 | 位置 |
|------|------|------|
| 搜索 | `Search` | prefix |
| 用户名/账号 | `User` | prefix |
| 密码 | `Lock` | prefix |
| 邮箱 | `Mail` | prefix |
| 手机号 | `Phone` | prefix |
| 链接/网址 | `Link` | suffix |
| 日历（非 DatePicker） | `Calendar` | prefix |
| 时间（非 TimePicker） | `Clock` | prefix |

> **注意**：DatePicker / TimePicker 的日历/时钟图标由 `el-theme/components/datepicker.scss` 通过 CSS mask 全局替换为 Lucide 风格，无需在模板中手动处理

### Select 多选
默认使用 `collapse-tags collapse-tags-tooltip :max-collapse-tags="2"`，显示 2 个 tag 后折叠，hover 展示全部

### Tag 标签（数量克制）
**尽量避免在同一处（同一行/同一区域）一次性并列出现 3 个以上标签**（即 ≤3 个为宜，4 个及以上应避免）。

- **为什么**：标签是"轻量强调"，靠稀疏才有识别力；一排堆太多会让每个都失去焦点、色彩互相打架，退化成噪音（违背「装饰有度、主色克制」）。
- **反例**：状态列 / 卡片头一次平铺 4~6 个彩色 Tag。
- **例外**：demo / 规范展示页为了**枚举全部状态色板**（如本页一次列出「已完成/待审核/已驳回…」）不受此限——那是"展示所有可选项"，非真实业务里的单条记录并列。

### Dropdown 下拉菜单（面板 + 触发器）
`el-dropdown` 由**两部分**组成：**下拉面板本身**（菜单项 / 分隔线 / 禁用项 / hover，样式归 `el-theme` 源头）+ **触发器**（用户点/hover 后弹出面板的那个元素）。

- **触发器不是固定形态**：`el-dropdown` **常与「触发器」组合使用**——触发器可以是**按钮、图标、下拉选择器、轻量文字**等多种形态，按场景选，不写死成某一种。
  - **主操作 / 显式入口** → 用**按钮**触发（`<el-button>`，图标 + 文字规范见按钮章节）。
  - **紧凑 / 操作列 / 工具栏** → 用**纯图标**触发（如 `MoreHorizontal` 更多，配 `.btn-icon-square`）。
  - **次要 / 行内轻量入口**（如"更多操作 ⌄"）→ 用**轻量文字 + 箭头**触发。
- **强制做法**：触发器放在 `el-dropdown` 默认插槽、菜单放 `#dropdown` 插槽的 `<el-dropdown-menu>`；分隔用 `<el-dropdown-item divided>`；禁用项用 `disabled`；危险项文字走 `--iflyv-danger-primary`。
- **选中态（Dropdown 当导航用时）**：`el-dropdown` 本身没有"当前选中项"概念，若用它承载导航类选项（如侧边栏折叠态下用它顶替 `el-sub-menu` 展示二级导航），需要体现当前处于哪一项时，给命中的 `<el-dropdown-item>` 传 `class="is-active"`（样式定义见 `el-theme/components/dropdown.scss`，品牌浅底 + 品牌字色 + 半粗字重，与 Menu 组件的 `.el-menu-item.is-active` 视觉同源），由接入方按当前路由/选中值自行判断并传入。
- **反例**：手撸一个绝对定位的浮层当下拉；触发器和菜单不用 `el-dropdown` 组合而各写各的；把本该是按钮/图标的主入口硬做成裸文字（或反之）。

### 按钮间距
design-spec 已**全局清零** EP 原生的 `.el-button + .el-button { margin-left: 12px }`（见 `el-theme/components/button.scss`）。

**统一约定**：按钮组的间距**一律由父容器 `display: flex; gap: <token>` 提供**，推荐 `gap: var(--iflyv-spacing-3)`（12px）；紧凑场景 `var(--iflyv-spacing-2)`（8px）。

**禁止**：
- 不要在按钮上写 `margin-left` / `margin-right` / `margin-inline-start` / `margin-inline-end`
- 不要在使用方写 `.el-button + .el-button { ... }` 这种相邻按钮间距规则——它会和父容器 gap 叠加导致重复间距

**例外**：
- `.el-button-group` 内部按钮按 EP 默认行为（边框 -1px 重叠），不要包裹 flex+gap。
- `.el-button.table-operation`（表格操作列文字按钮）使用 `<td>` 内 inline 排版，间距由 `el-theme/components/table.scss` 的 `.table-operation + .table-operation { margin-inline-start: spacing-3 }` 相邻选择器自带，**不要包裹 flex+gap**，也不要在使用方覆盖 margin。

> **相关：表单控件（checkbox / radio）间距说明**
>
> `.el-checkbox` / `.el-radio` 在 `el-theme/components/{checkbox,radio}.scss` 中保留 EP 默认的 `margin-inline-end: 30px`——**这不是反模式**，与上述按钮间距规则不冲突。差异：表单控件有标准 group 容器（`<el-checkbox-group>` / `<el-radio-group>`），间距是 group 内部实现细节，使用方一律用 group 包装即可，**不需要也不应该再加 flex+gap**。30px 是行业默认值（EP / AntD / 飞书一致），避免相邻选项误点。

### Breadcrumb 面包屑（带返回箭头）
面包屑 = **前置返回箭头（可选）+ 路径导航**。**一律用业务组件 `Breadcrumb`**（源头 `design-spec/components/Breadcrumb/`），不要自己用 `el-breadcrumb` + 手写返回 `span` 拼装。

- **强制做法**：
  ```vue
  import { Breadcrumb, type BreadcrumbItem } from '<path>/design-spec/components'

  <Breadcrumb :items="items" @back="router.back()" />
  ```
  - `items`：路径项数组 `{ label, to? }[]`；**最后一项自动为当前页**（不可点击，`text-1`），带 `to` 的项可点击跳转（透传 EP 路由）。
  - `@back`：点返回箭头触发——**真实项目里通常接 `router.back()`**（或跳固定上级路由）。返回行为是业务才知道的事，由使用方在此提供。
  - `back-disabled`：无上一级时传 `true`，箭头自动切禁用态（`icon-4`、不可点、不 emit）。
  - `show-back="false"`：不需要返回箭头时隐藏（只留路径导航）。
- **返回箭头外观**（图标 / 与首项 8px 间距 / 激活 `icon-2` / 禁用 `icon-4`）单一数据源在 `el-theme/components/breadcrumb.scss` 的约定 class `.breadcrumb-back`，`Breadcrumb` 组件内部引用它——**使用方不碰外观，只传 `items` + 接 `@back`**。
- **反例**：用 `el-breadcrumb` 自己在前面塞一个 `<span>` 挂 `@click` 手拼返回箭头（脱离组件、间距/色态/禁用逻辑各处不一致、源头更新不同步）；把 `@back` 写成空函数让箭头点了没反应。

### PageHeader 页面标题栏（页面级 header）
页面顶部通栏（白底 + 下边线，最小高 60），用来标识「当前在哪一页」。**一律用业务组件 `PageHeader`**（源头 `design-spec/components/PageHeader/`），不要手写 div 拼页头，也不要用 `el-page-header` 复刻。

**按页面层级选形态**（三个正交配置项自由叠加，不是三种组件）：

| 层级 | 形态 | 写法 |
|---|---|---|
| 一级页面 | 纯标题 | `<PageHeader title="文献检索" :show-back="false" />` |
| 二级页面 | 返回按钮 + 短竖线 + 标题 | `<PageHeader title="检索结果" @back="router.back()" />` |
| 三级及以上 | 返回按钮 + 短竖线 + 面包屑 | `<PageHeader :breadcrumb="crumbs" @back="router.back()" />` |
| 任意层级 + 说明 | 标题下方一行说明 | 加 `description="点任意一条继续该对话"` |
| 任意层级 + 右侧操作 | 右侧按钮组 | `<template #extra>…</template>` |

**规格约束**（全在源头，使用方不改）：
- 通栏：`bg-page-white` + 下边线 `border-subtle`；内边距上下 `spacing-3`、左右 `spacing-6`；最小高 60（36 按钮 + 上下 12），有说明时随内容撑高。
- 返回按钮：`el-button circle`（36×36 正圆，宽高同取 `--el-component-size`），后接 1×16 短竖线（`border-subtle`），元素间距 `spacing-4`。这是 `circle` 禁用规则的**唯一例外**——页头返回按钮固定圆形，其余纯图标按钮仍用 `.btn-icon-square`。
- 标题：16/24 · semibold · `text-1`，单行省略。
- 说明：12/18 · regular · `text-3`，单行省略。
- 面包屑（三级及以上）：字号与标题同级 16/24，分隔符 `/`（`icon-3`）。**当前层级 `text-1` 加粗**；**其他层级 `text-3` 不加粗，hover 时变 `text-1`**。样式单一数据源在 `el-theme/components/breadcrumb.scss` 的 `.breadcrumb-page`，`PageHeader` 内部引用。
  - 与 `Breadcrumb` 业务组件区分：`Breadcrumb` 是内容区路径导航（13px、箭头分隔）；页面级头部的面包屑一律走 `PageHeader` 的 `breadcrumb` prop。

**右侧操作区（`#extra`）**：组内间距 `spacing-3`，按以下三种写法之一，**同一页头内不混用**：

```vue
<!-- 1. 纯图标：.btn-icon-square + el-tooltip + aria-label（三者缺一不可） -->
<template #extra>
  <el-tooltip content="论文收藏" placement="top">
    <el-button class="btn-icon-square" aria-label="论文收藏">
      <template #icon><Star :size="16" :stroke-width="2" /></template>
    </el-button>
  </el-tooltip>
</template>

<!-- 2. 文字 -->
<template #extra>
  <el-button>历史对话</el-button>
  <el-button>新对话</el-button>
</template>

<!-- 3. 图标 + 文字：图标走 #icon 插槽 -->
<template #extra>
  <el-button><template #icon><Plus :size="16" :stroke-width="2" /></template>新对话</el-button>
</template>
```

- 页头右侧以次按钮为主；如确有主操作，最多一个 `type="primary"`，放最右。
- 纯图标适合 ≥3 个高频、含义明确的工具类操作；含义不直观或只有 1~2 个操作时用文字 / 图标+文字。

**反例**：
- ❌ 手写 `<header>` + `<button>` + `<span class="bar">` 拼页头（参考页 `.history-header` / `.results-page-header` / `.tw-topbar` 都属于这种，应迁移到 `PageHeader`）。
- ❌ 在使用方 scoped 里 `:deep(.el-breadcrumb__inner)` 改面包屑颜色 / 字重——层级色态归 `.breadcrumb-page` 源头。
- ❌ 纯图标按钮不加 `.btn-icon-square`（被 `min-width: 80px` 撑成长方形）、不配 tooltip / aria-label。
- ❌ 标题字号写 17px 等非令牌值（参考页里出现过），一律 16/24。
- ❌ 二级以上页面不放返回按钮，或一级页面放返回按钮——层级与返回按钮必须对应。

### AppSidebar 左导航（应用级固定侧栏）

桌面优先的控制台 / 工作台类产品的固定左栏，承载**品牌 + 模块导航 + 账号 + 通知**。最多两级菜单；桌面可折叠，移动端自动转抽屉。**一律用业务组件 `AppSidebar`**（源头 `design-spec/components/AppSidebar/`），不要手写 div / 用 `el-aside` + `el-menu` 拼装。

**何时用 / 何时不用**：
- ✅ 适用：桌面优先，固定左栏，最多二级菜单，导航项 < 15 个。
- ❌ 不适用：三级及以上菜单（改用顶部导航 + 左侧二级菜单）；移动优先产品（改用底部 TabBar）；动态长列表（改用可搜索 Drawer）。

**最小用法**：
```vue
<AppSidebar
  v-model:active-key="activeKey"
  v-model:collapsed="collapsed"
  v-model:open="drawerOpen"
  :brand="{ logo, title: '应急管理学科大模型', subtitle: '中国矿业大学' }"
  :items="[
    { key:'qa', label:'学科问答', icon: MessageSquare },
    { key:'kb', label:'学科知识库', icon: BookOpen,
      children:[
        { key:'kb-personal', label:'个人知识库' },
        { key:'kb-shared', label:'共享知识库' }
      ]
    }
  ]"
  :user="{ name:'刘承颐老师', role:'teacher-male' }"
  :notification-count="6"
  :menu-items="[
    { key:'profile', label:'个人资料', icon: UserRound },
    { key:'logout', label:'退出登录', icon: LogOut, divided: true }
  ]"
  @select="onSelect"
  @menu-select="onMenuSelect"
  @notification="openNotice"
/>
```

**规格约束**（全在源头，使用方不改）：
- **几何**：展开宽 232px、折叠宽 68px（用户可手动切换，或容器 < 1024px 时自动收起）。移动端（<768px）强制展开态，收起时转抽屉 + 遮罩。
- **结构（自上而下）**：品牌区（72px 高，logo 36×36 圆形 + 标题/副标题竖排）→ 导航区（可滚动）→ 底部（账号下拉 + 通知按钮）→ 折叠把手（右边缘垂直居中凸包，桌面显示、移动隐藏）。
- **导航项**：高 44px，间距 `spacing-2`，圆角 `radius-md`，图标 20px / stroke-width 2。未选中文字 `text-1` + 0.2px 描边补重量；选中 `brand-primary` + `brand-bg` 底色 + semibold。
- **二级菜单（分组）**：父项只开合不跳转，可同时展开多个分组。展开态原地 grid 0fr→1fr 过渡；折叠态 hover 时右侧弹 popover 浮层承接子项。选中项落在某分组时该分组自动展开。子项文字再缩进 8px（相对一级）。
- **折叠态**：文字淡出（opacity 0），图标保留，hover 显示 tooltip。折叠把手箭头翻转 180°。
- **底部**：账号行与导航项等高 44px，el-dropdown 触发；通知按钮 `.btn-icon-square`（36×36，= `--el-component-size`），el-badge 显示未读数。折叠态下账号与通知竖排。
- **抽屉**：<768px 时抽屉从左滑出（max 80vw），带遮罩，Esc 关闭。关闭态 `visibility: hidden`（键盘 Tab 不会跳进看不见的链接）。

**图标插槽**：
```vue
<!-- 默认：items 里的 icon 字段（Lucide 组件） -->
<AppSidebar :items="[{ key:'qa', label:'学科问答', icon: MessageSquare }]" />

<!-- 自定义：#icon 插槽，接收 { item } -->
<AppSidebar :items="customItems">
  <template #icon="{ item }">
    <div class="custom-icon" :style="{ background: item.color }">
      {{ item.emoji }}
    </div>
  </template>
</AppSidebar>
```

**反例**：
- ❌ 手写 `<aside>` + `el-menu` 拼左导航（门户参考页 `src/vendor/design-spec/` 那份应急拷贝就是这种，已封装为本组件）。
- ❌ 在使用方 scoped 里 `:deep(.sidebar)` 改外观——改源头 `AppSidebar.vue`，所有引用方同步。
- ❌ 把折叠把手挪到组件外、用外部按钮控制 `collapsed`——把手是组件固有部件，跟着侧栏宽度自动定位。
- ❌ 抽屉只写 `transform` 不写 `visibility: hidden`——关闭态仍可被键盘 Tab 聚焦。
- ❌ 三级菜单硬塞进 children 的 children——本组件只支持二级，三级改架构。

### 分页器默认用法
```vue
<el-pagination
  v-model:current-page="currentPage"
  v-model:page-size="pageSize"
  :page-sizes="[10, 20, 50, 100]"
  :total="total"
  layout="prev, pager, next, sizes, jumper"
/>
```

- layout 顺序：`prev, pager, next, sizes, jumper`（不含 `total`）
- **分页器区域布局**：外层容器使用 `flex` + `justify-content: space-between`，左侧放总数文本（如"共 128 条"），右侧放 `el-pagination`。总数不通过分页器的 `total` layout 项展示

### 空状态（Empty）
- **图片区**：使用 `#image` 插槽替换 EP 默认 SVG，内容为圆角矩形底板（`.empty-icon-plate`，样式由 `el-theme/components/empty.scss` 全局提供）+ Lucide 图标
- **图标选择**：根据场景使用语义化图标（如 `Inbox` 暂无数据、`FileSearch` 无搜索结果、`FolderOpen` 暂无文件、`AlertCircle` 加载失败）
- **底部操作按钮**：使用**默认态**（`<el-button>`），不使用 `type="primary"`——空状态按钮属于辅助引导，遵循「主操作唯一」原则

### Dialog 两类：操作弹窗 vs 提示弹窗（先分清是哪类）

弹窗按「用户来干嘛」分两类，先判类别再定形态（宽度 / 语义变体 / 按钮）：

| 类别 | 用途 | 特征 | 形态要点 |
|---|---|---|---|
| **操作弹窗** | 在弹窗内**进行操作**（表单填写、编辑、配置等）的载体 | 信息量更少、信息关联度更高、任务连贯性更弱、页面遮挡更多 | 宽度按场景三档（确认/单字段 400、常规表单 640、复杂/双列 800）；内含表单再叠 form-pattern；高度下限 240px |
| **提示弹窗** | **传达系统给用户的提醒**——需要打断用户、信息较重要 | 内容轻（一两行文案 + 按钮），不承载复杂操作 | 加语义变体类（is-warning/is-danger/is-success/is-info，见下）；宽度多为 400；高度下限 160px |

- **判断入口**：先问「用户是要在这弹窗里*做一件事*（填表/编辑），还是系统要*提醒/打断*用户？」——做事 → 操作弹窗；提醒 → 提示弹窗。
- 两类都用 `el-dialog`（下方语义变体、按钮个数等规则通用）；载体是否该用弹窗（vs 页面/抽屉）另见 `references/patterns/dialog-pattern.md` 的四维判据。

### Dialog 语义化标题（4 种变体）

**背景**：本设计系统**统一使用 Dialog**（不引入 `ElMessageBox` 命令式 API）。为了让 Dialog 也能表达「警示 / 危险 / 成功 / 信息」语义，提供 4 个变体类——使用方加一个 class 即可在标题前自动渲染圆形彩色底板 + 白色 Lucide 图标。

**4 个变体的语义与使用场景**：

| 变体类 | 视觉 | 使用场景 |
|--------|------|---------|
| `is-warning` | 橙色圆底 + 感叹号「!」 | **警示但非危险**：未保存离开、配额接近上限、操作可逆但需提醒 |
| `is-danger` | 红色圆底 + 叉号「X」 | **危险且不可逆**：删除、清除、永久禁用、批量销毁 |
| `is-success` | 绿色圆底 + 勾「✓」 | **操作完成结果反馈**：批量操作成功、流程完成 |
| `is-info` | 蓝色圆底 + 字母「i」 | **中性信息提示**：版本更新、功能说明、用户引导 |

**用法**：

```vue
<!-- ✅ 推荐：危险操作，标题语义化 + type="danger" 主按钮 -->
<el-dialog class="is-danger" title="删除用户「张三」" width="400px">
  <p>此操作不可撤销，张三的所有数据将被永久删除。</p>
  <template #footer>
    <el-button @click="visible = false">取消</el-button>
    <el-button type="danger" @click="handleDelete">确认删除</el-button>
  </template>
</el-dialog>

<!-- ✅ 推荐：警示提醒，主按钮用 primary（操作本身不危险） -->
<el-dialog class="is-warning" title="离开未保存页面" width="400px">
  <p>当前页有 3 处修改未保存。</p>
  <template #footer>
    <el-button @click="visible = false">取消</el-button>
    <el-button type="primary" @click="handleLeave">保存并离开</el-button>
  </template>
</el-dialog>
```

**按钮个数（footer 放几个按钮）——拆成「退路」和「进路」两部分分别数**：

- **退路**（用户"不往前做"的出口，如 取消 / 稍后 / 留下）：最多 **1 个**。要么给一个退路，要么（纯告知类）不给。
- **进路**（用户"往前做"的正向动作，如 确认删除 / 保存并离开）：**1 个或多个并列分支**。当"往前"有多种走法且它们地位并列（不是主次），就是多个进路。

由此得出的常见形态：

| 弹窗性质 | 按钮数 | 组成 | 典型 |
|---|---|---|---|
| **纯结果告知 / 无需抉择** | **1 个** | 仅一个进路（关闭） | 操作完成反馈（知道了）、单纯信息通知（确定） |
| **一退路 + 一进路** | **2 个** | 退路在左 + 进路（主按钮）在右 | 删除确认（取消 / 确认删除）、版本更新（稍后 / 立即更新） |
| **一退路 + 多个并列进路** | **3 个（或更多）** | 退路在最左 + 若干并列进路在右 | 离开未保存（取消 / 不保存离开 / 保存并离开）：「取消」是退路，「不保存离开」「保存并离开」是两条并列的"往前走"分支 |

- **判断入口**：先分「用户往前走有几种走法」（进路数）+「要不要留一个不做的出口」（退路 0 或 1）。二者相加即按钮数。
- **三钮的合法前提是"多出来的是并列进路"**：三个及以上按钮，仅在多出来的确实是**并列的正向分支**（地位平等、都是"往前走"的不同走法）时才成立。若多出来的是**不相关的第四类动作**（如在删除确认里塞"另存为""导出"），说明它已超出简单确认——回 `dialog-pattern.md` 判据改用更重载体（页面/抽屉），而非在 footer 堆无关按钮。
- **进路里可再分主次**：多个并列进路中，可把最推荐的一个设为 `type="primary"`（如「保存并离开」为主、「不保存离开」用默认样式），但它们语义上仍是并列走法，不是"主操作 + 退路"。
- 按钮**顺序**：退路在最左，进路依次在右；主推荐的进路放最右。**type** 按上文与语义匹配。

**反模式**：

- ❌ **混用语义色与按钮 type**：`class="is-warning"` 配 `type="danger"` 主按钮——语义不一致（警告色标题但危险色按钮，让用户困惑是不是危险操作）。**正确**：变体类与主按钮 type 应匹配语义（is-danger 配 type="danger"，is-warning / is-info / is-success 配 type="primary"）。

- ❌ **不带变体类的危险操作**：`<el-dialog title="删除"><el-button type="danger">确认</el-button></el-dialog>` —— 标题前无视觉警示，仅靠按钮颜色提醒，警示强度弱。**正确**：危险操作一律加 `class="is-danger"`。

- ❌ **滥用 is-success 做"完成态弹窗"**：`is-success` 用于反馈"操作已完成"（多见于批量操作结果汇总、复杂流程完结）。**禁止**用于普通成功提示——后者用 `ElMessage.success()` 即可，不需要弹窗。

- ❌ **变体类用错语义层级**：误把"未保存离开"用 `is-danger`、"删除"用 `is-warning`——会让用户对警示等级的认知失准。**判断标准**：
  - is-warning = "你确定要这么做吗？做错了能反悔"
  - is-danger = "做了就回不去了"

**实现细节见**：`el-theme/components/dialog.scss` 的「语义化标题图标变体」段。
**示例代码见**：`design-spec/examples/dialog.examples.vue` 的「语义化标题」section。
