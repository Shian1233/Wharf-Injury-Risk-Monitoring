<template>
  <!-- 历史项 -->
  <li
    v-for="item in list"
    :key="item.sessionId"
    class="history-item"
    :class="{
      'batch-mode': batchDeleteMode,
      selected: batchDeleteMode && selectedItems?.includes(item.sessionId)
    }"
    @click="batchDeleteMode ? handleBatchModeClick(item, $event) : handleSessionClick(item, $event)"
  >
    <div class="dialog-item">
      <!-- 批量选择框 -->
      <div v-if="batchDeleteMode" class="checkbox-container">
        <el-checkbox
          :model-value="selectedItems?.includes(item.sessionId)"
          @change="toggleSelectItem(item.sessionId)"
          size="large"
        ></el-checkbox>
      </div>

      <!-- 主要内容区域 -->
      <div class="content-container">
        <div class="dialog-item-top">
          <!-- 标题 -->
          <div class="dialog-item-title">
            <span>{{ item.title }}</span>
            <!-- 置顶图标 -->
            <CfIcon
              v-if="item.isPinned"
              name="pin"
              :size="16"
            />
          </div>

          <!-- 操作下拉菜单 -->
          <el-dropdown
            v-if="!batchDeleteMode"
            placement="bottom"
            popper-class="history-action-dropdown-menu"
            @command="(command) => handleDropdownCommand(command, item)"
          >
            <span>
              <CfIcon
                name="more-h"
                :size="18"
                class="more-icon"
                @click.stop
              />
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="enablePin" command="pin">
                  <CfIcon
                    :name="item.isPinned ? 'unpin' : 'pin'"
                    :size="20"
                    class="item-icon"
                  />
                  <span>{{ item.isPinned ? '取消置顶' : '置顶' }}</span>
                </el-dropdown-item>
                <el-dropdown-item v-if="enableRename" command="rename">
                  <CfIcon
                    name="pencil"
                    :size="20"
                    class="item-icon"
                  />
                  <span>重命名</span>
                </el-dropdown-item>
                <el-dropdown-item command="delete">
                  <CfIcon
                    name="trash"
                    :size="20"
                    class="item-icon delete-item-icon"
                  />
                  <span class="delete-item-text">删除</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <!-- 内容预览 -->
        <div class="dialog-item-content" v-html="sanitizeContent(item.answer)"></div>

        <!-- 时间显示 -->
        <div class="dialog-item-time">
          {{ formatTime(item.createTime || item.updateTime) }}
        </div>
      </div>
    </div>
  </li>
</template>

<script setup lang="ts">
import { watch, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { preprocessLaTeX, sanitizeHtml } from '../../utils/latex'
import CfIcon from '../CfIcon.vue'

interface HistoryItem {
  sessionId: string
  title: string
  answer: string
  createTime: string | number
  updateTime: string | number
  topFlag: number
  isPinned: boolean
}

interface Props {
  list: HistoryItem[]
  type: 'pinned' | 'today' | 'sevenDays' | 'thirtyDays' | 'year' | 'more'
  selectedItems?: string[]
  batchDeleteMode?: boolean
  enablePin?: boolean
  enableRename?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  batchDeleteMode: false,
  enablePin: true,
  enableRename: true
})

interface Emits {
  (e: 'toggle-select-item', sessionId: string): void
  (e: 'handle-session-click', item: HistoryItem, event: MouseEvent): void
  (e: 'pin', payload: { sessionId: string; currentTopFlag: number }): void
  (e: 'rename', payload: { sessionId: string; oldTitle: string; newTitle: string }): void
  (e: 'delete', sessionIds: string[]): void
}

const emit = defineEmits<Emits>()

// ==================== XSS 防护 ====================
/**
 * 在 DOM 层面移除危险链接和事件处理器，防止 XSS 攻击
 */
