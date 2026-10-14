<!-- PDF 查看器 · ChatFlow v1.0 -->
<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import CfIcon from './CfIcon.vue'
import { getPdfjs, getPdfWorkerUrl } from '../utils/externalDeps.js'

const props = defineProps({
  src: { type: String, required: true },
})

const container = ref(null)
const loading = ref(true)
const error = ref('')
const total = ref(0)
const scale = ref(1)
const SCALES = [0.75, 1, 1.25, 1.5, 2]
const moreMenuOpen = ref(false)
const rotation = ref(0) // 0, 90, 180, 270
const textLayerEnabled = ref(false)
const searchOpen = ref(false)
const searchQuery = ref('')
const searchMatches = ref([])
const currentMatchIndex = ref(-1)

let pdfDoc = null
let lib = null

async function getLib() {
  if (lib) return lib
  /* pdfjs 已从 bundle external 出去（gzip 720KB，只有原文溯源用得上）。
     取值走 externalDeps：CDN 场景读接入方注入，源码拷贝场景回落动态 import。 */
  const m = await getPdfjs()
  /* worker 地址同理走 externalDeps：
     源码拷贝场景仍用 ?url 交给 Vite（构建期内联成 base64 data URL，自包含）；
     CDN 场景 ?url 这个 Vite 专有语法不成立，必须由接入方注入真实 URL。
     不能用 new URL('...', import.meta.url)：UMD 下 import.meta 被替换成
     空对象（构建期有 EMPTY_IMPORT_META 警告），算出来的地址是错的。 */
  m.GlobalWorkerOptions.workerSrc = await getPdfWorkerUrl()
  lib = m
  return lib
}

async function load(src) {
  loading.value = true
  error.value = ''
  pdfDoc = null
  total.value = 0
  try {
    const pdfjsLib = await getLib()
    pdfDoc = await pdfjsLib.getDocument({ url: src }).promise
    total.value = pdfDoc.numPages
    loading.value = false
    await nextTick()
    await renderAllPages()
  } catch (e) {
    /* 预签名地址过期是最常见的失败原因：resourceUrl 带 X-Amz-Expires，
       超期后对象存储返回一段 AccessDenied 的 XML，pdfjs 拿到的不是 PDF
       字节流 → 抛 InvalidPDFStructure/UnexpectedResponse 这类底层错误。
       原样把 e.message 吐给用户看不懂，这里翻译成一句能行动的提示。
       真正的修法在后端：下发时重新签发地址。 */
    error.value = explainError(e)
    loading.value = false
  }
}

/** 把 pdfjs 的底层错误翻译成用户能看懂的一句话 */
function explainError(e) {
  const raw = String(e?.message || e || '')
  const name = e?.name || ''
  if (/expired|AccessDenied|403/i.test(raw)) {
    return '文档链接已失效，请刷新页面重新获取'
  }
  if (name === 'InvalidPDFException' || /Invalid PDF structure/i.test(raw)) {
    return '文档内容无法解析，链接可能已失效'
  }
  if (name === 'MissingPDFException' || /404|Missing PDF/i.test(raw)) {
    return '文档不存在或已被删除'
  }
  if (/Failed to fetch|NetworkError|CORS/i.test(raw)) {
    return '文档读取失败，请检查网络或稍后重试'
  }
  return raw || '文档加载失败'
}

async function renderAllPages() {
  if (!pdfDoc || !container.value) return
  container.value.innerHTML = ''

  // 获取容器宽度用于计算基准缩放
  const containerWidth = container.value.parentElement.clientWidth - 32 // 减去左右 padding

  for (let num = 1; num <= total.value; num++) {
    const pdfPage = await pdfDoc.getPage(num)
    // 先获取原始尺寸
    const originalViewport = pdfPage.getViewport({ scale: 1, rotation: rotation.value })
    // 计算让页面宽度刚好填满容器的基准缩放
    const baseScale = containerWidth / originalViewport.width
    // 应用用户选择的缩放倍数
    const finalScale = baseScale * scale.value
    const viewport = pdfPage.getViewport({ scale: finalScale, rotation: rotation.value })

    // 创建页面容器
    const pageDiv = document.createElement('div')
    pageDiv.className = 'cf-pdf-page'
    pageDiv.style.position = 'relative'
    pageDiv.style.marginBottom = '12px'
    pageDiv.style.width = viewport.width + 'px'
    pageDiv.style.height = viewport.height + 'px'

    // Canvas 层
    const canvas = document.createElement('canvas')
    canvas.width = viewport.width
    canvas.height = viewport.height
    canvas.style.display = 'block'

    const ctx = canvas.getContext('2d')
    const renderTask = pdfPage.render({ canvasContext: ctx, viewport })
    await renderTask.promise

    pageDiv.appendChild(canvas)

    // 文本层（如果启用）
    if (textLayerEnabled.value) {
      const textLayerDiv = document.createElement('div')
      textLayerDiv.className = 'cf-pdf-text-layer'
      textLayerDiv.style.position = 'absolute'
      textLayerDiv.style.left = '0'
      textLayerDiv.style.top = '0'
      textLayerDiv.style.right = '0'
      textLayerDiv.style.bottom = '0'
      textLayerDiv.style.overflow = 'hidden'
      textLayerDiv.style.lineHeight = '1'

      pageDiv.appendChild(textLayerDiv)

      // 渲染文本层
      const textContent = await pdfPage.getTextContent()
      const pdfjsLib = await getLib()
      pdfjsLib.renderTextLayer({
        textContentSource: textContent,
        container: textLayerDiv,
        viewport: viewport,
      })
    }

    container.value.appendChild(pageDiv)
  }
}

