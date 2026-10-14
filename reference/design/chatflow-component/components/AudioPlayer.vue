<!-- ============================================================
     语音播放器 · ChatFlow v1.0
     ------------------------------------------------------------
     文字转语音技能的回答产物。原型没有真音频，按合成文本长度估时长
     （中文播报约 4.2 字/秒），用 rAF 按真实经过时间推进进度条。

     不参与逐字流式：时间码、倍速这些数字被一个个敲出来会很怪，
     所以流式结束后才整块挂到回答体末尾（见 useChatFlow 的 after 字段）。

     进度条只读（role="progressbar"，不是 slider），不支持点击/拖动定位。
     ============================================================ -->
<script setup>
import { ref, computed, onBeforeUnmount, nextTick, inject } from 'vue'
import CfIcon from './CfIcon.vue'
import { useToast } from '../composables/useToast.js'
import { estimateDuration } from '../composables/useTts.js'

const props = defineProps({
  /** 合成时长（秒）。有真实音频时以 <audio> 实际时长为准，这里作占位/估算 */
  duration: { type: Number, default: 0 },
  /** 真实音频源（mp3 objectURL）。有值走原生 <audio>；为空走历史现合成或 mock 假进度 */
  src: { type: String, default: '' },
  /** 待播报文本。历史消息现合成时用 */
  text: { type: String, default: '' },
  /** 合成参数对象。历史消息现合成时用 */
  params: { type: Object, default: null },
  /** 历史现合成钩子：() => Promise<{src, duration}>。显式传优先，否则用 inject 的组件级能力 */
  onSynthesize: { type: Function, default: null },
})

/* 组件级注入：ChatFlow 顶层 provide 的合成能力 (text, params) => Promise<{src,duration}>。
   历史消息（无 src）首次播放时用它现合成，无需层层透传 prop */
const injectedTts = inject('ttsSynthesize', null)

/** 现合成钩子：优先 prop，其次 inject（用本条消息的 text/params 现合成） */
const synthesizeHook = computed(() => {
  if (props.onSynthesize) return props.onSynthesize
  if (injectedTts && props.text) {
    return () => injectedTts(props.text, props.params)
  }
  return null
})

const RATES = [1, 1.25, 1.5, 2, 0.75]

const { toast } = useToast()

const playing = ref(false)
const pos = ref(0)
const rateIdx = ref(0)
const rate = computed(() => RATES[rateIdx.value])

/* 真实音频：优先用 props.src，历史现合成后填 realSrc；两者皆空则走 mock 假进度 */
const realSrc = ref(props.src || '')
const hasAudio = computed(() => !!realSrc.value)
const audioEl = ref(null)
const synthesizing = ref(false)
/* 显示时长：有真实音频用 audio.duration，否则用估算/传入的 duration */
const realDuration = ref(0)
const effDuration = computed(() => {
  if (hasAudio.value && realDuration.value) return realDuration.value
  return props.duration || estimateDuration(props.text)
})

/* mock 假进度用（无真实音频、无现合成能力时，保持 demo 可跑） */
let raf = null
let last = 0