const sanitizeDangerousContent = () => {
  const contentElements = document.querySelectorAll('.dialog-item-content')

  contentElements.forEach((container) => {
    if (!container) return

    // 处理所有链接
    const links = container.querySelectorAll('a[href]')
    links.forEach((link) => {
      const href = link.getAttribute('href') || ''
      const hrefLower = href.toLowerCase().trim()

      // 检查各种危险的协议和编码
      const dangerousPatterns = [
        /^javascript:/i,
        /^javascript\s*:/i,
        /javascript&colon;/i,
        /javascript&#58;/i,
        /javascript&#x3a;/i,
        /javascript%3a/i,
        /^data:text\/html/i,
        /vbscript:/i
      ]

      // 检查 Unicode 编码的 javascript
      let decodedHref = href
      try {
        decodedHref = decodeURIComponent(href)
      } catch (e) {
        // 解码失败，使用原始值
      }

      const hasDangerousPattern = dangerousPatterns.some(
        (pattern) => pattern.test(href) || pattern.test(decodedHref)
      )

      // 检查是否包含危险函数调用
      const hasDangerousFunction =
        /alert|confirm|prompt|eval|exec|document\.cookie/i.test(href) ||
        /alert|confirm|prompt|eval|exec|document\.cookie/i.test(decodedHref)

      if (hasDangerousPattern || hasDangerousFunction) {
        link.removeAttribute('href')
        // 添加样式使其看起来像普通文本
        ;(link as HTMLElement).style.pointerEvents = 'none'
        ;(link as HTMLElement).style.cursor = 'default'
        ;(link as HTMLElement).style.textDecoration = 'none'
        ;(link as HTMLElement).style.color = 'inherit'
        // 阻止点击事件
        link.addEventListener(
          'click',
          (e) => {
            e.preventDefault()
            e.stopPropagation()
            return false
          },
          true
        )
      }
    })

    // 移除所有元素上的危险事件处理器
    const allElements = container.querySelectorAll('*')
    allElements.forEach((el) => {
      Array.from(el.attributes).forEach((attr) => {
        if (/^on/i.test(attr.name)) {
          el.removeAttribute(attr.name)
        }
      })
    })

    // 处理 img 标签
    const images = container.querySelectorAll('img')
    images.forEach((img) => {
      Array.from(img.attributes).forEach((attr) => {
        if (/^on/i.test(attr.name)) {
          img.removeAttribute(attr.name)
        }
      })
      const src = img.getAttribute('src') || ''
      if (/^javascript:/i.test(src) || /^data:text\/html/i.test(src)) {
        img.removeAttribute('src')
      }
    })

    // 移除所有 iframe 标签
    const iframes = container.querySelectorAll('iframe')
    iframes.forEach((iframe) => {
      iframe.remove()
    })

    // 移除所有 script 标签
    const scripts = container.querySelectorAll('script')
    scripts.forEach((script) => {
      script.remove()
    })

    // 移除所有 object 和 embed 标签
    const objects = container.querySelectorAll('object, embed')
    objects.forEach((obj) => {
      obj.remove()
    })
  })
}

/**
 * 清理并预处理内容，防止 XSS 攻击
 */
