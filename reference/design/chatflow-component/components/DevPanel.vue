<!-- ============================================================
     开发调试面板 · ChatFlow v1.0
     ------------------------------------------------------------
     提供主题、字号、布局等开发调试功能
     ============================================================ -->
<script setup>
import { ref, onMounted } from 'vue'
import CfIcon from './CfIcon.vue'

const open = ref(false)
const theme = ref('light')
const fontSize = ref('normal')

onMounted(() => {
  // 读取当前设置
  theme.value = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'
  const font = document.documentElement.getAttribute('data-font')
  fontSize.value = font || 'normal'
})

function toggleTheme() {
  if (theme.value === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark')
  } else {
    document.documentElement.removeAttribute('data-theme')
  }
}

function setTheme(newTheme) {
  theme.value = newTheme
  toggleTheme()
}

function setFontSize(size) {
  fontSize.value = size
  if (size === 'normal') {
    document.documentElement.removeAttribute('data-font')
  } else {
    document.documentElement.setAttribute('data-font', size)
  }
}

function copyColors() {
  const colors = {
    '--cf-primary': getComputedStyle(document.documentElement).getPropertyValue('--cf-primary'),
    '--cf-text-1': getComputedStyle(document.documentElement).getPropertyValue('--cf-text-1'),
    '--cf-text-2': getComputedStyle(document.documentElement).getPropertyValue('--cf-text-2'),
    '--cf-page': getComputedStyle(document.documentElement).getPropertyValue('--cf-page'),
    '--cf-surface': getComputedStyle(document.documentElement).getPropertyValue('--cf-surface'),
  }
  navigator.clipboard.writeText(JSON.stringify(colors, null, 2))
  alert('颜色变量已复制到剪贴板')
}
</script>

<template>
  <div class="dev-panel">
    <!-- 浮动按钮 -->
    <button
      class="dev-panel-trigger"
      :class="{ 'is-open': open }"
      @click="open = !open"
      title="开发面板"
    >
      <CfIcon name="settings" :size="20" />
    </button>

    <!-- 面板内容 -->
    <div v-if="open" class="dev-panel-overlay" @click="open = false" />
    <div v-if="open" class="dev-panel-content">
      <div class="dev-panel-header">
        <h3>开发调试面板</h3>
        <button class="dev-panel-close" @click="open = false">
          <CfIcon name="x" :size="18" />
        </button>
      </div>

      <div class="dev-panel-body">
        <!-- 主题切换 -->
        <div class="dev-panel-section">
          <div class="dev-panel-section-title">主题模式</div>
          <div class="dev-panel-buttons">
            <button
              :class="{ 'is-active': theme === 'light' }"
              @click="setTheme('light')"
            >
              <CfIcon name="sun" :size="16" />
              浅色
            </button>
            <button
              :class="{ 'is-active': theme === 'dark' }"
              @click="setTheme('dark')"
            >
              <CfIcon name="moon" :size="16" />
              暗色
            </button>
          </div>
          <div class="dev-panel-hint">
            当前：<code>{{ theme === 'dark' ? 'data-theme="dark"' : '默认浅色' }}</code>
          </div>
        </div>

        <!-- 字号调整 -->
        <div class="dev-panel-section">
          <div class="dev-panel-section-title">字号大小</div>
          <div class="dev-panel-buttons">
            <button
              :class="{ 'is-active': fontSize === 'small' }"
              @click="setFontSize('small')"
            >
              小 (14px)
            </button>
            <button
              :class="{ 'is-active': fontSize === 'normal' }"
              @click="setFontSize('normal')"
            >
              标准 (16px)
            </button>
            <button
              :class="{ 'is-active': fontSize === 'large' }"
              @click="setFontSize('large')"
            >
              大 (18px)
            </button>
          </div>
          <div class="dev-panel-hint">
            当前：<code>{{ fontSize === 'normal' ? '默认' : `data-font="${fontSize}"` }}</code>
          </div>
        </div>

        <!-- 颜色变量 -->
        <div class="dev-panel-section">
          <div class="dev-panel-section-title">颜色变量</div>
          <div class="dev-panel-colors">
            <div class="dev-panel-color-item">
              <span class="dev-panel-color-swatch" style="background:var(--cf-primary)"></span>
              <code>--cf-primary</code>
            </div>
            <div class="dev-panel-color-item">
              <span class="dev-panel-color-swatch" style="background:var(--cf-text-1)"></span>
              <code>--cf-text-1</code>
            </div>
            <div class="dev-panel-color-item">
              <span class="dev-panel-color-swatch" style="background:var(--cf-page)"></span>
              <code>--cf-page</code>
            </div>
          </div>
          <button class="dev-panel-button-outline" @click="copyColors">
            复制颜色变量
          </button>
        </div>

        <!-- 快捷信息 -->
        <div class="dev-panel-section">
          <div class="dev-panel-section-title">快捷信息</div>
          <div class="dev-panel-info">
            <div>设计系统：iflyv</div>
            <div>灰阶：11 档（gray-0 到 gray-10）</div>
            <div>字号单位：rem（自动缩放）</div>
            <div>间距单位：px（固定密度）</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 浮动触发按钮 */
