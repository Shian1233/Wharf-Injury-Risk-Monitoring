<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import UserMenu from './UserMenu.vue'
import AppearancePanel from './AppearancePanel.vue'
import { IconBell, IconChevronDown, IconChevronLeft } from '../icons.js'

// 头像渐变的 id 必须逐实例唯一：同页多个实例引用同一个 id 会互相串色
let uidSeed = 0
const uid = ++uidSeed

const props = defineProps({
  brand: { type: Object, default: () => ({}) },      // { logo, title, subtitle }
  items: { type: Array, default: () => [] },         // [{ key, label, children?: [{ key, label }] }]
  activeKey: { type: String, default: '' },
  collapsed: { type: Boolean, default: false },      // 桌面折叠态
  open: { type: Boolean, default: false },           // H5 抽屉开合
  user: { type: Object, default: () => ({}) },       // { name }
  notificationCount: { type: Number, default: 0 },
  menuItems: { type: Array, default: () => [] },     // 账号菜单
  // 容器宽度低于此值自动收起。这是 JS 常量，不是 CSS 断点 ——
  // 它不参与任何媒体查询，改它不影响布局档位
  autoCollapseWidth: { type: Number, default: 1024 }
})

const emit = defineEmits([
  'update:activeKey', 'update:collapsed', 'update:open',
  'select', 'menuSelect', 'notification'
])

const root = ref(null)
const menuOpen = ref(false)
const apOpen = ref(false)

/* ---------- 折叠 ---------- */

function toggleCollapse () {
  emit('update:collapsed', !props.collapsed)
}

// 只在跨越阈值的那一刻动作，不逐像素同步：这样用户在同一档内的
// 手动切换会保留，直到下一次跨越才被覆盖
let ro = null
let wasNarrow = null

onMounted(() => {
  const host = root.value?.parentElement
  if (!host || !window.ResizeObserver) return
  ro = new ResizeObserver(entries => {
    const narrow = entries[0].contentRect.width < props.autoCollapseWidth
    if (narrow === wasNarrow) return
    wasNarrow = narrow
    if (isH5.value) return          // H5 是抽屉，折叠没有意义
    emit('update:collapsed', narrow)
  })
  ro.observe(host)
})

onBeforeUnmount(() => {
  ro?.disconnect()
  mq?.removeEventListener('change', onBreakpoint)
  document.removeEventListener('click', closeMenu)
  document.removeEventListener('keydown', onKeydown)
})

/* ---------- 断点 ---------- */

// 全局唯一断点，与 styles 里的媒体查询保持一致，改动需两边同步
const MQ_H5 = '(max-width: 767.98px)'
const isH5 = ref(false)
let mq = null
let freezeTimer = null

function onBreakpoint () {
  isH5.value = mq.matches
  // 抽屉状态与账号菜单必须清掉：前者会残留遮罩与滚动锁，
  // 后者两档各有落点，留着会在另一档以打开态复现
  emit('update:open', false)
  menuOpen.value = false
  apOpen.value = false

  const el = document.documentElement
  el.classList.add('is-resizing')
  clearTimeout(freezeTimer)
  freezeTimer = setTimeout(() => el.classList.remove('is-resizing'), 80)
}

onMounted(() => {
  mq = window.matchMedia(MQ_H5)
  isH5.value = mq.matches
  mq.addEventListener('change', onBreakpoint)

  // iOS Safari 只有在存在 touch 监听时才会给元素套用 :active
  document.addEventListener('touchstart', () => {}, { passive: true })
  document.addEventListener('click', closeMenu)
  document.addEventListener('keydown', onKeydown)
})

/* ---------- 抽屉 ---------- */

watch(() => props.open, v => {
  document.body.style.overflow = v && isH5.value ? 'hidden' : ''
})

function closeDrawer () { emit('update:open', false) }

/* ---------- 账号菜单 ---------- */

function closeMenu () {
  menuOpen.value = false
  apOpen.value = false
  closeFly()
}

