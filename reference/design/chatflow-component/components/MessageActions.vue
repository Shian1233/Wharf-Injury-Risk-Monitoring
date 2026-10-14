<!-- ============================================================
     消息操作栏 · ChatFlow v1.0
     ------------------------------------------------------------
     复制 / 重新生成 ｜ 有帮助 / 没帮助 / 举报。
     每一项都可通过 features.actions 单独关掉；全关则整栏不渲染。
     点踩与举报都会打开反馈弹窗，由父级统一处理。
     ============================================================ -->
<script setup>
import { computed } from 'vue'
import CfIcon from './CfIcon.vue'

const props = defineProps({
  /** features.actions */
  actions: { type: Object, default: () => ({}) },
  /** 当前投票态：'' | 'up' | 'down' */
  vote: { type: String, default: '' },
  /** 生成中禁用整栏 */
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['copy', 'regenerate', 'vote', 'report'])

/** 左组（复制/重新生成）与右组（投票/举报）都为空时整栏不画 */
const hasLeft = computed(() => props.actions.copy || props.actions.regenerate)
const hasRight = computed(() => props.actions.vote || props.actions.report)

/* 投票按钮的互斥禁用：点赞后点踩按钮禁用，点踩后点赞按钮禁用，取消后恢复 */
const upDisabled = computed(() => props.disabled || props.vote === 'down')
const downDisabled = computed(() => props.disabled || props.vote === 'up')
</script>

<template>
  <div v-if="hasLeft || hasRight" class="cf-acts">
    <button
      v-if="actions.copy"
      v-vtip="'复制'"
      class="cf-act cf-tap40" type="button" :disabled="disabled"
      aria-label="复制回答" title="复制"
      @click="emit('copy')"
    ><CfIcon name="copy" :size="15" /></button>

    <button
      v-if="actions.regenerate"
      v-vtip="'重新生成'"
      class="cf-act cf-tap40" type="button" :disabled="disabled"
      aria-label="重新生成" title="重新生成"
      @click="emit('regenerate')"
    ><CfIcon name="refresh" :size="15" /></button>

    <span v-if="hasLeft && hasRight" class="cf-act-sep" aria-hidden="true" />

    <template v-if="actions.vote">
      <button
        v-vtip="'有帮助'"
        class="cf-act cf-tap40" :class="{ 'is-up': vote === 'up' }"
        type="button" :disabled="upDisabled"
        :aria-pressed="vote === 'up'" aria-label="有帮助" title="有帮助"
        @click="emit('vote', 'up')"
      ><CfIcon name="up" :size="15" /></button>
      <button
        v-vtip="'没帮助'"
        class="cf-act cf-tap40" :class="{ 'is-down': vote === 'down' }"
        type="button" :disabled="downDisabled"
        :aria-pressed="vote === 'down'" aria-label="没帮助" title="没帮助"
        @click="emit('vote', 'down')"
      ><CfIcon name="down" :size="15" /></button>
    </template>

    <button
      v-if="actions.report"
      v-vtip="'举报'"
      class="cf-act cf-tap40" type="button" :disabled="disabled"
      aria-label="举报" title="举报"
      @click="emit('report')"
    ><CfIcon name="flag" :size="15" /></button>
  </div>
</template>

<style scoped>
.cf-acts{display:flex;align-items:center;gap:var(--cf-space-1);margin-top:var(--cf-space-2)}
.cf-act{
  display:inline-flex;align-items:center;justify-content:center;
  width:28px;height:28px;border-radius:6px;
  color:var(--cf-text-2);cursor:pointer;background:transparent;
  transition:all .15s ease;
}
/* :not() 里带上选中态，否则 hover 的特异性（0,3,0）会压过 .is-up（0,2,0），
   悬停一个已选中的投票按钮会变回中性灰，看着像取消了 */
@media (hover:hover){
  .cf-act:hover:not(:disabled):not(.is-up):not(.is-down){
    background:var(--cf-ink-06);color:var(--cf-text-1);
  }
}
.cf-act:active:not(:disabled){background:var(--cf-ink-10);color:var(--cf-text-1)}
.cf-act:disabled{opacity:.4;cursor:not-allowed}
/* 投票选中态：用语义色的浅底，与 hover 的中性灰区分开 */
.cf-act.is-up{color:var(--cf-success);background:var(--cf-success-soft)}
.cf-act.is-down{color:var(--cf-danger);background:var(--cf-danger-soft)}
.cf-act-sep{
  width:1px;height:14px;background:var(--cf-ink-10);
  margin:0 var(--cf-space-1);
}
</style>
