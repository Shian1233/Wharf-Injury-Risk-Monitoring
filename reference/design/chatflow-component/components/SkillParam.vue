<!-- ============================================================
     技能参数下拉 · ChatFlow v1.0
     ------------------------------------------------------------
     两种形态，由字段自己声明：
       单选列表 —— 比例、风格、音色这类离散选项
       滑块     —— 语速/音量/音高这类 1-10 连续档位。列 10 个选项太长，
                   拖动更快，也更能表达「这是连续量」

     外形与知识库/模型/联网共用同一套底部控件（34px 高、12px 圆角、
     透明底描边），保持「参数与其它条件同级」的观感。
     ============================================================ -->
<script setup>
import { ref, computed } from 'vue'
import CfIcon from './CfIcon.vue'

const props = defineProps({
  /** {key,label,icon,options,def,slider} */
  field: { type: Object, required: true },
  /** 当前值（options 里的某一项） */
  value: { type: String, default: '' },
})

const emit = defineEmits(['update:value'])

const open = ref(false)
const buttonRef = ref(null)
const menuStyle = ref({})

const idx = computed(() => {
  const i = props.field.options.indexOf(props.value)
  return i > -1 ? i : (props.field.def ?? 0)
})
const shown = computed(() => props.field.options[idx.value] ?? '')

/** 滑块轨道的已过进度（0-100），驱动 --cf-p */
const pct = computed(() => {
  const n = props.field.options.length
  return n > 1 ? (idx.value / (n - 1)) * 100 : 0
})

function pick(i) {
  emit('update:value', props.field.options[i])
  if (!props.field.slider) open.value = false
}

function onSlide(e) {
  /* input[range] 是 1..n，选项下标是 0..n-1 */
  pick(Number(e.target.value) - 1)
}

function toggleMenu() {
  if (open.value) {
    open.value = false
    return
  }
  // 计算按钮位置
  if (buttonRef.value) {
    const rect = buttonRef.value.getBoundingClientRect()
    menuStyle.value = {
      left: `${rect.left}px`,
      bottom: `${window.innerHeight - rect.top + 9}px`,
    }
  }
  open.value = true
}
</script>

<template>
  <span class="cf-param" @keydown.esc="open = false">
    <button
      ref="buttonRef"
      class="cf-tool-btn" :class="{ 'is-open': open }"
      type="button"
      :aria-haspopup="field.slider ? 'dialog' : 'listbox'"
      :aria-expanded="open" :aria-label="field.key"
      @click="toggleMenu"
    >
      <CfIcon v-if="field.icon" :name="field.icon" :size="15" />
      <span v-if="field.label" class="cf-param-lb">{{ field.label }}</span>
      <!-- 值宽按两位数预留并居中：从「5」切到「10」时整行不跟着变宽、后面的参数不错位 -->
      <span class="cf-param-v">{{ shown }}</span>
      <CfIcon name="caret-down" :size="12" class="cf-caret" />
    </button>

    <span v-if="open" class="cf-catch" @click="open = false" />

    <!-- 滑块形态 -->
    <span
      v-if="open && field.slider"
      class="cf-param-menu is-slider" :style="menuStyle" role="dialog" :aria-label="field.key"
    >
      <span class="cf-param-h">{{ field.key }}</span>
      <span class="cf-sld-row">
        <CfIcon v-if="field.icon" :name="field.icon" :size="15" class="cf-sld-ico" />
        <input
          class="cf-sld" type="range"
          :min="1" :max="field.options.length" step="1"
          :value="idx + 1" :aria-label="field.key"
          :style="{ '--cf-p': pct + '%' }"
          @input="onSlide"
        >
        <span class="cf-sld-v">{{ shown }}</span>
      </span>
    </span>

    <!-- 单选列表形态 -->
    <span
      v-else-if="open"
      class="cf-param-menu" :style="menuStyle" role="listbox" :aria-label="field.key"
    >
      <span class="cf-param-h">{{ field.key }}</span>
      <span class="cf-param-list cf-scroll">
        <button
          v-for="(o, j) in field.options" :key="o"
          class="cf-param-item" :class="{ 'is-on': j === idx }"
          type="button" role="option" :aria-selected="j === idx"
          @click.stop="pick(j)"
        >
          {{ o }}
          <CfIcon name="check" :size="14" />
        </button>
      </span>
    </span>
  </span>