function onKeydown (e) {
  if (e.key !== 'Escape') return
  closeDrawer()
  closeMenu()
}

function onMenuSelect (item) {
  // 外观设置不是跳转，就地把菜单换成设置面板
  if (item.key === 'appearance') {
    menuOpen.value = false
    apOpen.value = true
    return
  }
  menuOpen.value = false
  emit('menuSelect', item)
}

/* ---------- 菜单项 ---------- */

function select (item) {
  // 分组父项只负责开合，不是跳转目标
  if (item.children?.length) return toggleGroup(item)
  emit('update:activeKey', item.key)
  emit('select', item)
  // 选完关抽屉，留一帧让新的选中态先显示出来再滑走
  if (isH5.value) setTimeout(closeDrawer, 140)
}

/* ---------- 二级菜单 ---------- */

// 展开着的分组。分组之间互不影响，可以同时开多个
const openKeys = ref(new Set())

const parentOf = key => props.items.find(i => i.children?.some(c => c.key === key))

// 选中项落在某个分组里时自动展开该分组，保证选中态看得见
watch(() => props.activeKey, key => {
  const p = parentOf(key)
  if (p && !openKeys.value.has(p.key)) openKeys.value = new Set(openKeys.value).add(p.key)
}, { immediate: true })

const isOpen = item => openKeys.value.has(item.key)
const hasActiveChild = item => !!item.children?.some(c => c.key === props.activeKey)

function toggleGroup (item) {
  // 折叠态没地方放子菜单，改由右侧浮层承接；点击用于触屏，鼠标走 hover
  if (props.collapsed && !isH5.value) {
    flyKey.value === item.key ? closeFly() : openFly(item)
    return
  }
  const next = new Set(openKeys.value)
  next.has(item.key) ? next.delete(item.key) : next.add(item.key)
  openKeys.value = next
}

/* ---------- 折叠态浮层 ---------- */

const flyKey = ref('')
const flyPos = ref({ top: 0, left: 0 })
const itemEls = {}
let flyTimer = null

const flyItem = computed(() => props.items.find(i => i.key === flyKey.value))

// 浮层顶边与父项顶边对齐。用 fixed 定位：.nav 有 overflow，放在里面会被裁
function openFly (item) {
  if (!props.collapsed || isH5.value) return
  clearTimeout(flyTimer)
  const r = itemEls[item.key]?.getBoundingClientRect()
  const sb = root.value?.getBoundingClientRect()
  // 横坐标取侧栏右边线 + 12px，侧栏不贴视口左边时也对得上
  if (r && sb) flyPos.value = { top: r.top, left: sb.right + 12 }
  flyKey.value = item.key
}

function closeFly () {
  clearTimeout(flyTimer)
  flyKey.value = ''
}

// 鼠标从父项移到浮层要穿过 12px 空隙，留一段宽限期不让浮层闪掉
function closeFlyLater () {
  clearTimeout(flyTimer)
  flyTimer = setTimeout(closeFly, 120)
}

function onItemClick (e, item) {
  // 折叠态点分组父项是开浮层，不能冒泡到 document 再被立刻关掉
  if (item.children?.length && props.collapsed) e.stopPropagation()
  select(item)
}

function selectFromFly (child) {
  closeFly()
  select(child)
}

watch(() => props.collapsed, closeFly)

const collapseLabel = computed(() => (props.collapsed ? '展开侧边栏' : '收起侧边栏'))
</script>

