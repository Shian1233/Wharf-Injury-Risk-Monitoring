<!-- ============================================================
     用户消息 · ChatFlow v1.0
     ------------------------------------------------------------
     三种形态，由数据自动决定，调用方不用选：
     1. 纯文字 / 文字+知识库标签  → 常规气泡
     2. 纯图片附件                → 无气泡，直接露出缩略图
     3. 文字 + 文件附件           → 气泡下方 6px 挂脚注（📎 N 份资料，hover 展开）

     视频归到脚注一路：只有图片值得单独占一块视觉面积。
     ============================================================ -->
<script setup>
import { ref, computed } from 'vue'
import CfIcon from './CfIcon.vue'

const props = defineProps({
  /** {text, kbs:[{name}], attachment:{name,kind,url}, files:[{name, fileIds, fileType, size}|string]} */
  message: { type: Object, required: true },
})

const emit = defineEmits(['preview-file'])

/** 多文件时的完整列表：桌面靠 hover 展开，触屏没有 hover，靠点开/点关切换 */
const attOpen = ref(false)

/** 只有图片走无气泡的媒体形态（与发送链路一致：ChatComposer 的 isMedia 也只认
    image，视频归到脚注一路）。这里不要求「无文字」—— 历史接口把附件和提问合在
    一条记录里返回，要求无文字的话历史里的图片永远显示不出来。 */
const isMedia = computed(() => {
  const a = props.message.attachment
  return !!a && a.kind === 'image'
})

/** 先滤掉空文件名，没有有效附件就整块不画，
    否则会剩一个孤零零的回形针；兼容旧格式 string 转为对象 */
const files = computed(() =>
  (props.message.files ?? [])
    .filter(f => f && (typeof f === 'string' ? f.trim() : f.name?.trim()))
    .map(f => typeof f === 'string' ? { name: f, fileIds: null } : f)
)
const oneFile = computed(() => files.value.length === 1)

/** 知识库芯片文案。kbs 里的项有三种来源形态：
 *    {id,name}（正常）/ {id}（接入方只给 id，名称还没反查到）/ 纯字符串（旧格式）
 *  绝不能直接把对象交给模板插值 —— name 为 undefined 时会渲染成
 *  「@{ "id": "10645" }」，正是历史上出过的那个 bug。 */
function kbLabel(kb) {
  if (kb == null) return '知识库'
  if (typeof kb === 'string' || typeof kb === 'number') return String(kb) || '知识库'
  return kb.name || '知识库'
}

/** 列表 key：优先 id，再退名称，最后用下标（对象不能当 key） */
function kbKey(kb, i) {
  if (kb == null) return i
  if (typeof kb === 'string' || typeof kb === 'number') return String(kb)
  return kb.id ?? kb.name ?? i
}

const VIDEO_EXT = ['mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv', 'm4v', 'mpeg', 'mpg', '3gp']

/** 是不是视频附件。fileType 有两种来源、两种形态，都要认：
 *    上传链路 → resourceFileType，扩展名字符串（'mp4'）
 *    历史链路 → resourceType，数字编码（3 = 视频）
 *  都取不到时退回按文件名后缀判断。 */
function isVideo(file) {
  if (file.kind === 'video') return true
  const t = file.fileType
  if (t != null && String(t).trim() !== '') {
    const s = String(t).toLowerCase()
    if (s === '3') return true
    if (VIDEO_EXT.includes(s.replace(/^\./, ''))) return true
  }
  const ext = (file.name || '').split('.').pop()?.toLowerCase()
  return !!ext && VIDEO_EXT.includes(ext)
}

/** 附件可点：视频要有资源地址，其余要有 fileIds（文档预览路由靠它取件） */
function canPreview(file) {
  return isVideo(file) ? !!(file.url || file.resourceUrl) : !!file.fileIds
}

/** 点击文件打开预览
 *  视频：直接开资源地址（/agent/preview 是文档预览页，打不开视频）
 *  其余：对齐接入方，拼 /agent/preview?resourceId=xxx 新窗口打开
 */
