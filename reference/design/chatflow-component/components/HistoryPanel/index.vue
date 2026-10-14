<template>
  <div :class="['history-panel', containerClass]" :style="{ background }">
    <!-- 图标雪碧图：HistoryPanel 单独引入时（不经 ChatFlow/ChatHeader）也能渲染 #cf-i-* 图标。
         多处挂载时 id 重复无妨，<use> 取首个匹配的 symbol。 -->
    <IconSprite />

    <!-- 头部筛选区 -->
    <div class="header">
      <!-- 搜索输入框 -->
      <el-input
        v-model="searchQuery"
        placeholder="搜索历史对话"
        clearable
        class="search-input"
        @input="handleSearchInput"
        @clear="handleClearSearch"
        style="width: 248px"
      >
        <template #prefix>
          <CfIcon name="search" :size="16" />
        </template>
      </el-input>

      <!-- 右侧控制按钮组 -->
      <div class="control-icons">
        <!-- 时间筛选 -->
        <el-popover
          v-if="enableTimeFilter"
          :visible="timeFilterVisible"
          placement="bottom-end"
          @update:visible="handleTimeFilterVisibleChange"
          :width="320"
          trigger="click"
          popper-class="time-filter-popover"
        >
          <template #reference>
            <div class="time-filter-icon" :class="{ active: timeFilterType !== 'all' }">
              <CfIcon name="filter" :size="16" />
            </div>
          </template>
          <div class="time-filter-content">
            <div class="filter-title">时间筛选</div>
            <div class="filter-options">
              <div
                v-for="option in timeFilterOptions"
                :key="option.value"
                class="filter-option"
                :class="{ active: timeFilterType === option.value }"
                @click="handleTimeFilterSelect(option.value)"
              >
                <span>{{ option.label }}</span>
                <!-- 选中对勾走 svg 而非 CSS content:'✓'，见下方 .filter-check 注释 -->
                <CfIcon
                  v-if="timeFilterType === option.value"
                  class="filter-check" name="check" :size="16"
                />
              </div>
            </div>
            <!-- 自定义时间段 -->
            <div v-if="timeFilterType === 'custom'" class="custom-date-range">
              <!-- el-config-provider 只渲染 slot（内部用 renderSlot），不产生额外
                   DOM，所以下面的样式嵌套照旧。locale 走 provide/inject，而 inject
                   顺组件树不顺 DOM 树，因此面板 teleport 到 body 也能拿到。 -->
              <el-config-provider :locale="zhCn">
                <el-date-picker
                  v-model="customDateRange"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  format="YYYY-MM-DD"
                  value-format="YYYY-MM-DD"
                  popper-class="history-date-panel"
                  @change="handleCustomDateChange"
                  @visible-change="handleDatePickerVisibleChange"
                />
              </el-config-provider>
            </div>
          </div>
        </el-popover>

        <!-- 批量操作下拉 -->
        <el-dropdown
          v-if="enableBatchDelete"
          placement="bottom-end"
          popper-class="history-action-dropdown-menu"
          @command="handleDropdownCommand"
        >
          <div class="batch-action-icon">
            <CfIcon name="more-h" :size="16" />
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="delete" class="delete-item-text">批量删除</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 列表区域 -->
    <div ref="listWrapperRef" class="infinite-list-wrapper" @scroll="handleScroll">
      <ul v-if="groupedHistory" class="history-list">
        <!-- 置顶会话 -->
        <template v-if="groupedHistory.pinned && groupedHistory.pinned.length > 0">
          <li class="group-title">置顶会话</li>
          <HistoryItem
            :list="groupedHistory.pinned"
            type="pinned"
            :selected-items="selectedItems"
            :batch-delete-mode="batchDeleteMode"
            :enable-pin="enablePin"
            :enable-rename="enableRename"
            @toggle-select-item="toggleSelectItem"
            @handle-session-click="handleSessionClick"
            @pin="handlePinClick"
            @rename="handleRenameClick"
            @delete="handleDeleteClick"
          />
        </template>

        <!-- 今天 -->
        <template v-if="groupedHistory.today && groupedHistory.today.length > 0">
          <li class="group-title">今天</li>
          <HistoryItem
            :list="groupedHistory.today"
            type="today"
            :selected-items="selectedItems"
            :batch-delete-mode="batchDeleteMode"
            :enable-pin="enablePin"
            :enable-rename="enableRename"
            @toggle-select-item="toggleSelectItem"
            @handle-session-click="handleSessionClick"
            @pin="handlePinClick"
            @rename="handleRenameClick"
            @delete="handleDeleteClick"
          />
        </template>

        <!-- 近7天 -->
        <template v-if="groupedHistory.sevenDays && groupedHistory.sevenDays.length > 0">
          <li class="group-title">近7天</li>
          <HistoryItem
            :list="groupedHistory.sevenDays"
            type="sevenDays"
            :selected-items="selectedItems"
            :batch-delete-mode="batchDeleteMode"
            :enable-pin="enablePin"
            :enable-rename="enableRename"
            @toggle-select-item="toggleSelectItem"
            @handle-session-click="handleSessionClick"
            @pin="handlePinClick"
            @rename="handleRenameClick"
            @delete="handleDeleteClick"
          />
        </template>

        <!-- 近30天 -->
        <template v-if="groupedHistory.thirtyDays && groupedHistory.thirtyDays.length > 0">
          <li class="group-title">近30天</li>
          <HistoryItem
            :list="groupedHistory.thirtyDays"
            type="thirtyDays"
            :selected-items="selectedItems"
            :batch-delete-mode="batchDeleteMode"
            :enable-pin="enablePin"
            :enable-rename="enableRename"
            @toggle-select-item="toggleSelectItem"
            @handle-session-click="handleSessionClick"
            @pin="handlePinClick"
            @rename="handleRenameClick"
            @delete="handleDeleteClick"
          />
        </template>

        <!-- 近一年 -->
        <template v-if="groupedHistory.year && groupedHistory.year.length > 0">
          <li class="group-title">近一年</li>
          <HistoryItem
            :list="groupedHistory.year"
            type="year"
            :selected-items="selectedItems"
            :batch-delete-mode="batchDeleteMode"
            :enable-pin="enablePin"
            :enable-rename="enableRename"
            @toggle-select-item="toggleSelectItem"
            @handle-session-click="handleSessionClick"
            @pin="handlePinClick"
            @rename="handleRenameClick"
            @delete="handleDeleteClick"
          />
        </template>

        <!-- 更多 -->
        <template v-if="groupedHistory.more && groupedHistory.more.length > 0">
          <li class="group-title">更多</li>
          <HistoryItem
            :list="groupedHistory.more"
            type="more"
            :selected-items="selectedItems"
            :batch-delete-mode="batchDeleteMode"
            :enable-pin="enablePin"
            :enable-rename="enableRename"
            @toggle-select-item="toggleSelectItem"
            @handle-session-click="handleSessionClick"
            @pin="handlePinClick"
            @rename="handleRenameClick"
            @delete="handleDeleteClick"
          />
        </template>
      </ul>

      <!-- 加载更多提示 -->
      <div v-if="loading" class="loading-wrapper">
        <div class="loading-spinner"></div>
        <span>加载更多...</span>
      </div>

      <!-- 空状态 -->
      <div
        v-if="historyData.totalCount === 0 && !loading"
        class="no-more"
      >
        <CfIcon name="empty" :size="80" />
        <div>暂时还没有历史对话~</div>
      </div>

      <!-- 没有更多：仅在翻过页（currentPage > 1）后到底时提示，第一页不显示 -->
      <div
        v-if="
          historyData.totalCount > 0 &&
          !loading &&
          historyData.currentPage > 1 &&
          historyData.currentPage >= historyData.totalPage
        "
        class="no-more-text"
      >
        没有更多了
      </div>
    </div>

    <!-- 批量操作栏 - 相对于历史记录容器居中 -->
    <div v-if="batchDeleteMode" class="batch-operation-bar">
      <el-checkbox
        :model-value="allSelected"
        @change="toggleSelectAll"
      >
        全选
      </el-checkbox>
      <div class="selected-count">已选 {{ selectedItems.length }} 个对话</div>
      <div class="batch-delete-btn" @click="handleConfirmBatchDelete">删除</div>
      <div class="close-btn" @click="exitBatchDeleteMode">关闭</div>
    </div>

    <!-- 返回顶部 -->
    <BackToTop :scroll-container="scrollContainer" :threshold="100" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox, ElConfigProvider } from 'element-plus'
