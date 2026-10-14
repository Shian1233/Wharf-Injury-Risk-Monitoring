<!-- ============================================================
     知识库选择器 · ChatFlow v1.0
     ------------------------------------------------------------
     两层浮层：
       一级 206px —— 四个分类，各自带已选数角标，hover 或点击都能展开
       二级 288px —— 独立浮层贴在一级右侧（空间不足翻到左侧）
                     团队/课程多一条分段器；课程再分左右栏（课程 / 该课程知识库）

     两层而不是一个宽浮层：分类数固定、二级内容长度差异大，
     分开后一级永远是四行，二级各自按需要的宽度展开。
     ============================================================ -->
<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import CfIcon from './CfIcon.vue'
import { KB_SEARCH_MIN, KB_MAX } from '../mock/knowledgeBases.js'

const props = defineProps({
  /** KB_TREE */
  tree: { type: Object, default: () => ({}) },
  /** KB_CATEGORIES */
  categories: { type: Array, default: () => [] },
  /** 已选：[{id,name}] */
  selected: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  max: { type: Number, default: KB_MAX },
  /**
   * 交互前置守卫（由 ChatComposer 透传）。返回 false 则不展开浮层。
   * 用于未登录时跳登录页 —— 跳转/提示都在接入方的实现里，本组件只认返回值。
   * 不传 = 不拦。
   */
  beforeInteract: { type: Function, default: null },
})

const emit = defineEmits(['update:selected', 'over-max', 'kb-pick'])

const open = ref(false)
const root = ref(null)
/** 由 @ 唤起时为 true；决定选中后是否自动收起并吃掉触发的 @ */
const atMode = ref(false)
/** @ 唤起时光标的视口坐标 {left, top}；按钮点击唤起时为 null，走默认贴按钮定位 */
const anchorPos = ref(null)
/** 当前展开的一级分类 key；空串表示还没展开二级 */
const cat = ref('')
/** 当前分段 key（团队/课程才有） */
const segment = ref('')
/** 课程分类下当前选中的课程 id */
const courseId = ref('')
/** 二级列表与课程列的关键词分开存，切分类时各自清空 */
const kw = ref('')
const courseKw = ref('')
/** 二级浮层翻到左侧 */
const subLeft = ref(false)
/** <1280px 时使用底部抽屉模式 */
const useDrawer = ref(false)

const activeCat = computed(() => props.categories.find((c) => c.key === cat.value) ?? null)

/** 当前分段对应的数据键：有分段取分段 key，没有取分类 key */
const listKey = computed(() => {
  const c = activeCat.value
  if (!c) return ''
  return c.segments ? (segment.value || c.segments[0].key) : c.key
})

const courses = computed(() =>
  (activeCat.value?.nested ? props.tree[listKey.value] : null) ?? [])
const coursesHit = computed(() => {
  const q = courseKw.value.trim()
  if (!q) return courses.value
  return courses.value.filter((c) =>
    `${c.name}${c.teacher ?? ''}${c.code ?? ''}`.includes(q))
})
const currentCourse = computed(() =>
  courses.value.find((c) => c.id === courseId.value) ?? null)

/** 二级的知识库列表：课程分类取当前课程的，其余取分段的 */
const items = computed(() => {
  if (activeCat.value?.nested) return currentCourse.value?.kbs ?? []
  return props.tree[listKey.value] ?? []
})
const itemsHit = computed(() => {
  const q = kw.value.trim()
  if (!q) return items.value
  return items.value.filter((x) => x.name.includes(q))
})
/** 未过滤的条数，决定要不要出搜索框 */
const flatCount = computed(() =>
  activeCat.value?.nested ? 0 : (props.tree[listKey.value] ?? []).length)

const count = computed(() => props.selected.length)
const label = computed(() => (count.value ? `知识库·${count.value}` : '知识库'))

function has(id) { return props.selected.some((k) => k.id === id) }

function toggle(item) {
  if (has(item.id)) {
    emit('update:selected', props.selected.filter((k) => k.id !== item.id))
    return
  }
  if (props.selected.length >= props.max) {
    emit('over-max', props.max)
    return
  }
  emit('update:selected', [...props.selected, { id: item.id, name: item.name }])
  /* 父级只需要知道「这次是不是 @ 唤起的」以便吃掉触发字符；
     芯片本身由父级监听 update:selected 拿到的 kbs 数组直接渲染，不需要 item */
  emit('kb-pick', { atMode: atMode.value })
  /* @ 唤起时选完直接收起，与原型 kbToggle 的 eatAt+关闭一致；
     按钮点击唤起的保持打开，方便连续多选 */
  if (atMode.value) {
    atMode.value = false
    open.value = false
  }
}

function clear() { emit('update:selected', []) }

/** 某分类下已选了几个（含它所有分段与课程） */
function catCount(c) {
  const ids = new Set()
  const keys = c.segments ? c.segments.map((s) => s.key) : [c.key]
  keys.forEach((k) => {
    (props.tree[k] ?? []).forEach((x) => {
      if (x.kbs) x.kbs.forEach((kb) => ids.add(kb.id))
      else ids.add(x.id)
    })
  })
  return props.selected.filter((k) => ids.has(k.id)).length
}

