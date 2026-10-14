<!-- ============================================================
     麦克风授权气泡 · ChatFlow v1.0
     ------------------------------------------------------------
     模拟浏览器的权限申请：贴在视口左上角，仅首次使用语音时出现，
     允许后本次会话内记住，不再重复弹。

     这是原型演示用的仿真件。真实项目里浏览器会自己弹权限框，
     可以通过 features.micPermission:false 关掉这一层。
     ============================================================ -->
<script setup>
import CfIcon from './CfIcon.vue'

defineProps({
  open: { type: Boolean, default: false },
  /** 申请方域名，显示在标题里 */
  origin: { type: String, default: 'cumt.edu.cn' },
})

const emit = defineEmits(['allow', 'deny'])
</script>

<template>
  <div
    class="cf-mic-perm" :class="{ 'is-on': open }"
    role="dialog" aria-modal="false" :aria-hidden="!open"
  >
    <div class="cf-mp-head">
      <CfIcon name="mic" :size="17" />
      <span>{{ origin }} 想要使用您的麦克风</span>
    </div>
    <p class="cf-mp-body">
      用于语音输入：说话内容将实时转写为文字填入输入框，不会上传原始录音。
    </p>
    <div class="cf-mp-act">
      <button class="cf-mp-gh" type="button" @click="emit('deny')">阻止</button>
      <button class="cf-mp-pr" type="button" @click="emit('allow')">允许</button>
    </div>
  </div>
</template>

<style scoped>
/* 固定在视口左上：模仿浏览器权限框的位置，让人一眼认出「这是系统级询问」 */
.cf-mic-perm{
  position:fixed;z-index:95;left:var(--cf-space-6);top:80px;
  width:352px;
  padding:var(--cf-space-4);
  background:#ffffff;
  border:1px solid var(--cf-line);border-radius:var(--cf-radius-md);
  box-shadow:0 18px 44px rgba(5,20,36,.28);
  opacity:0;pointer-events:none;transform:translateY(-8px);
  transition:var(--cf-transition);
}
.cf-mic-perm.is-on{opacity:1;pointer-events:auto;transform:none}
.cf-mp-head{
  display:flex;align-items:center;gap:var(--cf-space-2);
  font-size:var(--cf-fs-sm);font-weight:600;color:var(--cf-text-1);
}
.cf-mp-head :deep(svg){color:var(--cf-primary);flex:none}
.cf-mp-body{
  margin-top:var(--cf-space-2);
  font-size:var(--cf-fs-xs);line-height:18px;color:var(--cf-text-2);
}
.cf-mp-act{
  display:flex;justify-content:flex-end;gap:var(--cf-space-2);
  margin-top:var(--cf-space-3);
}
.cf-mp-act button{
  height:30px;padding:0 var(--cf-space-3);border-radius:var(--cf-radius-sm);
  font-size:var(--cf-fs-sm);cursor:pointer;transition:var(--cf-transition);
}
.cf-mp-gh{color:var(--cf-text-2)}
.cf-mp-pr{background:var(--cf-primary);color:#fff;font-weight:600}
@media (hover:hover){
  .cf-mp-gh:hover{background:var(--cf-page);color:var(--cf-text-1)}
  .cf-mp-pr:hover{background:var(--cf-primary-deep)}
}
</style>