<template>
  <aside
    ref="root"
    class="sidebar"
    :class="{ 'is-collapsed': collapsed, 'is-open': open }"
  >
    <!-- 品牌：H5 抽屉里保留，它补的是被抽屉盖住的那段顶栏 -->
    <div class="brand">
      <span v-if="brand.logo" class="brand-logo">
        <img :src="brand.logo" :alt="brand.title" />
      </span>
      <span class="brand-text">
        <span class="brand-title">{{ brand.title }}</span>
        <span v-if="brand.subtitle" class="brand-sub">{{ brand.subtitle }}</span>
      </span>
    </div>

    <nav class="nav" aria-label="主导航">
      <template v-for="item in items" :key="item.key">
        <a
          class="nav-item"
          :class="{
            'is-active': item.key === activeKey,
            'is-group': item.children?.length,
            'is-open': isOpen(item),
            'has-active-child': hasActiveChild(item)
          }"
          :data-label="item.label"
          :aria-expanded="item.children?.length ? String(isOpen(item)) : undefined"
          href="#"
          :ref="el => { if (item.children?.length) itemEls[item.key] = el }"
          @click.prevent="onItemClick($event, item)"
          @mouseenter="item.children?.length && openFly(item)"
          @mouseleave="item.children?.length && closeFlyLater()"
        >
          <span class="nav-icon"><slot name="icon" :item="item" /></span>
          <span class="nav-label">{{ item.label }}</span>
          <span v-if="item.children?.length" class="nav-arrow" aria-hidden="true"><IconChevronDown /></span>
        </a>

        <!-- grid 0fr → 1fr 做高度过渡，不用 JS 量高 -->
        <div
          v-if="item.children?.length"
          class="nav-sub"
          :class="{ 'is-open': isOpen(item) }"
        >
          <div class="nav-sub__inner">
            <a
              v-for="child in item.children"
              :key="child.key"
              class="nav-item nav-child"
              :class="{ 'is-active': child.key === activeKey }"
              :tabindex="isOpen(item) && !collapsed ? undefined : -1"
              href="#"
              @click.prevent="select(child)"
            >
              <span class="nav-label">{{ child.label }}</span>
            </a>
          </div>
        </div>
      </template>
    </nav>

    <!-- 折叠态的二级浮层。放在 .nav 外面，避免被它的 overflow 裁掉 -->
    <div
      v-if="flyItem"
      class="nav-fly"
      role="menu"
      :aria-label="flyItem.label"
      :style="{ top: `${flyPos.top}px`, left: `${flyPos.left}px` }"
      @click.stop
      @mouseenter="openFly(flyItem)"
      @mouseleave="closeFlyLater"
    >
      <div class="nav-fly__title">{{ flyItem.label }}</div>
      <a
        v-for="child in flyItem.children"
        :key="child.key"
        class="nav-fly__item"
        :class="{ 'is-active': child.key === activeKey }"
        role="menuitem"
        href="#"
        @click.prevent="selectFromFly(child)"
      >{{ child.label }}</a>
    </div>

    <!-- 底部：用户 + 通知。折叠态下两者竖排 -->
    <div class="sidebar-foot">
      <div class="user-bar">
        <UserMenu
          :items="menuItems"
          :open="menuOpen"
          @select="onMenuSelect"
        />

        <AppearancePanel :open="apOpen" @close="apOpen = false" />

        <button
          class="user"
          type="button"
          aria-haspopup="menu"
          :aria-expanded="String(menuOpen)"
          @click.stop="apOpen = false; menuOpen = !menuOpen"
        >
          <span class="avatar" aria-hidden="true">
            <svg viewBox="0 0 40 40">
              <defs>
                <linearGradient :id="`av-${uid}`" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0" stop-color="#7FA8E8" />
                  <stop offset="1" stop-color="#3D6FD0" />
                </linearGradient>
              </defs>
              <circle cx="20" cy="20" r="20" :fill="`url(#av-${uid})`" />
              <circle cx="20" cy="16.4" r="6.4" fill="#fff" opacity=".95" />
              <path d="M6.6 36.4c1.6-6.3 7-10.2 13.4-10.2s11.8 3.9 13.4 10.2A20 20 0 0 1 20 40a20 20 0 0 1-13.4-3.6Z" fill="#fff" opacity=".95" />
            </svg>
          </span>
          <span class="user-name">{{ user.name }}</span>
        </button>

        <button
          class="icon-btn bell-btn"
          type="button"
          :aria-label="`通知，${notificationCount} 条未读`"
          @click="emit('notification')"
        >
          <IconBell />
          <span v-if="notificationCount > 0" class="badge">{{ notificationCount }}</span>
        </button>
      </div>
    </div>

    <!-- 折叠把手：贴在右边缘垂直居中。放在 .sidebar 内部，
         横坐标自动跟着侧栏宽度走，不需要额外的 calc 同步 -->
    <button
      class="rail-toggle"
      type="button"
      :aria-label="collapseLabel"
      :aria-expanded="String(!collapsed)"
      @click="toggleCollapse"
    >
      <svg class="rail-toggle__shape" width="17" height="82" viewBox="0 0 17 82" fill="none" aria-hidden="true">
        <path
          class="rail-toggle__fill"
          d="M0,0L0,81.254836C0,77.011374,1.685710,72.941702,4.686291,69.941122L11.313709,63.313712C14.314291,60.313132,16,56.243460,16,52L16,29.254836C16,25.011374,14.314291,20.941708,11.313709,17.941126L4.686291,11.313708C1.685710,8.313126,0,4.243464,0,0Z"
        />
        <path
          class="rail-toggle__stroke"
          d="M0,81.254836C0,77.011374,1.685710,72.941702,4.686291,69.941122L11.313709,63.313712C14.314291,60.313132,16,56.243460,16,52L16,29.254836C16,25.011374,14.314291,20.941708,11.313709,17.941126L4.686291,11.313708C1.685710,8.313126,0,4.243464,0,0"
        />
      </svg>
      <span class="rail-toggle__icon" aria-hidden="true"><IconChevronLeft /></span>
    </button>
  </aside>

  <div class="overlay" :class="{ 'is-open': open }" @click="closeDrawer" />