/** 某门课程下已选几个 */
function courseCount(c) {
  const ids = new Set((c.kbs ?? []).map((k) => k.id))
  return props.selected.filter((k) => ids.has(k.id)).length
}

/** 落到第一门有知识库的课程；否则右栏一上来就是空态，看着像坏了 */
function firstUsefulCourse(key) {
  const list = props.tree[key] ?? []
  return (list.find((x) => x.kbs?.length) ?? list[0])?.id ?? ''
}

function openCat(key) {
  if (cat.value === key) return
  cat.value = key
  kw.value = ''
  courseKw.value = ''
  const c = props.categories.find((x) => x.key === key)
  segment.value = c?.segments ? c.segments[0].key : ''
  courseId.value = c?.nested ? firstUsefulCourse(segment.value) : ''
  placeSub()
}

function pickSegment(key) {
  segment.value = key
  kw.value = ''
  courseKw.value = ''
  if (activeCat.value?.nested) courseId.value = firstUsefulCourse(key)
  placeSub()
}

/** 二级浮层的左右方向要按本次分类的实际宽度算，所以每次切换都重判 */
function placeSub() {
  nextTick(() => {
    const el = root.value?.querySelector('.cf-kb-menu')
    if (!el) return
    const need = activeCat.value?.nested ? 474 : 288
    subLeft.value = el.getBoundingClientRect().right + 8 + need > window.innerWidth - 12
  })
}

/* 收起时清掉二级，也清掉 @ 态与定位，避免下次按钮点击复用上一次的锚点 */
/** 页面滚动时关闭弹窗：浮层是 position:fixed 用打开那一刻的视口坐标，
    滚动后会与按钮错位。与大多数下拉一致，滚动即收起，避免错位/跟随异常。 */
function closeOnScroll() {
  if (open.value) open.value = false
}

/**
 * 点外部关闭。
 *
 * 不靠 .cf-catch 那个全屏透明遮罩：浮层 Teleport 到 body 后，遮罩的样式来自
 * 全局 `.cf-root .cf-catch`，祖先关系断了选不中 → 零尺寸 → 点外部无效。
 * 而给它补上 position:fixed;inset:0 又会吃掉页面所有点击（接入方首页实测
 * 连输入框内部都点不动了）。
 *
 * 改成判断点击落点：既不在按钮上、也不在浮层内，就关。
 * 浮层被传送到了 body，不是 root 的后代，所以必须单独判。
 */
/** 面板打开的时刻。用来忽略「打开它的那一下点击」—— 同一次交互里
    pointerdown 可能在监听挂上之后才到（尤其 @ 唤起那条路），不忽略会立刻关掉。 */
let openedAt = 0

function closeOnOutside(e) {
  if (!open.value) return
  /* 开启后 250ms 内的点击一律放过：那是打开面板的同一次交互 */
  if (Date.now() - openedAt < 250) return
  const t = e.target
  /* 按钮及其容器（root 内）—— 点按钮由 toggleMenu 自己处理，这里放过，
     否则会和 toggleMenu 打架：先被这里关掉、再被 toggle 打开。 */
  if (root.value?.contains(t)) return
  /* 浮层内部：一级菜单 cf-kb-menu、二级 cf-kb-sub、窄屏抽屉 cf-kb-drawer。
     Teleport 后它们在 body 下、不是 root 的后代，所以要单独按类名判。
     closest 能覆盖点在其子元素上的情况。
     注意 cf-kb-sub 是 cf-kb-menu 的子节点（absolute 贴着它定位），
     本来就会被 cf-kb-menu 命中，列出来是为了让意图明确、将来改结构也不漏。 */
  if (t?.closest?.('.cf-kb-menu, .cf-kb-sub, .cf-kb-drawer')) return
  open.value = false
}

watch(open, (v) => {
  if (v) {
    /* 捕获阶段监听：滚动容器可能是内部元素，事件不冒泡到 window，
       用捕获才能在任意层级的滚动上触发。passive 不拦截滚动。 */
    window.addEventListener('scroll', closeOnScroll, { capture: true, passive: true })
    /* 点外部关闭：
       - 用 pointerdown 而不是 click —— 它在事件序列里更早，且接入方页面里
         那些 @click.stop 拦不到它；
       - 捕获阶段挂在 window 上，比 document 更外层，任何 stopPropagation 都影响不到；
       - 不用 nextTick 延迟挂载：那样如果面板在下一帧前就被关掉，else 分支已经
         removeEventListener 过了，延迟挂上的监听永远清不掉，越积越多，
         最终表现为「面板一打开就被关」。改由 closeOnOutside 内部用 openedAt
         时间戳忽略掉开启那一下。 */
    openedAt = Date.now()
    window.addEventListener('pointerdown', closeOnOutside, true)
  } else {
    cat.value = ''
    atMode.value = false
    anchorPos.value = null
    window.removeEventListener('scroll', closeOnScroll, { capture: true })
    window.removeEventListener('pointerdown', closeOnOutside, true)
  }
})