/* 日期面板的月份/星期文案走 element-plus 官方中文包。
   注意：external 里的 'element-plus' 是字符串精确匹配，只拦裸说明符，
   这个子路径会被打进产物 —— 它是 4.9KB 的纯数据对象，可以接受，
   换来的是不用自己抄一份 locale（抄了会和 EP 版本脱节）。
   之所以不挂全局：window.ElementPlus（EP 的 UMD 全量包）不导出 zhCn，
   539 个键里没有，只有 buildLocaleContext / useLocale 这些工具。 */
import zhCn from 'element-plus/es/locale/lang/zh-cn.mjs'
import BackToTop from '../BackToTop.vue'
import HistoryItem from './HistoryItem.vue'
import CfIcon from '../CfIcon.vue'
import IconSprite from '../../icons/IconSprite.vue'

interface HistoryItem {
  sessionId: string
  title: string
  answer: string
  createTime: string | number
  updateTime: string | number
  topFlag: number  // 1=未置顶, 2=已置顶
  isPinned: boolean
  dayNum: number  // 0=今天, 1-6=近7天, 7-29=近30天, 30-364=近一年, 365+=更多
}

interface GroupedHistory {
  pinned: HistoryItem[]
  today: HistoryItem[]
  sevenDays: HistoryItem[]
  thirtyDays: HistoryItem[]
  year: HistoryItem[]
  more: HistoryItem[]
}