</template>

<style scoped>
/* ---------- 容器 ---------- */

.sidebar {
  --sb-width: 232px;
  --sb-width-collapsed: 68px;
  --sb-pad: 12px;
  --sb-radius: var(--iflyv-radius-md);
  --sb-item-h: 44px;
  --sb-text: var(--app-text-1);
  --sb-text-muted: var(--app-text-3);
  --sb-active: var(--app-brand);
  --sb-active-bg: var(--app-brand-bg);
  --sb-hover-bg: var(--app-bg-hover);
  --sb-divider: var(--app-border);

  /* 0 = 展开，1 = 折叠。折叠态的所有几何量都由这个开关算出来，
     不写第二套规则。H5 档在文件末尾把它强制归 0 */
  --sb-collapsed: 0;

  /* 折叠态可用内容宽 = 68 - 12*2 = 44px，与菜单项等宽。
     图标按钮的左右外边距由它反推，展开态与折叠态共用同一个值 */
  --sb-btn-inset: calc((44px - var(--btn)) / 2);
  --sb-btn-step: calc(var(--btn) + 8px);

  position: relative;
  display: flex;
  flex-direction: column;
  flex: 0 0 auto;
  width: calc(var(--sb-width) + (var(--sb-width-collapsed) - var(--sb-width)) * var(--sb-collapsed));
  height: 100%;
  padding: 0 var(--sb-pad);
  background: var(--app-bg-panel);
  border-right: 1px solid var(--sb-divider);
  transition: width var(--iflyv-duration-normal) var(--iflyv-ease-default);
}

.sidebar.is-collapsed { --sb-collapsed: 1; }

.sidebar::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 140px;
  pointer-events: none;
  /* 从品牌色派生，不写死 rgba：换品牌时晕染自动跟着变 */
  background:
    radial-gradient(160px 90px at 60% -10%,
      color-mix(in srgb, var(--app-brand) 7%, transparent), transparent 70%);
}

.sidebar > * { position: relative; }

/* ---------- 品牌 ---------- */