const sanitizeContent = (content: string | null | undefined): string => {
  if (!content) return ''

  let cleaned = content

  // 移除所有 iframe 标签
  cleaned = cleaned.replace(/<iframe[\s\S]*?>/gi, '')
  cleaned = cleaned.replace(/<\/iframe>/gi, '')
  cleaned = cleaned.replace(/<iframe[^>]*>/gi, '')

  // 移除所有 script 标签
  cleaned = cleaned.replace(/<script[\s\S]*?<\/script>/gi, '')
  cleaned = cleaned.replace(/<script[^>]*>/gi, '')
  cleaned = cleaned.replace(/<\/script>/gi, '')

  // 移除所有 object 和 embed 标签
  cleaned = cleaned.replace(/<object[\s\S]*?<\/object>/gi, '')
  cleaned = cleaned.replace(/<object[^>]*>/gi, '')
  cleaned = cleaned.replace(/<\/object>/gi, '')
  cleaned = cleaned.replace(/<embed[\s\S]*?<\/embed>/gi, '')
  cleaned = cleaned.replace(/<embed[^>]*>/gi, '')
  cleaned = cleaned.replace(/<\/embed>/gi, '')

  // 移除所有包含 javascript: 协议的属性
  cleaned = cleaned.replace(
    /\s+(src|href|action|formaction)\s*=\s*["']?\s*javascript\s*:/gi,
    ''
  )
  cleaned = cleaned.replace(
    /\s+(src|href|action|formaction)\s*=\s*["']?\s*javascript\s*%3a/gi,
    ''
  )
  cleaned = cleaned.replace(
    /\s+(src|href|action|formaction)\s*=\s*["']?\s*javascript\s*&#58;/gi,
    ''
  )

  // 移除所有事件处理器属性（on*）
  cleaned = cleaned.replace(/\s+on\w+\s*=\s*["'][^"']*["']/gi, '')
  cleaned = cleaned.replace(/\s+on\w+\s*=\s*[^\s>]*/gi, '')

  // 处理 LaTeX 公式
  const processed = preprocessLaTeX(cleaned)

  // 最后再次使用 sanitizeHtml 进行清理
  return sanitizeHtml(processed)
}

// ==================== 时间格式化 ====================
/**
 * 格式化时间显示
 * 同年内显示：03-25 13:20
 * 非本年内显示：2024-12-21
 */
const formatTime = (timeStr: string | number) => {
  if (!timeStr) return ''

  const date = new Date(timeStr)
  const now = new Date()
  const currentYear = now.getFullYear()
  const itemYear = date.getFullYear()

  // 如果是同一年
  if (itemYear === currentYear) {
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    return `${month}-${day} ${hours}:${minutes}`
  } else {
    // 如果不是同一年
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  }
}

// ==================== 交互处理 ====================
const handleSessionClick = (item: HistoryItem, event: MouseEvent) => {
  emit('handle-session-click', item, event)
}

const handleBatchModeClick = (item: HistoryItem, event: MouseEvent) => {
  // 如果点击的是选择框或其父容器，不处理
  const target = event.target as HTMLElement
  if (target.closest('.checkbox-container') || target.closest('.el-checkbox')) {
    return
  }

  // 批量选择模式下，点击卡片切换选择状态
  toggleSelectItem(item.sessionId)
}

const toggleSelectItem = (sessionId: string) => {
  emit('toggle-select-item', sessionId)
}

const handleDropdownCommand = (command: string, item: HistoryItem) => {
  if (command === 'pin') {
    emit('pin', {
      sessionId: item.sessionId,
      currentTopFlag: item.topFlag
    })
  } else if (command === 'rename') {
    showRenameDialog(item)
  } else if (command === 'delete') {
    showDeleteConfirm(item)
  }
}

// ==================== 重命名 ====================
const showRenameDialog = async (item: HistoryItem) => {
  try {
    const messageBoxPromise = ElMessageBox.prompt('', '编辑对话名称', {
      inputValue: item.title,
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      inputValidator: (value) => {
        if (!value || !value.trim()) {
          return '会话名称不能为空'
        }
        if (value.length > 20) {
          return '标题最多20个字'
        }
        return true
      },
      customClass: 'rename-dialog',
      beforeClose: (action, instance, done) => {
        if (action === 'confirm') {
          const inputValue = instance.inputValue
          if (!inputValue || !inputValue.trim()) {
            ElMessage.error('会话名称不能为空')
            return
          }
          if (inputValue.length > 20) {
            ElMessage.error('标题最多20个字')
            return
          }
        }
        done()
      }
    })

    // 添加输入框实时监听
    setTimeout(() => {
      const dialog = document.querySelector('.rename-dialog')
      const input = dialog?.querySelector('.el-input__inner') as HTMLInputElement
      const confirmBtn = dialog?.querySelector('.el-button--primary') as HTMLButtonElement

      if (input && confirmBtn) {
        const handleInput = () => {
          const inputValue = input.value
          if (inputValue.length > 20) {
            confirmBtn.disabled = true
            confirmBtn.classList.add('is-disabled')
            dialog?.classList.add('input-error')
          } else {
            confirmBtn.disabled = false
            confirmBtn.classList.remove('is-disabled')
            dialog?.classList.remove('input-error')
          }
        }

        input.addEventListener('input', handleInput)
        handleInput()
      }
    }, 100)

    const { value } = await messageBoxPromise

    const newValue = value?.trim()
    const oldValue = item.title?.trim()

    if (newValue && newValue !== oldValue) {
      emit('rename', {
        sessionId: item.sessionId,
        oldTitle: oldValue,
        newTitle: newValue
      })
    } else {
      ElMessage.info('标题未修改')
    }
  } catch (error: any) {
    console.log('取消重命名')
  }
}

// ==================== 删除 ====================
const showDeleteConfirm = (item: HistoryItem) => {
  ElMessageBox.confirm(
    '确认删除对话？删除后，聊天记录不可恢复',
    '删除对话',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
      // 挂组件库自己的 class：按钮间距由 cf-message-box 样式用 flex gap 保证，
      // 不依赖 EP 的 .el-button+.el-button margin（接入方常把它全局清零）
      customClass: 'cf-message-box'
    }
  ).then(() => {
    emit('delete', [item.sessionId])
  }).catch(() => {
    // 用户取消删除，不做任何操作
  })
}

// ==================== 生命周期 ====================
// 监听列表变化，在内容更新后执行 XSS 防护
watch(
  () => props.list,
  () => {
    nextTick(() => {
      sanitizeDangerousContent()
    })
  },
  { deep: true, immediate: true }
)

// 组件挂载后执行 XSS 防护
onMounted(() => {
  // 立即执行一次清理
  sanitizeDangerousContent()

  // 使用 MutationObserver 实时监控 DOM 变化
  const observer = new MutationObserver((mutations) => {
    let shouldClean = false
    mutations.forEach((mutation) => {
      if (mutation.addedNodes.length > 0) {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            const element = node as HTMLElement
            if (
              element.tagName === 'IFRAME' ||
              element.tagName === 'SCRIPT' ||
              element.tagName === 'OBJECT' ||
              element.tagName === 'EMBED' ||
              element.querySelector('iframe, script, object, embed')
            ) {
              shouldClean = true
            }
          }
        })
      }
    })
    if (shouldClean) {
      sanitizeDangerousContent()
    }
  })

  // 观察所有内容容器的变化
  const contentElements = document.querySelectorAll('.dialog-item-content')
  contentElements.forEach((container) => {
    observer.observe(container, {
      childList: true,
      subtree: true
    })
  })

  // 组件卸载时断开观察
  onUnmounted(() => {
    observer.disconnect()
  })

  // 延迟执行一次清理
  nextTick(() => {
    sanitizeDangerousContent()
  })
})
</script>