interface HistoryData {
  list: HistoryItem[]
  totalCount: number
  totalPage: number
  currentPage: number
}

interface Props {
  // 数据注入（父组件请求后传入）
  historyData: HistoryData
  loading?: boolean

  // 功能开关
  enableSearch?: boolean
  enableTimeFilter?: boolean
  enableBatchDelete?: boolean
  enablePin?: boolean
  enableRename?: boolean

  // 外部状态
  isGenerating: boolean
  isUploading: boolean

  // 样式定制
  containerClass?: string
  scrollContainer?: string
  background?: string
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  enableSearch: true,
  enableTimeFilter: true,
  enableBatchDelete: true,
  enablePin: true,
  enableRename: true,
  containerClass: '',
  scrollContainer: '.infinite-list-wrapper',
  background: '#f4f7f9'
})

interface Emits {
  (e: 'load-data', params: {
    page: number
    pageSize: number
    searchQuery?: string
    timeFlag?: 1 | 2
    startTime?: string
    endTime?: string
  }): void
  (e: 'load-more'): void
  (e: 'delete', sessionIds: string[]): void
  (e: 'pin', payload: { sessionId: string; currentTopFlag: number }): void
  (e: 'rename', payload: { sessionId: string; oldTitle: string; newTitle: string }): void
  (e: 'session-click', payload: { sessionId: string; item: HistoryItem }): void
  (e: 'search-change', searchQuery: string): void
  (e: 'time-filter-change', filter: {
    type: 'all' | '7d' | '30d' | 'custom'
    startTime?: string
    endTime?: string
  }): void
}

const emit = defineEmits<Emits>()

// ==================== 搜索和筛选状态 ====================
const searchQuery = ref('')
const timeFilterVisible = ref(false)
const timeFilterType = ref<'all' | '7d' | '30d' | 'custom'>('all')
const customDateRange = ref<[string, string] | null>(null)

const timeFilterOptions = [
  { label: '全部', value: 'all' },
  { label: '近7天', value: '7d' },
  { label: '近30天', value: '30d' },
  { label: '自定义时间段', value: 'custom' }
]

// ==================== 批量操作状态 ====================
const batchDeleteMode = ref(false)
const selectedItems = ref<string[]>([])

const allSelected = computed(() => {
  if (!props.historyData?.list || props.historyData.list.length === 0) {
    return false
  }
  return selectedItems.value.length === props.historyData.list.length
})

