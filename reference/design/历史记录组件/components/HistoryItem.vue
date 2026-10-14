<template>
  <li
    class="history-item"
    :class="{ pinned: item.pinned, 'batch-mode': batchMode, selected }"
    @click="handleOpen"
  >
    <div class="dialog-item">
      <div v-if="batchMode" class="checkbox-container" @click.stop>
        <input type="checkbox" :checked="selected" @change="emit('toggle-select', item)" />
      </div>
      <div class="content-container">
        <div class="dialog-item-top">
          <div class="dialog-item-title">
            <input
              v-if="editing"
              ref="inputRef"
              v-model="draftTitle"
              class="title-input"
              type="text"
              @click.stop
              @keyup.enter="confirmRename"
              @blur="confirmRename"
              @keyup.esc="cancelRename"
            />
            <span v-else>{{ item.title }}</span>
          </div>
          <ActionDropdown v-if="!batchMode" :actions="actions" @select="handleAction" />
        </div>
        <div v-if="item.preview" class="dialog-item-content">{{ item.preview }}</div>
      </div>
    </div>
  </li>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import ActionDropdown from './ActionDropdown.vue'

const props = defineProps({
  item: {
    type: Object,
    required: true
    // { id, title, preview, createdAt, pinned }
  },
  batchMode: {
    type: Boolean,
    default: false
  },
  selected: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['open', 'topup', 'rename', 'delete', 'toggle-select'])

const editing = ref(false)
const draftTitle = ref('')
const inputRef = ref(null)

const actions = [
  { key: 'topup', label: '置顶', icon: 'topup' },
  { key: 'rename', label: '重命名', icon: 'edit' },
  { key: 'delete', label: '删除', icon: 'delete', danger: true }
]

function handleOpen() {
  if (editing.value) return
  if (props.batchMode) {
    emit('toggle-select', props.item)
  } else {
    emit('open', props.item)
  }
}

function handleAction(key) {
  if (key === 'topup') {
    emit('topup', props.item)
  } else if (key === 'rename') {
    startRename()
  } else if (key === 'delete') {
    emit('delete', props.item)
  }
}

function startRename() {
  draftTitle.value = props.item.title
  editing.value = true
  nextTick(() => inputRef.value?.focus())
}

function confirmRename() {
  if (!editing.value) return
  const next = draftTitle.value.trim()
  editing.value = false
  if (next && next !== props.item.title) {
    emit('rename', props.item, next)
  }
}

function cancelRename() {
  editing.value = false
}
</script>

<style scoped>
.history-item {
  padding: 16px;
  border-radius: var(--history-item-radius);
  background: var(--history-item-bg);
  border: 1px solid #e3e6e7;
  transition: background 0.2s, box-shadow 0.2s, border-color 0.2s;
  cursor: pointer;
  list-style: none;
}

.history-item + .history-item {
  margin-top: 12px;
}

.history-item:hover {
  background: var(--history-item-bg-hover);
  border-color: transparent;
  box-shadow: var(--history-item-shadow-hover);
}

.history-item:hover .action-dropdown {
  visibility: visible;
}

.history-item.batch-mode:hover {
  border-color: #d1d5d8;
  box-shadow: none;
}

.history-item.batch-mode.selected {
  background: var(--text-black-4);
  border-color: var(--primary-p0);
}

.dialog-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.checkbox-container {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.checkbox-container input {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.content-container {
  flex: 1;
  min-width: 0;
}

.dialog-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.dialog-item-title {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  line-height: 28px;
  color: var(--history-title-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dialog-item-content {
  margin-top: 8px;
  font-size: 14px;
  font-weight: 400;
  line-height: 20px;
  color: var(--history-preview-color);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

:deep(.action-dropdown) {
  visibility: hidden;
}

.title-input {
  flex: 1;
  min-width: 0;
  font-size: 16px;
  font-weight: 600;
  line-height: 28px;
  color: var(--history-title-color);
  border: 1px solid var(--primary-p0);
  border-radius: 6px;
  padding: 0 6px;
  outline: none;
  font-family: inherit;
}
</style>
