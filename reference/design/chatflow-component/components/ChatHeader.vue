<!-- ============================================================
     对话顶部栏 · ChatFlow v1.0
     ------------------------------------------------------------
     从原项目 EasyHeader + AgentInfo 抽出的公共顶部组件。
     纯展示 + 事件驱动：不含 store / router / websocket，
     新建对话、历史记录、返回三个动作只发事件，业务逻辑（清消息、
     路由跳转、暂停 SSE、上传中拦截）全部由接入方在回调里处理。

     两种触发方式：
     1. 事件：@back / @new-chat / @history
     2. ref 方法：triggerBack() / triggerNewChat() / triggerHistory()
        —— 供接入方主动调用（如快捷键），与点击走同一内部函数。

     独立使用：
       <ChatHeader :agent-name="智能体名" :agent-icon="url"
                   @new-chat="..." @history="..." />
     ============================================================ -->
<script setup>
import CfIcon from './CfIcon.vue'
import IconSprite from '../icons/IconSprite.vue'

const props = defineProps({
  /** 智能体标题 */
  agentName: { type: String, default: '' },
  /** 智能体图标 URL */
  agentIcon: { type: String, default: '' },
  /** 是否显示返回按钮 */
  showBack: { type: Boolean, default: false },
  /** 是否显示新建对话按钮 */
  showNewChat: { type: Boolean, default: true },
  /** 是否显示历史记录按钮 */
  showHistory: { type: Boolean, default: true },
  /** 历史面板是否打开（按钮高亮态） */
  historyActive: { type: Boolean, default: false },
  /** 生成中/上传中禁用交互 */
  disabled: { type: Boolean, default: false },
  /** 顶部栏背景色，默认白色。可传任意 CSS background 值（纯色/渐变/图片） */
  background: { type: String, default: '#ffffff' },
})

const emit = defineEmits([
  /** 点击返回 */
  'back',
  /** 点击新建对话 */
  'new-chat',
  /** 点击历史记录 */
  'history',
])

function triggerBack() {
  if (props.disabled) return
  emit('back')
}
function triggerNewChat() {
  if (props.disabled) return
  emit('new-chat')
}
function triggerHistory() {
  if (props.disabled) return
  emit('history')
}

/* 对外方法：供接入方通过 ref 主动触发，与点击同源 */
defineExpose({ triggerBack, triggerNewChat, triggerHistory })
</script>

<template>
  <div class="cf-header" :style="{ background }">
    <!-- 图标雪碧图：确保组件独立可用 -->
    <IconSprite />

    <div class="cf-header-info">
      <!-- 返回按钮（可选） -->
      <button
        v-if="showBack"
        class="cf-header-btn cf-header-back"
        type="button" :disabled="disabled"
        aria-label="返回" @click="triggerBack"
      >
        <CfIcon name="caret-left" :size="16" />
      </button>

      <!-- 新建对话 -->
      <button
        v-if="showNewChat"
        class="cf-header-btn"
        type="button" :disabled="disabled"
        aria-label="新建对话" @click="triggerNewChat"
      >
        <CfIcon name="plus" :size="16" />
      </button>

      <!-- 历史记录 -->
      <button
        v-if="showHistory"
        class="cf-header-btn" :class="{ 'is-active': historyActive }"
        type="button" :disabled="disabled"
        aria-label="历史记录" :aria-pressed="historyActive" @click="triggerHistory"
      >
        <CfIcon name="clock" :size="16" />
      </button>

      <!-- 左侧按钮组扩展点：历史记录之后、智能体图标之前。
           作用域给 disabled，接入方按钮可跟随顶部栏禁用态；不订阅则不出现。 -->
      <slot name="header-actions" :disabled="disabled" />

      <!-- 智能体图标 -->
      <span v-if="agentIcon" class="cf-header-icon">
        <img :src="agentIcon" alt="" />
      </span>

      <!-- 短竖线分隔符 -->
      <span v-if="agentName" class="bar-div"></span>

      <!-- 智能体标题 -->
      <span v-if="agentName" class="cf-header-title">{{ agentName }}</span>
    </div>

    <!-- 顶部栏最右扩展点：新增右容器 margin-left:auto 推到最右。
         不订阅则整个容器被 v-if 守卫、DOM 不生成，顶部栏视觉与原来完全一致。 -->
    <div v-if="$slots['header-right']" class="cf-header-right">
      <slot name="header-right" :disabled="disabled" />
    </div>
  </div>
</template>

<style scoped>
/* 容器：白底、下方 16px 圆角，对齐原项目 EasyHeader */
.cf-header{
  display:flex;align-items:center;justify-content:flex-start;
  flex:none;width:100%;
  padding:16px 24px;
  /* 背景由 background prop 通过内联 style 注入，默认白色 */
  /* border-radius:0 0 var(--cf-radius-lg) var(--cf-radius-lg); */
  box-shadow:inset 0 -1px 0 0 #ffffff;
  border-bottom:1px solid var(--border-color-1, #e3e6e7);
}
.cf-header-info{
  display:flex;align-items:center;justify-content:flex-start;
  gap:14px;min-width:0;
}

/* 右侧扩展容器：margin-left:auto 吃掉中间空白把它推到最右；
   仅在订阅 header-right 时渲染，未用时不占位、不影响原布局 */
.cf-header-right{
  display:flex;align-items:center;gap:14px;flex:none;
  margin-left:auto;
}

/* 圆形图标按钮：32px，无边框，hover 淡灰底 */
.cf-header-btn{
  display:inline-flex;align-items:center;justify-content:center;flex:none;
  width:32px;height:32px;padding:0;
  border:none;border-radius:50%;
  background:transparent;
  color:#4B535C; /* 直接使用颜色值代替 var(--cf-text-2) */
  cursor:pointer;transition:var(--cf-transition);
}
@media (hover:hover){
  .cf-header-btn:hover:not(:disabled){background:var(--cf-ink-04)}
}
.cf-header-btn:disabled{opacity:.45;cursor:not-allowed}
.cf-header-btn.is-active{color:var(--cf-primary);background:var(--cf-primary-soft)}

/* 返回按钮：caret-left 已是朝左箭头，无需旋转 */
.cf-header-back{color:var(--cf-text-2)}

.cf-header-icon{
  width:28px;height:28px;flex:none;border-radius:50%;overflow:hidden;
}
.cf-header-icon img{width:100%;height:100%;object-fit:cover;display:block}

.bar-div{
  width:1px;height:20px;flex:none;
  background:var(--border-color-1);
}

.cf-header-title{
  min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  font-size:var(--cf-fs-base);font-weight:600;line-height:24px;
  color:var(--cf-text-1);
}
</style>