async function changeScale(delta) {
  const idx = SCALES.indexOf(scale.value)
  const next = idx + delta
  if (next < 0 || next >= SCALES.length) return
  scale.value = SCALES[next]
  await renderAllPages()
}

function rotate(deg) {
  rotation.value = (rotation.value + deg + 360) % 360
  renderAllPages()
  moreMenuOpen.value = false
}

function goToTop() {
  container.value?.parentElement?.scrollTo({ top: 0, behavior: 'smooth' })
  moreMenuOpen.value = false
}

function goToBottom() {
  const parent = container.value?.parentElement
  if (parent) {
    parent.scrollTo({ top: parent.scrollHeight, behavior: 'smooth' })
  }
  moreMenuOpen.value = false
}

function toggleTextLayer() {
  textLayerEnabled.value = !textLayerEnabled.value
  renderAllPages()
  moreMenuOpen.value = false
}

function print() {
  window.print()
  moreMenuOpen.value = false
}

function showDocProps() {
  if (!pdfDoc) return
  pdfDoc.getMetadata().then(({ info }) => {
    const lines = [
      `标题：${info.Title || '无'}`,
      `作者：${info.Author || '无'}`,
      `主题：${info.Subject || '无'}`,
      `关键词：${info.Keywords || '无'}`,
      `创建者：${info.Creator || '无'}`,
      `生成器：${info.Producer || '无'}`,
      `创建日期：${info.CreationDate || '无'}`,
      `修改日期：${info.ModDate || '无'}`,
      `总页数：${total.value}`,
    ]
    alert(lines.join('\n'))
  })
  moreMenuOpen.value = false
}

async function performSearch() {
  if (!searchQuery.value.trim() || !pdfDoc) {
    searchMatches.value = []
    currentMatchIndex.value = -1
    clearHighlights()
    return
  }

  searchMatches.value = []
  clearHighlights()

  const query = searchQuery.value.toLowerCase()

  for (let pageNum = 1; pageNum <= total.value; pageNum++) {
    const page = await pdfDoc.getPage(pageNum)
    const textContent = await page.getTextContent()

    let pageText = ''
    const items = textContent.items
    for (let i = 0; i < items.length; i++) {
      pageText += items[i].str
    }

    const lowerPageText = pageText.toLowerCase()
    let index = lowerPageText.indexOf(query)

    while (index !== -1) {
      searchMatches.value.push({ pageNum, index })
      index = lowerPageText.indexOf(query, index + 1)
    }
  }

  if (searchMatches.value.length > 0) {
    currentMatchIndex.value = 0
    highlightMatch(0)
  }
}

function clearHighlights() {
  document.querySelectorAll('.cf-pdf-highlight').forEach(el => el.remove())
}

