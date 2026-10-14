<!-- ============================================================
     反馈弹窗 · ChatFlow v1.0
     ------------------------------------------------------------
     点踩与举报共用一个弹窗，标题随入口切换。
     提交后把 {mode, tags, text} 交给接入方，组件不负责上报。
     ============================================================ -->
<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import CfIcon from './CfIcon.vue'
import { defaultMetaService } from '../services/metaService.js'
import { submitFeedback } from '../services/feedbackService.js'
import { useToast } from '../composables/useToast.js'

/* 弹窗 Teleport 到 body，但 ToastHost 由 ChatFlow/ChatComposer 渲染，
   useToast 是模块级单例，提示照样能显示出来。 */
const { toast } = useToast()

const props = defineProps({
  open: { type: Boolean, default: false },
  /** 'vote' 点踩入口 | 'report' 举报入口 */
  mode: { type: String, default: 'vote' },
  /**
   * 标签选项。不传（null）= 走 /feedback/type/list 字典接口；
   * 接口失败或返回为空时不显示标签（没有内置兜底数据）。
   * 接入方要写死也行：传字符串数组或 [{ code, name }] 均可，传了就不请求接口。
   */
  tags: { type: Array, default: null },
  maxLength: { type: Number, default: 500 },
  /**
   * 问答对定位信息 { answerId, questionId, sessionId, humanId }。
   * 由 ChatFlow 从被反馈的那条消息上取，组件内部调 /dialog/report 要用。
   * 缺 answerId（这轮还没落库）时不发请求，只 emit 给接入方。
   */
  ids: { type: Object, default: null },
  /** 是否由组件自己调 /dialog/report。接入方要自己上报就传 false */
  report: { type: Boolean, default: true },
})

const emit = defineEmits(['close', 'submit'])

/** 选中的标签，元素是归一化后的 { code, name }。多选，提交时 code 用逗号拼 */
const picked = ref([])
const text = ref('')
const area = ref(null)
/** 请求进行中：禁用提交，防连点重复上报 */
const submitting = ref(false)
/** 已提交成功：按钮保持禁用，避免同一条反馈重复提交 */
const done = ref(false)

/* 接口拉回的字典：只作展示用（重新请求期间先显示上一次的列表，
   标签区不闪烁）。不做请求缓存 —— 每次打开弹窗都重新请求字典。 */
const fetched = ref(null)
const loading = ref(false)

/** 字符串或 {typeCode,typeName} / {code,name} 统一成 { code, name } */
function normalize(t) {
  if (typeof t === 'string') return { code: '', name: t }
  return {
    code: String(t?.code ?? t?.typeCode ?? ''),
    name: t?.name ?? t?.typeName ?? '',
  }
}

/* 优先级：接入方传的 tags > 接口字典 > 空（不显示标签）。
   接口还在飞的时候 fetched 为 null，这里先给空数组，
   标签区显示加载态而不是先空一下再被替换。 */
const options = computed(() => {
  if (props.tags) return props.tags.map(normalize)
  if (fetched.value) return fetched.value
  return []
})

/** 用 code 比较；接入方传的纯字符串项没有 code，回落用 name 比 */
function isSame(a, b) {
  return a.code && b.code ? a.code === b.code : a.name === b.name
}

function isPicked(t) {
  return picked.value.some((p) => isSame(p, t))
}

async function loadTypes() {
  // 接入方传了 tags 就不用请求；正在请求中不重复发。
  // 注意：不再因 fetched 已有数据而跳过 —— 每次打开都重新拉字典。
  if (props.tags || loading.value) return
  loading.value = true
  try {
    const list = await defaultMetaService.loadFeedbackTypes()
    if (list.length) {
      fetched.value = list
    } else if (!fetched.value) {
      // 首次拉取就空（接口异常或无配置）：fetched 留空，标签区不显示
    }
    // 已有旧列表时本次拉空（接口抖动）：保留旧列表，不退化成空白
  } finally {
    loading.value = false
  }
}

/* 每次打开都重置：上一次的选择留着会让人以为提交失败。
   不预勾任何标签——类型和内容都是必填，预勾会让用户以为已经选好了。
   焦点落到文本域，用户可以直接开始写，不用先 Tab */
watch(() => props.open, (v) => {
  if (!v) return
  text.value = ''
  picked.value = []
  submitting.value = false
  done.value = false
  nextTick(() => area.value?.focus())
  loadTypes()
})

/* 多选：reportType 按后端约定用英文逗号拼多个字典码（如 "2,3,4"）。
   再点已选中的可以取消。 */
function toggle(t) {
  picked.value = isPicked(t)
    ? picked.value.filter((x) => x.code !== t.code)
    : [...picked.value, t]
}