.brand {
  display: flex;
  align-items: center;
  gap: var(--iflyv-spacing-2);
  height: 72px;
  /* 4px = 折叠态 (44 - 36) / 2，保证 logo 在两种状态下横坐标一致 */
  padding: 0 var(--iflyv-spacing-1);
  flex: 0 0 auto;
}

.brand-logo {
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
}

.brand-logo img { display: block; width: 100%; height: 100%; object-fit: contain; }

/* 文字块统一由 --sb-collapsed 控制淡入淡出；pointer-events 常关，
   折叠后溢出到侧边栏外的隐形文字不会挡住点击 */
.brand-text,
.nav-label,
.user-name {
  opacity: calc(1 - var(--sb-collapsed));
  pointer-events: none;
  /* 折叠时文字立刻淡出，展开时等宽度先撑开一段再淡入 */
  transition: opacity calc(var(--iflyv-duration-normal) * .5) var(--iflyv-ease-default)
    calc(var(--iflyv-duration-normal) * .35 * (1 - var(--sb-collapsed)));
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: var(--iflyv-spacing-1);
  min-width: 0;
  white-space: nowrap;
}

.brand-title {
  font-size: var(--iflyv-font-size-16);
  font-weight: var(--iflyv-font-weight-semibold);
  letter-spacing: .2px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.brand-sub { font-size: var(--iflyv-font-size-12); color: var(--sb-text-muted); }

/* ---------- 导航 ---------- */

.nav {
  display: flex;
  flex-direction: column;
  gap: var(--iflyv-spacing-2);
  padding: var(--iflyv-spacing-2) 0;
  flex: 1 1 auto;
  overflow-y: auto;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--iflyv-spacing-2);
  height: var(--sb-item-h);
  padding: 0 var(--iflyv-spacing-3);
  border-radius: var(--sb-radius);
  color: var(--sb-text);
  font-size: var(--iflyv-font-size-14);
  font-weight: var(--iflyv-font-weight-regular);
  text-decoration: none;
  white-space: nowrap;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background-color var(--iflyv-duration-fast) var(--iflyv-ease-default), color var(--iflyv-duration-fast) var(--iflyv-ease-default);
}

/* 未选中态字重 400 偏细、500 偏重，用极细描边补出中间的重量 */
.nav-item:not(.is-active) { -webkit-text-stroke: .2px currentColor; }

@media (hover: hover) {
  .nav-item:hover { background: var(--sb-hover-bg); }
}

.nav-item:active { background: var(--sb-hover-bg); }

.nav-item.is-active {
  background: var(--sb-active-bg);
  color: var(--sb-active);
  font-weight: var(--iflyv-font-weight-semibold);
}

.nav-icon {
  flex: 0 0 auto;
  width: 20px;
  height: 20px;
  color: var(--sb-text);
}

.nav-item.is-active .nav-icon { color: var(--sb-active); }

.nav-icon :deep(svg) { display: block; width: 100%; height: 100%; }

.nav-label { overflow: hidden; text-overflow: ellipsis; }

/* ---------- 二级菜单 ---------- */

.nav-item.is-group .nav-label { flex: 1 1 auto; }

/* 子项选中时父项只变色加粗，不铺底——底色留给真正的选中项 */
.nav-item.has-active-child {
  color: var(--sb-active);
  font-weight: var(--iflyv-font-weight-semibold);
  -webkit-text-stroke: 0;
}

.nav-item.has-active-child .nav-icon { color: var(--sb-active); }

/* 折叠态子项看不见，父项整块铺底兜住选中位置 */
.sidebar.is-collapsed .nav-item.has-active-child { background: var(--sb-active-bg); }

.nav-arrow {
  flex: 0 0 auto;
  width: 16px;
  height: 16px;
  color: var(--sb-text-muted);
  opacity: calc(1 - var(--sb-collapsed));
  transition: transform var(--iflyv-duration-normal) var(--iflyv-ease-default),
    opacity calc(var(--iflyv-duration-normal) * .5) var(--iflyv-ease-default);
}

