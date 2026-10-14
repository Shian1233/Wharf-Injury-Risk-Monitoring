<!-- ============================================================
     轻提示 · ChatFlow v1.0
     ------------------------------------------------------------
     单例，居中偏下浮现。用 aria-live 让读屏也能播报。
     ============================================================ -->
<script setup>
import { useToast } from '../composables/useToast.js'

const { message, visible } = useToast()
</script>

<template>
  <!-- Teleport 到 body：与 FeedbackModal 同理，跳出接入方的层叠上下文。
       接入方页面若给组件挂载点的某个祖先加了 transform/filter/position+z-index，
       那个祖先就成了新的层叠上下文，toast 的 z-index 只在它内部有效——
       整个上下文被接入方压在 body 层的弹窗之下时，z-index 写多高都没用
       （接入方 /qa 页面就是这种情况，agentChat 页面的祖先没形成上下文所以正常）。 -->
  <Teleport to="body">
    <div class="cf-toast" :class="{ 'is-on': visible }" role="status" aria-live="polite">
      {{ message }}
    </div>
  </Teleport>
</template>

<style scoped>
.cf-toast{
  position:fixed;
  left:calc(240px + (100% - 240px) / 2);
  bottom:100px;
  /* 10000 > 弹窗遮罩的 9999：两者都 Teleport 到 body，同为 9999 时
     DOM 顺序在后的弹窗会赢，校验提示就被遮罩压住看不见了。 */
  z-index:10000;
  transform:translateX(-50%) translateY(8px);
  max-width:min(420px,86vw);
  padding:10px 18px;
  border-radius:var(--cf-radius-pill);
  background:var(--cf-toast-bg);
  color:#fff;
  font-size:var(--cf-fs-sm);
  line-height:1.5;
  text-align:center;
  box-shadow:var(--cf-shadow-float);
  opacity:0;
  pointer-events:none;
  transition:opacity var(--cf-transition),transform var(--cf-transition);
  backdrop-filter:blur(8px);
  -webkit-backdrop-filter:blur(8px);
  will-change:transform, opacity;
}
.cf-toast.is-on{
  opacity:1;
  transform:translateX(-50%) translateY(0);
}

/* 移动端：没有侧边栏时回到正常居中 */
@media (max-width: 767.98px) {
  .cf-toast {
    left: 50%;
  }
}
</style>
