<!-- ============================================================
     基础模型选择 · ChatFlow v1.0
     ------------------------------------------------------------
     下拉里带一条固定的标题栏（「模型选择」），选项列表单独滚动。
     选中项主色加粗 + 右侧对勾；对勾常驻但透明，选中只改 opacity，
     避免出现/消失时整行宽度跳动。

     只有 core 模型带能力插件，切到通用模型时技能入口整行收起
     （由 ChatComposer 依据 model.core 处理）。
     ============================================================ -->
<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import CfIcon from './CfIcon.vue'

const props = defineProps({
  /** [{id,name,core}] */
  models: { type: Array, default: () => [] },
  /** 当前选中的下标 */
  index: { type: Number, default: 0 },
  disabled: { type: Boolean, default: false },
  /**
   * 交互前置守卫（接入方注入，与 KbSelector 同口径）。
   * 返回 false 表示已被拦截（如未登录已跳登录页），此时不展开菜单。
   * 未登录占位态下模型列表是假数据，点开也没有意义 —— 直接引导去登录。
   */
  beforeInteract: { type: Function, default: null },
})

const emit = defineEmits(['update:index'])

const open = ref(false)
const current = computed(() => props.models[props.index] ?? null)
const menuStyle = ref({})
const buttonRef = ref(null)
/** <1280px 时使用底部抽屉模式，与 KbSelector 同一断点 */
const useDrawer = ref(false)

function pick(i) {
  emit('update:index', i)
  open.value = false
}

async function toggleMenu() {
  if (open.value) {
    open.value = false
    return
  }

  /* 未登录等接入方拦截条件：不展开菜单（接入方已在 guard 内跳登录）。
     放在展开分支之前、收起分支之后 —— 已经打开的菜单要能正常关掉。 */
  if (typeof props.beforeInteract === 'function') {
    try {
      if (props.beforeInteract() === false) return
    } catch (e) {
      console.error('[ModelSelector] beforeInteract 执行出错，本次按放行处理:', e)
    }
  }

  // 计算按钮位置（抽屉模式下不需要，但保留不影响）
  if (buttonRef.value) {
    const rect = buttonRef.value.getBoundingClientRect()
    menuStyle.value = {
      left: `${rect.left}px`,
      bottom: `${window.innerHeight - rect.top + 9}px`,
    }
  }

  open.value = true
}

let mediaQuery = null
function updateDrawerMode() {
  useDrawer.value = window.innerWidth < 1280
}
onMounted(() => {
  updateDrawerMode()
  mediaQuery = window.matchMedia('(max-width: 1279.98px)')
  mediaQuery.addEventListener('change', updateDrawerMode)
})
onBeforeUnmount(() => {
  if (mediaQuery) mediaQuery.removeEventListener('change', updateDrawerMode)
})
</script>

<template>
  <span class="cf-model" @keydown.esc="open = false">
    <button
      ref="buttonRef"
      class="cf-tool-btn" :class="{ 'is-open': open }"
      type="button" :disabled="disabled"
      :aria-expanded="open" aria-haspopup="listbox" aria-label="基础模型"
      @click="toggleMenu"
    >
      <CfIcon name="chip" :size="16" />
      <!-- 模型名加粗：它是这一轮最重要的一个条件 -->
      <span class="cf-model-v">{{ current?.name }}</span>
      <CfIcon name="caret-down" :size="12" class="cf-caret" />
    </button>

    <!-- 抽屉模式: <1280px，与 KbSelector 同一断点、同一视觉规格 -->
    <template v-if="useDrawer">
      <Teleport to="body">
        <span v-if="open" class="cf-model-mask" @click="open = false" />
        <div v-if="open" class="cf-model-drawer" role="dialog" aria-label="基础模型">
          <div class="cf-model-drawer-head">
            <h2 class="cf-model-drawer-title">模型选择</h2>
            <button
              class="cf-model-drawer-close"
              type="button"
              aria-label="关闭"
              @click="open = false"
            >
              <CfIcon name="x" :size="20" />
            </button>
          </div>

          <div class="cf-model-drawer-body">
            <button
              v-for="(m, i) in models" :key="m.id"
              class="cf-model-drawer-item" :class="{ 'is-on': i === index }"
              type="button" role="option" :aria-selected="i === index"
              @click.stop="pick(i)"
            >
              <span>{{ m.name }}</span>
            </button>
          </div>
        </div>
      </Teleport>
    </template>

    <!-- 浮层模式: ≥1280px -->
    <template v-else>
      <span v-if="open" class="cf-catch" @click="open = false" />

      <span v-if="open" class="cf-model-menu" :style="menuStyle" role="listbox" aria-label="基础模型">
        <span class="cf-model-h">模型选择</span>
        <span class="cf-model-list cf-scroll">
          <button
            v-for="(m, i) in models" :key="m.id"
            class="cf-model-item" :class="{ 'is-on': i === index }"
            type="button" role="option" :aria-selected="i === index"
            @click.stop="pick(i)"
          >
            {{ m.name }}
            <CfIcon name="check" :size="14" />
          </button>
        </span>
      </span>
    </template>
  </span>
</template>

<style scoped>
.cf-model{position:relative;display:inline-flex;flex:none}
.cf-model-v{font-weight:600}