function fmt(s) {
  const sec = Math.max(0, Math.round(s))
  const m = Math.floor(sec / 60)
  const ss = sec % 60
  return `${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

const pct = computed(() => (effDuration.value ? (pos.value / effDuration.value) * 100 : 0))
const curLabel = computed(() => fmt(pos.value))
const durLabel = computed(() => fmt(effDuration.value))
const rateLabel = computed(() => `${rate.value.toFixed(2).replace(/0$/, '').replace(/\.$/, '.0')}×`)

/* ---------- 真实音频（原生 <audio>）---------- */
function onLoadedMeta() {
  if (audioEl.value && Number.isFinite(audioEl.value.duration)) {
    realDuration.value = audioEl.value.duration
  }
}
function onTimeUpdate() {
  if (audioEl.value) pos.value = audioEl.value.currentTime
}
function onEnded() {
  playing.value = false
}

async function ensureAudio() {
  /* 历史消息：无 src 但有现合成钩子 → 首次播放时现合成 */
  if (!hasAudio.value && synthesizeHook.value && !synthesizing.value) {
    try {
      synthesizing.value = true
      const res = await synthesizeHook.value()
      realSrc.value = res?.src || ''
      if (res?.duration) realDuration.value = res.duration
    } catch (err) {
      toast(err?.message || '语音合成失败')
    } finally {
      synthesizing.value = false
    }
  }
  return hasAudio.value
}

async function toggle() {
  if (hasAudio.value || synthesizeHook.value) {
    // 真实音频路径
    if (playing.value) {
      audioEl.value?.pause()
      playing.value = false
      return
    }
    const ok = await ensureAudio()
    if (!ok) return
    /* DOM 更新后 <audio> 才拿到 src，等一拍再播 */
    await nextTick()
    if (audioEl.value) {
      audioEl.value.playbackRate = rate.value
      try {
        await audioEl.value.play()
        playing.value = true
      } catch {
        playing.value = false
      }
    }
    return
  }
  // mock 假进度路径（demo 兜底）
  playing.value ? stopMock() : playMock()
}

function cycleRate() {
  rateIdx.value = (rateIdx.value + 1) % RATES.length
  /* 真实音频立即生效；mock 路径 rAF 每帧现读 rate.value */
  if (audioEl.value) audioEl.value.playbackRate = rate.value
}

function download() {
  if (hasAudio.value) {
    const a = document.createElement('a')
    a.href = realSrc.value
    a.download = `语音合成_${Date.now()}.mp3`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    return
  }
  toast('音频尚未合成')
}

/* ---------- mock 假进度（无真实音频、无现合成钩子时）---------- */
function stopMock() {
  if (raf) cancelAnimationFrame(raf)
  raf = null
  playing.value = false
}
function step(now) {
  const dt = (now - last) / 1000
  last = now
  const next = pos.value + dt * rate.value
  if (next >= effDuration.value) {
    pos.value = effDuration.value
    stopMock()
    return
  }
  pos.value = next
  raf = requestAnimationFrame(step)
}
function playMock() {
  if (pos.value >= effDuration.value) pos.value = 0
  playing.value = true
  last = performance.now()
  raf = requestAnimationFrame(step)
}

onBeforeUnmount(() => {
  stopMock()
  audioEl.value?.pause()
  /* 现合成产生的 objectURL 由本组件回收；props.src 由创建方（消息层）负责 */
  if (realSrc.value && realSrc.value !== props.src) URL.revokeObjectURL(realSrc.value)
})
</script>

<template>
  <div class="cf-audio" :class="{ 'is-playing': playing }">
    <!-- 真实音频承载：无真实音频（纯 mock）时不渲染 -->
    <audio
      v-if="hasAudio"
      ref="audioEl"
      :src="realSrc"
      preload="metadata"
      @loadedmetadata="onLoadedMeta"
      @timeupdate="onTimeUpdate"
      @ended="onEnded"
    />

    <button
      class="cf-audio-play cf-tap40" type="button"
      :disabled="synthesizing"
      :aria-label="synthesizing ? '合成中' : (playing ? '暂停' : '播放')"
      @click="toggle"
    >
      <CfIcon v-if="synthesizing" name="refresh" :size="15" class="cf-audio-spin" />
      <CfIcon v-else-if="!playing" name="playfill" :size="15" class="cf-audio-ic-play" />
      <CfIcon v-else name="pause" :size="15" />
    </button>

    <span class="cf-audio-time">{{ curLabel }}</span>

    <div
      class="cf-audio-bar" role="progressbar" aria-label="播放进度"
      :aria-valuemin="0" :aria-valuemax="duration" :aria-valuenow="Math.round(pos)"
      :aria-valuetext="`${curLabel} / ${durLabel}`"
    >
      <span class="cf-audio-fill" :style="{ width: pct + '%' }" />
    </div>

    <span class="cf-audio-time">{{ durLabel }}</span>

    <span class="cf-audio-acts">
      <button
        class="cf-audio-act cf-tap40" type="button"
        :aria-label="`播放倍速，当前 ${rate} 倍速`"
        @click="cycleRate"
      >{{ rateLabel }}</button>
      <button
        class="cf-audio-act cf-audio-dl cf-tap40" type="button" aria-label="下载音频"
        @click="download"
      ><CfIcon name="download" :size="14" /></button>
    </span>
  </div>
</template>

<style scoped>
/* 视觉参考 shadcn/ui：细进度条（中性灰轨道 + 主色填充），播放键为实心主色，
   右侧倍速与下载同为 outline 档；交互态统一走 hover 底色，不靠改描边色区分。 */
.cf-audio{
  display:flex;align-items:center;gap:var(--cf-space-3);margin:var(--cf-space-4) 0;
  padding:10px var(--cf-space-3);
  border:1px solid var(--cf-line);border-radius:var(--cf-radius-md);
  background:var(--cf-surface);
}
.cf-audio-play{
  width:36px;height:36px;flex:none;border-radius:50%;
  display:grid;place-items:center;cursor:pointer;
  background:var(--cf-primary);color:#fff;
  transition:background var(--cf-transition),transform .12s var(--cf-ease-out);
}
@media (hover:hover){
  .cf-audio-play:hover{background:var(--cf-primary-deep)}
}
.cf-audio-play:active{transform:scale(.94)}
/* 三角图标在网格里偏右，往左推 1px 才在圆里视觉居中 */
.cf-audio-ic-play{margin-left:-1px}
.cf-audio-play:disabled{cursor:default;opacity:.7}
/* 合成中：refresh 图标旋转，代替 loading（sprite 无 loading 图标） */
.cf-audio-spin{animation:cf-audio-rot .8s linear infinite}
@keyframes cf-audio-rot{to{transform:rotate(360deg)}}

.cf-audio-bar{
  flex:1;min-width:0;height:4px;border-radius:var(--cf-radius-pill);
  background:var(--cf-ink-10);overflow:hidden;
}
/* 宽度由 rAF 每帧直接写，不能加过渡：过渡会追着新值跑，反而拖出滞后感 */
.cf-audio-fill{display:block;height:100%;border-radius:var(--cf-radius-pill);background:var(--cf-primary)}

.cf-audio-time{
  flex:none;font-size:var(--cf-fs-xs);color:var(--cf-text-3);
  font-variant-numeric:tabular-nums;letter-spacing:.01em;
}

.cf-audio-acts{flex:none;display:flex;align-items:center;gap:var(--cf-space-2)}
.cf-audio-act{
  height:28px;padding:0 10px;border-radius:var(--cf-radius-sm);cursor:pointer;
  display:inline-flex;align-items:center;justify-content:center;gap:4px;
  border:1px solid var(--cf-line);background:var(--cf-surface);color:var(--cf-text-2);
  font-size:var(--cf-fs-xs);font-variant-numeric:tabular-nums;
  transition:background var(--cf-transition),color var(--cf-transition),border-color var(--cf-transition);
}
@media (hover:hover){
  .cf-audio-act:hover{background:var(--cf-page);color:var(--cf-text-1);border-color:var(--cf-line-strong)}
}
.cf-audio-act:active{background:var(--cf-page);border-color:var(--cf-line-strong)}
.cf-audio-dl{padding:0;width:28px}
</style>
