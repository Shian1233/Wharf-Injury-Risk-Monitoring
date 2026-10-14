<!-- ============================================================
     返回顶部按钮 · ChatFlow v1.0
     ------------------------------------------------------------
     监听指定容器或 window 的滚动，超过阈值时显示按钮，
     点击平滑滚动到顶部。
     ============================================================ -->
<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import CfIcon from './CfIcon.vue'

const props = defineProps({
  /** 滚动容器选择器，不传则监听 window */
  scrollContainer: { type: String, default: null },
  /** 显示按钮的滚动阈值（px） */
  threshold: { type: Number, default: 200 },
})

const isVisible = ref(false)
let scrollElement = null
let retryTimer = null
let retryCount = 0

// 按钮距离顶部的位置（85%视口高度）
const topPosition = computed(() => `${window.innerHeight * 0.85}px`)

function handleScroll() {
  if (!scrollElement) return

  const scrollTop = scrollElement === window
    ? window.scrollY
    : scrollElement.scrollTop

  isVisible.value = scrollTop > props.threshold
}

function scrollToTop() {
  if (!scrollElement) return

  if (scrollElement === window) {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } else {
    scrollElement.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

function bindScrollEvent() {
  if (scrollElement) {
    scrollElement.addEventListener('scroll', handleScroll)
  }
}

function unbindScrollEvent() {
  if (scrollElement) {
    scrollElement.removeEventListener('scroll', handleScroll)
  }
}

function tryFindScrollContainer() {
  unbindScrollEvent()
  scrollElement = null

  // 1. 指定容器
  if (props.scrollContainer) {
    scrollElement = document.querySelector(props.scrollContainer)
  }

  // 2. 自动检测可滚动容器
  if (!scrollElement) {
    const containers = document.querySelectorAll('[class*="scroll"], [class*="container"]')
    for (const container of containers) {
      const style = window.getComputedStyle(container)
      if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
        scrollElement = container
        break
      }
    }
  }

  // 3. 降级到 window
  if (!scrollElement) {
    scrollElement = window
  }

  // 4. 如果指定了容器但没找到，重试最多 20 次
  if (scrollElement === window && props.scrollContainer && retryCount < 20) {
    retryCount++
    retryTimer = setTimeout(tryFindScrollContainer, 100)
    return
  }

  bindScrollEvent()
}

onMounted(async () => {
  await nextTick()
  retryCount = 0
  tryFindScrollContainer()
})

onUnmounted(() => {
  unbindScrollEvent()
  if (retryTimer) clearTimeout(retryTimer)
})
</script>

<template>
  <div
    v-show="isVisible"
    class="cf-back-top"
    :style="{ top: topPosition }"
    @click="scrollToTop"
    role="button"
    aria-label="返回顶部"
  >
    <CfIcon name="caret-up" :size="20" />
  </div>
</template>

<style scoped>
.cf-back-top {
  position: fixed;
  right: 20px;
  z-index: 1000;
  width: 44px;
  height: 44px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: var(--cf-surface, #ffffff);
  border: 1px solid var(--cf-line);
  border-radius: 50%;
  box-shadow: var(--cf-shadow-card);
  cursor: pointer;
  transition: var(--cf-transition);
  color: var(--cf-text-2);
}

@media (hover: hover) {
  .cf-back-top:hover {
    transform: translateY(-2px);
    box-shadow: var(--cf-shadow-float);
    color: var(--cf-text-1);
  }
}

.cf-back-top:active {
  transform: translateY(0);
}
</style>