// ==================== 分组数据 ====================
const groupedHistory = computed<GroupedHistory>(() => {
  const groups: GroupedHistory = {
    pinned: [],
    today: [],
    sevenDays: [],
    thirtyDays: [],
    year: [],
    more: []
  }

  if (!props.historyData?.list) {
    return groups
  }

  props.historyData.list.forEach(item => {
    // 处理置顶
    if (item.topFlag === 2) {
      groups.pinned.push({ ...item, isPinned: true })
      return
    }

    // 按 dayNum 分组
    if (item.dayNum === 0) {
      groups.today.push(item)
    } else if (item.dayNum >= 1 && item.dayNum <= 6) {
      groups.sevenDays.push(item)
    } else if (item.dayNum >= 7 && item.dayNum <= 29) {
      groups.thirtyDays.push(item)
    } else if (item.dayNum >= 30 && item.dayNum <= 364) {
      groups.year.push(item)
    } else {
      groups.more.push(item)
    }
  })

  return groups
})

// ==================== 搜索处理 ====================
const handleSearchInput = () => {
  emit('search-change', searchQuery.value)
  emit('load-data', {
    page: 1,
    pageSize: 20,
    searchQuery: searchQuery.value,
    timeFlag: timeFilterType.value === '7d' ? 1 : timeFilterType.value === '30d' ? 2 : undefined,
    startTime: timeFilterType.value === 'custom' ? customDateRange.value?.[0] : undefined,
    endTime: timeFilterType.value === 'custom' ? customDateRange.value?.[1] : undefined
  })
}

const handleClearSearch = () => {
  searchQuery.value = ''
  emit('search-change', '')
  emit('load-data', {
    page: 1,
    pageSize: 20,
    timeFlag: timeFilterType.value === '7d' ? 1 : timeFilterType.value === '30d' ? 2 : undefined,
    startTime: timeFilterType.value === 'custom' ? customDateRange.value?.[0] : undefined,
    endTime: timeFilterType.value === 'custom' ? customDateRange.value?.[1] : undefined
  })
}

// ==================== 时间筛选处理 ====================
const handleTimeFilterSelect = (type: 'all' | '7d' | '30d' | 'custom') => {
  timeFilterType.value = type

  if (type === 'custom') {
    // 等待用户选择日期
    return
  }

  // 非自定义时间段，立即触发筛选
  customDateRange.value = null
  timeFilterVisible.value = false

  const filter: any = { type }
  if (type === '7d') {
    filter.timeFlag = 1
  } else if (type === '30d') {
    filter.timeFlag = 2
  }

  emit('time-filter-change', filter)
  emit('load-data', {
    page: 1,
    pageSize: 20,
    searchQuery: searchQuery.value,
    timeFlag: filter.timeFlag,
    startTime: undefined,
    endTime: undefined
  })
}

/**
 * 日历面板开合状态。
 *
 * 面板是 teleport 到 body 的（不能改成 :teleported="false"，那样它会变成
 * popover 内部一个 646px 宽的绝对定位层，被 320px 的 popover 裁掉），
 * 所以不在 el-popover 的 DOM 子树里 —— popover 的 click-outside 判定
 * 把「点日历里的某一天」当成点了外面，于是点第一个日期就把整个弹窗关了。
 *
 * 这里记面板开没开，开着就拦掉 popover 的关闭请求，等用户选完整个区间
 * 由 handleCustomDateChange 主动关。
 */
const datePanelOpen = ref(false)
// 面板开着时收到过关闭请求：等面板关了再补上，避免「要点两次外面才能关」
const pendingPopoverClose = ref(false)

const handleDatePickerVisibleChange = (visible: boolean) => {
  datePanelOpen.value = visible
  if (!visible && pendingPopoverClose.value) {
    pendingPopoverClose.value = false
    timeFilterVisible.value = false
  }
}

/**
 * popover 的关闭请求拦一道。用 :visible + @update:visible 代替 v-model:visible，
 * 就能在日历面板开着的时候把 false 吃掉。
 */
const handleTimeFilterVisibleChange = (visible: boolean) => {
  if (!visible && datePanelOpen.value) {
    // 记下意图：真的点在外面时，面板关闭后会走 handleDatePickerVisibleChange 补关
    pendingPopoverClose.value = true
    return
  }
  pendingPopoverClose.value = false
  timeFilterVisible.value = visible
}

const handleCustomDateChange = () => {
  if (!customDateRange.value) {
    return
  }

  // 整个区间选完了才关；单个日期不会走到这（daterange 的 change 要两个日期都有才 emit）
  datePanelOpen.value = false
  pendingPopoverClose.value = false
  timeFilterVisible.value = false

  emit('time-filter-change', {
    type: 'custom',
    startTime: customDateRange.value[0],
    endTime: customDateRange.value[1]
  })

  emit('load-data', {
    page: 1,
    pageSize: 20,
    searchQuery: searchQuery.value,
    startTime: customDateRange.value[0],
    endTime: customDateRange.value[1]
  })
}

