<!-- ============================================================
     推荐追问 · ChatFlow v1.0
     ------------------------------------------------------------
     挂在操作栏之后、已出了回答体。
     不需要标题行与分隔线——操作栏本身就是视觉断点，位置已能自明语义，
     只留一段上边距把它和图标行拉开。aria-label 补上读屏所需的分组说明。
     ============================================================ -->
<script setup>
import CfIcon from './CfIcon.vue'

defineProps({
  items: { type: Array, default: () => [] },
  /** 生成中禁止追问，否则会打断当前回答 */
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['pick'])
</script>

<template>
  <div v-if="items.length" class="cf-follow" role="group" aria-label="推荐追问">
    <div class="cf-follow-list">
      <button
        v-for="q in items"
        :key="q"
        class="cf-follow-item"
        type="button"
        :disabled="disabled"
        @click="emit('pick', q)"
      >
        <span>{{ q }}</span>
        <CfIcon name="caret-right" :size="14" class="cf-follow-go" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.cf-follow{margin-top:14px}
/* 一行一条：追问是完整句子，横向排会被迫截断。
   宽度由文字撑开（align-items:flex-start + max-width 兜底），不铺满整行 */
.cf-follow-list{
  display:flex;flex-direction:column;align-items:flex-start;
  gap:var(--cf-space-2);
}
.cf-follow-item{
  display:inline-flex;align-items:center;gap:10px;
  max-width:100%;text-align:left;
  padding:9px var(--cf-space-3);
  border:none;background:var(--cf-ink-04);
  border-radius:var(--cf-radius-sm);cursor:pointer;
  font-size:var(--cf-fs-sm);line-height:22px;color:var(--cf-text-2);
  font-family:inherit;transition:var(--cf-transition);
}
@media (hover:hover){
  .cf-follow-item:hover:not(:disabled){
    background:var(--cf-primary-soft);color:var(--cf-primary);
  }
}
.cf-follow-item:active:not(:disabled){background:var(--cf-primary-soft);color:var(--cf-primary)}
.cf-follow-item:disabled{opacity:.55;cursor:not-allowed}
.cf-follow-item>span{min-width:0}

/* 尾部箭头：常态宽度归零（不占位、气泡按文字收紧），hover 才展开滑入。
   margin-left 承担 gap 的活——gap 是容器属性，无法只对单个子项做动画。 */
.cf-follow-go{
  height:14px;flex:none;color:var(--cf-text-3);
  width:0;opacity:0;margin-left:-10px;transform:translateX(-4px);
  overflow:hidden;
  transition:width var(--cf-transition),opacity var(--cf-transition),
    margin-left var(--cf-transition),transform var(--cf-transition),
    color var(--cf-transition);
}
@media (hover:hover){
  .cf-follow-item:hover:not(:disabled) .cf-follow-go{
    width:14px;opacity:1;margin-left:0;transform:none;color:var(--cf-primary);
  }
}
.cf-follow-item:active:not(:disabled) .cf-follow-go{
  width:14px;opacity:1;margin-left:0;transform:none;color:var(--cf-primary);
}
</style>
