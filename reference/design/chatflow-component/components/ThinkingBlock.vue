<!-- ============================================================
     思考过程 · ChatFlow v1.0
     ------------------------------------------------------------
     显示大模型的思考内容，不分步骤展示。
     ============================================================ -->
<script setup>
import { ref, watch, computed } from 'vue'

const props = defineProps({
  /** [{index, text, state:'running'|'done'}] */
  steps: { type: Array, default: () => [] },
  /** 生成是否结束。结束时自动折叠一次 */
  finished: { type: Boolean, default: false },
})

const collapsed = ref(false)

/* 只在「未结束 → 结束」这一次自动折叠。
   之后用户手动展开不会被再次折叠掉。 */
watch(() => props.finished, (now, before) => {
  if (now && !before) collapsed.value = true
})

// 将所有步骤的文本合并为一段
const thinkingContent = computed(() => {
  return props.steps.map(s => s.text).join('，')
})
</script>

<template>
  <div class="cf-think" :class="{ 'is-collapsed': collapsed }">
    <button
      class="cf-think-hd"
      type="button"
      :aria-expanded="!collapsed"
      @click="collapsed = !collapsed"
    >
      <span class="cf-think-title">{{ finished ? '思考过程' : '正在思考' }}</span>
      <svg class="cf-think-arrow" width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path
          d="M6 4l4 4-4 4" stroke="currentColor" stroke-width="1.5"
          stroke-linecap="round" stroke-linejoin="round"
        />
      </svg>
    </button>

    <div v-show="!collapsed" class="cf-think-content">
      <p>{{ thinkingContent }}</p>
    </div>
  </div>
</template>

<style scoped>
.cf-think{
  padding:16px 0;margin-bottom:8px;
  font-size:var(--cf-fs-sm);color:var(--cf-text-2);
}
/* 折叠后只剩标题一行，清掉容器上下留白 */
.cf-think.is-collapsed{padding:0}

.cf-think-hd{
  display:flex;align-items:center;gap:6px;width:100%;
  text-align:start;line-height:1.6;
  margin-bottom:12px;cursor:pointer;user-select:none;
  background:transparent;border:none;
  padding:0;
}
.cf-think-title{font-weight:400;color:var(--cf-text-2);font-size:15px;line-height:24px}
.cf-think-arrow{
  flex-shrink:0;color:var(--cf-text-3);
  transition:transform .2s ease;transform:rotate(90deg);
}
.cf-think.is-collapsed .cf-think-arrow{transform:rotate(0deg)}

.cf-think-content{
  padding-left:14px;
  border-left:1px solid var(--cf-line);
}

.cf-think-content p{
  line-height:22px;
  color:var(--cf-text-2);
  font-size:var(--cf-fs-sm);
  margin:0;
  padding:2px 0;
}
</style>
