<!-- ============================================================
     参考资料抽屉 · ChatFlow v1.0
     ------------------------------------------------------------
     两种模式共用一个面板外壳：
       list —— 联网资料列表（网页来源外跳，知识库来源可就地点进 doc 模式）
       doc  —— 知识库文档：命中片段直接平铺展示（移除页签切换）

     宽屏是并排推入（把正文挤窄，不盖遮罩），窄屏改底部弹出加遮罩。
     出口只有关闭按钮、Esc、窄屏点遮罩三条。
     ============================================================ -->
<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import CfIcon from './CfIcon.vue'
import PdfViewer from './PdfViewer.vue'
import { useToast } from '../composables/useToast.js'
import { renderMarkdown } from '../utils/markdown.js'

const props = defineProps({
  open: { type: Boolean, default: false },
  /** 'list' | 'doc' */
  mode: { type: String, default: 'list' },
  /** list 模式的数据 */
  webSources: { type: Array, default: () => [] },
  /** doc 模式的数据：{title,kbName,fileType,pages,date,chunks} */
  doc: { type: Object, default: null },
  /** doc 模式是否显示返回（从 list 点进来才有） */
  canBack: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'back', 'open-doc'])

const closeBtn = ref(null)
const { toast } = useToast()

/** favicon 服务偶尔取不到图（站点没有 favicon、离线环境等），记下失败的下标，
    那一条就回落回品牌色 + 简称，不留破图 */
const logoFailed = ref(new Set())
function onLogoError(i) {
  logoFailed.value = new Set(logoFailed.value).add(i)
}

/* doc 模式的视图切换：'excerpt'（显示切片）| 'full'（显示原文） */
const docView = ref('excerpt')

const title = computed(() =>
  props.mode === 'doc' ? '原文溯源' : `参考资料（${props.webSources.length}）`
)

const FILE_ICONS = {
  pdf: 'file-pdf',
  doc: 'file-doc',
  xls: 'file-xls',
  ppt: 'file-ppt',
}
function iconOf(doc) {
  return FILE_ICONS[doc?.fileType] || 'file-generic'
}

/* ---------- 原文预览：按扩展名分流 ----------
   内置 PdfViewer 只认 PDF，非 PDF 塞进去必然失败（pdfjs 解析不了那些字节流），
   之前不分类型一律塞，所以 .md 点「查看原文」就报 pdfjs 解析错误。

   分四条路：
     pdf   → 内置 PdfViewer
     图片  → <img>，浏览器原生渲染，不受 CORS 限制
     文本  → fetch 取文本，markdown 走 renderMarkdown，纯文本套 <pre>
     其余  → 外跳（Office 三件套等浏览器不认的格式）

   fileType 是上游从文件名切出来的扩展名。 */
const PDF_EXT = new Set(['pdf'])
const IMAGE_EXT = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'])
const MARKDOWN_EXT = new Set(['md', 'markdown'])
const TEXT_EXT = new Set(['txt', 'log', 'csv', 'json', 'xml', 'yml', 'yaml'])

/* 从 URL 里取扩展名：要先剥掉 ?query 和 #hash，否则
   xxx.pdf?Expires=123 会切出 "pdf?expires=123" 这种东西。 */