// ==================== 批量操作处理 ====================
const handleDropdownCommand = (command: string) => {
  if (command === 'delete') {
    batchDeleteMode.value = true
    selectedItems.value = []
  }
}

const exitBatchDeleteMode = () => {
  batchDeleteMode.value = false
  selectedItems.value = []
}

const toggleSelectItem = (sessionId: string) => {
  const index = selectedItems.value.indexOf(sessionId)
  if (index > -1) {
    selectedItems.value.splice(index, 1)
  } else {
    selectedItems.value.push(sessionId)
  }
}

const toggleSelectAll = (checked: boolean) => {
  if (checked) {
    selectedItems.value = props.historyData.list.map(item => item.sessionId)
  } else {
    selectedItems.value = []
  }
}

const handleConfirmBatchDelete = () => {
  if (selectedItems.value.length === 0) {
    ElMessage.warning('请至少选择一个对话')
    return
  }

  ElMessageBox.confirm(
    `确认删除 ${selectedItems.value.length} 个对话？删除后，聊天记录不可恢复`,
    '批量删除',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
      // 同 HistoryItem：间距由库内 .cf-message-box 样式兜底，防接入方清零 EP 相邻按钮 margin
      customClass: 'cf-message-box'
    }
  ).then(() => {
    emit('delete', [...selectedItems.value])
    exitBatchDeleteMode()
  }).catch(() => {
    // 用户取消删除，不做任何操作
  })
}

// ==================== 会话操作处理 ====================
const handleSessionClick = (item: HistoryItem) => {
  // 批量模式下不触发跳转
  if (batchDeleteMode.value) {
    return
  }

  // 前置校验
  if (props.isUploading) {
    ElMessage.warning('文件正在上传中，请稍后...')
    return
  }

  if (props.isGenerating) {
    ElMessage.warning('检测到对话正在生成中，请等待生成结束')
    return
  }

  // 触发跳转事件
  emit('session-click', { sessionId: item.sessionId, item })
}

const handlePinClick = (payload: { sessionId: string; currentTopFlag: number }) => {
  emit('pin', payload)
}

const handleRenameClick = (payload: { sessionId: string; oldTitle: string; newTitle: string }) => {
  emit('rename', payload)
}

const handleDeleteClick = (sessionIds: string[]) => {
  emit('delete', sessionIds)
}

// ==================== 分页加载 ====================
const loadMoreDisabled = computed(() => {
  // 正在加载时禁用
  if (props.loading) {
    return true
  }

  // 没有数据时禁用
  if (!props.historyData || !props.historyData.list) {
    return true
  }

  const { list, totalCount, currentPage, totalPage } = props.historyData

  // 还没有任何数据时不禁用（允许首次加载）
  if (totalCount === 0 && list.length === 0) {
    return false
  }

  // 优先用分页信息判断：还没到最后一页就允许继续加载。
  // useHistory 用 totalPage 表达"还有没有下一页"（满页=currentPage+1，不满页=currentPage），
  // 而它把 totalCount 设成已加载条数本身、无法用于 count 对比，所以这里以页码为准。
  if (totalPage && currentPage) {
    return currentPage >= totalPage
  }

  // 没有分页信息时回退到 count 对比（接入方自带真实 totalCount 的场景）
  return list.length >= totalCount
})

const handleLoadMore = () => {
  if (loadMoreDisabled.value) {
    return
  }
  emit('load-more')
}

// ==================== 滚动分页 ====================
const listWrapperRef = ref<HTMLElement | null>(null)
let isLoadingMore = false

const handleScroll = () => {
  if (!listWrapperRef.value || loadMoreDisabled.value || isLoadingMore) {
    return
  }

  const { scrollTop, scrollHeight, clientHeight } = listWrapperRef.value
  const threshold = 100 // 距离底部 100px 时触发加载

  if (scrollTop + clientHeight >= scrollHeight - threshold) {
    isLoadingMore = true
    handleLoadMore()
    // 200ms 防抖，避免快速滚动时多次触发
    setTimeout(() => {
      isLoadingMore = false
    }, 200)
  }
}

