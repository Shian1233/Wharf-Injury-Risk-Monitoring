<template>
  <div class="action-dropdown" ref="rootRef">
    <button
      class="dropdown-trigger"
      type="button"
      :aria-expanded="open"
      aria-haspopup="menu"
      @click.stop="toggle"
    >
      <slot name="trigger">
        <Icon name="more" :size="18" />
      </slot>
    </button>
    <Transition name="dropdown-fade">
      <ul v-if="open" class="dropdown-menu" role="menu">
        <li
          v-for="action in actions"
          :key="action.key"
          class="dropdown-menu__item"
          :class="{ 'is-danger': action.danger }"
          role="menuitem"
          @click.stop="handleSelect(action)"
        >
          <Icon :name="action.icon" :size="20" class="item-icon" />
          <span class="item-text">{{ action.label }}</span>
        </li>
      </ul>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import Icon from './Icon.vue'

const props = defineProps({
  actions: {
    type: Array,
    required: true
    // [{ key, label, icon, danger }]
  }
})

const emit = defineEmits(['select'])

const open = ref(false)
const rootRef = ref(null)

function toggle() {
  open.value = !open.value
}

function close() {
  open.value = false
}

function handleSelect(action) {
  emit('select', action.key)
  close()
}

function handleClickOutside(e) {
  if (rootRef.value && !rootRef.value.contains(e.target)) {
    close()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.action-dropdown {
  position: relative;
  flex-shrink: 0;
}

.dropdown-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2px;
  border-radius: 4px;
  border: none;
  background: transparent;
  color: var(--text-f1);
  cursor: pointer;
  outline: none;
}

.dropdown-trigger:hover {
  background: var(--text-black-4);
}

.dropdown-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 10;
  width: 128px;
  padding: 4px;
  margin: 0;
  list-style: none;
  background: #ffffff;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(18, 21, 26, 0.12);
}

.dropdown-menu__item {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 120px;
  padding: 8px 6px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 400;
  line-height: 20px;
  color: var(--text-f1);
  cursor: pointer;
}

.dropdown-menu__item + .dropdown-menu__item {
  margin-top: 4px;
}

.dropdown-menu__item:hover {
  background: var(--text-black-4);
}

.dropdown-menu__item.is-danger,
.dropdown-menu__item.is-danger .item-icon {
  color: var(--danger);
}

.dropdown-fade-enter-active,
.dropdown-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.dropdown-fade-enter-from,
.dropdown-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