async function submit() {
  if (submitting.value || done.value) return

  /* 类型与内容都是必填。先校验类型：它在上面，
     按从上到下的顺序提示，用户不会补完文字才发现还得选类型。 */
  const pickedList = picked.value
  if (!pickedList.length) {
    toast('请选择反馈类型')
    return
  }
  /* 多个字典码按后端约定用英文逗号拼："2,3,4"。
     顺序即用户点选顺序，后端按码取值不依赖顺序。 */
  const reportType = pickedList.map((t) => t.code).join(',')
  const content = text.value.trim()
  if (!content) {
    toast('请输入你的想法')
    area.value?.focus()
    return
  }

  const payload = {
    mode: props.mode,
    /* tags 保留字符串数组：接入方已有的 @feedback 处理逻辑不用改 */
    tags: pickedList.map((t) => t.name),
    /** 字典码，对应后端 reportType；多选时形如 "2,3,4" */
    reportType,
    types: pickedList.map((t) => ({ ...t })),
    text: content,
  }

  /* 组件自己上报（props.report 未显式关掉时）。
     ids 由 ChatFlow 传入——answerId/questionId/sessionId 只有它那边有。
     缺 ids 说明这轮对话还没落库，此时不该发请求，交给接入方处理。 */
  if (props.report && props.ids?.answerId) {
    submitting.value = true
    const ok = await submitFeedback({
      ...props.ids,
      reportType,
      content,
    })
    submitting.value = false
    if (!ok) {
      toast('提交失败，请稍后重试')
      return
    }
    done.value = true
  }

  emit('submit', payload)
  emit('close')
}
</script>

<template>
  <!-- Teleport 到 body：跳出接入方的层叠上下文（接入方可能给挂载点祖先加 position+z-index，
       inline 渲染会让本弹窗被「关」在低层里、盖不住接入方顶栏/侧边栏）。这是可复用弹窗的标准做法。 -->
  <Teleport to="body">
  <div
    v-if="open" class="cf-overlay"
    role="dialog" aria-modal="true" aria-label="反馈与举报"
    @click.self="emit('close')"
  >
    <div class="cf-modal">
      <div class="cf-modal-hd">
        <h2>反馈与举报</h2>
        <button class="cf-modal-x cf-tap40" type="button" aria-label="关闭" @click="emit('close')">
          <CfIcon name="x" :size="18" />
        </button>
      </div>

      <div class="cf-fb-tags" :aria-busy="loading">
        <!-- key 用 code||name：接口项有 code，纯字符串项没有，回落到 name -->
        <button
          v-for="t in options" :key="t.code || t.name"
          class="cf-fb-tag" :class="{ 'is-on': isPicked(t) }"
          type="button" :aria-pressed="isPicked(t)"
          @click="toggle(t)"
        >{{ t.name }}</button>
        <span v-if="loading && !options.length" class="cf-fb-tip">加载中…</span>
      </div>

      <div class="cf-fb-box">
        <textarea
          ref="area" v-model="text" class="cf-fb-text"
          :maxlength="maxLength" placeholder="欢迎说出你的想法～"
        />
        <span class="cf-fb-count">{{ text.length }} / {{ maxLength }}</span>
      </div>

      <div class="cf-modal-ft">
        <button class="cf-btn-ghost" type="button" @click="emit('close')">取消</button>
        <button
          class="cf-btn" type="button"
          :disabled="submitting || done"
          @click="submit"
        >{{ submitting ? '提交中…' : done ? '已提交' : '提交' }}</button>
      </div>
    </div>
  </div>
  </Teleport>
</template>

<style scoped>
.cf-overlay{
  /* z-index 9999：与库内其他浮层（ModelSelector/KbSelector）一致，
     且高过接入方布局层（顶栏 30 / 侧边栏 99 / 布局 MAX 100），配合 Teleport 才能真正盖满全屏。 */
  position:fixed;inset:0;z-index:9999;
  background:var(--cf-scrim);
  backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);
  display:grid;place-items:center;padding:var(--cf-space-6);
}
.cf-modal{
  width:min(560px,90vw);max-height:90vh;overflow-y:auto;
  background:#ffffff;border-radius:var(--cf-radius-lg);
  padding:var(--cf-space-6);box-shadow:var(--cf-shadow-float);
}
.cf-modal-hd{
  display:flex;align-items:flex-start;gap:var(--cf-space-3);
  margin-bottom:var(--cf-space-5);
}
.cf-modal-hd h2{font-size:var(--cf-fs-lg);font-weight:600}
/* margin-left:auto 把关闭推到最右，标题按内容宽度收紧 */
.cf-modal-x{
  flex:none;margin-left:auto;width:32px;height:32px;border-radius:6px;
  display:grid;place-items:center;color:var(--cf-text-2);
  cursor:pointer;transition:var(--cf-transition);
}
@media (hover:hover){
  .cf-modal-x:hover{background:var(--cf-page);color:var(--cf-text-1)}
}