function openPreview(file) {
  if (!canPreview(file)) return
  emit('preview-file', file)
  const url = isVideo(file)
    ? (file.url || file.resourceUrl)
    : `/agent/preview?resourceId=${encodeURIComponent(file.fileIds)}`
  window.open(url, '_blank', 'noopener')
}
</script>

<template>
  <!-- 媒体消息：无气泡 -->
  <div v-if="isMedia" class="cf-user cf-user--media">
    <span class="cf-user-img">
      <img
        v-if="message.attachment.url"
        :src="message.attachment.url"
        :alt="message.attachment.name"
      >
      <!-- 拿不到原文件时（如从历史恢复）用占位块，文件名靠 aria-label 传给读屏 -->
      <span
        v-else class="cf-user-ph"
        role="img" :aria-label="`上传的图片 ${message.attachment.name}`"
      >
        <CfIcon name="image" :size="30" />
      </span>
    </span>
  </div>

  <!-- 常规气泡：有文字才画。媒体块与它不再互斥 ——
       历史恢复时后端把附件和提问合在一条记录里，两者要同时显示 -->
  <div v-if="message.text || (message.kbs ?? []).length" class="cf-user">
    <!-- @ 的知识库：气泡正文前的渐变色字段 -->
    <span
      v-for="(kb, i) in message.kbs ?? []"
      :key="kbKey(kb, i)" class="cf-user-kb"
    >@{{ kbLabel(kb) }}</span>{{ message.text }}
  </div>

  <!-- 附件脚注：贴在气泡下方 6px -->
  <component
    :is="oneFile ? 'div' : 'button'"
    v-if="files.length"
    class="cf-att-foot"
    :class="{ 'is-open': attOpen, 'is-clickable': oneFile && canPreview(files[0]) }"
    :type="oneFile ? undefined : 'button'"
    :aria-expanded="oneFile ? undefined : attOpen"
    @click="oneFile ? openPreview(files[0]) : (attOpen = !attOpen)"
  >
    <CfIcon name="clip" :size="14" />
    <template v-if="oneFile">{{ files[0].name }}</template>
    <template v-else>{{ files.length }} 份资料</template>
    <!-- 多个时展开完整文件名列表：桌面 hover 即出，触屏点开/点关（is-open 由点击驱动） -->
    <div v-if="!oneFile" class="cf-att-list">
      <div
        v-for="f in files"
        :key="f.name"
        :class="{ 'is-clickable': canPreview(f) }"
        @click.stop="openPreview(f)"
      >
        {{ f.name }}
      </div>
    </div>
  </component>
  <span v-if="attOpen" class="cf-catch" @click="attOpen = false" />
</template>

<style scoped>
.cf-user{
  margin-left:auto;max-width:min(560px, 75%);width:fit-content;
  background:var(--cf-user-bubble);color:var(--cf-text-1);
  border-radius:var(--cf-radius-bubble);padding:10px var(--cf-space-4);
  /* 不要加 min-height:48px：Chrome 下 width:fit-content + white-space:pre-wrap
     遇到消息里的显式换行 \n 时，min-height 会把盒子高度卡在 48px 不撑开，
     第二行文字溢出到气泡背景外（看起来像背景没包住字）。48px 本就是单行
     气泡的天然高度（行高 28px + 上下 padding 各 10px），去掉不影响短消息。 */
  font-size:var(--cf-fs-base);line-height:var(--cf-lh-body);
  word-break:break-word;
  /* 保留用户输入的换行：{{ message.text }} 插值出来的 \n 在默认
     white-space:normal 下会被当普通空白折叠成一个空格 —— 粘贴的多行文字
     发出去后会挤成一行（输入框里换行是对的、数据也带 \n，丢在渲染这一步）。
     pre-wrap 保留换行与连续空格，同时仍按容器宽度自动折行。
     模板里芯片与正文是紧凑相接的（</span>{{ text }} 中间无空白），
     标签边界的缩进浏览器会折叠掉，所以不会引入多余空格。 */
  white-space:pre-wrap;
  backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
}