<style scoped lang="scss">
.group-title {
  margin-top: 20px;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: normal;
  line-height: 20px;
  color: var(--cf-text-3);
}

.history-item {
  padding: 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.8);
  transition: all 0.3s ease;
  cursor: pointer;
  outline: none;

  &:focus,
  &:focus-visible {
    outline: none;
  }

  &:hover {
    background: rgba(255, 255, 255, 1);
    box-shadow: var(--iflyv-shadow-hover);
  }

  & + .history-item {
    margin-top: 12px;
  }

  // 批量选择模式样式
  &.batch-mode {
    cursor: pointer;

    &:hover {
      background: rgba(255, 255, 255, 0.8);
    }
  }

  &.selected {
    background: var(--cf-primary-soft);
  }

  .dialog-item {
    display: flex;
    align-items: center;
    gap: 12px;

    .checkbox-container {
      flex-shrink: 0;
      display: flex;
      align-items: center;
    }

    .content-container {
      flex: 1;
      min-width: 0;

      .dialog-item-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;

        .dialog-item-title {
          flex: 1;
          min-width: 0; /* 允许 flex 子项收缩，否则内部 span 的 ellipsis 不生效、长标题会撑宽 */
          font-size: 16px;
          font-weight: 600;
          line-height: 28px;
          color: var(--cf-text-1);

          display: flex;
          align-items: center;
          justify-content: flex-start;
          gap: 8px;

          span {
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
        }

        .el-dropdown {
          flex-shrink: 0;
          display: none;
          transition: all 0.3s ease;

          :deep(.el-tooltip__trigger) {
            cursor: pointer;
            outline: none;
            padding: 2px;
            border-radius: 4px;
            display: flex;
            align-items: center;

            &:hover {
              background: rgba(18, 21, 26, 0.04);
            }
          }
        }
      }

      .dialog-item-content {
        margin-top: 8px;
        font-size: 14px;
        font-weight: normal;
        line-height: 20px;
        color: #7b838c;

        display: -webkit-box;
        -webkit-line-clamp: 2;
        line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }

      .dialog-item-time {
        margin-top: 8px;
        font-size: 12px;
        font-weight: normal;
        line-height: 20px;
        color: #959da6;
      }
    }
  }

  &:hover {
    .el-dropdown {
      display: block !important;
    }
  }
}

