<!-- ============================================================
     回答抬头 · ChatFlow v1.0
     ------------------------------------------------------------
     一行元信息：回答类型 + 调用模型 +（知识库 N）+（联网搜索）。
     告诉用户这条回答是怎么来的，出问题时也便于定位。

     每一项都是独立的小胶囊（不是纯文字）：并排时彼此有边界，
     一眼能数出本轮带了几个条件。回答类型用主色底与其余项区分。
     ============================================================ -->
<script setup>
import CfIcon from './CfIcon.vue'

defineProps({
  /** {answerType, model, webSearch, kbCount} */
  meta: { type: Object, required: true },
})
</script>

<template>
  <div class="cf-meta">
    <span v-if="meta.answerType" class="cf-meta-tag">{{ meta.answerType }}</span>
    <span v-if="meta.model">
      <CfIcon name="chip" :size="14" />{{ meta.model }}
    </span>
    <span v-if="meta.kbCount">
      <CfIcon name="books" :size="14" />知识库 {{ meta.kbCount }}
    </span>
    <span v-if="meta.webSearch">
      <CfIcon name="globe" :size="14" />联网搜索
    </span>
  </div>
</template>

<style scoped>
/* 行高与字距对齐正文（--cf-lh-body / -0.16px）：
   原型里这一行是 .md 的第一个子节点，会继承正文的排版；
   本组件把它提到了 .md 之外（元信息不是正文内容），所以显式补上，
   两边渲染才一致 */
.cf-meta{
  display:flex;align-items:center;gap:var(--cf-space-2);flex-wrap:wrap;
  margin-bottom:var(--cf-space-4);
  font-size:var(--cf-fs-xs);color:var(--cf-gray-6);
  line-height:var(--cf-lh-body);letter-spacing:-0.16px;
}
/* 各项统一的胶囊骨架：并排时彼此有边界，一眼能数出本轮带了几个条件 */
.cf-meta>span{
  display:inline-flex;align-items:center;gap:var(--cf-space-1);
  height:28px;padding:0 10px;
  border-radius:var(--cf-radius-sm);
  font-size:13px;line-height:var(--cf-lh-body);
}
/* 回答类型：主色浅底 + 主色描边，与其余中性项区分 */
.cf-meta-tag{
  background:var(--cf-user-bubble);color:var(--cf-primary);
  font-weight:500;
  border:.5px solid var(--cf-primary-line);
}
/* 其余项：中性浅底 */
.cf-meta>span:not(.cf-meta-tag){
  color:var(--cf-gray-6);
  background:var(--cf-ink-03);border:.5px solid var(--cf-ink-08);
  transition:all .15s ease;
}
@media (hover:hover){
  .cf-meta>span:not(.cf-meta-tag):hover{
    background:var(--cf-ink-06);border-color:var(--cf-ink-12);
  }
}
.cf-meta :deep(svg){color:var(--cf-text-4);flex-shrink:0}
</style>
