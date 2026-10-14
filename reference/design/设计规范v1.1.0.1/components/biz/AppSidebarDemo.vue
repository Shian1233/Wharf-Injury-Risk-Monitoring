<template>
  <section id="app-sidebar" class="demo-section">
    <h2 class="demo-section__title">AppSidebar 左导航</h2>
    <p class="demo-section__desc">
      应用级固定左栏，承载品牌、模块导航、账号和通知。最多两级菜单，桌面可折叠，移动端自动转抽屉。
      详见 <code>references/component-interaction.md</code>「AppSidebar 左导航」段。
    </p>

    <div class="demo-block control-showcase">
      <div class="control-showcase__main">
      <div class="demo-desc">
        <strong>基础用法</strong> — 实际尺寸预览，点击右边缘把手可折叠，缩窄浏览器窗口观察自动收起和抽屉模式
      </div>
      <div class="sidebar-demo-stage">
        <AppSidebar
          v-model:active-key="activeKey"
          v-model:collapsed="collapsed"
          v-model:open="drawerOpen"
          :brand="brand"
          :items="navItems"
          :user="user"
          :notification-count="notificationCount"
          :menu-items="menuItems"
        />
        <div class="sidebar-demo-content">
          <div class="sidebar-demo-topbar">
            <button
              type="button"
              class="sidebar-demo-menu-btn"
              @click="drawerOpen = true"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="4" y1="6" x2="20" y2="6" />
                <line x1="4" y1="12" x2="20" y2="12" />
                <line x1="4" y1="18" x2="20" y2="18" />
              </svg>
              <span>菜单</span>
            </button>
            <span class="sidebar-demo-topbar-title">{{ activeLabel }}</span>
          </div>
        </div>
      </div>
      </div>
      <aside class="config-card">
        <p class="config-card__title">配置项</p>
        <el-form label-width="auto">
          <el-form-item label="当前选中">
            <el-select v-model="activeKey">
              <el-option
                v-for="opt in navOptions"
                :key="opt.key"
                :label="opt.label"
                :value="opt.key"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="折叠">
            <el-switch v-model="collapsed" />
          </el-form-item>
          <el-form-item label="未读通知">
            <el-input-number
              v-model="notificationCount"
              :min="0"
              controls-position="right"
            />
          </el-form-item>
        </el-form>
      </aside>
    </div>

    <div class="demo-block">
      <div class="demo-desc">
        <strong>自定义图标</strong> — 每项通过 <code>icon</code> 传入 Lucide 组件，也可用 <code>#icon</code> 插槽统一接管
      </div>
      <div class="sidebar-demo-stage">
        <AppSidebar
          v-model:active-key="activeKey2"
          v-model:collapsed="collapsed2"
          v-model:open="drawerOpen2"
          :brand="{ title: '自定义图标示例' }"
          :items="customIconItems"
          :user="user"
          :notification-count="0"
          :menu-items="[]"
        />
        <div class="sidebar-demo-content">
          <div class="sidebar-demo-topbar">
            <button
              type="button"
              class="sidebar-demo-menu-btn"
              @click="drawerOpen2 = true"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="4" y1="6" x2="20" y2="6" />
                <line x1="4" y1="12" x2="20" y2="12" />
                <line x1="4" y1="18" x2="20" y2="18" />
              </svg>
              <span>菜单</span>
            </button>
            <span class="sidebar-demo-topbar-title">
              {{ customIconItems.find(i => i.key === activeKey2)?.label || '自定义图标' }}
            </span>
          </div>
          <div class="sidebar-demo-main">
            <div class="sidebar-demo-card">
              <div class="sidebar-demo-card__content">
                图标统一使用 Lucide 图标库，<code>icon</code> 字段直接传组件本身，
                如 <code>{ key: 'home', label: '首页', icon: House }</code>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { AppSidebar } from '../../../../design-spec/components'
import type { SidebarNavItem, SidebarMenuItem } from '../../../../design-spec/components'
import {
  MessageSquare,
  BookOpen,
  Settings,
  UserRound,
  LogOut,
  Bell,
  House,
  Compass,
  Library,
  ChartColumn,
} from 'lucide-vue-next'

/* ========== 示例1：完整功能 ========== */

const activeKey = ref('qa')
const collapsed = ref(false)
const drawerOpen = ref(false)
const notificationCount = ref(6)

const brand = {
  logo: `${import.meta.env.BASE_URL}cumt-emblem.png`,
  title: '应急管理学科大模型',
  subtitle: '中国矿业大学',
}

const navItems: SidebarNavItem[] = [
  { key: 'qa', label: '学科问答', icon: MessageSquare },
  {
    key: 'kb',
    label: '学科知识库',
    icon: BookOpen,
    children: [
      { key: 'kb-personal', label: '个人知识库' },
      { key: 'kb-shared', label: '共享知识库' },
      { key: 'kb-public', label: '公共知识库' },
    ],
  },
  { key: 'settings', label: '系统设置', icon: Settings },
]