function highlightMatch(matchIdx) {
  if (matchIdx < 0 || matchIdx >= searchMatches.value.length) return

  clearHighlights()

  const match = searchMatches.value[matchIdx]
  const pageDiv = container.value?.children[match.pageNum - 1]
  if (!pageDiv) return

  // 简化高亮：在整页添加标记类
  pageDiv.classList.add('cf-pdf-highlight-page')
  setTimeout(() => pageDiv.classList.remove('cf-pdf-highlight-page'), 2000)

  // 滚动到对应页面
  pageDiv.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function searchNext() {
  if (searchMatches.value.length === 0) return
  currentMatchIndex.value = (currentMatchIndex.value + 1) % searchMatches.value.length
  highlightMatch(currentMatchIndex.value)
}

function searchPrev() {
  if (searchMatches.value.length === 0) return
  currentMatchIndex.value = (currentMatchIndex.value - 1 + searchMatches.value.length) % searchMatches.value.length
  highlightMatch(currentMatchIndex.value)
}

function closeSearch() {
  searchOpen.value = false
  searchQuery.value = ''
  searchMatches.value = []
  currentMatchIndex.value = -1
  clearHighlights()
}

function download() {
  const a = document.createElement('a')
  a.href = props.src
  a.download = props.src.split('/').pop() || 'document.pdf'
  a.click()
}

watch(() => props.src, (v) => { if (v) load(v) }, { immediate: true })
</script>

<template>
  <div class="cf-pdf">
    <!-- 工具栏 -->
    <div class="cf-pdf-bar">
      <div class="cf-pdf-zoom">
        <button class="cf-pdf-btn" :disabled="scale <= SCALES[0]" @click="changeScale(-1)">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="11" cy="11" r="7"/><path d="M8 11h6M21 21l-4.35-4.35"/>
          </svg>
        </button>
        <span class="cf-pdf-scale">{{ Math.round(scale * 100) }}%</span>
        <button class="cf-pdf-btn" :disabled="scale >= SCALES[SCALES.length - 1]" @click="changeScale(1)">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="11" cy="11" r="7"/><path d="M11 8v6M8 11h6M21 21l-4.35-4.35"/>
          </svg>
        </button>
      </div>
      <div class="cf-pdf-actions">
        <button class="cf-pdf-btn" title="搜索" @click="searchOpen = !searchOpen">
          <CfIcon name="search" :size="16" />
        </button>
        <div class="cf-pdf-more">
          <button class="cf-pdf-btn" title="更多" @click="moreMenuOpen = !moreMenuOpen">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/>
            </svg>
          </button>
          <div v-if="moreMenuOpen" class="cf-pdf-menu" @click.stop>
            <button class="cf-pdf-menu-item" @click="print">
              <CfIcon name="printer" :size="14" />
              <span>打印</span>
            </button>
            <button class="cf-pdf-menu-item" @click="download">
              <CfIcon name="download" :size="14" />
              <span>保存</span>
            </button>
            <div class="cf-pdf-menu-divider" />
            <button class="cf-pdf-menu-item" @click="goToTop">
              <CfIcon name="caret-up" :size="14" />
              <span>转到第一页</span>
            </button>
            <button class="cf-pdf-menu-item" @click="goToBottom">
              <CfIcon name="caret-down" :size="14" />
              <span>转到最后一页</span>
            </button>
            <div class="cf-pdf-menu-divider" />
            <button class="cf-pdf-menu-item" @click="rotate(90)">
              <CfIcon name="rotate-cw" :size="14" />
              <span>顺时针旋转</span>
            </button>
            <button class="cf-pdf-menu-item" @click="rotate(-90)">
              <CfIcon name="rotate-ccw" :size="14" />
              <span>逆时针旋转</span>
            </button>
            <div class="cf-pdf-menu-divider" />
            <button class="cf-pdf-menu-item" :class="{ 'is-active': textLayerEnabled }" @click="toggleTextLayer">
              <CfIcon name="cursor-text" :size="14" />
              <span>文本选择工具</span>
            </button>
            <div class="cf-pdf-menu-divider" />
            <button class="cf-pdf-menu-item" @click="showDocProps">
              <CfIcon name="info" :size="14" />
              <span>文档属性</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 搜索面板 -->
    <div v-if="searchOpen" class="cf-pdf-search">
      <input
        v-model="searchQuery"
        type="text"
        class="cf-pdf-search-input"
        placeholder="搜索文档内容..."
        @keyup.enter="performSearch"
      />
      <div class="cf-pdf-search-info">
        <span v-if="searchMatches.length > 0">
          {{ currentMatchIndex + 1 }} / {{ searchMatches.length }}
        </span>
        <span v-else-if="searchQuery && searchMatches.length === 0">
          无匹配
        </span>
      </div>
      <button class="cf-pdf-btn" :disabled="searchMatches.length === 0" @click="searchPrev">
        <CfIcon name="caret-up" :size="14" />
      </button>
      <button class="cf-pdf-btn" :disabled="searchMatches.length === 0" @click="searchNext">
        <CfIcon name="caret-down" :size="14" />
      </button>
      <button class="cf-pdf-btn" @click="closeSearch">
        <CfIcon name="x" :size="14" />
      </button>
    </div>

    <!-- 内容区 -->
    <div class="cf-pdf-body">
      <div v-if="loading" class="cf-pdf-state">加载中…</div>
      <div v-else-if="error" class="cf-pdf-state cf-pdf-err">加载失败：{{ error }}</div>
      <div v-else ref="container" class="cf-pdf-canvas" />
    </div>
  </div>
</template>

<style scoped>
.cf-pdf{
  display:flex;flex-direction:column;
  border:1px solid var(--cf-ink-08);border-radius:var(--cf-radius-md);
  overflow:hidden;background:var(--cf-surface);
  height:100%;
}
.cf-pdf-bar{
  flex:none;
  display:flex;align-items:center;justify-content:space-between;gap:var(--cf-space-2);
  padding:0 var(--cf-space-3);height:44px;
  background:var(--cf-ink-02);border-bottom:1px solid var(--cf-ink-08);
}
.cf-pdf-zoom{display:flex;align-items:center;gap:4px}
.cf-pdf-actions{display:flex;align-items:center;gap:4px}
.cf-pdf-btn{
  width:28px;height:28px;flex:none;border-radius:var(--cf-radius-sm);
  display:grid;place-items:center;
  background:none;border:none;color:var(--cf-text-2);cursor:pointer;
  transition:var(--cf-transition);
}
.cf-pdf-btn:hover:not(:disabled){background:var(--cf-ink-06);color:var(--cf-text-1)}
.cf-pdf-btn:disabled{opacity:.35;cursor:not-allowed}
.cf-pdf-scale{
  min-width:52px;font-size:var(--cf-fs-xs);color:var(--cf-text-2);
  text-align:center;font-variant-numeric:tabular-nums;
}
.cf-pdf-body{
  flex:1;min-height:0;overflow:auto;
  display:flex;flex-direction:column;
  background:#e4e4e4;
}
.cf-pdf-state{
  flex:1;display:grid;place-items:center;
  font-size:var(--cf-fs-sm);color:var(--cf-text-3);
}
.cf-pdf-err{color:var(--cf-danger)}
.cf-pdf-canvas{
  flex:none;margin:var(--cf-space-4) auto;
}
.cf-pdf-canvas canvas{display:block;box-shadow:0 2px 12px rgba(0,0,0,.15)}

/* PDF 文本层样式 */
.cf-pdf-text-layer{
  position:absolute;
  left:0;top:0;right:0;bottom:0;
  overflow:hidden;
  opacity:0.2;
  line-height:1;
}
.cf-pdf-text-layer :deep(span){
  color:transparent;
  position:absolute;
  white-space:pre;
  cursor:text;
  transform-origin:0% 0%;
}
.cf-pdf-text-layer :deep(::selection){
  background:rgba(0,123,255,0.3);
}

/* 搜索面板 */
.cf-pdf-search{
  flex:none;
  display:flex;align-items:center;gap:6px;
  padding:0 var(--cf-space-3);height:40px;
  background:var(--cf-ink-02);border-bottom:1px solid var(--cf-ink-08);
}
.cf-pdf-search-input{
  flex:1;min-width:0;
  height:28px;padding:0 10px;
  border:1px solid var(--cf-ink-12);border-radius:var(--cf-radius-sm);
  background:var(--cf-surface);
  font-size:var(--cf-fs-sm);color:var(--cf-text-1);
  outline:none;box-shadow:none;transition:var(--cf-transition);
}
.cf-pdf-search-input:focus{border-color:var(--cf-primary);box-shadow:none}
.cf-pdf-search-info{
  flex:none;min-width:50px;
  font-size:var(--cf-fs-xs);color:var(--cf-text-3);
  text-align:center;font-variant-numeric:tabular-nums;
}

/* 搜索高亮页面 */
.cf-pdf-page.cf-pdf-highlight-page{
  box-shadow:0 0 0 3px var(--cf-primary) !important;
}

/* 更多菜单 */
.cf-pdf-more{position:relative}
.cf-pdf-menu{
  position:absolute;top:calc(100% + 4px);right:0;z-index:10;
  min-width:160px;
  background:var(--cf-surface);
  border:1px solid var(--cf-ink-08);
  border-radius:var(--cf-radius-md);
  box-shadow:0 4px 12px rgba(0,0,0,.12);
  padding:4px 0;
}
.cf-pdf-menu-item{
  display:flex;align-items:center;gap:8px;
  width:100%;padding:8px 12px;
  background:none;border:none;
  font-size:var(--cf-fs-sm);color:var(--cf-text-1);
  text-align:left;cursor:pointer;
  transition:var(--cf-transition);
}
.cf-pdf-menu-item:hover{background:var(--cf-ink-04)}
.cf-pdf-menu-item.is-active{color:var(--cf-primary);font-weight:500}
.cf-pdf-menu-divider{
  height:1px;margin:4px 0;
  background:var(--cf-ink-08);
}
</style>