// ==================== 暴露方法 ====================
const navigateToSession = (sessionId: string, item: HistoryItem) => {
  // 前置校验
  if (props.isUploading) {
    ElMessage.warning('文件正在上传中，请稍后...')
    return false
  }

  if (props.isGenerating) {
    ElMessage.warning('检测到对话正在生成中，请等待生成结束')
    return false
  }

  // 触发事件
  emit('session-click', { sessionId, item })
  return true
}

const refresh = () => {
  searchQuery.value = ''
  timeFilterType.value = 'all'
  customDateRange.value = null
  selectedItems.value = []
  batchDeleteMode.value = false

  emit('load-data', {
    page: 1,
    pageSize: 20
  })
}

const clearSearch = () => {
  searchQuery.value = ''
  emit('search-change', '')
  emit('load-data', {
    page: 1,
    pageSize: 20,
    timeFlag: timeFilterType.value === '7d' ? 1 : timeFilterType.value === '30d' ? 2 : undefined,
    startTime: timeFilterType.value === 'custom' ? customDateRange.value?.[0] : undefined,
    endTime: timeFilterType.value === 'custom' ? customDateRange.value?.[1] : undefined
  })
}

const resetFilters = () => {
  timeFilterType.value = 'all'
  customDateRange.value = null
  emit('time-filter-change', { type: 'all' })
  emit('load-data', {
    page: 1,
    pageSize: 20,
    searchQuery: searchQuery.value
  })
}

// ==================== 生命周期 ====================
// onMounted 不自动加载，由父组件控制加载时机（避免双调用）

defineExpose({
  navigateToSession,
  refresh,
  clearSearch,
  resetFilters
})
</script>

<style scoped lang="scss">
$primary-color: #409EFF;
$text-color: #333;
$text-secondary: #666;
$border-radius: 8px;
$spacing-sm: 8px;
$spacing-md: 16px;
$spacing-lg: 24px;
$danger-color: #F56C6C;

.history-panel {
  width: 100%;
  margin: 0 auto;
  position: relative;
  min-width: 0;
  /* 有界高度 + flex 纵向：头部固定、列表区 flex:1 内部滚动、批量栏相对本容器定位。
     height:100% 要求父容器给出高度（/qa 内嵌 .app-history 已给；单独引入时接入方
     需给 .history-page 之类的父容器一个确定高度，如 height:100vh 或 flex:1）。 */
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 48px 8% 0;
  box-sizing: border-box; /* padding 计入 width，避免 100%+16% 撑出横向滚动条 */
  overflow-x: hidden;
  /* background 由 props 控制，默认 #f4f7f9 */
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  .search-wrapper {
    position: relative;
    display: flex;
    align-items: center;
    gap: var(--iflyv-spacing-2);
  }

  .control-icons {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: var(--iflyv-spacing-2);
    flex-shrink: 0;
  }

  :deep(.el-input) {
    .el-input__wrapper {
      width: 248px;
      height: 34px;
      padding: var(--iflyv-spacing-1_5) var(--iflyv-spacing-3);
      gap: var(--iflyv-spacing-2);
      border-radius: var(--iflyv-radius-sm);
      background: var(--iflyv-bg-panel);
      border: 1px solid var(--iflyv-border-default);
      box-shadow: none !important;
      box-sizing: border-box;

      &.is-focus {
        border-color: var(--iflyv-brand-primary);
        box-shadow: none !important;
      }

      &:hover:not(.is-focus) {
        border-color: var(--iflyv-input-hover-border);
        box-shadow: none !important;
      }

      .el-input__inner {
        font-size: 14px;
        color: var(--iflyv-text-primary);
        line-height: 20px;

        &::placeholder {
          color: var(--iflyv-text-4);
        }
      }

      .el-input__prefix {
        color: var(--iflyv-icon-3);
      }

      .el-input__prefix-inner > :last-child {
        margin-right: 0 !important;
      }
    }
  }

  .time-filter-icon,
  .batch-action-icon {
    width: 34px;
    height: 34px;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: var(--iflyv-spacing-2);
    border-radius: var(--iflyv-radius-sm);
    background: var(--iflyv-bg-panel);
    box-sizing: border-box;
    border: 1px solid var(--iflyv-border-default);
    cursor: pointer;
    transition: all 0.3s ease;
    color: var(--iflyv-text-secondary);

    &:hover {
      border-color: var(--iflyv-border-strong);
      background: var(--iflyv-bg-hover);
    }

    &.active {
      border-color: var(--iflyv-brand-primary);
      background: var(--iflyv-brand-bg);
      color: var(--iflyv-brand-primary);
    }
  }

  :deep(.el-dropdown) {
    flex-shrink: 0;

    .el-tooltip__trigger {
      cursor: pointer;
      outline: none;
      padding: 2px;
      border-radius: var(--iflyv-radius-sm);

      &:hover {
        background: rgba(18, 21, 26, 0.04);
      }
    }
  }
}

