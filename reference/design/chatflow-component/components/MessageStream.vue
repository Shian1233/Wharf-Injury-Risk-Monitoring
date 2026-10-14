<!-- ============================================================
     消息流 · ChatFlow v1.0
     ------------------------------------------------------------
     滚动容器 + 消息列表。空态与消息互斥。

     自动滚动的规矩：只在用户本来就贴着底部时才跟随。
     用户往上翻看历史时强行拉回底部是很讨厌的行为，所以先判位置。
     ============================================================ -->
<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import UserMessage from './UserMessage.vue'
import AiMessage from './AiMessage.vue'
import EmptyState from './EmptyState.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  features: { type: Object, required: true },
  agent: { type: Object, default: () => ({}) },
  presetQuestions: { type: Array, default: () => [] },
  kbNames: { type: Array, default: () => [] },
  /** 流式输出中的实时 HTML，交给最后一条 ai 消息 */
  streamingHtml: { type: String, default: '' },
  /** 流式输出中的实时思考过程，交给最后一条 ai 消息 */
  streamingThoughts: { type: String, default: '' },
  /** 空态布局模式：'center' | 'split' */
  layout: { type: String, default: 'center' },
  /** IP 形象立绘 URL（仅 layout='split' 时生效） */
  illustrationUrl: { type: String, default: '' },
  /** 是否显示空状态（由父组件 ChatFlow 控制） */
  isEmpty: { type: Boolean, default: undefined },
})

const questionsVariant = computed(() => props.features.questionCards ? 'cards' : 'list')

const emit = defineEmits([
  'pick-question', 'select-kb', 'stop', 'copy', 'regenerate', 'vote', 'report',
  'open-doc', 'open-web', 'follow',
])

const scroller = ref(null)
/** 贴底判定的容差：差 40px 以内算「在底部」，
    正好等于一行多一点，用户微调滚动条不会误判成想看历史 */
const NEAR_BOTTOM = 40
let scrollTimer = null

function isNearBottom() {
  const el = scroller.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM
}

function scrollToBottom() {
  const el = scroller.value
  if (el) el.scrollTop = el.scrollHeight
}

/** 贴底意图：用户是否希望跟随到底部。滚动到底部时置 true，主动上翻时置 false。
    回答的正文/图片/来源/追问是分多次陆续撑高的，单次 scrollToBottom 追不上，
    用 ResizeObserver 在高度变化时按此意图重新贴底。 */
const stickToBottom = ref(true)

/** 滚动时给滚动条加深色，停手 600ms 后褪回；同时更新贴底意图 */
function onScroll() {
  const el = scroller.value
  if (!el) return
  el.classList.add('is-scrolling')
  clearTimeout(scrollTimer)
  scrollTimer = setTimeout(() => el?.classList.remove('is-scrolling'), 600)
  // 用户滚动后：贴底则恢复跟随，上翻则停止跟随
  stickToBottom.value = isNearBottom()
}

/* 新消息：无条件滚到底（是用户自己发的或刚触发的回答），恢复贴底意图，
   并在下一帧补观察 .cf-stream（空态切到有消息时它才挂上） */
watch(() => props.messages.length, () => {
  nextTick(observeInner)
  if (!props.features.autoScroll) return
  stickToBottom.value = true
  nextTick(scrollToBottom)
})

/* 流式输出：只在贴底时跟随，用户上翻则不打扰。
   判定要在 DOM 更新前做，更新后 scrollHeight 已经变了 */
watch(() => props.streamingHtml, () => {
  if (!props.features.autoScroll) return
  const stick = isNearBottom()
  if (stick) nextTick(scrollToBottom)
})

/* 内容区尺寸监听：回答分多次撑高（流式文本、图片加载、来源/追问渲染）时，
   单次 scrollToBottom 会追不上。只要用户仍贴底意图，就随高度变化持续贴底。 */
let ro = null
let observedInner = null
/** 观察内部内容容器（真正撑高的是 .cf-stream，滚动容器高度固定不变） */
function observeInner() {
  if (!ro) return
  const el = scroller.value
  const inner = el?.querySelector('.cf-stream')
  if (inner && inner !== observedInner) {
    if (observedInner) ro.unobserve(observedInner)
    ro.observe(inner)
    observedInner = inner
  }
}
onMounted(() => {
  const el = scroller.value
  if (!el || typeof ResizeObserver === 'undefined') return
  ro = new ResizeObserver(() => {
    if (!props.features.autoScroll) return
    if (stickToBottom.value) scrollToBottom()
  })
  observeInner()
})