.dev-panel-trigger{
  position:fixed;right:20px;bottom:20px;z-index:9998;
  width:56px;height:56px;
  display:grid;place-items:center;
  border-radius:50%;
  background:var(--cf-primary);
  color:#fff;
  box-shadow:0 4px 12px rgba(0,0,0,0.15);
  cursor:pointer;
  transition:all 0.3s ease;
}
@media (hover:hover){
  .dev-panel-trigger:hover{
    transform:scale(1.1);
    box-shadow:0 6px 16px rgba(0,0,0,0.2);
  }
}
.dev-panel-trigger.is-open{
  background:var(--cf-text-1);
}

/* 遮罩 */
.dev-panel-overlay{
  position:fixed;inset:0;z-index:9998;
  background:rgba(0,0,0,0.4);
}

/* 面板主体 */
.dev-panel-content{
  position:fixed;right:20px;bottom:90px;z-index:9999;
  width:360px;max-height:calc(100vh - 120px);
  display:flex;flex-direction:column;
  background:var(--cf-surface);
  border:1px solid var(--cf-line);
  border-radius:16px;
  box-shadow:0 10px 40px rgba(0,0,0,0.15);
  overflow:hidden;
  animation:panel-in 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes panel-in{
  from{opacity:0;transform:translateY(20px) scale(0.95)}
  to{opacity:1;transform:translateY(0) scale(1)}
}

.dev-panel-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:20px;
  border-bottom:1px solid var(--cf-line);
}
.dev-panel-header h3{
  font-size:16px;font-weight:600;color:var(--cf-text-1);
  margin:0;
}
.dev-panel-close{
  width:32px;height:32px;
  display:grid;place-items:center;
  border-radius:8px;
  background:transparent;
  color:var(--cf-text-3);
  cursor:pointer;
  transition:all 0.15s ease;
}
@media (hover:hover){
  .dev-panel-close:hover{
    background:var(--cf-fill);
    color:var(--cf-text-1);
  }
}

.dev-panel-body{
  flex:1;overflow-y:auto;
  padding:16px;
}

/* 区块 */
.dev-panel-section{
  margin-bottom:20px;
  padding-bottom:20px;
  border-bottom:1px solid var(--cf-line);
}
.dev-panel-section:last-child{
  border-bottom:none;
  margin-bottom:0;
  padding-bottom:0;
}

.dev-panel-section-title{
  font-size:13px;font-weight:600;
  color:var(--cf-text-2);
  margin-bottom:12px;
  text-transform:uppercase;
  letter-spacing:0.05em;
}

/* 按钮组 */
.dev-panel-buttons{
  display:flex;gap:8px;
}
.dev-panel-buttons button{
  flex:1;
  display:flex;align-items:center;justify-content:center;gap:6px;
  padding:10px 12px;
  border:1px solid var(--cf-line);
  border-radius:8px;
  background:transparent;
  font-size:14px;color:var(--cf-text-2);
  cursor:pointer;
  transition:all 0.15s ease;
}
@media (hover:hover){
  .dev-panel-buttons button:hover{
    border-color:var(--iflyv-brand-4);
    background:var(--cf-primary-soft);
    color:var(--cf-text-1);
  }
}
.dev-panel-buttons button.is-active{
  border-color:var(--cf-primary);
  background:var(--cf-primary);
  color:#fff;
  font-weight:500;
}

.dev-panel-hint{
  margin-top:8px;
  font-size:12px;color:var(--cf-text-3);
}
.dev-panel-hint code{
  padding:2px 6px;
  background:var(--cf-fill);
  border-radius:4px;
  font-family:var(--cf-font-mono);
  font-size:11px;
  color:var(--cf-primary);
}

/* 颜色示例 */
.dev-panel-colors{
  display:flex;flex-direction:column;gap:8px;
  margin-bottom:12px;
}
.dev-panel-color-item{
  display:flex;align-items:center;gap:10px;
  padding:8px;
  background:var(--cf-fill);
  border-radius:6px;
}
.dev-panel-color-swatch{
  width:24px;height:24px;
  border-radius:4px;
  border:1px solid var(--cf-line);
  flex:none;
}
.dev-panel-color-item code{
  font-family:var(--cf-font-mono);
  font-size:12px;
  color:var(--cf-text-2);
}

.dev-panel-button-outline{
  width:100%;
  padding:8px 12px;
  border:1px solid var(--cf-line);
  border-radius:6px;
  background:transparent;
  font-size:13px;color:var(--cf-text-2);
  cursor:pointer;
  transition:all 0.15s ease;
}
@media (hover:hover){
  .dev-panel-button-outline:hover{
    border-color:var(--iflyv-brand-4);
    background:var(--cf-primary-soft);
    color:var(--cf-primary);
  }
}

/* 信息列表 */
.dev-panel-info{
  font-size:13px;color:var(--cf-text-2);
  line-height:1.8;
}
</style>