.cf-model-menu{
  position:fixed;z-index:9999;
  min-width:180px;width:max-content;max-width:300px;max-height:288px;
  display:flex;flex-direction:column;overflow:hidden;
  padding:6px;
  background:#ffffff;
  border:1px solid var(--cf-line);border-radius:var(--cf-radius-md);
  box-shadow:var(--cf-shadow-float);
}
/* 标题栏：块级才能让分割线满宽（行内元素的下边框只有文字那么宽）；
   负的左右外边距抵掉菜单内边距，分割线通到菜单两侧边缘 */
.cf-model-h{
  display:block;flex:none;
  font-size:var(--cf-fs-xs);color:var(--cf-text-3);
  padding:6px var(--cf-space-3) var(--cf-space-3);
  margin:0 -6px;
  border-bottom:1px solid var(--cf-line);
}
/* 只有选项列表滚动，标题固定；上外边距让滚动条顶端落在分割线下方 6px */
.cf-model-list{
  display:flex;flex-direction:column;min-height:0;overflow-y:auto;
  margin-top:6px;
}
.cf-model-item{
  display:flex;align-items:center;gap:var(--cf-space-3);width:100%;
  padding:var(--cf-space-2) var(--cf-space-3);
  border-radius:var(--cf-radius-sm);
  font-size:var(--cf-fs-sm);color:var(--cf-text-2);
  cursor:pointer;text-align:left;white-space:nowrap;
  transition:var(--cf-transition);
}
@media (hover:hover){
  .cf-model-item:hover{background:var(--cf-page);color:var(--cf-text-1)}
}
.cf-model-item.is-on{color:var(--cf-primary);font-weight:600}
/* 对勾常驻占位，只切 opacity：出现/消失不会改变行宽 */
.cf-model-item :deep(svg){margin-left:auto;flex:none;opacity:0;color:var(--cf-primary)}
.cf-model-item.is-on :deep(svg){opacity:1}

/* 小屏收窄：模型名限宽省略，给其他控件让出空间。
   4em ≈ 4个字符宽，对于中文大约能完整显示3个字+省略号 */
@media (max-width:767.98px){
  .cf-model-v{max-width:4em}
}

/* ---------- 抽屉模式: <1280px ----------
   与 KbSelector 的 cf-kb-drawer 同一视觉规格，传送到 body 的重置理由也相同
   （见 KbSelector.vue 顶部注释）：脱离 .cf-root 子树后要补 button/box-sizing 重置。 */
:where(.cf-model-drawer) button{
  font-family:inherit;font-size:inherit;
  border:none;background:none;padding:0;color:inherit;
  -webkit-tap-highlight-color:transparent;
}
:where(.cf-model-drawer),
:where(.cf-model-drawer) *,
:where(.cf-model-drawer) *::before,
:where(.cf-model-drawer) *::after{
  box-sizing:border-box;
}
:where(.cf-model-drawer) svg{display:block}

.cf-model-mask{
  position:fixed;inset:0;z-index:9998;
  background:rgba(0,0,0,0.8);
  animation:cf-model-mask-in 0.2s ease-out;
}
@keyframes cf-model-mask-in{
  from{opacity:0}
  to{opacity:1}
}
.cf-model-drawer{
  position:fixed;left:0;right:0;bottom:0;z-index:9999;
  max-height:80vh;display:flex;flex-direction:column;
  background:#ffffff;
  border-radius:16px 16px 0 0;
  box-shadow:0 -10px 40px rgba(0,0,0,0.25);
  animation:cf-model-drawer-in 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}
@keyframes cf-model-drawer-in{
  from{transform:translateY(100%)}
  to{transform:translateY(0)}
}
.cf-model-drawer::before{
  content:'';
  position:absolute;top:12px;left:50%;transform:translateX(-50%);
  width:32px;height:4px;border-radius:100px;
  background:var(--cf-ink-20);
}
.cf-model-drawer-head{
  display:flex;align-items:center;justify-content:space-between;
  padding:32px 20px 16px;flex:none;
  border-bottom:1px solid var(--cf-ink-08);
}
.cf-model-drawer-close{
  width:36px;height:36px;flex:none;
  display:grid;place-items:center;
  border-radius:8px;
  background:transparent;color:var(--cf-text-3);
  cursor:pointer;transition:all 0.15s ease;
}
@media (hover:hover){
  .cf-model-drawer-close:hover{
    background:var(--cf-ink-06);color:var(--cf-text-1);
  }
}
.cf-model-drawer-title{
  flex:1;font-size:18px;font-weight:600;color:var(--cf-text-1);
  letter-spacing:-0.01em;
}
.cf-model-drawer-body{
  flex:1;min-height:0;overflow-y:auto;
  padding:8px 0 max(12px, env(safe-area-inset-bottom));
}
.cf-model-drawer-item{
  display:flex;align-items:center;gap:10px;width:100%;
  padding:10px 20px;
  background:transparent;
  font-size:14px;color:var(--cf-text-1);
  cursor:pointer;text-align:left;
  transition:all 0.15s ease;
}
@media (hover:hover){
  .cf-model-drawer-item:hover{
    background:var(--cf-ink-04);
  }
}
.cf-model-drawer-item.is-on{
  color:var(--cf-primary);font-weight:600;
}

</style>
