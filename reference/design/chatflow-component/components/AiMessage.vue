<!-- ============================================================
     AI 回答 · ChatFlow v1.0
     ------------------------------------------------------------
     版式自上而下：
       思考过程 → 抬头 → 正文 →（停止按钮｜AI 提示 → 知识库依据 → 联网资料）
       → 操作栏 → 推荐追问

     顺序不是随手排的：
     - AI 提示紧跟正文，是对这段回答的免责声明，贴着正文才有归属；
     - 知识库依据在联网资料之前，与抬头里「知识库→联网」的顺序一致
       （默认互斥下两者本不会同时出现，开启并行溯源后才需要这个先后关系）；
     - 操作栏与追问在回答体之外，属于「这一轮之后的动作」。
     ============================================================ -->
<script setup>
import { computed } from 'vue'
import CfIcon from './CfIcon.vue'
import ThinkingBlock from './ThinkingBlock.vue'
import ThoughtProcess from './ThoughtProcess.vue'
import MarkdownBody from './MarkdownBody.vue'
import AnswerMeta from './AnswerMeta.vue'
import AudioPlayer from './AudioPlayer.vue'
import SourceList from './SourceList.vue'
import WebSourceChip from './WebSourceChip.vue'
import FollowUps from './FollowUps.vue'
import MessageActions from './MessageActions.vue'

const props = defineProps({
  /** useChatFlow 里的 ai 消息对象 */
  message: { type: Object, required: true },
  features: { type: Object, required: true },
  /** 本轮检索范围，用于依据抬头回显 */
  kbNames: { type: Array, default: () => [] },
  /** 是否是消息流里的最后一条。
      只有最后一条给「重新生成」：整条发送链路（sendWebsocket 读
      lastSendMsg、adapter 只盯最后一条 SYSTEM 消息）都只支持重发最后一轮，
      老回答上放这个按钮点下去会重发另一轮，是假功能 */
  isLast: { type: Boolean, default: false },
  /** 流式输出中的实时 HTML。生成结束后为空，改读 message.html */
  streamingHtml: { type: String, default: '' },
  /** 思考过程的实时内容 */
  streamingThoughts: { type: String, default: '' },
})

const emit = defineEmits([
  'stop', 'copy', 'regenerate', 'vote', 'report', 'open-doc', 'open-web', 'follow',
])

const isThinking = computed(() => props.message.phase === 'thinking')
const isStreaming = computed(() => props.message.phase === 'streaming')
/** 生成结束（正常完成或被停止） */
const isSettled = computed(() =>
  props.message.phase === 'done' || props.message.phase === 'stopped'
)
/** 停止态不挂依据与追问：回答不完整，给出处会误导 */
const showTail = computed(() => props.message.phase === 'done')

/** 操作栏可用项：非最后一条时摘掉「重新生成」（见 isLast 注释） */
const actionsForMsg = computed(() =>
  props.isLast
    ? props.features.actions
    : { ...props.features.actions, regenerate: false }
)

/** 正文：流式期间读实时值，结束后读消息上固化的值 */
const bodyHtml = computed(() =>
  isSettled.value ? props.message.html : props.streamingHtml
)

/** 思考过程：流式期间读实时值，结束后读消息上固化的值 */
const thoughtsHtml = computed(() =>
  isSettled.value ? props.message.thoughts : props.streamingThoughts
)

/** 为 ThoughtProcess 组件构造兼容的 msg 对象，直接使用后端返回的 msgState */
const msgForThoughts = computed(() => ({
  msgState: props.message.msgState || 'FINISH',
  ...props.message
}))
</script>

