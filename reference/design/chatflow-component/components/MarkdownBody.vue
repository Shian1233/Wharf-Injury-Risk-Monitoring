<!-- ============================================================
     回答正文 · ChatFlow v1.0
     ------------------------------------------------------------
     渲染回答的 HTML 片段，并在挂载/更新后做两件增强：
     1. 给 <pre><code> 包上头部（语言标签 + 复制按钮）
     2. 给 <table> 包一层横向滚动容器，窄屏时表格自己滚，页面不横滚

     样式在 styles/markdown.css（全局 .cf-md 作用域），
     因为内容是 v-html 注入的，scoped 选择器加不上去。
     ============================================================ -->
<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import { useToast } from '../composables/useToast.js'

const props = defineProps({
  html: { type: String, default: '' },
  /** 生成中：显示流式光标，复制按钮禁用（此刻复制到的是残缺片段） */
  streaming: { type: Boolean, default: false },
  /** 本轮技能 key（t2i 时图片信息栏回显技能参数） */
  skill: { type: String, default: '' },
  /** 技能结构化参数：文生图用中文键 画面比例/画面风格 回显真实值 */
  skillParams: { type: Object, default: null },
})

const root = ref(null)
const { toast } = useToast()

const COPY_ICON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
  <rect x="9" y="9" width="11" height="11" rx="2"/>
  <path d="M5 15V5a2 2 0 0 1 2-2h8"/></svg>`
const DONE_ICON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M5 13l4 4L19 7"/></svg>`