/** @ 唤起时贴着光标；按钮点击唤起走按钮位置定位 */
const menuStyle = computed(() => {
  if (!anchorPos.value) return null
  return {
    left: `${anchorPos.value.left}px`,
    bottom: `${anchorPos.value.bottom}px`,
    top: 'auto',
  }
})

const buttonRef = ref(null)

/** 供父级唤起：不传参数=按钮点击，计算按钮位置；
   传 {left,top}（光标视口坐标）=@ 触发，贴光标定位 */
defineExpose({
  show: (anchor) => {
    atMode.value = !!anchor

    if (anchor) {
      // @ 唤起：贴光标
      const MENU_W = 206
      const viewportBottom = window.innerHeight - anchor.top + 8
      anchorPos.value = { left: anchor.left, bottom: viewportBottom }
    } else {
      // 按钮点击：计算按钮位置
      if (buttonRef.value) {
        const rect = buttonRef.value.getBoundingClientRect()
        anchorPos.value = {
          left: rect.left,
          bottom: window.innerHeight - rect.top + 9,
        }
      }
    }
    open.value = true
  },
})

/** 按钮点击切换 */
function toggleMenu() {
  if (open.value) {
    open.value = false
    return
  }
  /* 接入方前置守卫（如未登录跳登录）：只在「要打开」时问，关闭不拦 ——
     已经打开的面板必须能关掉，否则会卡住不能收起 */
  if (props.beforeInteract && props.beforeInteract() === false) return
  // 计算按钮位置
  if (buttonRef.value) {
    const rect = buttonRef.value.getBoundingClientRect()
    anchorPos.value = {
      left: rect.left,
      bottom: window.innerHeight - rect.top + 9,
    }
  }
  open.value = true
}

/* 监听视口宽度，<1280px 时切换为抽屉模式 */
let mediaQuery = null
function updateDrawerMode() {
  useDrawer.value = window.innerWidth < 1280
}
onMounted(() => {
  updateDrawerMode()
  mediaQuery = window.matchMedia('(max-width: 1279.98px)')
  mediaQuery.addEventListener('change', updateDrawerMode)
})
onBeforeUnmount(() => {
  if (mediaQuery) mediaQuery.removeEventListener('change', updateDrawerMode)
  // 弹窗开着时组件被销毁：兜底解绑两个全局监听，避免留下野监听
  window.removeEventListener('scroll', closeOnScroll, { capture: true })
  window.removeEventListener('pointerdown', closeOnOutside, true)
})

</script>