.nav-arrow :deep(svg) { display: block; width: 100%; height: 100%; }

.nav-item.is-open .nav-arrow { transform: rotate(180deg); }

/* .nav 的 gap 会在收起的子菜单两侧各留一份，负边距抵掉上面那份；
   展开时由首个子项的 margin-top 补回来，节奏与一级项一致 */
.nav-sub {
  display: grid;
  grid-template-rows: 0fr;
  margin-top: calc(var(--iflyv-spacing-2) * -1);
  transition: grid-template-rows var(--iflyv-duration-normal) var(--iflyv-ease-default);
}

.nav-sub.is-open { grid-template-rows: 1fr; }

/* 折叠态收起子菜单，但不清 openKeys，展开侧栏后原样恢复 */
.sidebar.is-collapsed .nav-sub { grid-template-rows: 0fr; }

.nav-sub__inner {
  display: flex;
  flex-direction: column;
  gap: var(--iflyv-spacing-2);
  min-height: 0;
  overflow: hidden;
}

.nav-child:first-child { margin-top: var(--iflyv-spacing-2); flex-shrink: 0; }

/* 子项文字比一级文字再缩进 8px：12 内边距 + 20 图标 + 8 间距 + 8 */
.nav-child {
  flex-shrink: 0;
  padding-left: calc(var(--iflyv-spacing-3) + 20px + var(--iflyv-spacing-2) * 2);
  color: var(--app-text-2);
}

.nav-child.is-active { color: var(--sb-active); }

/* 子项不会出现在折叠态，不需要悬浮提示 */
.nav-child::after { display: none; }

/* 分组父项在折叠态由浮层自带标题，不再叠一个悬浮提示 */
.nav-item.is-group::after { display: none; }

/* ---------- 折叠态浮层 ---------- */

/* 坐标由 JS 给出。只在桌面折叠态出现，此时 .sidebar 无 transform，fixed 相对视口 */
.sidebar > .nav-fly {
  position: fixed;
  z-index: 40;
  min-width: 200px;
  padding: var(--iflyv-spacing-2);
  border: 1px solid var(--sb-divider);
  border-radius: var(--iflyv-radius-md);
  background: var(--app-bg-panel);
  box-shadow: var(--app-shadow-independent);
}

/* 浮层左侧补一条 12px 透明桥，鼠标从父项斜着移过来也不会断 hover */
.nav-fly::before {
  content: "";
  position: absolute;
  inset: 0 100% 0 auto;
  width: var(--iflyv-spacing-3);
}

.nav-fly__title {
  padding: var(--iflyv-spacing-2) var(--iflyv-spacing-3);
  color: var(--sb-text-muted);
  font-size: var(--iflyv-font-size-12);
}

.nav-fly__item {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 var(--iflyv-spacing-3);
  border-radius: var(--iflyv-radius-sm);
  color: var(--app-text-2);
  font-size: var(--iflyv-font-size-14);
  font-weight: var(--iflyv-font-weight-regular);
  text-decoration: none;
  white-space: nowrap;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background-color var(--iflyv-duration-fast) var(--iflyv-ease-default);
}

/* 字重、颜色与展开态的子项一致：未选中同样补 .2px 描边 */
.nav-fly__item:not(.is-active) { -webkit-text-stroke: .2px currentColor; }

@media (hover: hover) {
  .nav-fly__item:hover { background: var(--sb-hover-bg); }
}

.nav-fly__item:active { background: var(--sb-hover-bg); }

.nav-fly__item.is-active {
  background: var(--sb-active-bg);
  color: var(--sb-active);
  font-weight: var(--iflyv-font-weight-semibold);
}

/* 折叠态的悬浮提示。触屏没有 hover 因而没有提示，不做补偿——
   认不出图标就点把手展开回去 */
