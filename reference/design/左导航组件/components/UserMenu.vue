<script setup>
defineProps({
  items: { type: Array, default: () => [] },   // [{ key, label, icon, disabled, divided }]
  open: { type: Boolean, default: false }
})

const emit = defineEmits(['select'])
</script>

<template>
  <!-- 挂在用户区上向上弹：用户行在侧栏底部，只有这一个方向 -->
  <div
    class="user-menu"
    :class="{ 'is-open': open }"
    role="menu"
    aria-label="账号菜单"
    @click.stop
  >
    <template v-for="item in items" :key="item.key">
      <div v-if="item.divided" class="um-sep" role="separator" />
      <button
        class="um-item"
        type="button"
        role="menuitem"
        :disabled="item.disabled"
        @click="emit('select', item)"
      >
        <component :is="item.icon" v-if="item.icon" />
        <span>{{ item.label }}</span>
      </button>
    </template>
  </div>
</template>

<style scoped>
.user-menu {
  position: absolute;
  left: 0;
  bottom: calc(100% + var(--iflyv-spacing-2));
  z-index: 60;
  min-width: 168px;
  padding: var(--iflyv-spacing-2);
  border-radius: var(--iflyv-radius-lg);
  background: var(--app-bg-panel);
  border: 1px solid var(--app-border);
  box-shadow: var(--app-shadow-related);
  opacity: 0;
  visibility: hidden;
  transform: translateY(6px);
  transition: opacity var(--iflyv-duration-normal) var(--iflyv-ease-default),
              transform var(--iflyv-duration-normal) var(--iflyv-ease-default),
              visibility 0s linear var(--iflyv-duration-normal);
}

.user-menu.is-open {
  opacity: 1;
  visibility: visible;
  transform: none;
  transition: opacity var(--iflyv-duration-normal) var(--iflyv-ease-default), transform var(--iflyv-duration-normal) var(--iflyv-ease-default), visibility 0s;
}

.um-item {
  display: flex;
  align-items: center;
  gap: var(--iflyv-spacing-2);
  width: 100%;
  height: 40px;
  padding: 0 var(--iflyv-spacing-3);
  border: 0;
  border-radius: var(--iflyv-radius-sm);
  background: transparent;
  color: var(--app-text-1);
  font: inherit;
  font-size: var(--iflyv-font-size-14);
  font-weight: var(--iflyv-font-weight-regular);
  text-align: left;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background-color var(--iflyv-duration-fast) var(--iflyv-ease-default);
}

.um-item :deep(svg) {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  color: var(--app-text-2);
}

@media (hover: hover) {
  .um-item:not(:disabled):hover { background: var(--app-bg-hover); }
}

.um-item:not(:disabled):active { background: var(--app-bg-hover); }

.um-item:disabled { color: var(--app-text-4); cursor: not-allowed; }

.um-item:disabled :deep(svg) { color: var(--app-text-4); }

.um-sep {
  height: 1px;
  margin: var(--iflyv-spacing-2) var(--iflyv-spacing-1);
  background: var(--app-border);
}
</style>