<template>
  <span ref="root" class="cf-kb" @keydown.esc="open = false">
    <!-- disabled 只在面板关着时生效：面板开着时一律可点，否则
         「打开面板 → 发消息（busy 变 true）→ 按钮被原生 disabled 吞掉点击」
         会让面板卡在屏幕上关不掉（它 Teleport 到 body，组件没卸载）。
         与 toggleMenu 里「关闭不拦守卫」同一个道理：已打开的必须能关。 -->
    <button
      ref="buttonRef"
      class="cf-tool-btn"
      :class="{ 'is-open': open, 'is-picked': count > 0, 'is-disabled': disabled }"
      type="button" :disabled="disabled && !open"
      :aria-expanded="open" aria-haspopup="true" aria-label="选择知识库"
      @click="toggleMenu"
    >
      <CfIcon name="books" :size="16" />
      <span>{{ label }}</span>
      <CfIcon name="caret-down" :size="12" class="cf-caret" />
    </button>

    <!-- 抽屉模式: <1280px
         ------------------------------------------------------------
         Teleport 到 body：浮层/抽屉都是 position:fixed + z-index:9999，但
         fixed 与 z-index 都只在「最近的层叠上下文」内生效。接入方只要在任意祖先上
         写了 position:relative + z-index:0（很常见，比如给背景层排层级），就形成了
         一个层叠上下文，本组件的 9999 只能在它内部比较，于是被接入方同级的兄弟节点盖住。
         传送到 body 后脱离接入方的层叠上下文，直接与 body 的子节点比层级 ——
         接入方怎么排 z-index 都不再影响这里，也不需要接入方改任何代码。 -->
    <template v-if="useDrawer">
      <Teleport to="body">
      <span v-if="open" class="cf-kb-mask" @click="open = false" />
      <div v-if="open" class="cf-kb-drawer" role="dialog" aria-label="选择知识库">
        <!-- 顶部栏 -->
        <div class="cf-kb-drawer-head">
          <h2 class="cf-kb-drawer-title">选择知识库</h2>
          <button
            class="cf-kb-drawer-close"
            type="button"
            aria-label="关闭"
            @click="open = false"
          >
            <CfIcon name="x" :size="20" />
          </button>
        </div>

        <!-- 抽屉内容区 -->
        <div class="cf-kb-drawer-body">
          <!-- 所有分类，可折叠展开（过滤掉课程分类） -->
          <div class="cf-kb-drawer-sections">
            <div v-for="c in categories.filter(cat => !cat.nested)" :key="c.key" class="cf-kb-drawer-section">
              <!-- 分类标题 -->
              <button
                class="cf-kb-drawer-section-head"
                :class="{ 'is-open': cat === c.key }"
                type="button"
                @click.stop="cat = cat === c.key ? '' : c.key; if(cat === c.key) openCat(c.key)"
              >
                <CfIcon :name="c.icon" :size="22" />
                <span>{{ c.label }}</span>
                <span v-if="catCount(c)" class="cf-kb-badge is-pri">{{ catCount(c) }}</span>
                <CfIcon
                  name="caret-down"
                  :size="18"
                  class="cf-kb-section-arrow"
                />
              </button>

              <!-- 分类内容（折叠展开） -->
              <div v-if="cat === c.key" class="cf-kb-drawer-section-body">
                <!-- 分段器：团队「我创建的/我加入的」 -->
                <div v-if="c.segments" class="cf-kb-drawer-segments">
                  <button
                    v-for="s in c.segments" :key="s.key"
                    type="button"
                    :class="{ 'is-on': listKey === s.key }"
                    @click.stop="pickSegment(s.key)"
                  >{{ s.label }}</button>
                </div>

                <!-- 知识库列表 -->
                <div class="cf-kb-drawer-items">
                  <!-- 搜索框 -->
                  <label v-if="flatCount >= KB_SEARCH_MIN" class="cf-kb-drawer-search">
                    <CfIcon name="search" :size="16" />
                    <input
                      v-model="kw" type="search"
                      placeholder="搜索知识库" @click.stop
                    >
                  </label>

                  <!-- 知识库列表 -->
                  <button
                    v-for="kb in itemsHit" :key="kb.id"
                    class="cf-kb-drawer-item"
                    :class="{ 'is-on': has(kb.id) }"
                    type="button"
                    @click.stop="toggle(kb)"
                  >
                    <span class="cf-kb-drawer-check">
                      <CfIcon name="check" :size="12" />
                    </span>
                    <span>{{ kb.name }}</span>
                  </button>
                  <p v-if="!itemsHit.length" class="cf-kb-drawer-empty">没有匹配的知识库</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 底部状态栏 -->
        <div class="cf-kb-drawer-foot">
          <span>{{ count ? `已选 ${count} / ${max} 个` : '未选择' }}</span>
          <button class="cf-kb-clear" type="button" @click.stop="clear">清空</button>
        </div>
      </div>
      </Teleport>
    </template>

    <!-- 浮层模式: ≥1280px —— 同样 Teleport 到 body，理由见上方抽屉处的注释。
         二级浮层是一级的子节点（position:absolute 贴着一级定位），跟着一起传送，
         相对定位关系不变。 -->
    <template v-else>
      <Teleport to="body">
      <!-- 这里原先有个 .cf-catch 全屏透明遮罩用来「点外部关闭」，已移除：
           它的样式来自全局 `.cf-root .cf-catch`，Teleport 到 body 后祖先关系断了、
           选择器选不中 → 零尺寸 span → 点外部根本点不到它，形同虚设；
           而补上 position:fixed;inset:0 又会吃掉页面所有点击（接入方首页实测
           连输入框内部都点不动）。改由 closeOnOutside 判断点击落点，见 script。 -->
      <span v-if="open" class="cf-kb-menu" :style="menuStyle" role="menu">
      <!-- ---------- 一级：分类（过滤掉课程分类） ---------- -->
      <button
        v-for="c in categories.filter(cat => !cat.nested)" :key="c.key"
        class="cf-kb-cat" :class="{ 'is-on': cat === c.key }"
        type="button"
        @click.stop="openCat(c.key)"
        @mouseenter="openCat(c.key)"
      >
        <CfIcon :name="c.icon" :size="16" />
        <span class="cf-kb-cat-nm">{{ c.label }}</span>
        <span v-if="catCount(c)" class="cf-kb-badge is-pri">{{ catCount(c) }}</span>
        <CfIcon name="caret-right" :size="14" class="cf-kb-cat-ar" />
      </button>

      <!-- 清空按钮始终显示（与原型一致，不随是否已选切换），
           没有选择时点击也不会出错，只是清空一个空集合 -->
      <span class="cf-kb-foot">
        <span>{{ count ? `已选 ${count} / ${max} 个知识库，作为本轮检索范围`
          : '未选择，默认检索全部可见知识库' }}</span>
        <button class="cf-kb-clear" type="button" @click.stop="clear">清空</button>
      </span>

      <!-- ---------- 二级：独立浮层 ---------- -->
      <span
        v-if="cat" class="cf-kb-sub"
        :class="{ 'is-wide': activeCat?.nested, 'is-left': subLeft }"
        role="group" :aria-label="activeCat?.label"
      >
        <!-- 分段器：团队「我创建的/我加入的」、课程「混合式/共享包」 -->
        <span v-if="activeCat?.segments" class="cf-kb-seg" role="tablist">
          <button
            v-for="s in activeCat.segments" :key="s.key"
            type="button" role="tab"
            :class="{ 'is-on': listKey === s.key }" :aria-selected="listKey === s.key"
            @click.stop="pickSegment(s.key)"
          >{{ s.label }}</button>
        </span>

        <!-- 课程分类：左课程列表 / 右该课程知识库 -->
        <span v-if="activeCat?.nested" class="cf-kb-split">
          <span class="cf-kb-cl">
            <label v-if="courses.length >= 6" class="cf-kb-search">
              <CfIcon name="search" :size="14" />
              <input
                v-model="courseKw" type="search"
                placeholder="搜索课程 / 教师" aria-label="搜索课程 / 教师" @click.stop
              >
            </label>
            <span class="cf-kb-cl-list cf-scroll">
              <button
                v-for="c in coursesHit" :key="c.id"
                class="cf-kb-crow" :class="{ 'is-on': courseId === c.id }"
                type="button" @click.stop="courseId = c.id"
              >
                <span class="cf-kb-ci">
                  <span class="cf-kb-cn">{{ c.name }}</span>
                  <span class="cf-kb-cm">{{ [c.teacher, c.code].filter(Boolean).join(' · ') }}</span>
                </span>
                <span v-if="courseCount(c)" class="cf-kb-badge is-pri">{{ courseCount(c) }}</span>
                <span v-else-if="(c.kbs ?? []).length" class="cf-kb-badge">{{ c.kbs.length }}</span>
              </button>
              <p v-if="!coursesHit.length" class="cf-kb-empty">没有匹配的课程</p>
            </span>
          </span>
          <span class="cf-kb-kl">
            <p v-if="!currentCourse" class="cf-kb-empty is-mid">选择左侧课程查看知识库</p>
            <p v-else-if="!items.length" class="cf-kb-empty is-mid">该课程暂无知识库</p>
            <span v-else class="cf-kb-list cf-scroll">
              <button
                v-for="kb in items" :key="kb.id"
                class="cf-kb-item" :class="{ 'is-on': has(kb.id) }"
                type="button" role="menuitemcheckbox" :aria-checked="has(kb.id)"
                @click.stop="toggle(kb)"
              >
                <span class="cf-kb-bx"><CfIcon name="check" :size="11" /></span>
                <span class="cf-kb-nm">{{ kb.name }}</span>
              </button>
            </span>
          </span>
        </span>

        <!-- 其余分类：单列列表 -->
        <template v-else>
          <label v-if="flatCount >= KB_SEARCH_MIN" class="cf-kb-search">
            <CfIcon name="search" :size="14" />
            <input
              v-model="kw" type="search"
              placeholder="搜索知识库" aria-label="搜索知识库" @click.stop
            >
          </label>
          <span class="cf-kb-list cf-scroll">
            <button
              v-for="kb in itemsHit" :key="kb.id"
              class="cf-kb-item" :class="{ 'is-on': has(kb.id) }"
              type="button" role="menuitemcheckbox" :aria-checked="has(kb.id)"
              @click.stop="toggle(kb)"
            >
              <span class="cf-kb-bx"><CfIcon name="check" :size="11" /></span>
              <span class="cf-kb-nm">{{ kb.name }}</span>
            </button>
            <p v-if="!itemsHit.length" class="cf-kb-empty">没有匹配的知识库</p>
          </span>
        </template>
      </span>
    </span>
      </Teleport>
    </template>
  </span>
