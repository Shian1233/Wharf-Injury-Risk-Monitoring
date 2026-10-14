<!-- ============================================================
     思考过程（深度思考）· ChatFlow v1.0
     ------------------------------------------------------------
     展示模型深度思考的原文内容（msgState === 'THOUGHTS' 时为思考中）。
     标题可点击折叠/展开思考正文；思考中默认展开，完成后自动折叠。

     自包含版：不依赖接入方 store / 图片资源，图标走 CfIcon，
     思考中的状态用 CSS 动画表现（不用 gif）。
     ============================================================ -->
<script setup>
import { ref, computed, watch } from 'vue'
import CfIcon from './CfIcon.vue'
import thoughtProcessGif from '../assets/images/agent/thought_process.gif'
import thoughtProcessDone from '../assets/images/agent/thought_process.png'

const props = defineProps({
  /** 兼容消息对象：只读 msgState，'THOUGHTS' 表示正在深度思考 */
  msg: { type: Object, default: () => ({}) },
  /** 思考过程的 HTML 内容 */
  thoughtProcess: { type: String, default: '' },
})

const close = ref(true)
const handleArrowDownFn = () => {
  close.value = !close.value
}

// 是否正在深度思考
const isThoughting = computed(() => props.msg?.msgState === 'THOUGHTS')

// 思考中默认展开，完成后自动折叠
watch(() => props.msg?.msgState, () => {
  close.value = props.msg?.msgState !== 'THOUGHTS'
}, { immediate: true })
</script>

<template>
  <div class="thought-process">
    <div class="collapse-wrapper" :class="{ 'is-show': !close }">
      <!-- 标题 -->
      <div class="title" @click="handleArrowDownFn">
        <div class="desc">
          <img :src="isThoughting ? thoughtProcessGif : thoughtProcessDone" class="thought-process-icon" alt="" />
          <span class="think-block-title" :class="{ 'light-text': isThoughting }">
            {{ isThoughting ? '深度思考中' : '已完成思考' }}
          </span>
        </div>
        <CfIcon name="caret-down" :size="12" class="thought-arrow" />
      </div>
      <!-- 思考内容 -->
      <div v-if="thoughtProcess" class="content">
        <div class="line"></div>
        <span class="text" v-html="thoughtProcess"></span>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.thought-process {
  width: 100%;
  overflow: hidden;

  .collapse-wrapper {
    .title {
      width: 130px;
      overflow: hidden;
      user-select: none;
      position: relative;
      cursor: pointer;
      padding: 8px;
      border-radius: 12px;

      display: flex;
      gap: 4px;
      align-items: center;
      justify-content: flex-start;

      .desc {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
        z-index: 10;

        .thought-process-icon {
          width: 20px;
          height: 20px;
          object-fit: contain;
        }

        .think-block-title {
          font-size: 14px;
          color: var(--text-f1, #12151a);
          font-weight: 400;
          line-height: 20px;
          z-index: 10;

          &.light-text {
            animation: text-show .3s linear 0ms 1 both, text-blink 2.4s ease-in infinite;
            background: linear-gradient(90deg, rgba(0, 87, 255, 0), var(--text-f1, #12151a) 50%, rgba(0, 87, 255, 0)) no-repeat 0 0;
            -webkit-background-clip: text;
            background-clip: text;
            background-size: 50% 100%;
            color: var(--border-color-6, rgba(18, 21, 26, 0.6));
            opacity: 0;
            z-index: 10;
          }
        }
      }

      .thought-arrow {
        transition: transform .3s ease-in-out;
        color: var(--text-f7, #6b7280);
      }

      &:hover {
        background: var(--text-black-2, rgba(18, 21, 26, 0.04));
      }
    }

    .content {
      position: relative;
      height: 0;
      opacity: 0;
      overflow: hidden;

      .line {
        position: absolute;
        left: 0;
        top: 0;
        width: 1px;
        height: 100%;
        background: var(--text-black-8, rgba(18, 21, 26, 0.08));
      }

      :deep(.text) {
        flex: 1;
        font-size: 14px;
        font-weight: 400;
        color: var(--text-f7, #6b7280);
        line-height: 24px;

        ul,
        ol {
          padding-left: 2em;
        }
      }
    }

    &.is-show {
      .title {
        .thought-arrow {
          transform: rotate(180deg);
        }
      }

      .content {
        margin-top: 8px;
        padding-left: 10px;
        height: fit-content;
        opacity: 1;
        transition: opacity .5s cubic-bezier(.4, 0, .1, 1);
      }
    }
  }
}

@keyframes text-show {
  0% { opacity: 0; }
  100% { opacity: 1; }
}

@keyframes text-blink {
  0% { background-position: -100% 0; }
  15% { background-position: -100% 0; }
  55% { background-position: 200% 100%; }
  100% { background-position: 200% 100%; }
}
</style>