onBeforeUnmount(() => {
  clearTimeout(scrollTimer)
  if (ro) { ro.disconnect(); ro = null }
})

defineExpose({ scrollToBottom })
</script>

<template>
  <div ref="scroller" class="cf-scroll cf-stream-scroll" @scroll="onScroll">
    <EmptyState
      v-if="features.emptyState && (isEmpty !== undefined ? isEmpty : !messages.length)"
      :agent="agent"
      :questions="presetQuestions"
      :questions-variant="questionsVariant"
      :layout="layout"
      :illustration-url="illustrationUrl"
      @pick="emit('pick-question', $event)"
      @select-kb="emit('select-kb', $event)"
    >
      <template #input>
        <slot name="composer"></slot>
      </template>
      <!-- 空态品牌区/附加区插槽向上透传（接入方注入 mascot、知识库卡片等）。
           v-if 守卫：接入方未传时不占位，让 EmptyState 渲染默认内容（其它页面不受影响）。 -->
      <template v-if="$slots['empty-brand']" #brand="s">
        <slot name="empty-brand" v-bind="s"></slot>
      </template>
      <template v-if="$slots['empty-extra']" #extra="s">
        <slot name="empty-extra" v-bind="s"></slot>
      </template>
    </EmptyState>

    <div v-else class="cf-stream">
      <template v-for="(m, i) in messages" :key="m.id">
        <UserMessage v-if="m.role === 'user'" :message="m" />
        <AiMessage
          v-else
          :message="m"
          :features="features"
          :kb-names="kbNames"
          :is-last="i === messages.length - 1"
          :streaming-html="i === messages.length - 1 ? streamingHtml : ''"
          :streaming-thoughts="i === messages.length - 1 ? streamingThoughts : ''"
          @stop="emit('stop')"
          @copy="emit('copy', $event)"
          @regenerate="emit('regenerate', $event)"
          @vote="emit('vote', $event)"
          @report="emit('report', $event)"
          @open-doc="emit('open-doc', $event)"
          @open-web="emit('open-web', $event)"
          @follow="emit('follow', $event)"
        >
          <!-- ai-card 守卫透传：未订阅则不出现，AiMessage 内部插槽也不渲染 -->
          <template v-if="$slots['ai-card']" #ai-card="s">
            <slot name="ai-card" v-bind="s"></slot>
          </template>
        </AiMessage>
      </template>
    </div>
  </div>
</template>

<style scoped>
.cf-stream-scroll{
  flex:1;overflow-y:auto;min-height:0;
  display:flex;
}
/* 当显示空状态时，让内容垂直居中。
   用 `safe center` 而不是 `center`：内容高于滚动容器时，普通 center 会让溢出
   **两端对称**，顶部那段溢到可滚动区上方且滚不到（flex 居中的既有行为），
   表现为空态标题被 ChatHeader 压住 —— 浏览器放大/缩放让 CSS 视口变矮时就会触发。
   safe 关键字正是为此设计：放得下照常居中，放不下自动退化成 start 对齐，
   顶部始终可达。不支持 safe 的旧浏览器会忽略整条声明、退回默认的 start 对齐，
   同样不会出现内容被裁——比裁掉安全。
   H5 不在此列（下方媒体查询自己处理），这里只修 PC。 */
.cf-stream-scroll:has(.cf-empty){
  justify-content:safe center;
}

/* 消息流容器 */
.cf-stream{
  flex:none;
  max-width:var(--cf-stream-max);width:100%;margin:0 auto;
  padding:var(--cf-space-6) 0 var(--cf-space-4);
  display:flex;flex-direction:column;
  gap:var(--cf-msg-gap);
}

/* H5 响应式适配 */
@media (max-width: 767.98px) {
  .cf-stream-scroll:has(.cf-empty) {
    min-height: 100vh;
    /* 显式写回普通 center：H5 这条链路（100vh + center）原样保留不动，
       本次只修 PC。上面改成 safe center 后若不写这行，H5 会跟着继承。 */
    justify-content: center;
    flex-direction: unset !important;
  }

  /* 消息流左右安全区适配 */
  .cf-stream {
    padding-left: calc(16px + env(safe-area-inset-left, 0px));
    padding-right: calc(16px + env(safe-area-inset-right, 0px));
  }

  /* 消息间距缩小 */
  .cf-stream {
    gap: var(--cf-space-4);
  }
}
</style>