</template>

<style scoped>
/* ---------- 传送出去后的基础重置 ----------
   浮层与抽屉 Teleport 到 body 后脱离了 .cf-root 子树，base.css 里
   `.cf-root button{border:none;background:none;padding:0}` 这类子树选择器
   对它们失效，按钮露出浏览器默认的粗边框与灰底。
   （变量不受影响 —— tokens.css 挂在 :root 上，继承链不经过 .cf-root。）

   全部用 :where() 包裹：它自身特异性为 0，整条规则只有末尾元素选择器的 (0,0,1)，
   加上 scoped 的 data-v 是 (0,1,1)。而组件自己的 .cf-kb-drawer-section-head
   等类选择器是 (0,2,0)，稳压本条 —— 这正是 base.css 里
   「重置低、组件高」的关系，组件各自的 padding/背景/描边照常生效。
   不用 :where() 的话本条会变成 (0,2,1) 反压组件规则，把内边距一起清掉。

   不给传送节点补 .cf-root 类来解决：.cf-root 自带 background:var(--cf-page)，
   套到 .cf-kb-mask / .cf-catch 两个透明遮罩上会刷成不透明底色、糊住整屏。 */
:where(.cf-kb-menu, .cf-kb-sub, .cf-kb-drawer) button{
  font-family:inherit;font-size:inherit;
  border:none;background:none;padding:0;color:inherit;
  -webkit-tap-highlight-color:transparent;
}
/* box-sizing 同理来自 .cf-root 子树选择器，传送后要补 */
:where(.cf-kb-menu, .cf-kb-drawer),
:where(.cf-kb-menu, .cf-kb-drawer) *,
:where(.cf-kb-menu, .cf-kb-drawer) *::before,
:where(.cf-kb-menu, .cf-kb-drawer) *::after{
  box-sizing:border-box;
}
/* svg 默认 inline 会在图标下方留基线间隙 */
:where(.cf-kb-menu, .cf-kb-drawer) svg{display:block}

