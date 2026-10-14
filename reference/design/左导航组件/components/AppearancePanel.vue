<script setup>
import { ref } from 'vue'

const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['close'])

const THEMES = [
  { key: 'light', label: '浅色' },
  { key: 'dark', label: '深色' }
]

const FONTS = [
  { key: 'small', label: '小' },
  { key: 'normal', label: '标准' },
  { key: 'large', label: '大' }
]

const root = document.documentElement

// 演示包不做持久化：每次打开一律回到默认态（浅色 / 标准字号）。
// 这是演示与产品的区别 —— 产品里主题是长期偏好该记住，
// 而演示会发给不同的人看，上次切过的状态不该带到下次
const theme = ref('light')
const font = ref('normal')

let themingTimer = null

function setTheme (k) {
  if (theme.value === k) return
  theme.value = k

  // 挂 200ms 的全局颜色过渡，切完摘掉。不常驻，否则 hover 等交互都会被拖慢
  root.classList.add('is-theming')
  clearTimeout(themingTimer)
  themingTimer = setTimeout(() => root.classList.remove('is-theming'), 220)

  if (k === 'dark') root.dataset.theme = 'dark'
  else delete root.dataset.theme
}

function setFont (k) {
  font.value = k
  if (k === 'normal') delete root.dataset.font
  else root.dataset.font = k
}
</script>

<template>
  <div class="appearance" :class="{ 'is-open': open }" @click.stop>
    <div class="ap-row">
      <span class="ap-label">主题</span>
      <div class="ap-seg">
        <button
          v-for="t in THEMES"
          :key="t.key"
          class="ap-btn"
          :class="{ 'is-on': theme === t.key }"
          type="button"
          @click="setTheme(t.key)"
        >{{ t.label }}</button>
      </div>
    </div>

    <div class="ap-row">
      <span class="ap-label">字号</span>
      <div class="ap-seg">
        <button
          v-for="f in FONTS"
          :key="f.key"
          class="ap-btn"
          :class="{ 'is-on': font === f.key }"
          type="button"
          @click="setFont(f.key)"
        >{{ f.label }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 挂在账号菜单同一个定位容器上，向上弹 */
.appearance {
  position: absolute;
  left: 0;
  bottom: calc(100% + var(--iflyv-spacing-2));
  z-index: 60;
  min-width: 200px;
  padding: var(--iflyv-spacing-3);
  border-radius: var(--iflyv-radius-lg);
  background: var(--app-bg-panel);
  border: 1px solid var(--app-border-strong);
  box-shadow: var(--app-shadow-related);
  opacity: 0;
  visibility: hidden;
  transform: translateY(6px);
  transition: opacity var(--iflyv-duration-normal) var(--iflyv-ease-default),
              transform var(--iflyv-duration-normal) var(--iflyv-ease-default),
              visibility 0s linear var(--iflyv-duration-normal);
}

.appearance.is-open {
  opacity: 1;
  visibility: visible;
  transform: none;
  transition: opacity var(--iflyv-duration-normal) var(--iflyv-ease-default),
              transform var(--iflyv-duration-normal) var(--iflyv-ease-default),
              visibility 0s;
}

.ap-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--iflyv-spacing-3);
}

.ap-row + .ap-row { margin-top: var(--iflyv-spacing-3); }

.ap-label {
  font-size: var(--iflyv-font-size-14);
  color: var(--app-text-2);
  white-space: nowrap;
}

.ap-seg {
  display: flex;
  gap: 2px;
  padding: 2px;
  border-radius: var(--iflyv-radius-sm);
  background: var(--app-bg-hover);
}

.ap-btn {
  padding: var(--iflyv-spacing-1) var(--iflyv-spacing-2);
  border: 0;
  border-radius: var(--iflyv-radius-xs);
  background: transparent;
  color: var(--app-text-2);
  font: inherit;
  font-size: var(--iflyv-font-size-12);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background-color var(--iflyv-duration-fast) var(--iflyv-ease-default),
              color var(--iflyv-duration-fast) var(--iflyv-ease-default);
}

@media (hover: hover) {
  .ap-btn:hover { color: var(--app-text-1); }
}

/* 选中态用品牌底白字。原来是「面板底 + 一级文字色」，
   暗色下面板底和槽底两种深色几乎同色，文字压上去看不清 */
.ap-btn.is-on {
  background: var(--app-brand);
  color: var(--app-text-on-dark);
  font-weight: var(--iflyv-font-weight-semibold);
}

@media (hover: hover) {
  .ap-btn.is-on:hover { color: var(--app-text-on-dark); }
}
</style>
