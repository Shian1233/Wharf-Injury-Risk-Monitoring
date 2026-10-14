<!-- ============================================================
     空态 · ChatFlow v1.0
     ------------------------------------------------------------
     没有消息时显示：智能体头像 + 名称 + 一句介绍 + 推荐问。
     首次挂载时调用 digitalHumanInfo 接口获取动态数据。
     ============================================================ -->
<script setup>
import { computed } from 'vue'
import CfIcon from './CfIcon.vue'
import qaAvatar from '../assets/images/qa-avatar.png'

const props = defineProps({
  /** {name, description, icon} 由 App 层合并 digitalHumanInfo 后下传 */
  agent: { type: Object, default: () => ({}) },
  questions: { type: Array, default: () => [] },
  /** 父级（MessageStream）按 features.questionCards 传入的排布标识。
      当前仅声明以吸收传参、避免落到 $attrs；不改变默认样式（保持原卡片流布局）。 */
  questionsVariant: { type: String, default: 'cards' },
  /** 空态布局模式：'center'(经典上下版) | 'split'(左图右文版) */
  layout: { type: String, default: 'center' },
  /** IP 形象立绘 URL（仅在 layout='split' 时生效，无值时不显示立绘） */
  illustrationUrl: { type: String, default: '' },
})

/* pick: 点推荐问；select-kb: 选中知识库卡片（预留，父级 ChatFlow→composer.selectKb 消费）。
   这两个 emit 都显式声明，避免父级绑定落到 $attrs 变成无效传参。 */
const emit = defineEmits(['pick', 'select-kb'])

/* extra 插槽作用域暴露的代理：接入方卡片点选知识库时调它，
   经 select-kb 事件冒泡到 ChatFlow → composer.selectKb，作用到输入框的知识库选择。 */
function onSelectKbProxy(kb) {
  emit('select-kb', kb)
}

// 纯展示：数据全部来自 props（App 层已合并接口数据）
const displayName = computed(() => props.agent.name || '')
// icon 为 http(s) URL 时当图片用，否则回退到内置头像（图标名如 'qa' 不作图片地址）
const displayIcon = computed(() => {
  const ic = props.agent.icon
  return typeof ic === 'string' && /^https?:\/\//.test(ic) ? ic : qaAvatar
})
const displayDesc = computed(() => props.agent.description || '')
const displayQuestions = computed(() => props.questions || [])

// split 模式：是否显示立绘区域
const showIllustration = computed(() => props.layout === 'split' && !!props.illustrationUrl)
</script>

<template>
  <div class="cf-empty" :class="{ 'cf-empty-split': layout === 'split' }">
    <!-- 经典上下版 (center) -->
    <template v-if="layout === 'center'">
      <!-- 品牌区插槽：接入方可注入自定义 mascot/渐变标题替换默认「头像+名称+描述」。
           不传插槽时渲染下面的默认内容，其它页面行为不变。 -->
      <slot name="brand" :agent="agent">
        <div class="cf-empty-header">
          <span class="cf-empty-ava">
            <img :src="displayIcon" :alt="displayName" />
          </span>
          <h2>{{ displayName }}</h2>
        </div>
        <p v-if="displayDesc">{{ displayDesc }}</p>
      </slot>

      <!-- 输入框插槽 -->
      <div class="cf-empty-input">
        <slot name="input"></slot>
      </div>

      <div v-if="displayQuestions.length" class="cf-empty-qs">
        <button
          v-for="(q, i) in displayQuestions"
          :key="q"
          class="cf-empty-q"
          type="button"
          :style="{ '--cf-spark-i': i % 3 }"
          @click="emit('pick', q)"
        >
          <span class="cf-spark" aria-hidden="true" />
          <span class="cf-empty-q-text">{{ q }}</span>
        </button>
      </div>

      <!-- 附加区插槽：推荐问下方，接入方放知识库卡片等。
           作用域暴露 select-kb：接入方卡片点选即作用到组件库输入框的知识库选择。 -->
      <slot name="extra" :select-kb="onSelectKbProxy"></slot>
    </template>

    <!-- 左图右文版 (split) -->
    <template v-else-if="layout === 'split'">
      <!-- 品牌区插槽：接入方注入自定义 mascot/渐变标题时整块替换（含立绘布局）。
           不传插槽时渲染默认的立绘+名称描述。 -->
      <slot name="brand" :agent="agent">
        <!-- 上半部分：左侧立绘 + 右侧名称描述 -->
        <div v-if="showIllustration" class="cf-empty-top">
          <div class="cf-empty-illustration">
            <img :src="illustrationUrl" :alt="displayName" />
          </div>
          <div class="cf-empty-info">
            <h2>{{ displayName }}</h2>
            <p v-if="displayDesc">{{ displayDesc }}</p>
          </div>
          <!-- SVG 背景装饰 -->
          <div class="cf-empty-top-bg"></div>
        </div>

        <!-- 无立绘时：名称描述左对齐 -->
        <div v-else class="cf-empty-info-standalone">
          <h2>{{ displayName }}</h2>
          <p v-if="displayDesc">{{ displayDesc }}</p>
        </div>
      </slot>

      <!-- 下半部分：输入框（居中） + 推荐问题（左对齐） -->
      <div class="cf-empty-input">
        <slot name="input"></slot>
      </div>

      <div v-if="displayQuestions.length" class="cf-empty-qs cf-empty-qs-left">
        <button
          v-for="(q, i) in displayQuestions"
          :key="q"
          class="cf-empty-q"
          type="button"
          :style="{ '--cf-spark-i': i % 3 }"
          @click="emit('pick', q)"
        >
          <span class="cf-spark" aria-hidden="true" />
          <span class="cf-empty-q-text">{{ q }}</span>
        </button>
      </div>

      <!-- 附加区插槽：推荐问下方，接入方放知识库卡片等 -->
      <slot name="extra" :select-kb="onSelectKbProxy"></slot>
    </template>
  </div>