<template>
  <!-- 占位消息不渲染任何内容 -->
  <div v-if="!message.isPlaceholder" class="cf-ai-wrap">
    <div class="cf-ai">
      <!-- 思考过程组件 -->
      <ThoughtProcess
        v-if="thoughtsHtml"
        :msg="msgForThoughts"
        :thoughtProcess="thoughtsHtml"
      />

      <ThinkingBlock
        v-if="features.thinking && message.thinkSteps.length"
        :steps="message.thinkSteps"
        :finished="isSettled"
      />

      <!-- 思考完成前不出抬头：模型与检索范围此刻还没确定 -->
      <AnswerMeta
        v-if="features.answerMeta && message.meta && !isThinking"
        :meta="message.meta"
      />

      <!-- 思考中：文生图显示「正在生成图片」卡片动画；带 loadingTip 的（如文档总结）
           显示文案；其余显示三点等待动画 -->
      <div v-if="isThinking">
        <div v-if="message.textToImageLoading" class="cf-gen-img">
          <div class="cf-gi-canvas cf-gi-loading" aria-label="正在生成图片">
            <CfIcon name="wand" :size="32" />
            <span>{{ message.loadingTip || '正在生成图片，预计需要 10-30 秒...' }}</span>
          </div>
        </div>
        <p v-else-if="message.loadingTip" class="cf-doc-summary-loading" aria-label="正在总结文档">
          {{ message.loadingTip }}
        </p>
        <p v-else class="cf-typing" aria-label="正在生成回答">
          <i /><i /><i />
        </p>
      </div>

      <MarkdownBody
        v-else-if="!features.aiCardOnly"
        :html="bodyHtml"
        :streaming="isStreaming"
        :skill="message.skill || ''"
        :skill-params="message.skillParams || null"
      />

      <!-- 纯数据插槽：卡片样式/点击行为由接入方写，组件只把整条 message（含 SSE 原始返回 raw）交出去。
           不订阅时模板不出现，零副作用；接入方的点击处理器可直接从 message 读数据，无需回驱对话。 -->
      <slot name="ai-card" :message="message" />

      <!-- 不参与逐字流式的整块产物（目前只有语音播放器）：流式结束后才出现，
           紧跟正文，AI 提示要排在它下面才对——提示是「对这条回答」的免责声明 -->
      <AudioPlayer
        v-if="isSettled && message.after?.type === 'audio'"
        :duration="message.after.duration"
        :src="message.after.src || ''"
        :text="message.after.text || ''"
        :params="message.after.params || null"
      />

      <button
        v-if="features.stopButton && !isSettled"
        class="cf-stop" type="button" @click="emit('stop')"
      >
        <CfIcon name="x" :size="14" />停止生成
      </button>

      <template v-if="isSettled">
        <!-- 依据/资料紧贴正文下方，AI 免责声明排到最后：
             来源是「正文的出处」，读者看完正文顺势看来源；
             免责声明是对整条回答的兜底说明，属于最外层，放最后。
             并行溯源开启时知识库依据在前、联网资料在后（用户先看内部依据）；
             未开启时两者本就互斥，顺序不影响任何现有场景 -->
        <SourceList
          v-if="features.sources && showTail"
          :sources="message.sources"
          :kb-names="kbNames"
          :clickable="features.refDrawer"
          @open="emit('open-doc', $event)"
        />

        <WebSourceChip
          v-if="features.webSearch && showTail"
          :sources="message.webSources"
          :clickable="features.refDrawer"
          @open="emit('open-web', message)"
        />

        <p v-if="features.aiNote && !message.isPlaceholder" class="cf-ai-note">
          本回答由AI生成，内容仅供参考，请仔细甄别
        </p>
      </template>
    </div>

    <template v-if="isSettled">
      <MessageActions
        :actions="actionsForMsg"
        :vote="message.vote"
        @copy="emit('copy', message)"
        @regenerate="emit('regenerate', message)"
        @vote="emit('vote', { message, vote: $event })"
        @report="emit('report', message)"
      />

      <FollowUps
        v-if="features.followUps && showTail"
        :items="message.followUps"
        @pick="emit('follow', $event)"
      />
    </template>
  </div>
</template>

<style scoped>
.cf-ai-wrap{margin-right:auto;max-width:100%;width:100%}
/* 回答体不给底色也不给描边：与用户气泡形成「一侧有形、一侧无形」的对比，
   长回答不会被框住显得局促 */