</template>

<style scoped>
.cf-param{position:relative;display:inline-flex;flex:none}
.cf-param-lb{color:var(--cf-text-2)}
/* 两位数预留 */
.cf-param-v{min-width:1.35em;text-align:center}

.cf-param-menu{
  position:fixed;z-index:9999;
  min-width:160px;width:max-content;max-width:300px;max-height:288px;
  display:flex;flex-direction:column;overflow:hidden;
  padding:6px;
  background:var(--cf-surface);
  border:1px solid var(--cf-line);border-radius:var(--cf-radius-md);
  box-shadow:var(--cf-shadow-float);
}
.cf-param-menu.is-slider{width:208px;min-width:208px}
/* 标题栏：块级 + 负的左右外边距，分割线才能通到菜单两侧边缘 */
.cf-param-h{
  display:block;flex:none;
  font-size:var(--cf-fs-xs);color:var(--cf-text-3);
  padding:6px var(--cf-space-3) var(--cf-space-3);
  margin:0 -6px;
  border-bottom:1px solid var(--cf-line);
}
.cf-param-list{
  display:flex;flex-direction:column;min-height:0;overflow-y:auto;margin-top:6px;
}
.cf-param-item{
  display:flex;align-items:center;gap:var(--cf-space-3);width:100%;
  padding:var(--cf-space-2) var(--cf-space-3);border-radius:var(--cf-radius-sm);
  font-size:var(--cf-fs-sm);color:var(--cf-text-2);
  cursor:pointer;text-align:left;white-space:nowrap;transition:var(--cf-transition);
}
@media (hover:hover){
  .cf-param-item:hover{background:var(--cf-page);color:var(--cf-text-1)}
}
.cf-param-item.is-on{color:var(--cf-primary);font-weight:600}
.cf-param-item :deep(svg){margin-left:auto;flex:none;opacity:0;color:var(--cf-primary)}
.cf-param-item.is-on :deep(svg){opacity:1}

/* ---------- 滑块 ---------- */
.cf-sld-row{
  display:flex;align-items:center;gap:var(--cf-space-2);
  padding:var(--cf-space-3) var(--cf-space-2) var(--cf-space-2);
}
.cf-sld-ico{flex:none;color:var(--cf-text-3)}
/* 当前档位：按两位数预留宽度并右对齐，5→10 时整行不跳动 */
.cf-sld-v{
  flex:none;min-width:1.6em;text-align:right;
  font-size:var(--cf-fs-sm);color:var(--cf-text-1);
  font-variant-numeric:tabular-nums;
}
/* 轨道：已过部分主色、未过部分浅灰，进度由 --cf-p 驱动 */
.cf-sld{
  flex:1;min-width:0;height:16px;margin:0;padding:0;
  -webkit-appearance:none;appearance:none;background:transparent;cursor:pointer;
}
.cf-sld::-webkit-slider-runnable-track{
  height:4px;border-radius:var(--cf-radius-pill);
  background:linear-gradient(to right,
    var(--cf-primary) var(--cf-p,50%),var(--cf-ink-10) var(--cf-p,50%));
}
.cf-sld::-webkit-slider-thumb{
  -webkit-appearance:none;appearance:none;
  width:14px;height:14px;margin-top:-5px;border-radius:50%;
  background:var(--cf-surface);border:2px solid var(--cf-primary);
  box-shadow:0 1px 3px rgba(23,43,58,.2);
  transition:transform .15s ease;
}
@media (hover:hover){
  .cf-sld:hover::-webkit-slider-thumb{transform:scale(1.12)}
}
.cf-sld:active::-webkit-slider-thumb{transform:scale(1.2)}
/* Firefox 用 range-progress 画已过部分，不支持 track 渐变 */
.cf-sld::-moz-range-track{
  height:4px;border-radius:var(--cf-radius-pill);background:var(--cf-ink-10);
}
.cf-sld::-moz-range-progress{
  height:4px;border-radius:var(--cf-radius-pill);background:var(--cf-primary);
}
.cf-sld::-moz-range-thumb{
  width:14px;height:14px;border-radius:50%;
  background:var(--cf-surface);border:2px solid var(--cf-primary);
  box-shadow:0 1px 3px rgba(23,43,58,.2);
}
</style>