</template>

<style scoped>
/* ========== 经典上下版 (center) - 原有样式 ========== */
/* 宽度与输入区对齐（含左右内边距），窄屏一起收 */
.cf-empty{
  width:100%;
  max-width:1176px;
  margin:auto;
  padding:var(--cf-space-16) var(--cf-space-6);
  text-align:center;
}
.cf-empty-header{
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--cf-space-3);
  margin-bottom: var(--cf-space-2);
}
.cf-empty-ava{
  width:36px;height:36px;border-radius:10px;
  display:grid;place-items:center;
  background:var(--cf-primary-soft);color:var(--cf-primary);
  flex-shrink: 0;
  overflow: hidden;
}
.cf-empty-ava img{
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.cf-empty h2{font-size:var(--cf-fs-xl);font-weight:600;margin:0}
/* 智能体描述由后端下发，文案里带 \n 分段。HTML 默认会把换行折叠成空格，
   所以这里用 pre-line 让换行生效；选 pre-line 而不是 pre-wrap，是因为
   后端文案常带缩进空格，pre-line 会把多余空白收掉、只保留换行。
   center / split 两种布局的描述 p 都被这条后代选择器覆盖到 */
.cf-empty p{font-size:var(--iflyv-font-size-16);color:var(--cf-text-2);margin-top:var(--cf-space-2);white-space:pre-line}

/* 每条宽度贴合文案本身，不做等分；放不下自动换行，整组居中 */
.cf-empty-qs{
  display:flex;flex-wrap:wrap;justify-content:center;
  gap:var(--cf-space-2);margin-top:var(--cf-space-6);text-align:left;
}
.cf-empty-q{
  max-width:100%;
  display:flex;align-items:center;gap:10px;
  padding:13px var(--cf-space-4);
  background:var(--cf-surface);
  border:1px solid var(--cf-line);border-radius:var(--cf-radius-md);
  font-size:var(--cf-fs-sm);cursor:pointer;
  transition:var(--cf-transition);
}
.cf-empty-q-text{
  flex:1;
  min-width:0;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
@media (hover:hover){
  .cf-empty-q:hover{
    border-color:var(--iflyv-brand-4);color:var(--cf-primary);
    box-shadow:var(--cf-shadow-card);
  }
}
.cf-empty-q:active{border-color:var(--cf-primary);color:var(--cf-primary)}

/* ---------- 星芒图标 ----------
   渐变画不到 stroke 上，所以把图标形状做成 mask，
   底下垫一条 300% 宽的渐变来回扫。渐变首尾同色，往复到两端不跳色。
   每条按 --cf-spark-i 错开延时，不至于整组一起闪。 */
.cf-spark{
  width:17px;height:17px;flex:none;
  --cf-spark-ico:url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%23000" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5 13.9 9 19.5 11 13.9 13 12 18.5 10.1 13 4.5 11 10.1 9z"/><path d="M18.5 4v3M20 5.5h-3"/></svg>');
  -webkit-mask:var(--cf-spark-ico) center/contain no-repeat;
  mask:var(--cf-spark-ico) center/contain no-repeat;
  background-image:linear-gradient(to right,
    var(--cf-spark-1),var(--cf-spark-2),var(--cf-spark-3),var(--cf-spark-2),var(--cf-spark-1));
  background-size:300% 100%;
  animation:cfSpark var(--cf-spark-dur,8s) ease-in-out infinite alternate;
  /* 负延时：一上来就错开，不必等一轮 */
  animation-delay:calc(var(--cf-spark-i,0) * -.4s);
}
@keyframes cfSpark{
  from{background-position:0% 50%}
  to{background-position:100% 50%}
}
/* hover 提速并提亮，呼应卡片自身的 hover 态 */
@media (hover:hover){
  .cf-empty-q:hover .cf-spark{--cf-spark-dur:2.4s}
}

/* 输入框插槽容器 */
.cf-empty-input{
  margin-top: var(--cf-space-8);
  max-width: 1164px;
  margin-left: auto;
  margin-right: auto;
  text-align: left;
}

/* 空状态时隐藏输入框底部工具栏 */
.cf-empty-input :deep(.cf-composer-foot){
  display: none;
}

/* H5 响应式：安全区适配 + 间距调整 */
@media (max-width: 767.98px) {
  .cf-empty{
    padding: var(--cf-space-8) calc(16px + env(safe-area-inset-left, 0px)) var(--cf-space-8) calc(16px + env(safe-area-inset-right, 0px));
  }

  .cf-empty-input :deep(.cf-composer-wrap){
    padding-left: 0;
    padding-right: 0;
  }

  /* H5 下推荐问题卡片宽度自适应 */
  .cf-empty-q {
    min-width: 0;
    flex: 1 1 calc(50% - var(--cf-space-1));
    max-width: calc(50% - var(--cf-space-1));
  }

  /* 320px 窄屏时单列显示 */
  @media (max-width: 375px) {
    .cf-empty-q {
      flex: 1 1 100%;
      max-width: 100%;
    }
  }
}

/* ========== 左图右文版 (split) ========== */
.cf-empty-split {
  text-align: left;
}

/* 上半部分：左侧立绘 + 右侧名称描述 */
.cf-empty-top {
  display: flex;
  gap: 32px;
  margin-bottom: 0;
  align-items: flex-end;
  position: relative;
}

.cf-empty-top-bg {
  position: absolute;
  left: 0;
  right: 0;
  bottom: -116px;
  top: 0;
  background-image: url('../assets/images/info-bg.svg');
  background-size: 100% 100%;
  background-position: left center;
  background-repeat: no-repeat;
  z-index: -1;
  pointer-events: none;
}

.cf-empty-illustration {
  flex: none;
  width: 150px;
  height: 200px;
  border-radius: var(--cf-radius-lg);
  overflow: hidden;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cf-empty-illustration img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cf-empty-info {
  flex: 1;
  min-width: 0;
  padding-bottom: 24px;
}

.cf-empty-info h2 {
  font-size: var(--cf-fs-xl);
  font-weight: 600;
  margin: 0 0 8px 0;
  text-align: left;
  color: var(--cf-primary);
}

.cf-empty-info p {
  font-size: var(--iflyv-font-size-16);
  color: var(--cf-text-2);
  margin: 0;
  text-align: left;
}

/* split 模式下输入框紧贴上方内容 */
.cf-empty-split .cf-empty-input {
  margin-top: 0;
}

/* 无立绘时：名称描述左对齐 */
.cf-empty-info-standalone {
  margin-bottom: 32px;
}

.cf-empty-info-standalone h2 {
  font-size: var(--cf-fs-xl);
  font-weight: 600;
  margin: 0 0 8px 0;
  text-align: left;
}

.cf-empty-info-standalone p {
  font-size: var(--iflyv-font-size-16);
  color: var(--cf-text-2);
  margin: 0;
  text-align: left;
}

/* split 模式：推荐问题左对齐 */
.cf-empty-qs-left {
  justify-content: flex-start;
}

/* H5: split 模式切回单栏，隐藏立绘和背景 */
@media (max-width: 767.98px) {
  .cf-empty-split .cf-empty-illustration {
    display: none;
  }
  .cf-empty-split .cf-empty-top {
    display: block;
  }
  .cf-empty-split .cf-empty-top-bg {
    display: none;
  }
  .cf-empty-split .cf-empty-info {
    padding-top: 0;
    padding-bottom: var(--cf-space-4);
  }

  /* H5 下标题字号适配 */
  .cf-empty-split .cf-empty-info h2,
  .cf-empty-info-standalone h2 {
    font-size: var(--cf-fs-lg);
  }
}
</style>
