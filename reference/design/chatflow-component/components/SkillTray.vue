<!-- ============================================================
     能力舌头 · ChatFlow v1.0
     ------------------------------------------------------------
     选中技能后贴在输入卡上方，底边塞进卡片顶部背面（负外边距 + 卡片
     的 z-index 更高），看起来像从卡片里抽出来的一片舌头。

     宽度比卡片窄一点（96%），两侧留出台阶，才看得出是「压在下面」
     而不是另一块并列的条。
     ============================================================ -->
<script setup>
import CfIcon from './CfIcon.vue'

defineProps({
  /** SKILLS[key] */
  skill: { type: Object, required: true },
})

const emit = defineEmits(['close'])
</script>

<template>
  <div class="cf-tray" role="status" aria-live="polite">
    <!-- 与原型一致：舌头里只有图标 + 能力名 + 关闭这一枚 chip，
         没有描述文字（那会把舌头撑得比原型高，且原型 capTray.innerHTML 确实只画了这一段） -->
    <span class="cf-tray-chip">
      <span class="cf-tray-tl">
        <CfIcon :name="skill.icon" :size="15" />{{ skill.name }}
      </span>
      <button class="cf-tray-x cf-tap40" type="button" :aria-label="`退出${skill.name}`" @click="emit('close')">
        <CfIcon name="x" :size="10" />
      </button>
    </span>
  </div>
</template>

<style scoped>
/* 负的下外边距把底边塞进卡片背面；下 padding 含被盖住的那 12px，
   所以可见留白上下都是 6px。没有 gap——舌头里只有一枚 chip，不需要 */
.cf-tray{
  position:relative;z-index:0;
  display:flex;align-items:center;flex-wrap:nowrap;
  width:96%;max-width:1128.96px;margin:0 auto -12px;
  padding:6px var(--cf-space-3) 18px;
  border-radius:var(--cf-radius-md) var(--cf-radius-md) 0 0;
  /* 缓慢流动的渐变：区别于卡片的纯白，暗示「这是一种临时的工作模式」。
     取值都落在品牌蓝色阶（--cf-primary 同色系）内深浅流动，
     不用冰蓝/薄荷/暖黄三色混流——那会跟主题蓝色调脱节 */
  background:linear-gradient(135deg,#eaf3fe 0%,#dce9fc 20%,#eef5fd 40%,
    #d7e6fb 60%,#e6f0fd 80%,#eaf3fe 100%);
  background-size:300% 300%;
  animation:cfTrayFlow 8s ease infinite;
}
@keyframes cfTrayFlow{
  0%{background-position:0% 50%}
  50%{background-position:100% 50%}
  100%{background-position:0% 50%}
}
/* 能力 chip：图标 + 能力名 + 关闭 是一整段。
   高度锁 26px 且只留横向内边距，纵向留白交给舌头自身的 padding 控制 */
.cf-tray-chip{
  display:inline-flex;align-items:center;gap:var(--cf-space-3);flex:none;
  height:26px;padding:0 var(--cf-space-2);
  border-radius:var(--cf-radius-pill);
  border:.5px solid rgba(255,255,255,.9);background:rgba(255,255,255,.2);
  transition:background-color var(--cf-transition);
}
@media (hover:hover){
  .cf-tray-chip:hover{background:rgba(255,255,255,.72)}
}
.cf-tray-tl{
  display:inline-flex;align-items:center;gap:6px;flex:none;
  font-size:var(--cf-fs-sm);line-height:20px;
  font-weight:500;color:var(--cf-primary);
}
.cf-tray-tl :deep(svg){color:var(--cf-primary)}
/* 关闭：常态带白色 70% 圆底，hover 加深底色与图标 */
.cf-tray-x{
  width:14px;height:14px;flex:none;border-radius:50%;
  display:grid;place-items:center;
  background:rgba(255,255,255,.7);
  color:var(--cf-text-2);cursor:pointer;transition:var(--cf-transition);
}
@media (hover:hover){
  .cf-tray-x:hover{background:#fff;color:var(--cf-text-1)}
}
.cf-tray-x:active{background:#fff;color:var(--cf-text-1)}

/* ---------- 暗色主题适配 ---------- */
html[data-theme="dark"] .cf-tray{
  /* 舌头渐变：暗色下使用深色基调 + 更强的色彩对比 */
  background:linear-gradient(135deg,
    #1e3a52 0%,
    #2a4a66 20%,
    #1f4159 40%,
    #2b4d6b 60%,
    #204360 80%,
    #1e3a52 100%
  );
  background-size:300% 300%;
}

html[data-theme="dark"] .cf-tray-chip{
  /* Chip 背景和边框在暗色下调整：使用更轻的黑色半透明 */
  border:.5px solid rgba(0,0,0,.15);
  background:rgba(0,0,0,.1);
}

html[data-theme="dark"] .cf-tray-chip:hover{
  background:rgba(0,0,0,.2);
}

html[data-theme="dark"] .cf-tray-x{
  /* 关闭按钮在暗色下调整：使用更轻的黑色半透明 */
  background:rgba(0,0,0,.15);
  color:rgba(255,255,255,.9);
}

html[data-theme="dark"] .cf-tray-x:hover,
html[data-theme="dark"] .cf-tray-x:active{
  background:rgba(0,0,0,.25);
  color:#fff;
}
</style>