function extFromUrl(url) {
  if (!url) return ''
  const clean = String(url).split(/[?#]/)[0]
  const last = clean.split('/').pop() || ''
  if (!last.includes('.')) return ''
  return last.split('.').pop().toLowerCase()
}

/* 判断用哪种 viewer 只看 resourceUrl 的扩展名，不看 fileType。
   fileType 是上游从「文件名」切出来的（useChatFlow/createServiceAdapter 里
   都是 it.name.split('.').pop()），而后端会把 Office 文件转码成 PDF 再存：
     name = "xxx.pptx"  →  fileType = "pptx"
     resourceUrl = ".../xxx.pdf"  ← 真正要渲染的是这个
   按 fileType 分流的话，这种文件明明是 PDF 却被判成「不支持预览」。
   文件条上的图标仍用 fileType（显示原始格式对用户更准确）。 */
const docExt = computed(() => {
  const urlExt = extFromUrl(props.doc?.resourceUrl)
  if (urlExt) return urlExt
  // URL 上没有扩展名（少见）时才回落到文件名切出来的类型
  return String(props.doc?.fileType || '').toLowerCase()
})
const previewKind = computed(() => {
  const ext = docExt.value
  if (PDF_EXT.has(ext)) return 'pdf'
  if (IMAGE_EXT.has(ext)) return 'image'
  if (MARKDOWN_EXT.has(ext)) return 'markdown'
  if (TEXT_EXT.has(ext)) return 'text'
  return 'unsupported'
})

/* 文本类原文的拉取状态。资源在阿里云 OSS 上，默认不发 CORS 头，
   fetch 很可能被浏览器拦下——拦下就把 previewKind 降级成外跳，
   不停在「加载中」也不白屏。 */
const textLoading = ref(false)
const textHtml = ref('')
const textFailed = ref(false)

async function loadTextual() {
  const url = props.doc?.resourceUrl
  if (!url) { textFailed.value = true; return }

  textLoading.value = true
  textFailed.value = false
  textHtml.value = ''
  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const raw = await res.text()
    /* markdown 交给组件现成的渲染器（内部走 DOMPurify 净化，
       直接 v-html 安全）；纯文本套 <pre> 保留换行与缩进。 */
    textHtml.value = previewKind.value === 'markdown'
      ? renderMarkdown(raw)
      : `<pre class="cf-doc-pre">${escapeHtml(raw)}</pre>`
  } catch (e) {
    /* 绝大多数是 CORS（OSS 没配跨域），也可能是网络/404。
       统一降级到外跳，浏览器直接访问不受 CORS 约束。 */
    console.warn('[RefDrawer] 原文读取失败，降级为外跳:', e)
    textFailed.value = true
  } finally {
    textLoading.value = false
  }
}

/** 纯文本走 <pre>，必须转义——否则文件里的 <script> 会被当标签解析 */
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/* 切到原文视图、或文档本身变了，才去拉文本。
   切片视图不拉——用户可能根本不点「查看原文」，白发一个请求。 */
watch(
  [() => props.doc?.resourceUrl, docView],
  () => {
    if (docView.value !== 'full') return
    if (previewKind.value === 'markdown' || previewKind.value === 'text') {
      loadTextual()
    }
  },
  { immediate: true }
)

/** 浏览器里打开原文：Office 等格式内置渲染不了，交给浏览器/系统处理 */
function openOriginal() {
  const url = props.doc?.resourceUrl
  if (!url) {
    toast('该文档暂无原文链接')
    return
  }
  window.open(url, '_blank', 'noopener,noreferrer')
}

/* 打开时焦点移到关闭按钮，并重置为切片视图 */
watch(() => props.open, (v) => {
  if (v) {
    docView.value = 'excerpt'
    nextTick(() => closeBtn.value?.focus())
  }
})

function onCardClick(w, e) {
  if (w.kb) {
    emit('open-doc', { title: w.title, kbName: w.kbName })
  } else {
    /* 网页来源新标签页打开原文。noopener,noreferrer 是必须的：
       不加 noopener，新页面能通过 window.opener 反向操作本页（反向标签劫持）。 */
    if (w.url) {
      window.open(w.url, '_blank', 'noopener,noreferrer')
    } else {
      /* 后端偶发不带 url（字段为 null），静默无反应会让人以为卡了 */
      toast('该来源没有原文链接')
    }
    e?.currentTarget?.blur()
  }
}

function toggleView() {
  docView.value = docView.value === 'excerpt' ? 'full' : 'excerpt'
}
</script>

<template>
  <!-- 窄屏遮罩：宽屏 display:none，收不到点击，所以这条只在小屏生效 -->
  <div class="cf-scrim" :class="{ 'is-on': open }" aria-hidden="true" @click="emit('close')" />

  <!-- 宽屏：与消息区并排的 flex 项，靠自身宽度 0→380 推入，不盖遮罩 -->
  <aside
    class="cf-drawer" :class="{ 'is-open': open }"
    role="dialog" :aria-label="title" :aria-hidden="!open"
  >
    <div class="cf-panel">
      <div class="cf-panel-hd">
        <button
          v-if="mode === 'doc' && canBack"
          class="cf-back cf-tap40" type="button" aria-label="返回资料列表"
          @click="emit('back')"
        ><CfIcon name="caret-left" :size="18" /></button>
        <CfIcon name="filetext" :size="18" />
        <h2>{{ title }}</h2>
        <button ref="closeBtn" class="cf-close cf-tap40" type="button" aria-label="关闭" @click="emit('close')">
          <CfIcon name="x" :size="18" />
        </button>
      </div>

      <div class="cf-panel-bd">
        <!-- ---------- 联网资料列表 ---------- -->
        <div v-if="mode === 'list'" class="cf-scroll">
          <button
            v-for="(w, i) in webSources" :key="i"
            class="cf-ref-card" type="button"
            :aria-haspopup="w.kb ? 'dialog' : null"
            @click="onCardClick(w, $event)"
          >
            <h3>{{ w.title }}</h3>
            <p class="cf-ref-ex">{{ w.excerpt }}</p>
            <span class="cf-ref-foot">
              <!-- 知识库来源用文件夹图标 + 「来源于XXX」，网页来源用站点标识 + 站点名 -->
              <template v-if="w.kb">
                <span class="cf-ref-logo"><CfIcon name="note" :size="12" /></span>
                <span class="cf-ref-src">来源于{{ w.kbName }}</span>
              </template>
              <template v-else>
                <!-- 优先显示真实 logo 图片 -->
                <span
                  v-if="w.logo && !logoFailed.has(i)"
                  class="cf-ref-logo"
                >
                  <img :src="w.logo" :alt="w.site" @error="onLogoError(i)" />
                </span>
                <!-- logo 加载失败或不存在时的降级方案：
                     有品牌色(w.brand)时 → 品牌色背景+首字母缩写(w.ab)
                     无品牌色时 → 白色背景+边框+地球图标占位 -->
                <span
                  v-else
                  class="cf-ref-logo" :class="{ 'is-brand': !!w.brand }"
                  :style="w.brand ? { background: w.brand } : null"
                >
                  <template v-if="w.brand">{{ w.ab }}</template>
                  <CfIcon v-else name="globe" :size="12" />
                </span>
                <span class="cf-ref-src">{{ w.site }}</span>
              </template>
              <span class="cf-ref-date">{{ w.date }}</span>
            </span>
          </button>
        </div>

        <!-- ---------- 知识库文档：文档条 + 命中片段列表 ---------- -->
        <template v-else-if="doc">
          <!-- 文档条：文件图标 + 文档名 + 视图切换按钮（固定不滚动） -->
          <div class="cf-doc-bar">
            <CfIcon :name="iconOf(doc)" :size="32" class="cf-doc-icon" />
            <div class="cf-doc-info">
              <h3 class="cf-doc-title">{{ doc.title }}</h3>
            </div>
            <button
              class="cf-doc-view" type="button"
              @click="toggleView"
            >
              {{ docView === 'excerpt' ? '查看原文' : '查看切片' }}
              <CfIcon name="switch" :size="14" />
            </button>
          </div>

          <!-- 切片视图：命中片段列表（可滚动） -->
          <div v-if="docView === 'excerpt'" class="cf-excerpt-list cf-scroll">
            <div
              v-for="(c, i) in (doc.chunks || [])" :key="i"
              class="cf-excerpt"
            >
              <div class="cf-excerpt-hd">
                <p class="cf-excerpt-loc">{{ c.loc }}</p>
                <span class="cf-excerpt-no">{{ String(i + 1).padStart(2, '0') }}</span>
              </div>
              <p class="cf-excerpt-text">{{ c.text }}</p>
            </div>
          </div>

          <!-- 原文视图：按格式分流。PDF 走内置 viewer，图片直接 <img>，
               markdown/文本 fetch 回来渲染，其余（Office 等）给外跳入口。
               不分类型硬塞 PdfViewer 会让 .md 这类文件报 pdfjs 解析错误。 -->
          <div v-else class="cf-doc-full">
            <PdfViewer v-if="previewKind === 'pdf'" :src="doc.resourceUrl" />

            <!-- 图片：img 不受 CORS 约束，直接给 src 就能显示 -->
            <div v-else-if="previewKind === 'image'" class="cf-doc-image cf-scroll">
              <img :src="doc.resourceUrl" :alt="doc.title" />
            </div>

            <!-- markdown / 纯文本：读取成功就地渲染，失败（多为 OSS 跨域）降级外跳 -->
            <div
              v-else-if="(previewKind === 'markdown' || previewKind === 'text') && !textFailed"
              class="cf-doc-text cf-scroll"
            >
              <p v-if="textLoading" class="cf-doc-loading">正在读取原文…</p>
              <div v-else class="cf-md" v-html="textHtml" />
            </div>

            <!-- 兜底：格式不支持，或文本读取失败 -->
            <div v-else class="cf-doc-unsupported">
              <CfIcon :name="iconOf(doc)" :size="48" />
              <p class="cf-doc-unsupported-tip">
                {{ textFailed ? '原文无法在此读取' : '该格式暂不支持在此预览' }}
              </p>
              <button
                v-if="doc.resourceUrl"
                class="cf-doc-open" type="button"
                @click="openOriginal"
              >
                在新窗口打开
                <CfIcon name="external" :size="14" />
              </button>
            </div>
          </div>
        </template>
      </div>
    </div>
  </aside>
</template>

<style scoped>
/* 宽屏：与消息区并排的 flex 项，靠自身宽度 0→380 推入，不盖遮罩。
   overflow 挂在抽屉自己身上；visibility 是离散过渡，
   展开即刻可见、收起留到动画结束，正好用来管住 Tab 与读屏。 */
.cf-drawer{
  position:relative;flex:none;width:0;
  overflow:hidden;visibility:hidden;
  transition:width var(--cf-transition) var(--cf-ease-out),
    visibility var(--cf-transition);
}
.cf-drawer.is-open{width:min(380px,42vw);visibility:visible}

/* 内层固定宽度：外层收窄时内容不跟着压，用 overflow:hidden 裁掉看不见的部分 */
.cf-panel{
  width:380px;height:100%;
  display:flex;flex-direction:column;
  background:#ffffff;border-left:1px solid var(--cf-line);
}

.cf-panel-hd{
  flex:none;
  display:flex;align-items:center;gap:var(--cf-space-2);
  height:var(--cf-nav-h);padding:10px var(--cf-space-4);
  border-bottom:1px solid var(--cf-line);
}
.cf-panel-hd h2{
  flex:1;min-width:0;
  font-size:18px;font-weight:600;color:var(--cf-text-1);
}
.cf-back,.cf-close{
  flex:none;width:32px;height:32px;border-radius:var(--cf-radius-sm);
  display:grid;place-items:center;
  background:none;border:none;color:var(--cf-text-2);cursor:pointer;
  transition:var(--cf-transition);
}
.cf-back:hover,.cf-close:hover{background:var(--cf-fill);color:var(--cf-text-1)}

.cf-panel-bd{
  flex:1;min-height:0;
  display:flex;flex-direction:column;
}

.cf-scroll{
  flex:1;min-height:0;
  padding:var(--cf-space-4);
  display:flex;flex-direction:column;gap:var(--cf-space-3);
  overflow-y:auto;
}
.cf-scroll::-webkit-scrollbar{width:8px}
.cf-scroll::-webkit-scrollbar-track{background:transparent}
.cf-scroll::-webkit-scrollbar-thumb{background:var(--cf-ink-12);border-radius:4px}
.cf-scroll::-webkit-scrollbar-thumb:hover{background:var(--cf-ink-18)}

/* ---------- 联网资料卡片 ---------- */
.cf-ref-card{
  display:block;width:100%;text-align:left;
  padding:var(--cf-space-3);
  border:1px solid var(--cf-ink-08);border-radius:var(--cf-radius-md);
  background:#ffffff;cursor:pointer;
  transition:var(--cf-transition);
}
.cf-ref-card:hover{border-color:var(--cf-ink-12);background:var(--cf-ink-02)}
.cf-ref-card h3{
  font-size:16px;font-weight:600;color:var(--cf-text-1);
  line-height:var(--cf-lh-body);
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden;
  transition:color var(--cf-transition);
}
.cf-ref-card:hover h3{color:var(--cf-primary)}
.cf-ref-ex{
  margin-top:8px;
  font-size:14px;color:var(--cf-text-2);line-height:1.6;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;
  overflow:hidden;
}
.cf-ref-foot{
  display:flex;align-items:center;gap:6px;
  margin-top:var(--cf-space-4);
  font-size:11px;color:var(--cf-text-3);
}
.cf-ref-logo{
  flex:none;width:16px;height:16px;
  display:grid;place-items:center;
  border-radius:var(--cf-radius-xs);
  background:#fff;color:var(--cf-text-3);
  border:1px solid var(--cf-ink-08);
}
.cf-ref-logo.is-brand{
  font-size:9px;font-weight:700;color:#fff;
  text-transform:uppercase;
  border:none;
}
.cf-ref-logo>img{width:100%;height:100%;object-fit:contain;border-radius:inherit}
.cf-ref-src{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cf-ref-date{flex:none}

/* ---------- 文档条：文件图标 + 文档名 + 查看原文 ---------- */
.cf-doc-bar{
  flex:none;
  display:flex;align-items:center;gap:var(--cf-space-3);
  margin:var(--cf-space-4) var(--cf-space-4) 0;
  padding:var(--cf-space-3);
  border:1px solid var(--cf-ink-08);border-radius:var(--cf-radius-md);
  background:var(--cf-ink-02);
}
.cf-doc-icon{flex:none}
.cf-doc-info{flex:1;min-width:0}
.cf-doc-title{
  font-size:var(--cf-fs-sm);font-weight:500;color:var(--cf-text-1);
  line-height:var(--cf-lh-body);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}
.cf-doc-view{
  flex:none;
  display:inline-flex;align-items:center;gap:4px;
  padding:0 var(--cf-space-2);height:28px;
  border:1px solid var(--cf-primary-line);border-radius:var(--cf-radius-sm);
  background:var(--cf-user-bubble);
  font-size:var(--cf-fs-xs);color:var(--cf-primary);font-weight:500;
  cursor:pointer;transition:var(--cf-transition);
}
.cf-doc-view:hover{background:var(--cf-primary);color:#fff}

/* ---------- 命中片段：出处 + 原文，逐条平铺 ---------- */
.cf-excerpt-list{
  flex:1;min-height:0;
  padding:var(--cf-space-4);padding-top:var(--cf-space-3);
  display:flex;flex-direction:column;gap:var(--cf-space-3);
  overflow-y:auto;
}
.cf-excerpt-list::-webkit-scrollbar{width:8px}
.cf-excerpt-list::-webkit-scrollbar-track{background:transparent}
.cf-excerpt-list::-webkit-scrollbar-thumb{background:var(--cf-ink-12);border-radius:4px}
.cf-excerpt-list::-webkit-scrollbar-thumb:hover{background:var(--cf-ink-18)}
.cf-excerpt{
  padding:var(--cf-space-3);
  border:1px solid var(--cf-ink-08);border-radius:var(--cf-radius-md);
  background:#ffffff;
}
.cf-excerpt-hd{
  display:flex;align-items:center;justify-content:space-between;
  margin-bottom:var(--cf-space-2);
}
.cf-excerpt-loc{
  font-size:var(--cf-fs-xs);color:var(--cf-text-3);
}
.cf-excerpt-no{
  font-size:var(--cf-fs-xs);color:var(--cf-text-3);font-weight:600;
}
.cf-excerpt-text{
  font-size:var(--cf-fs-sm);color:var(--cf-text-1);line-height:1.9;
}

/* ---------- 原文视图：自建 PDF viewer，撑满抽屉剩余高度 ---------- */
.cf-doc-full{
  flex:1;min-height:500px;
  margin:0 var(--cf-space-4);margin-top:var(--cf-space-3);
}

/* 图片原文：等比缩放到抽屉宽度，超高时纵向滚动 */
.cf-doc-image{
  height:100%;min-height:500px;overflow:auto;
  border:1px solid var(--cf-ink-08);border-radius:var(--cf-radius-md);
  background:var(--cf-ink-02);
  padding:var(--cf-space-3);
}
.cf-doc-image>img{display:block;width:100%;height:auto;border-radius:var(--cf-radius-sm)}

/* markdown / 纯文本原文：白底，内容区自己滚 */
.cf-doc-text{
  height:100%;min-height:500px;overflow:auto;
  border:1px solid var(--cf-ink-08);border-radius:var(--cf-radius-md);
  background:var(--cf-surface);
  padding:var(--cf-space-4);
}
.cf-doc-loading{
  font-size:var(--cf-fs-sm);color:var(--cf-text-3);text-align:center;
  padding:var(--cf-space-6) 0;
}
/* 纯文本用 <pre> 保留换行缩进，但要允许长行折行，否则抽屉横滚 */
.cf-doc-text :deep(.cf-doc-pre){
  margin:0;font-family:var(--cf-font-mono,ui-monospace,monospace);
  font-size:var(--cf-fs-xs);line-height:1.8;color:var(--cf-text-1);
  white-space:pre-wrap;word-break:break-word;
}

/* 非 PDF 格式的占位：居中的图标 + 说明 + 外跳按钮。
   与 PdfViewer 同高，切换视图时抽屉高度不跳动。 */
.cf-doc-unsupported{
  height:100%;min-height:500px;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:var(--cf-space-3);
  border:1px solid var(--cf-ink-08);border-radius:var(--cf-radius-md);
  background:var(--cf-ink-02);
  color:var(--cf-text-3);
}
.cf-doc-unsupported-tip{
  font-size:var(--cf-fs-sm);color:var(--cf-text-2);text-align:center;
}
.cf-doc-open{
  display:inline-flex;align-items:center;gap:6px;
  height:34px;padding:0 16px;
  border:1px solid var(--cf-line-strong);border-radius:var(--cf-radius-pill);
  font-size:var(--cf-fs-sm);color:var(--cf-text-2);
  background:var(--cf-surface);cursor:pointer;
  transition:var(--cf-transition);
}
@media (hover:hover){
  .cf-doc-open:hover{border-color:var(--iflyv-brand-4);color:var(--cf-primary)}
}

/* 遮罩只服务小屏的底部弹出；宽屏是推入式，不该有遮罩 */
.cf-scrim{display:none}

/* ---------- H5：抽屉改底部弹出 + 安全区适配 ---------- */
@media (max-width:767.98px){
  .cf-scrim{
    display:block;position:fixed;inset:0;z-index:75;
    background:var(--cf-scrim);
    opacity:0;pointer-events:none;transition:opacity var(--cf-transition);
  }
  .cf-scrim.is-on{opacity:1;pointer-events:auto}
  .cf-drawer{
    position:fixed;
    left:0;right:0;bottom:0;top:auto;z-index:76;
    width:auto;
    /* 使用 dvh（动态视口高度）适配移动端浏览器地址栏 */
    height:66.67vh;height:66.67dvh;
    /* 底部安全区适配 */
    padding-bottom:env(safe-area-inset-bottom, 0px);
    transform:translateY(100%);
    transition:transform var(--cf-transition) var(--cf-ease-out),
      visibility var(--cf-transition);
  }
  .cf-drawer.is-open{width:auto;transform:none}
  .cf-panel{
    width:100%;
    border-radius:20px 20px 0 0;
    border:1px solid var(--cf-line);border-bottom:none;
  }

  /* 内容区域左右安全区适配 */
  .cf-scroll{
    padding-left:calc(var(--cf-space-4) + env(safe-area-inset-left, 0px));
    padding-right:calc(var(--cf-space-4) + env(safe-area-inset-right, 0px));
  }
}
</style>