.cf-kb{position:relative;display:inline-flex;flex:none}

/* ---------- 一级 ---------- */
.cf-kb-menu{
  position:fixed;z-index:9999;
  width:206px;padding:var(--cf-space-1);
  background:#ffffff;
  border:1px solid var(--cf-line);border-radius:var(--cf-radius-md);
  box-shadow:var(--cf-shadow-float);
}
.cf-kb-cat{
  display:flex;align-items:center;gap:var(--cf-space-2);width:100%;
  padding:9px 10px;border-radius:var(--cf-radius-sm);
  font-size:var(--cf-fs-sm);color:var(--cf-text-1);
  cursor:pointer;text-align:left;transition:var(--cf-transition);
}
.cf-kb-cat+.cf-kb-cat{margin-top:2px}
.cf-kb-cat.is-on{background:var(--cf-page)}
@media (hover:hover){
  .cf-kb-cat:hover{background:var(--cf-page)}
}
.cf-kb-cat.is-on{color:var(--cf-primary)}
.cf-kb-cat-nm{flex:1;min-width:0;white-space:nowrap}
.cf-kb-cat-ar{flex:none;color:var(--cf-text-3)}
.cf-kb-cat.is-on .cf-kb-cat-ar{color:var(--cf-primary)}
/* 已选数角标 */
.cf-kb-badge{
  flex:none;min-width:18px;height:18px;padding:0 5px;
  border-radius:var(--cf-radius-pill);background:var(--cf-ink-10);
  font-size:11px;line-height:18px;text-align:center;
  color:var(--cf-text-2);font-weight:600;
}
.cf-kb-cat.is-on .cf-kb-badge,.cf-kb-badge.is-pri{background:var(--cf-primary);color:#fff}
.cf-kb-foot{
  display:flex;align-items:center;justify-content:space-between;gap:var(--cf-space-2);
  margin-top:var(--cf-space-1);
  padding:var(--cf-space-2) var(--cf-space-2) var(--cf-space-1);
  border-top:1px solid var(--cf-line);
  font-size:var(--cf-fs-xs);color:var(--cf-text-3);
}
.cf-kb-clear{flex:none;font-size:var(--cf-fs-xs);color:var(--cf-primary);cursor:pointer}
@media (hover:hover){
  .cf-kb-clear:hover{text-decoration:underline}
}

/* ---------- 二级 ----------
   贴一级底边向右展开；空间不足时翻到左侧 */
.cf-kb-sub{
  position:absolute;bottom:-1px;left:calc(100% + 8px);
  width:288px;max-height:360px;
  display:flex;flex-direction:column;
  padding:var(--cf-space-2);
  background:#ffffff;
  border:1px solid var(--cf-line);border-radius:var(--cf-radius-md);
  box-shadow:var(--cf-shadow-float);
}
.cf-kb-sub.is-left{left:auto;right:calc(100% + 8px)}
.cf-kb-sub.is-wide{width:474px}

/* 分段器。position+z-index：它在 DOM 里排在列表之前，
   不抬层级的话选中项那圈投影会被后面带背景色的课程行盖掉 */
.cf-kb-seg{
  position:relative;z-index:1;
  display:flex;gap:3px;flex:none;
  padding:2px;margin-bottom:var(--cf-space-2);
  background:rgba(18, 21, 26, 0.02);border-radius:var(--cf-radius-sm);
}
.cf-kb-seg button{
  flex:1;padding:5px 8px;border-radius:6px;
  font-size:var(--cf-fs-xs);color:var(--cf-text-2);
  cursor:pointer;white-space:nowrap;transition:var(--cf-transition);
}
.cf-kb-seg button.is-on{
  background:#ffffff;color:var(--cf-primary);
  font-weight:600;box-shadow:var(--cf-shadow-card);
}

.cf-kb-search{
  display:flex;align-items:center;gap:var(--cf-space-2);
  height:32px;flex:none;margin-bottom:var(--cf-space-2);
  padding:0 var(--cf-space-3);
  border:1px solid var(--cf-line);border-radius:var(--cf-radius-sm);
  background:var(--cf-page);color:var(--cf-text-3);
}
.cf-kb-search input{
  flex:1;min-width:0;border:0;background:transparent;outline:none;
  font-family:inherit;font-size:var(--cf-fs-sm);color:var(--cf-text-1);
}

.cf-kb-list{flex:1;min-height:44px;overflow-y:auto;display:block}
.cf-kb-item{
  display:flex;align-items:center;gap:var(--cf-space-2);width:100%;
  padding:var(--cf-space-2);border-radius:var(--cf-radius-sm);
  font-size:var(--cf-fs-sm);color:var(--cf-text-2);
  cursor:pointer;text-align:left;transition:var(--cf-transition);
}
.cf-kb-item+.cf-kb-item{margin-top:2px}
@media (hover:hover){
  .cf-kb-item:hover{background:var(--cf-page);color:var(--cf-text-1)}
}
.cf-kb-nm{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* 勾选框：对勾常驻但透明，选中只改颜色，不改变盒模型（避免选中时行高跳动） */
.cf-kb-bx{
  width:15px;height:15px;flex:none;
  border:1px solid var(--cf-line-strong);border-radius:var(--cf-radius-xs);
  display:inline-flex;align-items:center;justify-content:center;
  color:transparent;
}
.cf-kb-item.is-on{color:var(--cf-primary)}
.cf-kb-item.is-on .cf-kb-nm{font-weight:600}
.cf-kb-item.is-on .cf-kb-bx{
  background:var(--cf-primary);border-color:var(--cf-primary);color:#fff;
}

/* 课程分类：左课程列表 / 右该课程知识库 */
.cf-kb-split{flex:1;min-height:236px;display:flex;overflow:hidden}
.cf-kb-cl{
  width:212px;flex:none;display:flex;flex-direction:column;
  padding-right:var(--cf-space-2);margin-right:var(--cf-space-2);
  border-right:1px solid var(--cf-line);
}
.cf-kb-cl-list{flex:1;overflow-y:auto}
.cf-kb-kl{flex:1;min-width:0;display:flex;flex-direction:column}
.cf-kb-crow{
  display:flex;align-items:center;gap:var(--cf-space-2);width:100%;
  padding:7px 10px;border-radius:var(--cf-radius-sm);
  cursor:pointer;text-align:left;transition:var(--cf-transition);
}
.cf-kb-crow+.cf-kb-crow{margin-top:2px}
.cf-kb-crow.is-on{background:var(--cf-page)}
@media (hover:hover){
  .cf-kb-crow:hover{background:var(--cf-page)}
}
.cf-kb-ci{flex:1;min-width:0}
/* 课程名与「教师 · 课号」是两行：两者都是 span，必须转块级才会上下堆叠，
   否则短文案会并排挤在一行，且行内盒上的 overflow / text-overflow 全部失效 */
.cf-kb-cn{
  display:block;font-size:var(--cf-fs-sm);line-height:20px;color:var(--cf-text-1);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}
.cf-kb-crow.is-on .cf-kb-cn{color:var(--cf-primary);font-weight:600}
.cf-kb-cm{
  display:block;margin-top:1px;font-size:var(--cf-fs-xs);line-height:16px;
  color:var(--cf-text-3);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}
.cf-kb-empty{
  padding:var(--cf-space-4);text-align:center;
  font-size:var(--cf-fs-xs);color:var(--cf-text-3);
}
.cf-kb-empty.is-mid{flex:1;display:flex;align-items:center;justify-content:center}

/* 抽屉模式: <1280px */
.cf-kb-mask{
  position:fixed;inset:0;z-index:9998;
  background:rgba(0,0,0,0.8);
  animation:cf-mask-in 0.2s ease-out;
}
@keyframes cf-mask-in{
  from{opacity:0}
  to{opacity:1}
}
.cf-kb-drawer{
  position:fixed;left:0;right:0;bottom:0;z-index:9999;
  max-height:80vh;display:flex;flex-direction:column;
  background:#ffffff;
  border-radius:16px 16px 0 0;
  box-shadow:0 -10px 40px rgba(0,0,0,0.25);
  animation:cf-drawer-in 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}
@keyframes cf-drawer-in{
  from{transform:translateY(100%)}
  to{transform:translateY(0)}
}

/* 顶部拖拽指示器 */
.cf-kb-drawer::before{
  content:'';
  position:absolute;top:12px;left:50%;transform:translateX(-50%);
  width:32px;height:4px;border-radius:100px;
  background:var(--cf-ink-20);
}

.cf-kb-drawer-head{
  display:flex;align-items:center;justify-content:space-between;
  padding:32px 20px 16px;flex:none;
  border-bottom:1px solid var(--cf-ink-08);
}
.cf-kb-drawer-close{
  width:36px;height:36px;flex:none;
  display:grid;place-items:center;
  border-radius:8px;
  background:transparent;color:var(--cf-text-3);
  cursor:pointer;transition:all 0.15s ease;
}
@media (hover:hover){
  .cf-kb-drawer-close:hover{
    background:var(--cf-ink-06);color:var(--cf-text-1);
  }
}
.cf-kb-drawer-title{
  flex:1;font-size:18px;font-weight:600;color:var(--cf-text-1);
  letter-spacing:-0.01em;
}
.cf-kb-drawer-body{
  flex:1;min-height:0;overflow-y:auto;
  padding:0;
}

/* 分类区块列表 */
.cf-kb-drawer-sections{
  display:flex;flex-direction:column;
  padding:8px 0;
}
.cf-kb-drawer-section{
  /* 无边框，靠间距分隔 */
}

/* 分类标题（可折叠） */
.cf-kb-drawer-section-head{
  display:flex;align-items:center;gap:10px;width:100%;
  padding:12px 20px;
  background:transparent;
  font-size:15px;color:var(--cf-text-2);font-weight:500;
  cursor:pointer;transition:all 0.15s ease;
  text-align:left;
}
@media (hover:hover){
  .cf-kb-drawer-section-head:hover{
    background:var(--cf-ink-04);
    color:var(--cf-text-1);
  }
}
.cf-kb-drawer-section-head.is-open{
  color:var(--cf-text-1);
}
.cf-kb-drawer-section-head>span:nth-child(2){
  flex:1;
  letter-spacing:-0.01em;
}
.cf-kb-drawer-section-head .cf-kb-badge{
  margin-left:auto;
}
.cf-kb-section-arrow{
  flex:none;color:var(--cf-text-3);
  transition:all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.cf-kb-drawer-section-head.is-open .cf-kb-section-arrow{
  transform:rotate(180deg);
  color:var(--cf-text-2);
}

/* 分类内容区 */
.cf-kb-drawer-section-body{
  padding:4px 20px 16px;
  animation:cf-section-expand 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes cf-section-expand{
  from{opacity:0;max-height:0}
  to{opacity:1;max-height:1000px}
}

/* 分段器 - shadcn tabs 风格 */
.cf-kb-drawer-segments{
  display:inline-flex;gap:2px;margin-bottom:12px;
  padding:2px;
  background:var(--cf-ink-06);
  border-radius:6px;
}
.cf-kb-drawer-segments button{
  padding:6px 12px;
  border-radius:4px;
  font-size:13px;color:var(--cf-text-2);font-weight:500;
  cursor:pointer;
  transition:all 0.15s ease;
}
.cf-kb-drawer-segments button.is-on{
  background:#ffffff;
  color:var(--cf-text-1);
  box-shadow:0 1px 3px rgba(0,0,0,0.1);
}
@media (hover:hover){
  .cf-kb-drawer-segments button:not(.is-on):hover{
    color:var(--cf-text-1);
  }
}

/* 知识库列表区 */
.cf-kb-drawer-items{
  display:flex;flex-direction:column;gap:6px;
}

/* 搜索框 - shadcn input 风格 */
.cf-kb-drawer-search{
  display:flex;align-items:center;gap:8px;
  padding:8px 12px;
  background:#ffffff;
  border:1px solid var(--cf-ink-10);
  border-radius:6px;
  margin-bottom:6px;
  transition:all 0.15s ease;
}
.cf-kb-drawer-search:focus-within{
  border-color:var(--cf-primary);
  box-shadow:0 0 0 3px var(--cf-primary-glow);
}
.cf-kb-drawer-search :deep(svg){
  color:var(--cf-text-3);
}
.cf-kb-drawer-search input{
  flex:1;min-width:0;border:none;outline:none;background:transparent;
  font-size:14px;color:var(--cf-text-1);
}
.cf-kb-drawer-search input::placeholder{
  color:var(--cf-text-3);
}

/* 知识库项 - shadcn checkbox + card 风格 */
.cf-kb-drawer-item{
  display:flex;align-items:center;gap:10px;
  padding:10px 12px;
  background:transparent;
  border:1px solid transparent;
  border-radius:6px;
  font-size:14px;color:var(--cf-text-1);
  cursor:pointer;
  transition:all 0.15s ease;
  text-align:left;
}
@media (hover:hover){
  .cf-kb-drawer-item:hover{
    background:var(--cf-ink-04);
  }
}
.cf-kb-drawer-item.is-on{
  background:var(--cf-primary-soft);
  border-color:var(--cf-primary);
}
.cf-kb-drawer-check{
  flex:none;
  width:18px;height:18px;
  display:grid;place-items:center;
  border:1px solid var(--cf-ink-20);
  border-radius:4px;
  background:#ffffff;
  transition:all 0.15s ease;
}
.cf-kb-drawer-item:hover .cf-kb-drawer-check{
  border-color:var(--cf-ink-30);
}
.cf-kb-drawer-item.is-on .cf-kb-drawer-check{
  background:var(--cf-primary);
  border-color:var(--cf-primary);
  color:#fff;
}
.cf-kb-drawer-check :deep(svg){
  opacity:0;
  transform:scale(0.8);
  transition:all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
}
.cf-kb-drawer-item.is-on .cf-kb-drawer-check :deep(svg){
  opacity:1;
  transform:scale(1);
}

/* 空状态 */
.cf-kb-drawer-empty{
  padding:32px 20px;
  text-align:center;
  font-size:13px;
  color:var(--cf-text-3);
}

/* 底部状态栏 - shadcn footer 风格 */
.cf-kb-drawer-foot{
  display:flex;align-items:center;justify-content:space-between;
  padding:12px 20px;
  flex:none;
  border-top:1px solid var(--cf-ink-08);
  background:var(--cf-ink-02);
  font-size:13px;
  color:var(--cf-text-3);
}
.cf-kb-drawer-foot .cf-kb-clear{
  font-weight:500;
  padding:6px 12px;
  border-radius:6px;
  color:var(--cf-primary);
  transition:all 0.15s ease;
}
@media (hover:hover){
  .cf-kb-drawer-foot .cf-kb-clear:hover{
    background:var(--cf-primary-soft);
  }
}

</style>