/** 代码块增强：加头部。已处理过的打标记，重复调用不会套娃。 */
function enhanceCode() {
  const el = root.value
  if (!el) return
  el.querySelectorAll('pre:not([data-cf-done])').forEach((pre) => {
    pre.setAttribute('data-cf-done', '1')
    const code = pre.querySelector('code')
    const cls = code?.className ?? ''
    const lang = (/language-([\w+#-]+)/.exec(cls)?.[1]) ?? 'text'

    const wrap = document.createElement('div')
    wrap.className = 'cf-code'
    const hd = document.createElement('div')
    hd.className = 'cf-code-hd'
    hd.innerHTML =
      `<span class="cf-code-lang">${lang}</span>`
      + `<button type="button" class="cf-code-copy">${COPY_ICON}<span>复制</span></button>`

    pre.parentNode.insertBefore(wrap, pre)
    wrap.appendChild(hd)
    wrap.appendChild(pre)
  })
  syncCopyDisabled()
}

/** 表格外面套滚动容器 */
function enhanceTable() {
  const el = root.value
  if (!el) return
  el.querySelectorAll('table:not([data-cf-done])').forEach((tb) => {
    tb.setAttribute('data-cf-done', '1')
    const box = document.createElement('div')
    box.className = 'cf-md-scroll cf-scroll'
    tb.parentNode.insertBefore(box, tb)
    box.appendChild(tb)
  })
}

/** 生成中禁用所有复制按钮 */
function syncCopyDisabled() {
  root.value?.querySelectorAll('.cf-code-copy').forEach((b) => {
    b.disabled = props.streaming
  })
}

/** 复制走事件委托：代码块是动态插入的，逐个绑监听会漏掉后来的 */
async function onClick(e) {
  /* 生成图卡的下载按钮：原型没有真文件，只弹提示 */
  const dl = e.target.closest('[data-toast]')
  if (dl) { toast(dl.getAttribute('data-toast') ?? ''); return }

  const btn = e.target.closest('.cf-code-copy')
  if (!btn || btn.disabled) return
  const code = btn.closest('.cf-code')?.querySelector('code')
  if (!code) return
  try {
    await navigator.clipboard.writeText(code.textContent ?? '')
    btn.classList.add('is-done')
    btn.innerHTML = `${DONE_ICON}<span>已复制</span>`
    setTimeout(() => {
      btn.classList.remove('is-done')
      btn.innerHTML = `${COPY_ICON}<span>复制</span>`
    }, 1600)
  } catch {
    /* 非 HTTPS 或用户拒权时 clipboard 不可用，退回提示 */
    toast('当前环境不支持自动复制，请手动选中')
  }
}

/** 图片增强：加载监听 + 工具栏（尺寸 + 下载）。对齐接入方 MarkdownBody enhanceImages。 */
function enhanceImages() {
  const el = root.value
  if (!el) return
  el.querySelectorAll('img:not([data-cf-done])').forEach((img) => {
    img.setAttribute('data-cf-done', '1')
    // 已加载完成
    if (img.complete && img.naturalHeight > 0) {
      img.classList.add('loaded')
      wrapImageWithToolbar(img)
    } else {
      img.addEventListener('load', () => {
        img.classList.add('loaded')
        wrapImageWithToolbar(img)
      })
      img.addEventListener('error', () => {
        img.classList.add('loaded')
      })
    }
  })
}

/** 图片信息栏文案：文生图回显真实技能参数（画面比例/画面风格，中文键），
    值动态取自本轮 skillParams，缺省兜底 1:1 / 照片写实。 */
function buildImageInfo() {
  const sp = props.skillParams || {}
  const ratio = sp.画面比例 ?? sp.ratio ?? '1:1'
  const style = sp.画面风格 ?? sp.style ?? '照片写实'
  return `画面比例 ${ratio}，画面风格 ${style}`
}

/** 给图片包裹工具栏：底部条显示画面比例/画面风格 + 下载原图按钮 */
function wrapImageWithToolbar(img) {
  if (img.parentElement?.classList.contains('cf-md-img-wrapper')) return

  const wrapper = document.createElement('div')
  wrapper.className = 'cf-md-img-wrapper'

  const toolbar = document.createElement('div')
  toolbar.className = 'cf-md-img-toolbar'

  const info = document.createElement('div')
  info.className = 'cf-md-img-info'
  info.textContent = buildImageInfo()

  const downloadBtn = document.createElement('button')
  downloadBtn.className = 'cf-md-img-download'
  downloadBtn.type = 'button'
  downloadBtn.innerHTML = '<span>下载原图</span>'
  downloadBtn.onclick = () => downloadImage(img.src)

  toolbar.appendChild(info)
  toolbar.appendChild(downloadBtn)

  img.parentNode.insertBefore(wrapper, img)
  wrapper.appendChild(img)
  wrapper.appendChild(toolbar)
}

/** 下载图片：fetch→blob→临时 a[download] 点击→回收 objectURL */
async function downloadImage(url) {
  try {
    const response = await fetch(url)
    const blob = await response.blob()
    const blobUrl = URL.createObjectURL(blob)

    const link = document.createElement('a')
    link.href = blobUrl
    link.download = `image_${Date.now()}.png`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)

    URL.revokeObjectURL(blobUrl)
    toast('图片下载成功')
  } catch (error) {
    console.error('[MarkdownBody] 下载图片失败:', error)
    toast('图片下载失败')
  }
}

function enhance() {
  enhanceCode()
  enhanceTable()
  enhanceImages()
}

onMounted(enhance)
/* 流式输出时 html 每帧都变，nextTick 后增强新出现的块。
   已处理的块带 data-cf-done，不会重复包裹 */
watch(() => props.html, () => nextTick(enhance))
watch(() => props.streaming, () => nextTick(syncCopyDisabled))
</script>

<template>
  <div
    ref="root"
    class="cf-md"
    :class="{ 'is-streaming': streaming }"
    v-html="html"
    @click="onClick"
  />
</template>

<style>
/* 非 scoped：作用于 v-html 注入的内容。
   表格滚动容器由本组件生成，圆角边框担在这一层，样式跟着放这儿。 */
.cf-md .cf-md-scroll{
  overflow-x:auto;margin:16px 0;
  border:1px solid var(--cf-ink-10);border-radius:var(--cf-radius-md);
}
.cf-md .cf-md-scroll>table{margin:0}
/* 停止生成时追加的说明段 */
.cf-md .cf-stopped{color:var(--cf-text-3)}
</style>