/* H5 响应式：气泡最大宽度调整 */
@media (max-width: 767.98px) {
  .cf-user{
    max-width: 85%;
  }
}
/* 纯图片消息不需要气泡背景，直接露出内容 */
.cf-user--media{
  background:none;border-radius:0;padding:0;min-height:0;
  backdrop-filter:none;-webkit-backdrop-filter:none;
}
/* 媒体消息与紧随的文字气泡是一组：抵掉消息流的 gap，组内固定 6px */
.cf-user--media+.cf-user{margin-top:calc(6px - var(--cf-msg-gap))}

/* @ 知识库标签：background-clip:text 让文字吃渐变；
   color 先给主色兜底，不支持 clip 的环境退化成纯色而不是透明看不见 */
.cf-user-kb{
  font-weight:600;margin-right:6px;color:var(--cf-kb-fallback);
  background:var(--cf-kb-gradient);
  -webkit-background-clip:text;background-clip:text;
  -webkit-text-fill-color:transparent;
}
/* 多个连排时收一点间距，避免 6px×N 累积得太散 */
.cf-user-kb+.cf-user-kb{margin-left:-2px}

/* ---------- 图片缩略图 ---------- */
.cf-user-img{display:block;text-align:right}
.cf-user-img img,.cf-user-ph{
  display:block;margin-left:auto;
  border-radius:10px;border:1px solid var(--cf-thumb-border);
}
/* 长边锁 260：宽图受 max-width 限、竖长图受 max-height 限，
   两个方向都按原比例缩，不裁切也不拉伸 */
.cf-user-img img{
  width:auto;height:auto;
  max-width:var(--cf-thumb-max);max-height:var(--cf-thumb-max);
}
/* 占位块靠固定宽 + 自身比例出尺寸，所以要单独给宽 */
.cf-user-ph{
  width:var(--cf-thumb-max);max-width:100%;aspect-ratio:4/3;
  display:grid;place-items:center;color:var(--cf-primary);
  background:linear-gradient(160deg,var(--cf-primary-soft),var(--cf-placeholder-end));
}

/* ---------- 附件脚注 ----------
   负 margin 抵掉消息流的 gap，贴到气泡下方 6px。
   胶囊底是一级文字色的 4% 透明度。 */
.cf-att-foot{
  margin:calc(6px - var(--cf-msg-gap)) 0 0 auto;width:fit-content;
  display:inline-flex;align-items:center;gap:5px;
  padding:3px 10px;border-radius:var(--cf-radius-pill);
  background:var(--cf-pill-bg);
  font-size:var(--cf-fs-xs);line-height:18px;color:var(--cf-text-2);
  position:relative;cursor:default;
}
/* 多文件时脚注渲染成 button：桌面靠 hover 展开列表，触屏没有 hover，
   点开/点关由 is-open 驱动——两条路径都要能看到完整文件名 */
button.cf-att-foot{cursor:pointer}
.cf-att-foot.is-clickable{cursor:pointer}
.cf-att-foot :deep(svg){flex-shrink:0;color:var(--cf-text-2)}
.cf-att-list{
  position:absolute;right:0;top:calc(100% + 4px);
  min-width:200px;max-width:360px;
  background:var(--cf-surface);border:1px solid var(--cf-line);
  border-radius:var(--cf-radius-lg);box-shadow:var(--cf-shadow-float);
  padding:var(--cf-space-2);
  opacity:0;pointer-events:none;transition:opacity .15s ease;z-index:41;
}
.cf-att-foot.is-open .cf-att-list{opacity:1;pointer-events:auto}
@media (hover:hover){
  .cf-att-foot:hover .cf-att-list{opacity:1;pointer-events:auto}
}
.cf-att-list>div{
  padding:var(--cf-space-2);border-radius:var(--cf-radius-md);
  font-size:13px;color:var(--cf-text-1);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.cf-att-list>div.is-clickable{cursor:pointer}
@media (hover:hover){
  .cf-att-list>div:hover{background:var(--cf-page)}
  .cf-att-list>div.is-clickable:hover{color:var(--cf-primary)}
  .cf-att-foot.is-clickable:hover{color:var(--cf-primary)}
}
</style>
