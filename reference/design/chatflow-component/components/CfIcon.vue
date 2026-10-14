<!-- ============================================================
     图标 · ChatFlow v1.0
     ------------------------------------------------------------
     统一入口，避免每处都写 <svg><use href="#cf-i-x"/></svg>。
     颜色跟随 currentColor，尺寸默认 16，按需传 size。
     ============================================================ -->
<script setup>
defineProps({
  /** 图标名，不含 cf-i- 前缀。见 icons/IconSprite.vue */
  name: { type: String, required: true },
  /** 边长（px）。非等宽等高的场景分别传 width/height */
  size: { type: [Number, String], default: 16 },
})
</script>

<template>
  <svg :width="size" :height="size" aria-hidden="true" focusable="false">
    <use :href="`#cf-i-${name}`" />
  </svg>
</template>