@media (hover: hover) {
  .nav-item::after {
    content: attr(data-label);
    position: absolute;
    left: calc(100% + var(--iflyv-spacing-3));
    top: 50%;
    transform: translateY(-50%);
    padding: var(--iflyv-spacing-2) var(--iflyv-spacing-3);
    border-radius: var(--iflyv-radius-xs);
    background: var(--app-tooltip-bg);
    color: var(--app-text-on-dark);
    font-size: var(--iflyv-font-size-12);
    font-weight: var(--iflyv-font-weight-regular);
    white-space: nowrap;
    opacity: 0;
    pointer-events: none;
    z-index: 20;
    transition: opacity var(--iflyv-duration-fast) var(--iflyv-ease-default);
  }

  .nav-item:hover::after { opacity: var(--sb-collapsed); }
}

/* ---------- 底部 ---------- */

.sidebar-foot {
  flex: 0 0 auto;
  padding-bottom: calc(var(--iflyv-spacing-3) + env(safe-area-inset-bottom, 0px));
}

/* 折叠态在 68px 栏里竖排，所以折叠后向下让出一行给通知 */
.user-bar {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--iflyv-spacing-2);
  padding-top: var(--iflyv-spacing-3);
  padding-bottom: calc(var(--sb-btn-step) * var(--sb-collapsed));
  border-top: 1px solid var(--sb-divider);
  transition: padding-bottom var(--iflyv-duration-normal) var(--iflyv-ease-default);
}

/* flex: 0 1 auto 而不是 1 1 auto —— 铺满整行会让 hover 背景一直延伸到
   相邻按钮下面，几个控件看起来像一个 */
.user {
  display: flex;
  align-items: center;
  gap: var(--iflyv-spacing-2);
  flex: 0 1 auto;
  min-width: 0;
  height: 44px;
  padding: 0 var(--iflyv-spacing-2);
  border: 0;
  border-radius: var(--sb-radius);
  background: transparent;
  color: var(--sb-text);
  font: inherit;
  font-size: var(--iflyv-font-size-14);
  font-weight: var(--iflyv-font-weight-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background-color var(--iflyv-duration-fast) var(--iflyv-ease-default);
}

@media (hover: hover) {
  .user:hover { background: var(--sb-hover-bg); }
}

.user:active { background: var(--sb-hover-bg); }

.avatar {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  overflow: hidden;
}

.avatar svg { display: block; width: 100%; height: 100%; }

.user-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.icon-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: var(--btn);
  height: var(--btn);
  padding: 0;
  border: 0;
  border-radius: var(--iflyv-radius-sm);
  background: transparent;
  color: var(--sb-text);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background-color var(--iflyv-duration-fast) var(--iflyv-ease-default), color var(--iflyv-duration-fast) var(--iflyv-ease-default);
}

@media (hover: hover) {
  .icon-btn:hover { background: var(--sb-hover-bg); }
}

.icon-btn:active { background: var(--sb-hover-bg); }

.icon-btn :deep(svg) { display: block; width: 20px; height: 20px; }

/* 展开态垂直居中在用户行，折叠态落到头像正下方 */
.bell-btn {
  position: absolute;
  right: var(--sb-btn-inset);
  bottom: calc(5px - 1px * var(--sb-collapsed));
  transition: bottom var(--iflyv-duration-normal) var(--iflyv-ease-default), background-color var(--iflyv-duration-fast) var(--iflyv-ease-default), color var(--iflyv-duration-fast) var(--iflyv-ease-default);
}

.badge {
  position: absolute;
  top: 1px;
  right: 1px;
  min-width: 16px;
  height: 16px;
  padding: 0 var(--iflyv-spacing-1);
  border-radius: var(--iflyv-radius-full);
  background: var(--app-danger);
  color: var(--app-text-on-dark);
  font-size: var(--iflyv-font-size-12);
  line-height: 16px;
  text-align: center;
  font-weight: var(--iflyv-font-weight-semibold);
}

/* ---------- 折叠把手 ---------- */

