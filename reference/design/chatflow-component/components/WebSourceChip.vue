<!-- ============================================================
     联网资料胶囊 · ChatFlow v1.0
     ------------------------------------------------------------
     开了联网搜索的回答，正文下方挂一枚胶囊：站点头像叠罗汉 +
     「联网搜索到 N 篇资料」+ 右箭头。点击打开参考资料抽屉。
     ============================================================ -->
<script setup>
import { ref } from 'vue'
import CfIcon from './CfIcon.vue'

const props = defineProps({
  /** pickWebSources 的返回值 */
  sources: { type: Array, default: () => [] },
  clickable: { type: Boolean, default: true },
})

const emit = defineEmits(['open'])

/** 头像最多露 5 个，够表达「来源不止一处」 */
const FAV_MAX = 5

/** favicon 取不到图时回落成品牌色 + 简称，跟抽屉里的卡片逻辑一致 */
const logoFailed = ref(new Set())
function onLogoError(i) {
  logoFailed.value = new Set(logoFailed.value).add(i)
}
</script>

<template>
  <div v-if="sources.length" class="cf-web">
    <button
      class="cf-web-chip"
      type="button"
      :disabled="!clickable"
      aria-haspopup="dialog"
      @click="emit('open')"
    >
      <span class="cf-web-favs" aria-hidden="true">
        <span
          v-for="(w, i) in sources.slice(0, FAV_MAX)"
          :key="i"
          class="cf-web-fav"
          :class="{ 'is-brand': !!w.brand && (!w.logo || logoFailed.has(i)) }"
          :style="w.brand && (!w.logo || logoFailed.has(i)) ? { background: w.brand } : null"
        >
          <img v-if="w.logo && !logoFailed.has(i)" :src="w.logo" :alt="w.site" @error="onLogoError(i)" />
          <template v-else-if="w.brand">{{ w.ab }}</template>
          <CfIcon v-else name="link" :size="13" />
        </span>
      </span>
      <span class="cf-web-label">联网搜索到 {{ sources.length }} 篇资料</span>
      <CfIcon v-if="clickable" name="caret-right" :size="16" class="cf-web-go" />
    </button>
  </div>
</template>

<style scoped>
.cf-web{margin-top:var(--cf-space-4)}
.cf-web-chip{
  display:inline-flex;align-items:center;gap:var(--cf-space-3);max-width:100%;
  padding:7px 14px 7px 10px;
  border:1px solid var(--cf-line);border-radius:var(--cf-radius-pill);
  background:var(--cf-surface);cursor:pointer;text-align:left;
  transition:background var(--cf-transition),border-color var(--cf-transition);
}
@media (hover:hover){
  .cf-web-chip:hover:not(:disabled){
    background:var(--cf-fill);border-color:var(--cf-line-strong);
  }
}
.cf-web-chip:active:not(:disabled){background:var(--cf-fill);border-color:var(--cf-line-strong)}
.cf-web-chip:disabled{cursor:default}

/* 头像叠罗汉：负边距压叠，白描边把彼此分开 */
.cf-web-favs{display:inline-flex;align-items:center;flex:none}
.cf-web-fav{
  width:26px;height:26px;border-radius:50%;
  display:grid;place-items:center;
  border:2px solid var(--cf-surface);background:var(--cf-fill);
  color:var(--cf-gray-5);font-size:10px;font-weight:600;overflow:hidden;
}
.cf-web-fav+.cf-web-fav{margin-left:-9px}
/* 有品牌色的站点：底色由内联样式给，文字转白 */
.cf-web-fav.is-brand{color:#fff}
.cf-web-fav>img{width:100%;height:100%;object-fit:cover}
.cf-web-label{
  font-size:var(--cf-fs-sm);color:var(--cf-text-1);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.cf-web-go{flex:none;color:var(--cf-text-4)}
</style>