.cf-ai{background:transparent;border:none;padding:0;width:100%;display:flex;flex-direction:column;gap:var(--cf-space-4)}

/* H5 响应式：间距调整 */
@media (max-width: 767.98px) {
  .cf-ai{gap: var(--cf-space-3)}
}

/* 等待动画：三点依次上跳。
   行高对齐正文（原型里这段在 .md 内部，继承正文行高），
   否则等待态与首字出现时会有一次跳动。
   display 必须是 flex 不是 inline-flex：这是个 <p>，需要保持块级独占一行，
   否则它会变成行内级元素，跟紧跟着的「停止生成」按钮（也是 inline-flex）
   挤到同一行去，而不是按钮另起一行排在下面。 */
.cf-typing{
  display:flex;align-items:center;gap:5px;height:20px;
  line-height:var(--cf-lh-body);
}
/* 文档总结等带 loadingTip 的思考态：显示文案（如「正在总结文档…」） */
.cf-doc-summary-loading{
  margin:0;height:20px;display:flex;align-items:center;
  font-size:var(--cf-fs-sm);color:var(--cf-text-2);
  line-height:var(--cf-lh-body);
}
.cf-typing i{
  width:7px;height:7px;border-radius:50%;
  background:var(--cf-text-3);
  animation:cfPulse 1.3s ease-in-out infinite;
}
.cf-typing i:nth-child(2){animation-delay:.18s}
.cf-typing i:nth-child(3){animation-delay:.36s}
@keyframes cfPulse{
  0%,60%,100%{opacity:.3;transform:translateY(0)}
  30%{opacity:1;transform:translateY(-3px)}
}

/* ---------- 文生图加载卡片 ----------
   思考态下若是文生图请求，用 16:9 渐变画布 + 魔杖图标 + 提示，代替三点动画。
   这个卡片在 .cf-md 之外（直接挂在 .cf-ai 下），样式写在这里的 scoped 块。 */
.cf-gen-img{
  margin:var(--cf-space-3) 0;border:1px solid var(--cf-line);
  border-radius:var(--cf-radius-md);overflow:hidden;
}
.cf-gi-canvas{
  aspect-ratio:16/9;display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:var(--cf-space-2);text-align:center;padding:var(--cf-space-5);
  background:linear-gradient(135deg,#dbe7f6 0%,#eef3fb 45%,#e3ecfa 100%);color:var(--cf-primary);
}
.cf-gi-canvas span{max-width:80%;font-size:var(--cf-fs-sm);color:var(--cf-text-2);line-height:1.6}
/* 魔杖图标缓慢脉冲，暗示「生成中」 */
.cf-gi-loading :deep(svg){animation:cfWand 1.6s ease-in-out infinite}
@keyframes cfWand{
  0%,100%{opacity:.55;transform:scale(1) rotate(0deg)}
  50%{opacity:1;transform:scale(1.08) rotate(-6deg)}
}

.cf-stop{
  /* .cf-ai 是 flex 列且 align-items 默认 stretch，会把 inline-flex 按钮拉满整行宽，
     且 flex gap 已负责与上一块的间距——所以这里 align-self 收窄为内容宽、去掉多余 margin-top */
  align-self:flex-start;
  display:inline-flex;align-items:center;gap:6px;
  height:32px;padding:0 14px;
  border:1px solid var(--cf-line-strong);border-radius:var(--cf-radius-pill);
  font-size:var(--cf-fs-xs);color:var(--cf-text-2);
  cursor:pointer;background:var(--cf-surface);
  transition:var(--cf-transition);
}
@media (hover:hover){
  .cf-stop:hover{border-color:var(--cf-danger);color:var(--cf-danger-deep)}
}
.cf-stop:active{border-color:var(--cf-danger);color:var(--cf-danger-deep)}

/* 比三级文字再弱一档并压透明度：它是常驻的免责声明，
   每条回答都有，不该反复抢注意力 */
.cf-ai-note{
  margin-top:var(--cf-space-1);
  font-size:var(--cf-fs-xs);color:var(--cf-text-faint);
  line-height:1.6;opacity:.8;
}
</style>