.more-icon {
  color: #626a73;
}
</style>

<style lang="scss">
.history-action-dropdown-menu {
  padding: 8px !important;
  border-radius: 8px !important;

  .el-dropdown-menu__item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 14px;
    color: var(--cf-text-1);

    &:hover {
      background: rgba(18, 21, 26, 0.04);
    }

    .delete-item-icon {
      color: var(--cf-danger);
    }

    .delete-item-text {
      color: var(--cf-danger);
    }
  }
}

.rename-dialog {
  width: 560px !important;
  padding: 24px !important;
  border-radius: 8px !important;
  background: #ffffff !important;
  box-sizing: border-box !important;
  border: 1px solid rgba(18, 21, 26, 0.1) !important;
  box-shadow: 0px 12px 48px 0px rgba(18, 21, 26, 0.08) !important;

  .el-message-box__container {
    padding: 0 !important;
  }

  .el-message-box__header {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    padding: 0 !important;
    margin-bottom: 24px !important;
  }

  .el-message-box__title {
    font-family: PingFang SC;
    font-size: 16px;
    font-weight: 600;
    line-height: 24px;
    letter-spacing: normal;
    color: #12151a;
    margin: 0 !important;
    padding: 0 !important;
    flex: 1;
  }

  .el-message-box__headerbtn {
    margin: 0 !important;
    padding: 0 !important;
    top: auto !important;
    position: relative !important;
    width: 20px !important;
    height: 20px !important;

    .el-message-box__close {
      font-size: 0 !important;
      width: 20px !important;
      height: 20px !important;
      position: relative !important;
      transition: all 0.3s ease !important;
      border-radius: 4px !important;

      &::before {
        content: '' !important;
        position: absolute !important;
        top: -2.5px !important;
        left: 0 !important;
        width: 20px !important;
        height: 20px !important;
        background-image: url("data:image/svg+xml,%3Csvg width='20' height='20' viewBox='0 0 20 20' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Crect fill='%23D8D8D8' opacity='0' width='20' height='20' rx='6'/%3E%3Cg transform='translate(4.5, 4.5)' fill='%2312151A' fill-rule='nonzero'%3E%3Cpath d='M0.220873735,10.7780231 C0.122896107,10.6859352 0.0543118034,10.5669096 0.0237457023,10.4359145 C-0.00791523409,10.3055868 -0.00791523409,10.169564 0.0237457023,10.0392363 C0.058537416,9.91184918 0.126998092,9.79620441 0.221922288,9.70447355 L4.41299009,5.49632705 L0.221922288,1.29447703 C0.126613566,1.20408094 0.0598968526,1.08768705 0.0300370225,0.959714256 C-0.0016239139,0.829386583 -0.0016239139,0.69336378 0.0300370225,0.563036107 C0.0620018752,0.434073741 0.128317838,0.316202925 0.221922288,0.221976852 C0.317343091,0.124839087 0.43787201,0.0561684749 0.570042006,0.0236377772 C0.699928695,-0.00787925908 0.835459936,-0.00787925908 0.965346625,0.0236377772 C1.09816338,0.05512017 1.21210618,0.118784564 1.30717502,0.21463096 L5.5055827,4.41648098 L9.6966505,0.21463096 C9.78739785,0.116203043 9.90714008,0.0492982763 10.0384789,0.0236377772 C10.1705966,-0.00784461553 10.2999182,-0.00784461553 10.4264436,0.0236377772 C10.5592604,0.05512017 10.6780965,0.121233195 10.7829518,0.221976852 C10.8780206,0.317823247 10.9412833,0.431509666 10.9727399,0.563036107 C11.0090867,0.692760281 11.0090867,0.829990082 10.9727399,0.959714256 C10.9412485,1.08893902 10.8752899,1.20718147 10.7819032,1.30182292 L6.59083543,5.49632705 L10.7819032,9.69817708 C10.8762852,9.79456315 10.9423128,9.91510786 10.9727399,10.0465822 C11.0041965,10.173911 11.0041965,10.3036884 10.9727399,10.4359145 C10.941073,10.5647641 10.8751258,10.6826235 10.7819032,10.7769737 C10.6866106,10.8744946 10.5660696,10.9435355 10.4337835,10.9763622 C10.3038968,11.0078793 10.1683656,11.0078793 10.0384789,10.9763622 C9.9092472,10.9445468 9.7910902,10.878165 9.6966505,10.7843196 L5.5055827,6.5824696 L1.30717502,10.7843196 C1.2126111,10.8777828 1.09446552,10.9437955 0.965346625,10.9753128 C0.835459936,11.0068298 0.699928695,11.0068298 0.570042006,10.9753128 C0.437987756,10.9430783 0.317470889,10.8747779 0.221922288,10.7780231'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E") !important;
        background-size: contain !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        transition: opacity 0.3s ease !important;
      }

      &:hover {
        background: rgba(18, 21, 26, 0.04) !important;

        &::before {
          opacity: 0.8 !important;
        }
      }
    }
  }

  .el-message-box__header.show-close {
    padding-right: 0 !important;
  }

  .el-message-box__content {
    margin: 0 !important;
    padding: 0 !important;
    margin-bottom: 0 !important;
  }

  .el-input__inner {
    font-family: PingFang SC;
    font-size: 14px;
    font-weight: normal;
    line-height: 28px;
    letter-spacing: normal;
    color: #12151a;
    height: 36px !important;
  }

  &.input-error {
    .el-message-box__btns {
      .el-button--primary {
        background-color: #c0c4cc !important;
        border-color: #c0c4cc !important;
        color: #ffffff !important;
        cursor: not-allowed !important;

        &:hover {
          background-color: #c0c4cc !important;
          border-color: #c0c4cc !important;
        }
      }
    }

    .el-input__inner {
      --el-input-focus-border-color: #f53f3f !important;
      border-color: #f53f3f !important;
    }

    .el-input__wrapper {
      --el-input-focus-border-color: #f53f3f !important;
      box-shadow: 0 0 0 1px #f53f3f inset !important;
    }
  }

  .el-button--primary.is-disabled {
    background-color: #c0c4cc !important;
    border-color: #c0c4cc !important;
    color: #ffffff !important;
    cursor: not-allowed !important;

    &:hover {
      background-color: #c0c4cc !important;
      border-color: #c0c4cc !important;
    }
  }

  .el-input__inner {
    --el-input-focus-border-color: var(--el-color-primary) !important;
  }

  .el-input__wrapper {
    --el-input-focus-border-color: var(--el-color-primary) !important;
  }

  .el-message-box__btns {
    margin-top: 24px !important;
    padding: 0 !important;
    display: flex !important;
    justify-content: flex-end !important;
    gap: 12px !important;

    .el-button {
      height: 36px !important;
      padding: 0 16px !important;
      margin: 0 !important;
    }
  }
}
</style>
