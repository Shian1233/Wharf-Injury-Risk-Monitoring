<!-- ============================================================
     知识库依据 · ChatFlow v1.0
     ------------------------------------------------------------
     问答正文底部的知识库命中列表：文件类型图标 + 文档名 + 命中片段数角标。
     点击任意条目触发 open，交给接入方打开 RefDrawer 抽屉。

     样式迁移自 source-trace-standalone 的 SourceCiteList 组件。
     ============================================================ -->
<script setup>
import { ref, computed } from 'vue'
import CfIcon from './CfIcon.vue'

const props = defineProps({
  /** 文档数组，每项需包含 {title, fileType, excerptCount} */
  sources: { type: Array, default: () => [] },
  /** 本轮的检索范围（知识库名），用于抽屉显示 */
  kbNames: { type: Array, default: () => [] },
  /** 关掉 refDrawer 时传 false，条目退化为纯展示 */
  clickable: { type: Boolean, default: true },
})

const emit = defineEmits(['open'])

/** 超过这个数收进「更多」，避免命中一多就把正文挤下去一大截 */
const MAX_VISIBLE = 5
const expanded = ref(false)
const hasMore = computed(() => props.sources.length > MAX_VISIBLE)
const remainCount = computed(() => props.sources.length - MAX_VISIBLE)
const visibleSources = computed(() =>
  expanded.value ? props.sources : props.sources.slice(0, MAX_VISIBLE)
)

/* 文件类型图标 → sprite 里的 symbol 名。
   彩色图标已注入 IconSprite.vue（id 形如 cf-i-file-pdf / cf-i-file-docx），
   用 <use> 引用，矢量直进 DOM，任何尺寸和 dpr 都锐利 ——
   之前试过 <img src="内联 svg">，高分屏下会糊，故弃用。
   fileType 来自文件名后缀（见 createServiceAdapter 与 useChatFlow 的 sources 映射），
   已经是小写扩展名；这里只做「扩展名 → 图标名」映射，
   没配到的类型回落到 file-generic（单色通用文件图标）。 */
function iconOf(doc) {
  const ext = String(doc?.fileType || '').toLowerCase().replace(/^\./, '')
  /* 图标名不带 cf-i- 前缀，CfIcon 会自动拼。凡是 icon-svg 目录里有的扩展名，
     这里列出来即可命中 sprite；没有对应 symbol 的扩展名自然落到通用图标。 */
  const known = ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx',
    'txt', 'md', 'png', 'jpg', 'jpeg', 'mp3', 'mp4']
  return known.includes(ext) ? `file-${ext}` : 'file-generic'
}

function open(doc, index) {
  if (!props.clickable) return
  /* 检索范围可能选了多个库，取第一个当归属 */
  emit('open', { ...doc, kbName: props.kbNames[0] ?? '' })
}
</script>

<template>
  <div v-if="sources.length" class="cf-cite">
    <p class="cf-cite-hd">
      为您找到以下内容<span class="cf-cite-total">({{ sources.length }})</span>
    </p>
    <ol class="cf-cite-list">
      <li v-for="(doc, i) in visibleSources" :key="i">
        <component
          :is="clickable ? 'button' : 'span'"
          class="cf-cite-item"
          :class="{ 'is-static': !clickable }"
          :type="clickable ? 'button' : undefined"
          :aria-haspopup="clickable ? 'dialog' : undefined"
          @click="open(doc, i)"
        >
          <span class="cf-cite-no">{{ i + 1 }}.</span>
          <CfIcon :name="iconOf(doc)" :size="22" class="cf-cite-icon" />
          <span class="cf-cite-name" :title="doc.title">{{ doc.title }}</span>
          <span class="cf-cite-count">{{ doc.excerptCount || 0 }}</span>
        </component>
      </li>
      <li v-if="hasMore">
        <button
          class="cf-cite-more"
          type="button"
          :aria-expanded="expanded"
          @click="expanded = !expanded"
        >
          <span>{{ expanded ? '收起' : `展开查看剩余 ${remainCount} 条` }}</span>
          <CfIcon name="caret-down" :size="14" class="cf-cite-more-ar" :class="{ 'is-up': expanded }" />
        </button>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.cf-cite{
  margin-top:var(--cf-space-4);
  padding-top:var(--cf-space-4);
  border-top:1px solid var(--cf-ink-08);
}
.cf-cite-hd{
  display:flex;align-items:center;gap:6px;
  margin-bottom:var(--cf-space-2);
  font-size:var(--cf-fs-sm);color:var(--cf-text-1);
}
/* 命中总数：纯文字，跟标题同色同级，不做徽标突出 */
.cf-cite-total{
  color:var(--cf-text-1);font-variant-numeric:tabular-nums;
}
.cf-cite-list{display:flex;flex-direction:column;gap:6px;padding:0;list-style:none;margin-top:10px}

.cf-cite-item{
  display:inline-flex;align-items:center;gap:var(--cf-space-2);max-width:100%;
  padding:6px var(--cf-space-2);border-radius:var(--cf-radius-sm);
  border:none;
  cursor:pointer;text-align:left;background:transparent;
  transition:background var(--cf-transition);
}
.cf-cite-item:hover{background:var(--cf-fill)}
.cf-cite-item.is-static{cursor:default}
.cf-cite-item.is-static:hover{background:transparent}

.cf-cite-no{
  flex:none;font-size:var(--cf-fs-sm);color:var(--cf-text-3);
  font-variant-numeric:tabular-nums;
}
.cf-cite-icon{flex:none}
.cf-cite-name{
  min-width:0;font-size:var(--cf-fs-sm);color:var(--iflyv-gray-8);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  transition:color var(--cf-transition);
}
.cf-cite-item:hover .cf-cite-name{color:var(--cf-primary)}
.cf-cite-item.is-static .cf-cite-name{color:var(--cf-text-1)}
/* 命中片段数角标：小方胶囊，弱化处理——它只是数量提示，不是重点信息 */
.cf-cite-count{
  flex:none;min-width:18px;height:18px;padding:0 5px;
  display:inline-flex;align-items:center;justify-content:center;
  border-radius:var(--cf-radius-xs);background:var(--cf-ink-06);
  font-size:11px;color:var(--cf-text-3);font-variant-numeric:tabular-nums;
}

.cf-cite-more{
  display:inline-flex;align-items:center;gap:4px;
  padding:6px var(--cf-space-2);
  border:none;border-radius:var(--cf-radius-sm);background:transparent;
  font-size:var(--cf-fs-sm);color:var(--cf-text-3);cursor:pointer;
  transition:background var(--cf-transition),color var(--cf-transition);
}
.cf-cite-more:hover{background:var(--cf-fill);color:var(--cf-primary)}
.cf-cite-more-ar{transition:transform var(--cf-transition)}
.cf-cite-more-ar.is-up{transform:rotate(180deg)}
</style>