/* 侧栏边线在中段向外鼓出的一个凸包。左侧竖边与边线齐平，
   两肩是 45° 斜切 + 圆角，中间一段竖直外沿。
   .sidebar > * 那条规则优先级是 (0,1,1)，这里必须用同等选择器才压得住 */
.sidebar > .rail-toggle {
  position: absolute;
  top: 50%;
  right: -17px;
  /* -1px 让凸包左边缘正好压在侧栏那条 1px 边线上，接缝不露白 */
  transform: translate(-1px, -50%);
  z-index: 30;
  width: 17px;
  height: 82px;
  padding: 0;
  border: 0;
  background: transparent;
  /* color 驱动凸包填充（__fill 用 currentColor），hover 时整块染灰 */
  color: var(--app-bg-panel);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: color var(--iflyv-duration-fast) var(--iflyv-ease-default);
}

.rail-toggle__shape { position: absolute; inset: 0; width: 100%; height: 100%; }

.rail-toggle__fill { fill: currentColor; }

.rail-toggle__stroke { fill: none; stroke: var(--sb-divider); stroke-width: 1; }

.rail-toggle__icon {
  position: absolute;
  top: 50%;
  left: 50%;
  /* 再往左 1px：凸包最宽处偏左，视觉重心才在中间 */
  transform: translate(calc(-50% - 1px), -50%);
  display: block;
  width: 14px;
  height: 14px;
  color: var(--sb-text-muted);
  transition: transform var(--iflyv-duration-normal) var(--iflyv-ease-default), color var(--iflyv-duration-fast) var(--iflyv-ease-default);
}

.rail-toggle__icon :deep(svg) { display: block; width: 100%; height: 100%; }

@media (hover: hover) {
  .sidebar > .rail-toggle:hover { color: var(--sb-hover-bg); }
  .sidebar > .rail-toggle:hover .rail-toggle__icon { color: var(--sb-text); }
}

.sidebar > .rail-toggle:active { color: var(--sb-hover-bg); }

.sidebar.is-collapsed .rail-toggle__icon {
  transform: translate(calc(-50% - 1px), -50%) rotate(180deg);
}

/* ---------- 遮罩 ---------- */

.overlay { display: none; }

/* ============================================================
   全局唯一断点 768px。侧栏的自动收起由 ResizeObserver 判断容器
   宽度驱动，不占用媒体断点
   ============================================================ */

@media (max-width: 767.98px) {
  /* 抽屉本身就是覆盖层，折叠没有意义：强制归 0 覆盖手动折叠。
     不清 is-collapsed 类，拖回桌面时折叠选择原样还在 */
  .sidebar { --sb-collapsed: 0 !important; }

  /* 关闭态必须带 visibility: hidden，否则移出视口的导航
     仍能被 Tab 聚焦，键盘用户会跳进看不见的链接里 */
  .sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 100;
    width: min(var(--sb-width), 80vw);
    transform: translateX(-100%);
    visibility: hidden;
    transition: transform var(--iflyv-duration-normal) var(--iflyv-ease-default),
                visibility 0s linear var(--iflyv-duration-normal);
  }

  .sidebar.is-open {
    transform: none;
    visibility: visible;
    box-shadow: var(--app-shadow-independent);
    transition: transform var(--iflyv-duration-normal) var(--iflyv-ease-default), visibility 0s;
  }

  .sidebar > .rail-toggle { display: none; }

  .overlay {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 99;
    background: var(--app-mask);
    /* 清单：半透明背景必须配合 backdrop-filter */
    backdrop-filter: blur(2px);
    opacity: 0;
    visibility: hidden;
    transition: opacity var(--iflyv-duration-normal) var(--iflyv-ease-default),
                visibility 0s linear var(--iflyv-duration-normal);
  }

  .overlay.is-open {
    opacity: 1;
    visibility: visible;
    transition: opacity var(--iflyv-duration-normal) var(--iflyv-ease-default), visibility 0s;
  }
}
</style>