/* 无限滚动列表样式 */
.infinite-list-wrapper {
  /* flex:1 占满头部以下剩余空间、min-height:0 允许收缩，内部才能真正滚动
     （否则内容会把整个 .history-panel 撑高、页面不滚动） */
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  /* 只设 overflow-y:auto 时，overflow-x 的默认值 visible 会被规范强制计算成 auto，
     导致内容稍有超宽就冒出横向滚动条。显式设 hidden 关掉横向滚动。 */
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  margin-top: 16px;

  &::-webkit-scrollbar {
    display: none;
  }

  -ms-overflow-style: none;
  scrollbar-width: none;
}

.history-list {
  padding: 0;
  margin: 0;
  list-style: none;

  .group-title {
    margin-top: 20px;
    margin-bottom: 8px;
    font-size: 14px;
    font-weight: normal;
    line-height: 20px;
    color: var(--cf-text-3);

    &:first-child {
      margin-top: 0;
    }
  }
}

/* 批量操作浮窗：相对 .history-panel（position:relative）绝对定位，稳定浮在面板底部居中。
   原先用 sticky+margin-top:auto，依赖滚动祖先与 flex 撑开，单独引入时容易失效不显示，
   改 absolute 后不依赖列表高度，进入批量模式即可见。 */
.batch-operation-bar {
  position: absolute;
  bottom: 28px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
  width: 398px;
  height: 60px;
  max-width: 800px;
  display: flex;
  align-items: center;
  background-color: #fff;
  border-radius: $border-radius;
  box-shadow: var(--iflyv-shadow-independent);
  padding: 12px 20px;
  gap: 0;
  pointer-events: auto;

  :deep(.el-checkbox) {
    display: flex;
    align-items: center;
    flex-shrink: 0;

    .el-checkbox__label {
      margin-left: 8px;
      font-size: 14px;
      color: $text-color;
    }
  }

  .selected-count {
    flex: 1;
    font-size: 14px;
    color: #959DA6;
    margin-left: 16px;
  }

  .batch-delete-btn,
  .close-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    line-height: 20px;
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
    flex-shrink: 0;
    transition: background-color 0.2s ease;

    &:hover {
      background-color: var(--cf-ink-04);
    }
  }

  .batch-delete-btn {
    color: var(--iflyv-danger-primary);
    margin-right: 8px;

    &.disabled {
      color: #C9CDD4;
      cursor: not-allowed;
    }
  }

  .close-btn {
    color: var(--cf-text-3);
  }
}

/* 加载状态样式 */
.loading-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $spacing-md 0;
  color: $text-secondary;

  .loading-spinner {
    width: 20px;
    height: 20px;
    border: 2px solid rgba(64, 158, 255, 0.3);
    border-radius: 50%;
    border-top-color: $primary-color;
    animation: spin 1s ease-in-out infinite;
    margin-right: $spacing-sm;
  }
}

.no-more-bottom {
  display: flex;
  justify-content: center;
  align-items: center;
  color: #959DA6;
  font-size: 14px;
  padding: 28px 0 24px 0;
}

/* 没有更多数据样式 */
.no-more {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  min-height: 400px;
  gap: 8px;

  div {
    font-family: PingFang SC;
    font-size: 14px;
    font-weight: normal;
    line-height: 22px;
    letter-spacing: normal;
    color: #3D3D3D;
  }
}

/* 动画效果 */
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