.cf-fb-tags{display:flex;flex-wrap:wrap;gap:var(--cf-space-2);margin-bottom:var(--cf-space-5)}
.cf-fb-tag{
  padding:7px 14px;
  border:1px solid var(--cf-line-strong);border-radius:var(--cf-radius-pill);
  background:transparent;
  font-size:var(--cf-fs-sm);color:var(--cf-text-2);
  cursor:pointer;transition:var(--cf-transition);
}
/* 点踩/举报这类负向反馈：选中与 hover 都走危险色，
   用主色会让「我要投诉」看起来像「我要确认」 */
@media (hover:hover){
  .cf-fb-tag:hover{border-color:var(--cf-danger);color:var(--cf-danger-deep)}
}
.cf-fb-tag.is-on{
  background:var(--cf-danger-bg);border-color:var(--cf-danger);
  color:var(--cf-danger-deep);font-weight:500;
}
/* 字典接口还没回来时的占位，与标签同高避免弹窗高度跳动 */
.cf-fb-tip{
  padding:7px 2px;
  font-size:var(--cf-fs-sm);color:var(--cf-text-3);
}

.cf-fb-box{position:relative}
/* padding-bottom 26 给右下角的字数计数让位 */
.cf-fb-text{
  width:100%;min-height:118px;
  padding:11px 14px 26px;
  border:1px solid var(--cf-line-strong);border-radius:var(--cf-radius-sm);
  background:#ffffff;resize:vertical;outline:none;
  font-family:inherit;font-size:var(--cf-fs-sm);color:var(--cf-text-1);
  transition:var(--cf-transition);
}
.cf-fb-text:focus{border-color:var(--cf-primary)}
/* 边框已经转主色示意聚焦，键盘焦点环会叠成双框。
   全局 :focus-visible 规则与这里的 outline:none 特异性打平，
   打包顺序让它赢，所以要单独用 :focus-visible 覆盖回去。 */
.cf-fb-text:focus-visible{outline:none}
.cf-fb-text::placeholder{color:var(--cf-text-3)}
/* iOS Safari 在聚焦 font-size < 16px 的输入框时会自动放大整个页面视口，
   且不会自己缩回去，只能手动双指缩小。本弹窗打开即 focus 这个 textarea，
   所以一点「举报」就会触发（iPhone 上必现）。
   把触屏下的字号抬到 16px 就不满足触发条件了——不动 <meta viewport>：
   那里加 maximum-scale/user-scalable=no 会全局禁掉双指缩放，是无障碍倒退，
   而且 viewport 标签属于宿主页面、库无权改。
   PC 仍是 14px（--cf-fs-sm），视觉不变。
   同库的 ChatComposer 主输入框本来就是 --cf-fs-base(16px)，故从不触发，
   这里也算和它对齐。 */
@media (pointer:coarse){
  .cf-fb-text{font-size:var(--cf-fs-base)}
}
.cf-fb-count{
  position:absolute;right:12px;bottom:9px;
  font-size:var(--cf-fs-xs);color:var(--cf-text-3);pointer-events:none;
}

/* 取消、提交两个按钮紧靠在一起整体靠右——不是分开在两端。
   之前加过 margin-left:auto 想把两个按钮拉开，结果中间空出一大段，
   与原型（justify-content:flex-end 单独就够）不符，去掉。 */
.cf-modal-ft{
  display:flex;justify-content:flex-end;gap:var(--cf-space-3);
  margin-top:var(--cf-space-5);
}
.cf-btn,.cf-btn-ghost{
  height:38px;padding:0 18px;border-radius:var(--cf-radius-sm);
  font-size:var(--cf-fs-sm);cursor:pointer;
  transition:var(--cf-transition);white-space:nowrap;
}
.cf-btn{
  display:inline-flex;align-items:center;gap:6px;
  background:var(--cf-primary);color:#fff;font-weight:500;
}
.cf-btn-ghost{border:1px solid var(--cf-line-strong);color:var(--cf-text-2)}
/* 提交中/已提交：置灰并挡住指针，hover 态也不再响应 */
.cf-btn:disabled{
  background:var(--cf-line-strong);
  color:var(--cf-text-3);
  cursor:not-allowed;
}
@media (hover:hover){
  .cf-btn:not(:disabled):hover{background:var(--cf-primary-deep)}
  .cf-btn-ghost:hover{background:var(--cf-page);color:var(--cf-text-1)}
}
</style>
