<template>
  <div class="history-dialog-container">
    <div class="header">
      <div class="header-row">
        <div class="history-title">历史对话</div>
        <ActionDropdown v-if="!batchMode" :actions="headerActions" @select="handleHeaderAction">
          <template #trigger>
            <Icon name="more" :size="18" />
          </template>
        </ActionDropdown>
        <button v-else class="cancel-batch-btn" type="button" @click="exitBatchMode">取消</button>
      </div>
    </div>

    <div class="infinite-list-wrapper hide-scrollbar">
      <ul class="history-list">
        <template v-for="group in groups" :key="group.label">
          <li class="group-title">{{ group.label }}</li>
          <HistoryItem
            v-for="item in group.items"
            :key="item.id"
            :item="item"
            :batch-mode="batchMode"
            :selected="selectedIds.has(item.id)"
            @open="handleOpen"
            @topup="handleTopup"
            @rename="handleRename"
            @delete="handleDelete"
            @toggle-select="toggleSelect"
          />
        </template>
      </ul>

      <div v-if="!groups.length" class="empty-state">暂无历史对话</div>
    </div>

    <div v-if="batchMode" class="batch-action-bar">
      <span class="batch-count">已选 {{ selectedIds.size }} 项</span>
      <button
        class="batch-delete-btn"
        type="button"
        :disabled="!selectedIds.size"
        @click="confirmBatchDelete"
      >
        删除
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import Icon from './Icon.vue'
import ActionDropdown from './ActionDropdown.vue'
import HistoryItem from './HistoryItem.vue'

const props = defineProps({
  items: {
    type: Array,
    required: true
    // [{ id, title, preview, createdAt, pinned }]
  }
})

const emit = defineEmits(['open', 'topup', 'rename', 'delete', 'batch-delete'])

const batchMode = ref(false)
const selectedIds = ref(new Set())

const headerActions = [
  { key: 'batch-delete', label: '批量删除', icon: 'delete', danger: true }
]

function groupLabel(date) {
  const now = new Date()
  const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24))
  if (diffDays < 1) return '今天'
  if (diffDays < 30) return '近30天'
  return '近一年'
}

const groups = computed(() => {
  const pinned = props.items.filter((i) => i.pinned)
  const rest = props.items.filter((i) => !i.pinned)

  const buckets = new Map()
  rest.forEach((item) => {
    const label = groupLabel(new Date(item.createdAt))
    if (!buckets.has(label)) buckets.set(label, [])
    buckets.get(label).push(item)
  })

  const order = ['今天', '近30天', '近一年']
  const result = []
  if (pinned.length) result.push({ label: '置顶', items: pinned })
  order.forEach((label) => {
    if (buckets.has(label)) result.push({ label, items: buckets.get(label) })
  })
  return result
})

function handleHeaderAction(key) {
  if (key === 'batch-delete') {
    batchMode.value = true
    selectedIds.value = new Set()
  }
}

function exitBatchMode() {
  batchMode.value = false
  selectedIds.value = new Set()
}

function toggleSelect(item) {
  const next = new Set(selectedIds.value)
  if (next.has(item.id)) {
    next.delete(item.id)
  } else {
    next.add(item.id)
  }
  selectedIds.value = next
}

function confirmBatchDelete() {
  if (!selectedIds.value.size) return
  emit('batch-delete', Array.from(selectedIds.value))
  exitBatchMode()
}

function handleOpen(item) {
  emit('open', item)
}

function handleTopup(item) {
  emit('topup', item)
}

function handleRename(item, newTitle) {
  emit('rename', item, newTitle)
}

function handleDelete(item) {
  emit('delete', item)
}
</script>

<style scoped>
.history-dialog-container {
  position: relative;
  width: 976px;
  max-width: 976px;
  margin: 0 auto;
  padding: 76px 100px 0;
}

.header {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 0 0 16px;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.history-title {
  font-size: 20px;
  font-weight: 600;
  line-height: 23px;
  color: var(--history-title-color);
}

.infinite-list-wrapper {
  margin-top: 16px;
  overflow: auto;
}

.hide-scrollbar {
  scrollbar-width: none;
}

.hide-scrollbar::-webkit-scrollbar {
  display: none;
}

.history-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.group-title {
  margin: 20px 0 8px;
  font-size: 14px;
  font-weight: 400;
  line-height: 20px;
  color: var(--text-f5);
  list-style: none;
}

.history-list > .group-title:first-child {
  margin-top: 0;
}

.empty-state {
  padding: 64px 0;
  text-align: center;
  font-size: 14px;
  color: var(--text-f7);
}

.cancel-batch-btn {
  padding: 4px 12px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-f5);
  font-size: 14px;
  cursor: pointer;
}

.cancel-batch-btn:hover {
  background: var(--text-black-4);
}

.batch-action-bar {
  position: sticky;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  padding: 12px 0;
  background: var(--history-surface-bg);
}

.batch-count {
  font-size: 14px;
  color: var(--text-f5);
}

.batch-delete-btn {
  padding: 6px 16px;
  border: none;
  border-radius: 8px;
  background: var(--danger);
  color: #ffffff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}

.batch-delete-btn:disabled {
  background: rgba(245, 63, 63, 0.4);
  cursor: not-allowed;
}
</style>