<style lang="scss">
/* 时间筛选弹窗样式 */
/* 解掉接入方主题对本弹窗的限高。
   宿主侧有一条给「文字型」浮层限高的规则（gest-app-web 的
   vendor/design-spec/el-theme/components/tooltip.scss）：
     .el-popper.is-light:not(.el-picker__popper):not(...)（共 8 个 :not()）
       { max-width: 318px; max-height: 240px; overflow: auto; }
   它用 :not() 排掉了 date-picker / select 这些功能性浮层，但本弹窗是
   「popover 里装了个 date-picker」，不在排除名单里 —— 于是选了自定义时间段后
   内容超过 240px 就被截断、出滚动条。
   这里用 !important 而不是靠特异性压：`:not()` 的权重等于它参数的权重，
   宿主那条是 2 个类 + 8 个 :not(.class) = 相当于 10 个类，纯靠叠选择器
   要写得很难看（且他们再加一个 :not() 就又失效）。 */
.el-popper.time-filter-popover {
  max-width: none !important;
  max-height: none !important;
  overflow: visible !important;
}

.time-filter-popover {
  --el-popover-padding: 6px;
  padding: 6px !important;
  border-radius: var(--iflyv-radius-sm);
  background: var(--iflyv-bg-panel);
  border: 1px solid var(--iflyv-border-default);
  box-shadow: 0px 8px 32px 0px rgba(18, 21, 26, 0.04);

  .el-popper__arrow {
    display: none;
  }

  .time-filter-content {
    .filter-title {
      font-size: 14px;
      font-weight: 600;
      color: var(--cf-text-1);
      margin: 6px 12px 12px;
    }

    .filter-options {
      display: flex;
      flex-direction: column;
      gap: var(--iflyv-spacing-1_5);

      .filter-option {
        height: 32px;
        padding: 0 var(--iflyv-spacing-3);
        font-size: 14px;
        color: var(--iflyv-text-secondary);
        background: transparent;
        border-radius: var(--iflyv-radius-sm);
        cursor: pointer;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: space-between;

        &:hover:not(.active) {
          background: rgba(18, 21, 26, 0.04);
        }

        &.active {
          color: var(--iflyv-brand-primary);
          background: var(--iflyv-brand-bg);

          /* 对勾不用 CSS content 画（原来是 content:'✓'）。
             产物 chatflow.css 既无 @charset、线上响应头也只有
             `Content-Type: text/css` 不带 charset —— 按 CSS 规范这种情况
             浏览器用**环境默认编码**解码外部样式表，默认非 UTF-8 的机器会把
             ✓ 的字节 E2 9C 93 按 Latin-1 渲染成「âœ"」。同一份文件不同机器
             表现不同就是这个原因。
             改用 CfIcon 画 svg：不含任何非 ASCII 字节，与编码无关。
             （试过 content 的 \2713 转义，但 CSS 压缩器认为两者等价、
             会还原成更短的字面字符，源码怎么写都拦不住。） */
          .filter-check {
            display: inline-flex;
            align-items: center;
            color: var(--iflyv-brand-primary);
          }
        }
      }
    }

    .custom-date-range {
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid var(--iflyv-border-default);

      .el-date-editor {
        width: 100%;

        .el-input__inner {
          height: 36px;
          line-height: 36px;
        }
      }
    }
  }
}

/* 下拉菜单样式 */
.history-action-dropdown-menu {
  border-radius: var(--iflyv-radius-sm);
  background: var(--iflyv-bg-panel);
  box-sizing: border-box;
  border: 1px solid var(--iflyv-border-default);
  box-shadow: 0px 8px 32px 0px rgba(18, 21, 26, 0.04);

  .el-dropdown-menu {
    padding: var(--iflyv-spacing-1);

    .el-dropdown-menu__item {
      width: 120px;
      height: 36px;
      line-height: 36px;
      padding: var(--iflyv-spacing-2) var(--iflyv-spacing-1_5);
      gap: var(--iflyv-spacing-1);
      border-radius: var(--iflyv-radius-xs);
      font-size: 14px;
      font-weight: normal;
      color: var(--iflyv-text-primary);

      .delete-item-icon,
      &.delete-item-text {
        color: var(--iflyv-danger-primary);
      }

      & + .el-dropdown-menu__item {
        margin-top: var(--iflyv-spacing-1);
      }

      &:not(.is-disabled):hover {
        background-color: var(--iflyv-bg-inset);
      }
    }
  }

  .el-popper__arrow {
    display: none;
  }
}
</style>