const user = {
  name: '刘承颐老师',
  role: 'teacher-male' as const,
}

const menuItems: SidebarMenuItem[] = [
  { key: 'profile', label: '个人资料', icon: UserRound },
  { key: 'logout', label: '退出登录', icon: LogOut, divided: true },
]

const navOptions = navItems.flatMap(i =>
  i.children ? i.children.map(c => ({ key: c.key, label: `${i.label} / ${c.label}` })) : [{ key: i.key, label: i.label }]
)

const activeLabel = computed(() => {
  const flat = navItems.flatMap(i =>
    i.children ? i.children.map(c => ({ ...c, parent: i.label })) : [i]
  )
  const hit = flat.find(i => i.key === activeKey.value)
  if (!hit) return '未选中'
  return 'parent' in hit ? `${hit.parent} / ${hit.label}` : hit.label
})

/* ========== 示例2：自定义图标 ========== */

const activeKey2 = ref('home')
const collapsed2 = ref(false)
const drawerOpen2 = ref(false)

const customIconItems: SidebarNavItem[] = [
  { key: 'home', label: '首页', icon: House },
  { key: 'explore', label: '探索', icon: Compass },
  { key: 'library', label: '资源库', icon: Library },
  { key: 'analytics', label: '数据分析', icon: ChartColumn },
]
</script>

<script lang="ts">
export default { components: { Bell } }
</script>

<style scoped>
/* Demo 专用样式：左侧边栏 + 右侧内容的布局舞台 */
.sidebar-demo-stage {
  display: flex;
  width: 100%;
  height: 600px;
  border: 1px solid var(--iflyv-border-base);
  border-radius: var(--iflyv-radius-lg);
  overflow: hidden;
  background: var(--iflyv-bg-base);
}

.sidebar-demo-content {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
}

.sidebar-demo-topbar {
  display: flex;
  align-items: center;
  gap: var(--iflyv-spacing-3);
  height: 56px;
  padding: 0 var(--iflyv-spacing-4);
  border-bottom: 1px solid var(--iflyv-border-base);
  background: var(--iflyv-bg-panel);
}

/* 抽屉触发按钮：桌面隐藏，<768px 才显示 */
.sidebar-demo-menu-btn {
  display: none;
  align-items: center;
  gap: var(--iflyv-spacing-2);
  height: 36px;
  padding: 0 var(--iflyv-spacing-3);
  border: 1px solid var(--iflyv-border-base);
  border-radius: var(--iflyv-radius-md);
  background: transparent;
  color: var(--iflyv-text-2);
  font: inherit;
  font-size: var(--iflyv-font-size-14);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background-color var(--iflyv-duration-fast) var(--iflyv-ease-default);
}

@media (hover: hover) {
  .sidebar-demo-menu-btn:hover {
    background: var(--iflyv-bg-inset);
  }
}

@media (max-width: 767.98px) {
  .sidebar-demo-menu-btn { display: flex; }
}

.sidebar-demo-topbar-title {
  font-size: var(--iflyv-font-size-16);
  font-weight: var(--iflyv-font-weight-semibold);
  color: var(--iflyv-text-1);
}

.sidebar-demo-main {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--iflyv-spacing-4);
  padding: var(--iflyv-spacing-4);
  flex: 1 1 auto;
  overflow-y: auto;
}

.sidebar-demo-card {
  padding: var(--iflyv-spacing-4);
  border: 1px solid var(--iflyv-border-base);
  border-radius: var(--iflyv-radius-lg);
  background: var(--iflyv-bg-panel);
}

.sidebar-demo-card__title {
  margin-bottom: var(--iflyv-spacing-2);
  font-size: var(--iflyv-font-size-12);
  font-weight: var(--iflyv-font-weight-semibold);
  color: var(--iflyv-text-3);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.sidebar-demo-card__content {
  font-size: var(--iflyv-font-size-14);
  color: var(--iflyv-text-1);
}

/* 左示例 + 右配置卡横向布局（与 StepBar / DatePicker 配置式范式一致） */
.control-showcase {
  display: flex;
  align-items: flex-start;
  gap: calc(var(--iflyv-spacing-8) + var(--iflyv-spacing-4));
}
.control-showcase__main { flex: 1; min-width: 0; }

@media (max-width: 1100px) {
  .control-showcase { flex-direction: column; }
  .config-card { width: 100%; }
}

.config-card {
  flex: 0 0 auto;
  width: 280px;
  align-self: flex-start;
  padding: var(--iflyv-spacing-4);
  background: var(--iflyv-bg-panel);
  border: 1px solid var(--iflyv-border-subtle);
  border-radius: var(--iflyv-radius-md);
}
.config-card__title {
  margin: 0 0 var(--iflyv-spacing-4);
  color: var(--iflyv-text-1);
  font: var(--iflyv-font-title-component);
}
.config-card :deep(.el-select),
.config-card :deep(.el-input-number) {
  width: 100%;
}
</style>
