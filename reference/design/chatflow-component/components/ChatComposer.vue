<!-- ============================================================
     输入区 · ChatFlow v1.0
     ------------------------------------------------------------
     一块输入卡：文本域 + 工具条（附件 / 模型 / 知识库 / 联网 / 技能 / 语音 / 发送）。
     每项都可通过 features 关掉，关掉后连分隔线一起收，不留空槽。

     技能态与基础态互斥：选中技能或挂了附件时，模型选择与联网搜索让位，
     换成该技能的参数下拉（与原型一致，工具条一行的空间有限，
     两套控件不能同时都要）。知识库选择器同理，此时一并隐藏。

     附件规则：每次仅 1 个（图片 / 视频 / 文件三选一），
     已挂附件时再点加号会提示先移除。

     【上传架构说明】
     ------------------------------------------------------------
     为了让组件跨项目复用，上传逻辑通过 props 传入，而非硬编码在组件内。

     **设计原则：**
     - 组件职责：UI 交互、状态展示、进度管理
     - 父组件职责：接口调用、业务逻辑、错误处理

     **使用方式：**
     1. 默认行为（当前项目）：
        <ChatComposer ... />
        不传 uploadHandler，使用内置的默认实现（fif-getway + fif-resource）

     2. 自定义上传（其他项目）：
        <ChatComposer :upload-handler="customUpload" ... />

        async function customUpload(file, kind, callbacks) {
          // file: File 对象
          // kind: 'image' | 'video' | 'file'
          // callbacks: { onProgress, onSuccess, onError }

          try {
            callbacks.onProgress(50)
            const result = await yourApi.upload(file)
            callbacks.onSuccess(result.fileId, result.fileType, result.url)
          } catch (error) {
            callbacks.onError('上传失败')
          }
        }

     **回调接口说明：**
     - onProgress(percent: number) - 更新进度 0-100
     - onSuccess(fileId: string, fileType: string, resourceUrl?: string) - 上传成功
     - onError(message: string) - 上传失败，会自动清除附件并提示

     **默认实现流程：**
     图片/视频：上传资源 → 保存信息 → 就绪
     文件：上传资源 → 保存信息 → 轮询解析 → 就绪
     ============================================================ -->
<script setup>
import { ref, computed, watch, onBeforeUnmount, onMounted, inject } from 'vue'
import CfIcon from './CfIcon.vue'
/* 图标雪碧本组件自带注入：CfIcon 全部 <use href="#cf-i-*">，须在挂载根内渲一个
   IconSprite 供 symbol 存在。完整应用（ChatFlow/ChatHeader/HistoryPanel）各自渲了，
   ChatComposer 常被当散件独立挂载，故这里也必须自带，否则接入方要另行注入 sprite。 */
import IconSprite from '../icons/IconSprite.vue'
import ToastHost from './ToastHost.vue'
import KbSelector from './KbSelector.vue'
import ModelSelector from './ModelSelector.vue'
import SkillParam from './SkillParam.vue'
import SkillTray from './SkillTray.vue'
import MicPermission from './MicPermission.vue'
import { DEFAULT_UPLOAD } from '../utils/config.js'
import { defaultSkillParams, skillParamSummary, VOICE_TEXT } from '../mock/skills.js'
import { KB_MAX } from '../mock/knowledgeBases.js'
import { isKbCategoryAllowed } from '../services/metaService.js'
import { useToast } from '../composables/useToast.js'
/* 运行时配置：npm 包场景下由接入方 configure() 注入，dev 回落 import.meta.env */
import { getConfig } from '@/config/runtime'
/* 上传 SDK 走这一层取：已从 bundle external 出去（体积占 45%），
   CDN 场景读接入方注入的 window.__CHATFLOW_DEPS__，源码拷贝场景回落动态 import */
import { getFifGetway, getFifResource } from '../utils/externalDeps.js'
// 语音输入 SDK（可选依赖，动态加载）
let AssistantChat = null
async function loadAssistantChat() {
  if (!AssistantChat) {
    try {
      const module = await import('@/utils/AssistantChat/index')
      AssistantChat = module.AssistantChat
    } catch (error) {
      console.warn('AssistantChat SDK 未安装，语音功能不可用')
      return null
    }
  }
  return AssistantChat
}

// 文件上传 SDK（默认实现使用，懒加载）
let Getway = null
async function loadGetway() {
  if (!Getway) {
    try {
      const module = await getFifGetway()
      Getway = module.Getway || module.default?.Getway || module.default
      if (!Getway) {
        console.warn('fif-getway 导出结构异常，默认上传功能不可用')
        return null
      }
    } catch (error) {
      /* getFifGetway 抛错时 message 里已带排查指引（接入方未注入 / 未安装），
         原样打出来，别只说「未安装」误导排查方向 */
      console.warn(error?.message || 'fif-getway 未安装，默认上传功能不可用')
      return null
    }
  }
  return Getway
}

const props = defineProps({
  features: { type: Object, required: true },
  /** adapter.meta：models / knowledgeBases / kbCategories / skills / skillOrder */
  meta: { type: Object, default: () => ({}) },
  /** 生成中：禁用发送，占位文案换成提示 */
  busy: { type: Boolean, default: false },
  /**
   * 短请求进行中：发送按钮转圈并禁用，但**不**变成停止按钮。
   *
   * 与 busy 的区别 —— busy 是「流式生成中」，可中止，所以按钮换成 ✕ 让用户点停；
   * loading 是「发出去了但还没回」这种不可中止的短请求（如接入方在 @send 里先做
   * 一次意图识别再决定去哪），此时给个停止按钮既没用也误导。
   *
   * 优先级 busy > loading：真在生成就必须留出中止入口。
   */
  loading: { type: Boolean, default: false },
  placeholder: { type: String, default: '继续提问，或输入 @ 选择知识库' },
  /** 字数上限。不传默认 250；0 表示不限；技能带 maxLength 时以技能的为准 */
  maxLength: { type: Number, default: 250 },
  upload: { type: Object, default: () => DEFAULT_UPLOAD },
  /** 是否显示底部"内容均由AI生成，请注意辨别"提示 */
  showDisclaimer: { type: Boolean, default: false },
  /**
   * 上传处理器（可插拔）：外部项目复用本组件时传入自己的上传实现。
   * 不传则使用内置的 defaultUploadHandler（当前项目 fif-getway + fif-resource）。
   * 签名：async (file, kind, callbacks) => void
   *   - file: File 对象
   *   - kind: 'image' | 'video' | 'file'
   *   - callbacks: { onProgress(percent), onSuccess(fileId, fileType?, resourceUrl?), onError(message) }
   */
  uploadHandler: { type: Function, default: null },
  /**
   * 附件数量上限（可配置）。支持两种写法：
   *   - 数字：所有类型共用一个上限，如 3
   *   - 对象：按类型分别配置，如 { image: 3, video: 1, file: 2 }
   * 不传默认 1（每次仅 1 个附件）。
   * 注：当前底层为单附件模型，>1 的上限暂按 1 生效，此 prop 先用于校验提示与后续扩展。
   */
  maxAttachments: { type: [Number, Object], default: 1 },
  /**
   * 动态 chat 入参（由 ChatFlow 下传，两个实例绑同一份响应式状态）。
   * ChatComposer 不理解其语义，只原样塞进 composer-above / composer-tools 插槽作用域，
   * 保持 dumb component。单散件用时接入方可直接 :params 绑定自己的状态。
   */
  params: { type: Object, default: () => ({}) },
  /**
   * 更新入参的函数。setParams(patch) 由上层实现（浅合并 + emit update:chatParams）。
   * 默认 no-op：单散件未接线时调用不报错、静默无效果。
   */
  setParams: { type: Function, default: () => {} },
  /**
   * 游客功能权限，直传后端 /visitor/access/config/query 的返回对象
   * （{ personalKb, teamKb, schoolKb, ... }，0-关闭 1-开启）。
   *
   * 不传（null）= 不限制，与升级前行为完全一致 —— 非游客接入方不需要传。
   * 传了就按最大权限裁剪：三类知识库全部无权限时，知识库入口整个不渲染。
   * 注：分类 tab 的裁剪由 meta.kbCategories 承担（metaService 已按权限过滤），
   * 这里只管「整个入口显不显示」，两者职责不重叠。
   */
  permissions: { type: Object, default: null },
  /**
   * 交互前置守卫（接入方注入）。在「知识库 / 上传附件 / 发送」三个交互动作发生前调用，
   * 返回 false 表示本次交互被接入方拦下，组件立即中止，不做任何后续动作。
   *
   * 典型用途：未登录时跳登录页。接入方实现形如
   *   () => { if (已登录) return true; 跳登录(); return false }
   *
   * 不传（null）= 不拦，与升级前行为完全一致。
   * 组件不关心拦截的原因，也不负责提示文案 —— 提示/跳转都由接入方在这个函数里自己做。
   */
  beforeInteract: { type: Function, default: null },
  /**
   * 发送后是否清空输入框。默认 true（对话场景：消息已上屏，输入框该空出来）。
   *
   * 传 false 用于「发送不等于进入对话」的场景 —— 比如门户首页发送后先弹意图
   * 识别窗让用户选智能体，用户可能取消、可能改主意，原文必须留在框里。
   * 这类接入方此前只能在关闭弹窗时回填文本，用户会看到「清空又冒出来」的闪动。
   *
   * 清空与否由接入方决定，组件不猜：它不知道 send 之后会发生什么。
   * 需要在特定时机手动清空的，用暴露出的 clear() 方法。
   */
  clearOnSend: { type: Boolean, default: true },
})

const emit = defineEmits(['send', 'stop'])

const { toast } = useToast()

// Toast 接入方去重：ChatFlow 外层已渲染 <ToastHost/> 时会 provide 此标记，
// 此时 ChatComposer 不再自渲染，避免嵌套使用叠两层；单独用输入框时无人 provide，
// ChatComposer 自带一份 ToastHost，保证独立场景下 toast/上传报错能可见。
const hasToastHost = inject('cf-has-toast-host', false)
const renderOwnToastHost = computed(() => !hasToastHost)

/**
 * 交互前置守卫：调接入方注入的 beforeInteract，返回 false 表示本次交互被拦下。
 *
 * 四个入口（发送 / 上传 / 知识库按钮 / @ 唤起知识库）都先过这里，
 * 拦下后立即 return，不做任何后续动作。未注入时恒放行（老接入方行为不变）。
 * 接入方函数抛异常时按「放行」处理 —— 守卫是增强能力，不该因接入方 bug 卡死输入框。
 */
function allowInteract() {
  const fn = props.beforeInteract
  if (typeof fn !== 'function') return true
  try {
    return fn() !== false
  } catch (e) {
    console.error('[ChatComposer] beforeInteract 执行出错，本次按放行处理:', e)
    return true
  }
}

// 注意：这两个 store 仅在默认上传实现中使用
// 外部项目传入 uploadHandler 时不会用到
let tokenStore = null
let userStore = null

// 懒加载 store（仅默认上传需要）
async function loadStores() {
  if (!tokenStore || !userStore) {
    try {
      const storeModule = await import('@/store/index')
      tokenStore = storeModule.useTokenStore()
      userStore = storeModule.useUserStore()
    } catch (error) {
      console.warn('Store 未找到，默认上传功能不可用')
    }
  }
  return { tokenStore, userStore }
}

// getway 实例（仅默认上传实现使用，懒加载）——
// 外部项目传入自己的 uploadHandler 时不会触碰这里，也就无需依赖本项目的上传环境变量。
let _getway = null

async function getGetway() {
  if (!_getway) {
    const GetwayClass = await loadGetway()
    if (!GetwayClass) {
      throw new Error('fif-getway 未安装')
    }
    _getway = new GetwayClass({
      appCode: 'adopt',
      tokenKey: getConfig('tokenKey'),
      baseUrl: getConfig('uploadApi'),
      timeout: 60000,
      isLog: true,
      toLogin: async () => {
        if (tokenStore) {
          tokenStore.goLogin()
        }
      }
    })
  }
  return _getway
}

/* ---------- 输入区：contenteditable 富文本 ----------
   已选知识库以不可编辑的渐变芯片反显在正文最前面（与原型 #ask 一致）。
   text 只存正文（不含芯片），kbs 是芯片的唯一数据源；DOM 由 renderAsk 手工管理，
   不走 Vue 的 vdom diff —— 模板里这个 div 不声明任何子节点，Vue 就不会碰它的子树。 */
const NBSP = ' '
const askEditor = ref(null)
const text = ref('')
const kbSelector = ref(null)
/** 当前打开的知识库浮层是不是由 @ 唤起的；选中后要吃掉触发的 @ */
const kbAtMode = ref(false)

/* ---------- 模型 ----------
   未登录占位：模型与技能列表都来自接口，未登录时接口拿不到数据，
   工具条上模型胶囊与技能按钮会整个消失 —— 用户看不到这个智能体有什么能力，
   也就没有登录的动机。所以未登录时铺一份假数据撑住界面，交互对齐知识库：
   点击时走 beforeInteract 守卫，由接入方跳登录。
   登录后 props.meta.models 有真实值，假数据自动让位，后续逻辑完全不变。 */

/** 未登录占位模型。abilityList 决定技能菜单里出现哪几项（见 availableSkills），
    这里给满三项，让用户看到完整能力清单。
    名称含「鼎安」是刻意的 —— supportsMultimodal 按名称判多模态，
    保持与真实核心模型一致的表现，避免占位态下附件入口莫名置灰。 */
const GUEST_MODELS = [{
  id: '__guest_placeholder__',
  name: '鼎安大模型',
  core: true,
  abilityList: ['image_to_text', 'text_to_image', 'text_to_speech'],
}]

/** 是不是「未登录占位态」：接口没给模型 + 接入方挂了守卫。
    两个条件都要：没挂守卫说明接入方不做登录拦截（如内部页面），
    这时模型为空是真的没有数据，铺假数据会骗人。 */
const isGuestPlaceholder = computed(() =>
  (props.meta.models ?? []).length === 0 && typeof props.beforeInteract === 'function'
)

const models = computed(() => {
  const real = props.meta.models ?? []
  return real.length ? real : (isGuestPlaceholder.value ? GUEST_MODELS : real)
})
const modelIdx = ref(0)
const model = computed(() => models.value[modelIdx.value] ?? null)
/** 只有 core 模型（学科大模型）带能力插件；通用模型选中后技能整行收起 */
const isCoreModel = computed(() => !!model.value?.core)
/** 判断当前模型是否支持多模态（图片/视频/文件）：模型名称包含"鼎安"关键字 */
const supportsMultimodal = computed(() => {
  const modelName = model.value?.name || model.value?.modelName || ''
  return modelName.includes('鼎安')
})

/** 多模态提示文本：模型不支持时显示 */
const multimodalTip = computed(() => {
  if (supportsMultimodal.value) return ''
  const modelName = model.value?.name || model.value?.modelName || '当前模型'
  return `${modelName}仅支持文本问答，切回鼎安大模型可上传附件`
})

/* ---------- 知识库 ---------- */
const kbs = ref([])

/** meta.knowledgeBases 是 {personal:[],team:[],school:[]} 三类树，
 *  摊平成 id → name 索引，供「接入方只给了 id」时反查名称 */
const kbNameById = computed(() => {
  const idx = {}
  const tree = props.meta?.knowledgeBases ?? {}
  Object.values(tree).forEach((list) => {
    if (!Array.isArray(list)) return
    list.forEach((kb) => {
      if (kb?.id != null && kb.name) idx[String(kb.id)] = kb.name
    })
  })
  return idx
})

/** 芯片/气泡上显示的名称。name 未知时给占位词，
 *  绝不能让 undefined 或裸对象漏到视图里 */
function kbLabel(kb) {
  return kb?.name || '知识库'
}

/** 归一化外部传入的知识库项。接入方（落地页 /home 跳转）常常只给 {id}，
 *  名称要按 id 去 meta 树反查；查不到先留空串，等 loadMeta 回来由下面的 watch 补。
 *  这里必须保证 name 是字符串而不是 undefined ——
 *  否则输入框芯片写出「@undefined」，气泡里 {{ kb.name ?? kb }} 会把
 *  整个对象渲染成 JSON（@{ "id": "10645" }）。 */
function normalizeKbs(list) {
  return (list ?? [])
    .map((k) => {
      if (k == null) return null
      /* 兼容接入方直接给字符串/数字 id 的写法 */
      if (typeof k === 'string' || typeof k === 'number') {
        const id = String(k)
        return id ? { id, name: kbNameById.value[id] || '' } : null
      }
      const id = k.id != null ? String(k.id) : ''
      if (!id) return null
      return { id, name: k.name || k.knowledgeBaseName || kbNameById.value[id] || '' }
    })
    .filter(Boolean)
}

/* 知识库树晚到（接入方不等 loadMeta 就跳转发送）：树一回来把缺名的补上。
   kbs 的 deep watch 会顺带重画输入框芯片，不用在这里手动调 renderAsk */
watch(kbNameById, (idx) => {
  kbs.value.forEach((kb) => {
    if (!kb.name && idx[kb.id]) kb.name = idx[kb.id]
  })
})

/* ---------- 联网搜索 ---------- */
const webSearch = ref(false)

/* ---------- 附件 ---------- */
/* stage: 'uploading' → ('parsing' 仅视频) → 'ready'。progress 只在 uploading 用 */
const attachment = ref(null)     // {name, kind, size, url, file, stage, progress}
/** 缩略图取不到时（格式异常）回落成图标，不留破图 */
const thumbFailed = ref(false)
watch(attachment, () => { thumbFailed.value = false })
const upImage = ref(null)
const upVideo = ref(null)
const upFile = ref(null)
const plusOpen = ref(false)
const plusBtnRef = ref(null)
const plusMenuStyle = ref({})

/** 附件配置：支持细粒度控制（对象）或简化写法（布尔值） */
const attachmentConfig = computed(() => {
  const feat = props.features.attachments
  if (typeof feat === 'boolean') {
    // 兼容旧格式：true = 全部支持，false = 全部不支持
    return { image: feat, video: feat, file: feat }
  }
  // 新格式：对象，细化控制
  return feat || { image: false, video: false, file: false }
})

/** 附件功能是否启用（至少有一种类型支持） */
const hasAttachments = computed(() => {
  return attachmentConfig.value.image || attachmentConfig.value.video || attachmentConfig.value.file
})

/**
 * 取某类型附件的数量上限：
 *   maxAttachments 是数字 → 各类型共用；是对象 → 按类型取，缺省回落 1。
 * 兜底 1，保证不传或传 0/负数时至少能传 1 个（与旧行为一致）。
 */
function maxOf(kind) {
  const m = props.maxAttachments
  const raw = typeof m === 'number' ? m : (m?.[kind])
  const n = Number(raw)
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : 1
}

/** 当前已选某类型附件的数量（底层单附件模型：最多 1 个，按 kind 匹配计数） */
function countOf(kind) {
  return attachment.value?.kind === kind ? 1 : 0
}

/* ---------- 技能 ---------- */
const skills = computed(() => props.meta.skills ?? {})
const skillOrder = computed(() => props.meta.skillOrder ?? [])

/**
 * 知识库入口是否可用。
 *
 * 只在传了 permissions 时才判断：三类知识库全部无权限 → 整个入口不渲染。
 * 不传 permissions 恒为 true（老接入方行为不变）。
 * 不用 meta.kbCategories.length 反推 —— 那个值初始为空、loadMeta 又是异步的，
 * 会先藏后显闪一下；单件引入时接入方也可能压根不传 kbCategories。
 */
const kbAllowed = computed(() => {
  const p = props.permissions
  if (!p) return true
  return p.personalKb == 1 || p.teamKb == 1 || p.schoolKb == 1
})

/**
 * 交给 KbSelector 的分类 tab：在 meta.kbCategories 之上按 permissions 再滤一道。
 *
 * 正常路径下 metaService.loadKnowledgeBases 已经用 filterKbCategories 裁过，
 * 这里本该是恒等变换。但单散件接入时 meta 由接入方自己拼装，未必经过那条链路
 * —— 实际踩到的是接入方带缓存的 meta：预热时权限配置还没回来、缓存了
 * 未裁剪的全量分类，之后带权限的调用命中缓存、参数被忽略，
 * 于是 teamKb=0 的分类照样显示。
 *
 * 权限判定放在组件自己这一层才可靠：permissions 是 prop，始终是最新值。
 * 不传 permissions 时恒等返回，老接入方行为不变。
 */
const kbCategoriesAllowed = computed(() => {
  const list = props.meta?.kbCategories ?? []
  const p = props.permissions
  if (!p) return list
  return list.filter((c) => isKbCategoryAllowed(c?.key, p))
})

/** 能力编码到技能 key 的映射 */
const ABILITY_TO_SKILL_MAP = {
  'image_to_text': 'i2t',
  'text_to_image': 't2i',
  'text_to_speech': 'tts'
}

/** 根据当前模型的 abilityList 过滤可用的技能 */
const availableSkills = computed(() => {
  // 支持多种字段名：abilityList (数组) 或 modelAbilities (字符串)
  let abilityList = model.value?.abilityList

  // 如果没有 abilityList，尝试从 modelAbilities 字符串解析
  if (!abilityList && model.value?.modelAbilities) {
    const abilitiesStr = model.value.modelAbilities
    abilityList = abilitiesStr.split(',').map(s => s.trim()).filter(Boolean)
  }

  // 如果 abilityList 为空或不存在，返回空数组（技能按钮隐藏）
  if (!abilityList || !Array.isArray(abilityList) || abilityList.length === 0) {
    return []
  }

  // 根据 abilityList 过滤出可用的技能 key
  const availableKeys = abilityList
    .map(code => ABILITY_TO_SKILL_MAP[code])
    .filter(Boolean)

  return availableKeys
})

/** 过滤后的技能顺序：只显示当前模型支持的技能 */
const filteredSkillOrder = computed(() => {
  if (availableSkills.value.length === 0) {
    return []
  }
  return skillOrder.value.filter(key => availableSkills.value.includes(key))
})

/** 技能功能是否可用：有可用技能时才显示技能按钮 */
const skillsAvailable = computed(() => {
  return props.features.skills && filteredSkillOrder.value.length > 0
})

/* 选了知识库时技能禁用：技能（文生图/文字转语音/图生文）走的是各自的生成分支，
   与知识库检索是两套互斥的问答形态，同时带上后端也不知道该按哪条走。
   置灰而不是隐藏 —— 让用户知道这个能力还在，只是当前被知识库占用了；
   清空知识库后 kbs.length 归零，按原有条件（skillsAvailable）恢复显示。 */
const skillBlockedByKb = computed(() => kbs.value.length > 0)
const skillBlockedTip = computed(() =>
  skillBlockedByKb.value ? '已选知识库时不能使用技能，请先移除知识库' : ''
)

/** 当前选中的技能 key，空串表示未选任何技能（基础问答态） */
const activeSkillKey = ref('')
const activeSkill = computed(() => skills.value[activeSkillKey.value] ?? null)
/** 各技能的参数值，key 是技能名，value 是 {参数名: 当前值} */
const skillParams = ref({})
const skillMenuOpen = ref(false)
const skillBtnRef = ref(null)
const skillMenuStyle = ref({})

/* 菜单开着时知识库被选中（@ 唤起或从面板勾选）：顺手收起，
   别留一个点不动的浮层。与加号菜单同处理。
   放在 skillMenuOpen 声明之后 —— const 有暂时性死区，写在前面靠回调延迟执行
   才不报错，太脆弱。 */
watch(skillBlockedByKb, (blocked) => { if (blocked) skillMenuOpen.value = false })

/** 计算菜单位置 */
function calcMenuPos(btnEl) {
  if (!btnEl) return {}
  const rect = btnEl.getBoundingClientRect()
  return {
    left: `${rect.left}px`,
    bottom: `${window.innerHeight - rect.top + 12}px`,
  }
}

function togglePlusMenu() {
  if (props.busy) return
  /* 文生图/文字转语音：入口置灰，点了只给原因提示，不展开菜单 */
  if (attachBlockedBySkill.value) { toast(attachBlockedTip.value); return }
  // 未登录等接入方拦截条件：不展开附件菜单（接入方已在 guard 内跳登录）
  if (!allowInteract()) return
  if (plusOpen.value) {
    plusOpen.value = false
    return
  }
  plusMenuStyle.value = calcMenuPos(plusBtnRef.value)
  plusOpen.value = true
}

function toggleSkillMenu() {
  if (skillMenuOpen.value) {
    skillMenuOpen.value = false
    return
  }
  /* 选了知识库：入口置灰，点了只给原因提示，不展开菜单。
     放在收起分支之后 —— 已经打开的菜单要能正常关掉。 */
  if (skillBlockedByKb.value) { toast(skillBlockedTip.value); return }
  skillMenuStyle.value = calcMenuPos(skillBtnRef.value)
  skillMenuOpen.value = true
}

/** 图片附件默认选中「图生文」，与原型一致 */
const ATTACHMENT_SKILL = { image: 'i2t' }

/* 文生图 / 文字转语音只吃纯文本提示词，选中后上传附件入口禁用。
   图生文（i2t）本身就靠图片驱动，不在此列。 */
const NO_ATTACH_SKILLS = ['t2i', 'tts']
const attachBlockedBySkill = computed(() => NO_ATTACH_SKILLS.includes(activeSkillKey.value))
const attachBlockedTip = computed(() => {
  if (!attachBlockedBySkill.value) return ''
  return `「${activeSkill.value?.name || '当前技能'}」不支持上传附件，请先退出该能力`
})
/* 菜单开着时技能被切过来（含 restore 外部恢复）：顺手收起，别留一个点不动的浮层 */
watch(attachBlockedBySkill, (blocked) => { if (blocked) plusOpen.value = false })

/* 技能态或挂了附件时，模型/联网让位给技能参数：工具条一行放不下两套控件 */
const inBaseMode = computed(() => !activeSkillKey.value && !attachment.value)

function paramsOf(key) {
  if (!skillParams.value[key]) skillParams.value[key] = defaultSkillParams(key)
  return skillParams.value[key]
}

function setSkill(key) {
  /* 再点一次当前技能退出，回到基础问答态 */
  activeSkillKey.value = activeSkillKey.value === key ? '' : key
  skillMenuOpen.value = false
}

function pickSkill(key) {
  const s = skills.value[key]
  if (!s) return
  /* 知识库门禁兜底：入口已置灰 + toggleSkillMenu 已拦，这里防其他调用路径绕过 */
  if (skillBlockedByKb.value) {
    toast(skillBlockedTip.value)
    skillMenuOpen.value = false
    return
  }
  /* 未登录等接入方拦截条件：菜单允许展开（让用户看到有哪些能力，这是登录动机），
     但真正选中某项时才拦 —— 接入方已在 guard 内跳登录。
     与知识库同口径，见 allowInteract。 */
  if (!allowInteract()) {
    skillMenuOpen.value = false
    return
  }
  /* 独立成页的技能（同声传译）：新页签打开，不打断当前对话 */
  if (s.page) {
    toast(`已在新页签打开「${s.name}」智能体`)
    skillMenuOpen.value = false
    return
  }
  /* 图生文与 + 里的「图片」是同一条路径：点击直接拉起选图，选完再切能力 */
  if (key === 'i2t') {
    if (attachment.value) {
      toast('每次仅支持上传 1 个附件，请先移除当前附件')
      skillMenuOpen.value = false
      return
    }
    skillMenuOpen.value = false
    upImage.value?.click()
    return
  }
  setSkill(key)
}

function exitSkill() {
  /* 附件带进来的能力：关闭连同附件一起撤掉，回到初始态 */
  if (attachment.value && ATTACHMENT_SKILL[attachment.value.kind] === activeSkillKey.value) {
    removeAttachment()
    return
  }
  activeSkillKey.value = ''
}

function updateSkillParam(field, value) {
  const key = activeSkillKey.value
  if (!key) return
  paramsOf(key)[field.key] = value
  toast(`已切换${field.key}：${value}`)
}

/* 图片可以不写一句话单独发出去；视频、文件必须配文字才能发，
   光挂着附件不算「有内容」，否则会发出一条没有说明的纯附件消息。 */
const canSend = computed(() =>
  !props.busy && (text.value.trim().length > 0 || attachment.value?.kind === 'image')
)

/** 联网搜索开关显隐：对齐接入方 /qa。
    总开关开 + 非技能/无附件（inBaseMode）+ 当前模型未显式关闭联网。
    模型 webSearch 口径用 `!== false`：未声明(undefined)视为支持，
    只有明确标记 webSearch===false 的模型才隐藏开关。 */
const showWebSearch = computed(() =>
  props.features.webSearch &&
  inBaseMode.value &&
  model.value?.webSearch !== false
)

/** 技能带字数上限时以它为准（如文字转语音 250 字），否则用 props.maxLength */
const effectiveMaxLength = computed(() => activeSkill.value?.maxLength || props.maxLength)
/* 与原型一致：只要当前有字数上限（props.maxLength 或技能自带的 maxLength）
   就出现计数，没有独立开关——字数上限本身就是计数该不该在的唯一判据 */
const showCharCount = computed(() => effectiveMaxLength.value > 0)

function fmtSize(b) {
  /* 跨页恢复的附件（接入方经 URL query 传 fileId/name/kind/url）往往没有 size，
     不兜底的话 Math.round(undefined/1024) → NaN，界面上出现「NaN KB」。
     返回空串，由调用处决定怎么拼（见 attPlaceholderMsg 与 chip 的 title）。 */
  const n = Number(b)
  if (!Number.isFinite(n) || n <= 0) return ''
  return n >= 1048576
    ? `${(n / 1048576).toFixed(1)} MB`
    : `${Math.max(1, Math.round(n / 1024))} KB`
}

function pickUpload(kind) {
  /* 技能门禁兜底：菜单入口已禁用，这里防止其他调用路径绕过 */
  if (attachBlockedBySkill.value) { toast(attachBlockedTip.value); return }
  // 多模态门禁：非多模态模型不能上传图片/视频（对齐接入方 /qa，文件不受限）
  if ((kind === 'image' || kind === 'video') && !supportsMultimodal.value) {
    return
  }
  // 数量上限校验（可配置，默认 1）
  const max = maxOf(kind)
  // 底层是单附件模型：已挂了任意附件都要先移除。这里同时给出与配置一致的文案。
  if (attachment.value) {
    const sameKind = attachment.value.kind === kind
    if (sameKind && countOf(kind) >= max) {
      const label = props.upload[kind]?.label || '附件'
      toast(max === 1 ? `每次仅支持 1 个${label}，请先移除当前${label}` : `${label}最多上传 ${max} 个`)
    } else {
      toast('每次仅支持 1 个附件，请先移除当前附件')
    }
    return
  }
  plusOpen.value = false
  const map = { image: upImage, video: upVideo, file: upFile }
  map[kind]?.value?.click()
}

/** 上传附件当前占位在输入框里的说明文案：优先级高于技能占位（与原型 attMsg 一致） */
const attPlaceholderMsg = computed(() => {
  const att = attachment.value
  if (!att) return ''
  const rule = props.upload[att.kind]
  if (att.stage === 'uploading') return `正在上传 ${att.name}`
  if (att.stage === 'parsing') return rule?.parseMsg || ''
  /* size 可能缺失（跨页恢复的附件只带 fileId/name/kind/url），fmtSize 此时返回空串；
     readyTip 也是可选的（接入方可通过 upload prop 覆盖）。两者都要能缺，
     不能留下「「a.pdf」 已就绪，」这种多余空格与孤零零的逗号。 */
  const size = fmtSize(att.size)
  const tip = rule?.readyTip
  return `「${att.name}」${size ? `${size} ` : ''}已就绪${tip ? `，${tip}` : ''}`
})

function attIcon(kind) {
  return props.upload[kind]?.icon
    || (kind === 'image' ? 'image' : kind === 'video' ? 'video' : 'clip')
}

/* 上传 / 解析的模拟计时器：与原型节奏一致（220 / 520 / 860ms，视频再加 1400ms 解析）。
   数组统一记录，方便移除附件或换文件时一次性清空，避免旧计时器晚到把新状态搞乱 */
let uploadTimers = []
function clearUploadTimers() {
  uploadTimers.forEach(clearTimeout)
  uploadTimers = []
}
function later(fn, ms) {
  uploadTimers.push(setTimeout(fn, ms))
}

function simulateUpload(rule) {
  later(() => { if (attachment.value) attachment.value.progress = 46 }, 220)
  later(() => { if (attachment.value) attachment.value.progress = 100 }, 520)
  later(() => {
    if (!attachment.value) return
    if (rule?.parse) {
      attachment.value.stage = 'parsing'
      later(() => {
        if (!attachment.value) return
        attachment.value.stage = 'ready'
        toast(rule.toast)
      }, 1400)
    } else {
      attachment.value.stage = 'ready'
      toast(rule?.toast)
    }
  }, 860)
}

/* ============================================================
   上传编排（组件侧，与具体接口解耦）
   ------------------------------------------------------------
   uploadFileToServer 只负责「调用上传处理器 + 把回调结果落到附件状态上」，
   真正的接口调用在 uploadHandler 里。默认用 defaultUploadHandler（本项目实现），
   外部项目可通过 props.uploadHandler 传入自己的实现替换它。

   回调契约（组件提供给 handler 调用）：
     - onProgress(percent)                         上传进度 0-100
     - onSuccess(fileId, fileType?, resourceUrl?)  成功，落地附件为 ready
     - onError(message)                            失败，清附件 + toast
   ============================================================ */
async function uploadFileToServer(file, kind) {
  // 组件侧统一的回调实现：handler 只管上传、这里只管状态展示
  const callbacks = {
    onProgress(percent) {
      if (attachment.value && typeof percent === 'number') {
        attachment.value.progress = Math.min(100, percent)
      }
    },
    onSuccess(fileId, fileType, resourceUrl) {
      if (!fileId) {
        callbacks.onError('上传失败，请重试')
        return
      }
      if (attachment.value) {
        attachment.value.progress = 100
        attachment.value.stage = 'ready'
        attachment.value.fileId = fileId
        if (fileType) attachment.value.fileType = fileType
        if (resourceUrl) attachment.value.resourceUrl = resourceUrl
      }
    },
    onError(message) {
      toast(message || '上传失败，请重试')
      removeAttachment()
    },
  }

  const handler = props.uploadHandler || defaultUploadHandler
  try {
    await handler(file, kind, callbacks)
  } catch (error) {
    console.error('文件上传失败:', error)
    callbacks.onError('上传失败，请重试')
  }
}

/* ------------------------------------------------------------
   默认上传实现（本项目：fif-getway + fif-resource）
   ------------------------------------------------------------
   外部项目复用本组件时，传入自己的 props.uploadHandler 即可整体替换本函数，
   无需依赖本项目的 store / 接口 / 环境变量。

   流程：
     图片 / 视频：上传资源 → onSuccess
                  （资源由上传 SDK 的 saveResourceInfo 落库，不需要 savDocInfo）
     文件：       上传资源 → 保存文档信息 → 轮询解析状态 → onSuccess
                  （savDocInfo 是后端建解析任务的前置，去掉 docBuildStatus 就拿不到状态）
------------------------------------------------------------ */
async function defaultUploadHandler(file, kind, callbacks) {
  // 懒加载 store
  const stores = await loadStores()
  if (!stores.tokenStore || !stores.userStore) {
    // 内置上传实现依赖接入方 @/store（登录态/token）+ 内网包 fif-getway/fif-resource，
    // 脱离本项目环境无法运行。独立复用请通过 props.uploadHandler 传入自己的上传实现。
    callbacks.onError('未配置上传，请传入 uploadHandler')
    return
  }

  // 检查登录状态
  if (!stores.userStore.isLoggedIn) {
    callbacks.onError('请先登录')
    stores.tokenStore.goLogin()
    return
  }

  // 上传前的进度铺垫（真实进度会覆盖它）
  later(() => callbacks.onProgress(30), 200)
  later(() => callbacks.onProgress(60), 500)
  later(() => callbacks.onProgress(90), 800)

  // 创建文件列表（符合 fif-resource Upload 的参数格式）
  const fileList = [{ file, index: 0 }]

  const getway = await getGetway()
  const { Axios } = await getway.createAxios()
  const { Upload } = await getFifResource()

  // 根据文件类型设置不同的 fileType —— 1: 图片, 2: 文档, 3: 视频
  let fileType = 2
  if (kind === 'image') {
    fileType = 1
  } else if (kind === 'video') {
    fileType = 3
  }

  await Upload(
    {
      fileList,
      appId: 'resc',
      classType: 1,
      fileType: fileType,
      resourceType: 1,
    },
    (progressData) => {
      console.log('上传进度:', progressData)
      if (progressData.progress) {
        callbacks.onProgress(Math.min(95, progressData.progress))
      }
    },
    async (result) => {
      console.log('上传成功:', result)
      if (!result.result?.id) {
        callbacks.onError('上传失败，请重试')
        return
      }

      const resourceId = result.result.id
      callbacks.onProgress(100)

      // 视频 / 图片：saveResourceInfo（上传 SDK 内部调用）已经把资源信息落库了，
      // 不用再走 /dialog/savDocInfo，直接完成。
      if (kind === 'video' || kind === 'image') {
        callbacks.onSuccess(resourceId, result.result.resourceFileType, result.result.previewUrl)
        toast(kind === 'video' ? '视频上传成功' : '图片上传成功')
        return
      }

      /* 文件：必须先 /dialog/savDocInfo 落文档信息，后端才会建解析任务，
         否则紧接着的 docBuildStatus（分片解析）拿不到状态。
         图片/视频不需要解析，所以上面已经提前 return，不走这一步。 */
      const saved = await saveDocInfo({
        id: resourceId,
        resourceName: result.result.resourceName,
        resourceUrl: result.result.previewUrl,
        resourceFileType: result.result.resourceFileType,
        resourceSize: result.result.resourceSize
      })
      if (!saved) return   // saveDocInfo 内已提示并清附件

      await analyzeDocStatus(resourceId, callbacks)
    },
    Axios
  )
}

/** 保存文档信息（仅文件类型走这里，是后端建解析任务的前置步骤） */
async function saveDocInfo(docInfo) {
  try {
    console.log('[saveDocInfo] 开始保存文档信息:', docInfo)
    // 动态加载 API
    const { default: APIF } = await import('@/api/chatflow.js').catch(() => {
      console.warn('API 模块未找到，默认上传功能不可用')
      return { default: null }
    })

    if (!APIF) {
      toast('上传功能不可用')
      removeAttachment()
      return false
    }

    const res = await APIF.savDocInfo({ data: docInfo })
    console.log('[saveDocInfo] 接口返回:', res)

    if (res.status != 1) {  // 使用 != 而不是 !== (兼容字符串 "1")
      console.error('[saveDocInfo] 接口调用失败, status:', res.status)
      toast(res.message || '保存文件信息失败')
      removeAttachment()
      return false
    }

    // 接口可能返回字符串 "0"，用 != 而非 !==（updateStatus 为 0 表示保存成功）
    if (res.data.updateStatus != 0) {
      console.error('[saveDocInfo] 更新状态异常, updateStatus:', res.data.updateStatus)
      toast(res.data.message || '文件保存失败')
      removeAttachment()
      return false
    }

    console.log('[saveDocInfo] 保存成功, updateStatus:', res.data.updateStatus)
    return true
  } catch (error) {
    console.error('[saveDocInfo] 异常:', error)
    toast('保存文件信息失败')
    removeAttachment()
    return false
  }
}

/** 轮询文档解析状态（默认实现专用，仅文件类型走这里） */
async function analyzeDocStatus(resourceId, callbacks) {
  try {
    console.log('[analyzeDocStatus] 查询解析状态, resourceId:', resourceId)
    // 动态加载 API
    const { default: APIF } = await import('@/api/chatflow.js').catch(() => {
      console.warn('API 模块未找到')
      return { default: null }
    })

    if (!APIF) {
      callbacks.onError('文档解析失败')
      return
    }

    const res = await APIF.docBuildStatus({ data: { id: resourceId } })
    console.log('[analyzeDocStatus] 接口返回:', res)

    if (res.status != 1) {  // 使用 != 而不是 !== (兼容字符串 "1")
      console.error('[analyzeDocStatus] 接口调用失败, status:', res.status)
      callbacks.onError('文档解析失败')
      return
    }

    // 接口可能返回字符串 "1"/"2"，统一转成数字判断（对齐 gest-app-web 的 Number() 处理）
    // FileStatus: 0=失败 1=解析中 2=成功 3=违规 4=违规失效
    const buildStatus = Number(res.data.docBuildStatus)

    // 1 = 解析中，继续轮询
    if (buildStatus === 1) {
      console.log('[analyzeDocStatus] 解析中，1秒后重试')
      setTimeout(() => analyzeDocStatus(resourceId, callbacks), 1000)
      return
    }

    // 2 = 解析成功
    if (buildStatus === 2) {
      console.log('[analyzeDocStatus] 解析成功')
      callbacks.onSuccess(resourceId, res.data.resourceFileType)
      toast('文件上传成功')
    } else {
      // 其他状态视为失败
      console.error('[analyzeDocStatus] 解析失败, buildStatus:', buildStatus)
      callbacks.onError('文档解析失败')
    }
  } catch (error) {
    console.error('[analyzeDocStatus] 异常:', error)
    callbacks.onError('文档解析失败')
  }
}

function onFile(kind, e) {
  const file = e.target.files?.[0]
  e.target.value = ''            // 清空以便同一文件能再次触发 change
  if (!file) return

  const rule = props.upload[kind]
  if (rule?.maxSize && file.size > rule.maxSize) {
    toast(`${rule.label}超过大小上限（${fmtSize(rule.maxSize)}）`)
    return
  }

  clearUploadTimers()
  /* 换文件时回收旧 blobURL，但已发给气泡的那个不能回收（urlShared，见 send()）——
     发完一张图接着换下一张时，上一条消息的缩略图还要显示。 */
  if (attachment.value?.url && !attachment.value.urlShared) {
    URL.revokeObjectURL(attachment.value.url)
  }

  /* 图片留 blobURL 给气泡显示缩略图；视频与文件不需要预览 */
  const url = kind === 'image' ? URL.createObjectURL(file) : ''
  attachment.value = { name: file.name, kind, size: file.size, url, file, stage: 'uploading', progress: 0 }

  /* 附件带来的能力：图片默认切到图生文，工具条直接切换。
     与原型一致：这一步在上传动画开始前就切换，不等就绪 */
  const ap = ATTACHMENT_SKILL[kind]
  if (ap) activeSkillKey.value = ap

  // 所有类型（图片、视频、文件）都走真实上传
  uploadFileToServer(file, kind)
}

/** 就绪态的快捷动作（内容总结 / 文字提取 / 总结）：
 *  记住 action（understand/ocr/summarize）→ 填入预设问题 → 直接发送。
 *  对齐接入方 runAttAction（setBody + send()）：点击即发，action 随附件透传给后端。
 *  注意顺序：先写 action 再 send()，否则 send() 读到的 attachment.action 还是空。
 *
 *  文件的「总结」这里只负责打上 action='summarize' 然后 send ——
 *  send 出的 payload 会带 action + 文件附件，由上层（ChatFlow.onSend）识别
 *  action='summarize' 走 docSummary 轮询这条独立路径，不再走 chat。
 *  图片/视频的快捷动作仍是点击即发、走 chat。 */
function runAttAction(act) {
  const att = attachment.value
  if (!att) return

  /* 文件总结：action 固定 'summarize'（文件 acts 里那个按钮没有 key 字段）。 */
  if (att.kind === 'file' && act.label === '总结') {
    att.action = 'summarize'
  } else {
    att.action = act.key
  }
  setBody(act.question)
  send()
}

/**
 * 归一化「从外部恢复」的附件对象（restore / applyState 两条路都走这里）。
 *
 * 接入方跨页传过来的附件只有 fileId / name / kind / url 这几个业务字段
 * （如首页把它们塞进 URL query，/qa 再拼成对象），没有组件内部的上传状态机字段。
 * 而附件 chip 的转圈条件是 `stage !== 'ready'` —— stage 为 undefined 时恒成立，
 * 表现为「进 /qa 后附件一直转圈，其实早就上传完了」。
 *
 * 能被恢复出来的附件必然已经上传完成（fileId 都拿到了），所以补 stage:'ready'。
 * 已经带了 stage 的原样保留，不覆盖调用方的显式意图。
 */
function normalizeRestoredAttachment(att) {
  if (!att) return att
  return {
    ...att,
    stage: att.stage || 'ready',
    /* progress 只在 uploading 阶段用得上，补 100 是为了万一有代码读它不至于是 undefined */
    progress: att.progress ?? 100,
  }
}

function removeAttachment() {
  const kind = attachment.value?.kind
  clearUploadTimers()
  /* blobURL 要显式回收，否则页面存活期间一直占内存。
     注意：已发出的消息还在用同一个 URL，所以只在「未发送就移除」时回收
     —— urlShared 由 send() 打标，见那里的注释。 */
  if (attachment.value?.url && !attachment.value.urlShared) {
    URL.revokeObjectURL(attachment.value.url)
  }
  attachment.value = null
  /* 能力是随附件进来的：关掉附件就一并退出，回到初始态 */
  if (kind && activeSkillKey.value === ATTACHMENT_SKILL[kind]) activeSkillKey.value = ''
}

/* ---------- 发送 ---------- */
function send() {
  if (!canSend.value) return
  /* 短请求未回时不许再发：按钮已 disabled，但回车那条路绕过按钮，
     不挡会重复发起（接入方那边就是重复调意图识别接口） */
  if (props.loading) return
  /* 接入方前置守卫（如未登录跳登录）。放在 canSend 之后 ——
     按钮没点亮时本来就不该触发任何接入方逻辑；点亮后点击/回车都会走到这里，
     两条路共用这一道门。 */
  if (!allowInteract()) return
  const q = text.value.trim()
  const att = attachment.value
  const skillKey = activeSkillKey.value

  /* 图片单独成一条无气泡消息，答案由紧随其后的文字消息触发；
     视频与文件跟着文字走脚注，不单独占一条 */
  const isMedia = att?.kind === 'image'

  // 构建附件数据：所有类型都传 fileId（如果有的话）
  let attachmentData = att
  if (att?.fileId) {
    // 上传成功后的附件：传必要字段 + fileId
    attachmentData = {
      name: att.name,
      kind: att.kind,
      size: att.size,
      url: att.url, // 图片需要 url 用于显示缩略图
      /* chat 的 fileIds 统一用上传得到的 resourceId，不用 docSummary 返回的 id。
         docSummary 只承担「总结完成才放行发送」的时序约束，其返回 fileId 暂不使用。 */
      fileId: att.fileId,
      fileType: att.fileType,
      resourceUrl: att.resourceUrl,
      action: att.action // 快捷按钮点选的操作：understand / ocr / summarize（未点则 undefined）
    }
  }

  emit('send', {
    text: q,
    model: model.value,
    knowledgeBases: [...kbs.value],
    webSearch: webSearch.value,
    attachment: attachmentData,
    isMedia,
    /* 无附件时别塞空串，否则脚注会空画一个回形针 */
    files: !att || isMedia ? [] : [{
      name: att.name,
      /* chat 的 fileIds 用上传 resourceId，与 attachmentData.fileId 同口径。
         docSummary 返回的 id 不用在 chat 里。 */
      fileIds: att.fileId,
      fileType: att.fileType,
      size: att.size,
      /* kind + url 要带上：视频脚注点击要直接打开资源地址，
         走 /agent/preview 那条文档预览路由是打不开的 */
      kind: att.kind,
      url: att.resourceUrl || att.url
    }],
    skill: skillKey,
    skillConfSummary: skillKey ? skillParamSummary(paramsOf(skillKey)) : '',
    /* 技能结构化参数（中文键 {音色,语速,...} / {比例,风格,...}）：
       文字转语音、文生图等据此走各自的合成/生图分支 */
    skillParams: skillKey ? { ...paramsOf(skillKey) } : null,
    action: att?.action // 透传给父组件（附件操作类型）
  })

  /* action 是「本次快捷动作」的一次性语义（understand/ocr/summarize），
     emit 出去即失效。必须清掉 —— 附件在 send 后是保留的，不清的话
     下一轮手动输入发送时 payload.action 还带着 'summarize'，
     ChatFlow 会误判成「又点了一次总结」而走 docSummary 而非 chat。 */
  if (att) att.action = undefined

  /* 标记「这个附件的 blobURL 已经交给消息气泡了」。
     附件在 send 后是保留的（见下方注释），所以卸载时 attachment.value 仍挂着
     同一个 blobURL；气泡里的 <img :src> 用的正是它。新建对话时输入框会被
     卸载重建，onBeforeUnmount 若无条件 revoke，已发出那条消息的图片立刻变破图。 */
  if (att) att.urlShared = true

  /* clearOnSend=false 时保留原文：门户首页这类「发送后先弹意图窗」的场景，
     用户可能取消或改主意，清了还得靠接入方回填，会看到清空又冒出来的闪动。 */
  if (props.clearOnSend) {
    setBody('')
  }

  /* 附件发送后**保留**：同一个文档/图片往往要连着追问好几轮，
     清掉的话用户得重新上传一次。附件 chip、「已就绪」占位文案、
     快捷动作按钮都跟着留在输入框里，可以直接接着问。
     要换文件或不想带附件时，点 chip 上的 × 手动移除（removeAttachment）。

     技能态同样不清：与原型一致，发送后仍停留在当前能力，连续追问不用重选。

     注意不能在这里回收图片的 blobURL —— 消息气泡还在用同一个 URL 显示缩略图，
     回收了气泡里的图会裂。真正的回收时机在 removeAttachment 与 onFile 换文件时。 */
}

/* ---------- 输入区渲染（对齐原型 renderAsk/askText/eatAt）----------
   知识库标签是不可编辑的芯片，正文是唯一的文本节点，芯片全部排在正文之前。
   这段 DOM 完全手工管理，不进 Vue 的 vdom：模板里的 .cf-ask 不声明任何子节点，
   Vue diff 不会碰它，重画、光标保留都靠这里的原生 DOM API 完成。 */

/** 芯片后紧跟的 NBSP 是分隔符，不算正文；用户紧跟着打字时也要剥掉这一个字符 */
function bodyOf(node) {
  let t = node.textContent || ''
  if (node.previousSibling && node.previousSibling.nodeType === 1 && t.charAt(0) === NBSP) {
    t = t.slice(1)
  }
  return t
}

/** 只取正文：跳过芯片节点与其后的分隔符 */
/* contenteditable 里换行有三种 DOM 形态，读文本时都要认：
     1. <br>                     —— 按 Enter（shift+Enter）产生
     2. <div>行</div><div>行</div> —— 粘贴多行文本时浏览器常这么包（Chrome）
     3. <p>行</p>                 —— 同上，部分浏览器/粘贴源用 p

   原实现只遍历直接子节点、且只认文本节点与 <br>，块级元素整个被跳过 ——
   表现为「粘贴带换行的文字，发送后只剩第一行」。
   现在递归取全部文本，并在块级元素之间补换行。 */
const BLOCK_TAGS = new Set(['DIV', 'P', 'LI', 'TR', 'SECTION', 'ARTICLE', 'BLOCKQUOTE', 'PRE'])

function collectText(node, out) {
  node.childNodes.forEach((n) => {
    if (n.nodeType === 3) {
      out.push(bodyOf(n))
      return
    }
    if (n.nodeType !== 1) return
    if (n.tagName === 'BR') {
      out.push('\n')
      return
    }
    /* 知识库芯片：它是 contenteditable=false 的 span，文本形如「@某知识库」。
       芯片不属于正文，由 kbs 数组单独承载，读正文时要跳过，
       否则发送的内容里会混进「@xxx」。 */
    if (n.classList?.contains('cf-kb-tag')) return

    const isBlock = BLOCK_TAGS.has(n.tagName)
    /* 块级元素前后各补换行，随后在 askText 里把连续换行折叠成一个。
       两边都要补的原因：Chrome 粘贴多行时**第一行是裸文本、后续行才包 div**
         「经济学思政案」<div>例库</div><div>例库</div>
       只在结束后补的话，裸文本与第一个 div 之间没有分隔，两行会粘成
       「经济学思政案例库」。
       折叠交给 askText 统一做，这里不判断前一项是不是换行 —— 那种判断
       在嵌套结构里不可靠（out 的最后一项可能来自更深层的递归）。 */
    if (isBlock) out.push('\n')
    collectText(n, out)
    if (isBlock) out.push('\n')
  })
}

function askText() {
  const el = askEditor.value
  if (!el) return ''
  const parts = []
  collectText(el, parts)
  return parts
    .join('')
    /* 先把 NBSP 统一成普通空格，后面只处理一种空白字符。
       NBSP 有两个来源：芯片后的分隔符、浏览器在换行处插的占位符 ——
       前者该变成空格，后者紧贴换行、会被下一步一并清掉。 */
    .split(NBSP)
    .join(' ')
    /* 折叠换行：把「连续换行 + 其两侧的空格」压成单个 \n。
       collectText 对块级元素前后都补了 \n，这里统一收口，既去掉
       `<div>A</div><div>B</div>` 产生的 A\n\nB 空行，也清掉换行处的
       占位空格（否则表现为「行尾/行首多一个空格」）。 */
    .replace(/[ \t]*\n[ \t\n]*/g, '\n')
    /* 首尾的换行与空格都是结构产物，不是用户内容 */
    .replace(/^\n+/, '')
    .replace(/[\n ]+$/, '')
}

function caretToEnd() {
  const el = askEditor.value
  if (!el || document.activeElement !== el) return
  const r = document.createRange()
  const s = window.getSelection()
  r.selectNodeContents(el)
  r.collapse(false)
  s.removeAllRanges()
  s.addRange(r)
}

/** 输入框是否处于聚焦态：占位文字只在失焦时显示，聚焦态即使为空也不显示，
 *  避免用户正在打字时占位文字在旁边晃 */
const askFocused = ref(false)

/** 正文为空、且未聚焦时才显示占位（芯片不算正文，有芯片时占位跟着排在芯片后面）。
 *  不依赖 contenteditable 的 :empty：删空后浏览器常残留一个空文本节点或 <br>，
 *  :empty 就再也不命中了，占位会跟着消失——data 属性不受这个影响 */
function syncAskPh() {
  const el = askEditor.value
  if (el) el.dataset.showPh = (!text.value.trim() && !askFocused.value) ? 'true' : 'false'
}

function onAskFocus() {
  askFocused.value = true
  syncAskPh()
}

function onAskBlur() {
  askFocused.value = false
  /* 删空后 contenteditable 常残留一个 <br>；askText() 把它读成字面的 '\n' 存进
     text.value，那次 renderAsk(false, true) 又把这个 '\n' 原样写回新文本节点——
     .cf-ask 是 white-space:pre-wrap，这个字符换行会被渲染出来，把紧跟其后的
     ::after 占位文字挤到第二行。用 setBody('') 显式清零，不能只 renderAsk，
     否则读的还是这份带 '\n' 的旧 text.value */
  if (!text.value.trim()) setBody('')
  syncAskPh()
}

/** 重画：芯片串 + 一个正文文本节点。
 *  keepCaret 时尽量把光标留在正文原来的相对位置；
 *  force 表示正文以 text.value 为准（程序化改值，比如语音听写/字数截断），
 *  不采信 DOM 里可能还没同步的旧文本节点。 */
function renderAsk(keepCaret, force) {
  const el = askEditor.value
  if (!el) return
  let saved = null
  let off = 0
  if (keepCaret && document.activeElement === el) {
    const sel = window.getSelection()
    if (sel && sel.rangeCount) saved = sel.getRangeAt(0).cloneRange()
  }

  let body
  if (!force) {
    const parts = []
    let hasText = false
    el.childNodes.forEach((n) => {
      if (n.nodeType !== 3) return
      const b = bodyOf(n)
      if (!b) return
      hasText = true
      if (saved && saved.startContainer === n) {
        off = parts.join('').length
          + Math.max(0, saved.startOffset - ((n.textContent || '').length - b.length))
      }
      parts.push(b)
    })
    body = hasText ? parts.join('') : text.value
  } else {
    body = text.value
  }

  el.innerHTML = ''
  /* scoped 样式给模板渲染的元素自动打 data-v-xxxx 属性来限定选择器；
     这两个 span 是手工 createElement 出来的，Vue 不会管，样式会全局透传
     除非手动补上同一个属性 —— 从 el 自身（模板渲染、已带该属性）上抄一份 */
  const scopeAttr = Array.prototype.find.call(el.attributes, (a) => a.name.startsWith('data-v-'))?.name
  kbs.value.forEach((kb) => {
    const tag = document.createElement('span')
    tag.className = 'cf-kb-tag'
    tag.contentEditable = 'false'
    tag.dataset.kbId = kb.id
    tag.title = `点击移除「${kbLabel(kb)}」`
    if (scopeAttr) tag.setAttribute(scopeAttr, '')
    const txt = document.createElement('span')
    txt.className = 'cf-kb-tag-t'
    txt.textContent = `@${kbLabel(kb)}`
    if (scopeAttr) txt.setAttribute(scopeAttr, '')
    tag.appendChild(txt)
    tag.addEventListener('click', () => removeKb(kb.id))
    el.appendChild(tag)
    el.appendChild(document.createTextNode(NBSP))
  })
  const tn = document.createTextNode(body || '')
  el.appendChild(tn)
  text.value = body || ''

  if (saved && document.activeElement === el) {
    try {
      const s2 = window.getSelection()
      const r2 = document.createRange()
      r2.setStart(tn, Math.min(off, (tn.textContent || '').length))
      r2.collapse(true)
      s2.removeAllRanges()
      s2.addRange(r2)
    } catch (err) {
      caretToEnd()
    }
  } else if (!keepCaret) {
    caretToEnd()
  }
  syncAskPh()
}

/** 程序化写正文（语音听写、字数截断、快捷动作填充问题……）：
 *  跟用户手打不同，DOM 里的旧文本已经过时，必须 force 重画 */
function setBody(v) {
  text.value = v
  renderAsk(false, true)
}

function removeKb(id) {
  kbs.value = kbs.value.filter((k) => k.id !== id)
}
/* kbs 的任何变化（新增、取消勾选、清空、@ 选中）都从这里统一驱动重画，
   不必在每个改动点都记得手动调用 —— 单一出口，不会漏 */
watch(kbs, () => { renderAsk(true) }, { deep: true })

/** 行首或空格后打 @ → 唤起知识库浮层，贴着光标弹出；
 *  contenteditable 下用 Range 直接量光标像素坐标，不需要 textarea 那套镜像 div 估算 */
function checkAt() {
  if (!props.features.knowledgeBase) return
  /* 打 @ 是独立于按钮的第二条入口，没权限时同样要挡住 ——
     只藏 KbSelector 按钮的话，用户打个 @ 还是能把面板唤出来 */
  if (!kbAllowed.value) return
  const sel = window.getSelection()
  if (!sel || !sel.rangeCount) return
  const r = sel.getRangeAt(0)
  if (!r.collapsed) return
  const node = r.startContainer
  if (node.nodeType !== 3) return
  const t = node.textContent || ''
  const off = r.startOffset
  const ch = t.charAt(off - 1)
  if (ch !== '@' && ch !== '＠') return
  const prev = off >= 2 ? t.charAt(off - 2) : ''
  if (prev !== '' && prev !== ' ' && prev !== NBSP) return
  /* 未登录：@ 也是一条交互入口，挡在唤起浮层之前。
     放在这里而不是函数开头 —— 前面那些 return 只是「这次按键不是 @」，
     不算用户意图，提前跳登录会在正常打字时误触发 */
  if (!allowInteract()) return
  let rect = r.getClientRects()[0] || r.getBoundingClientRect()
  if (!rect || (!rect.left && !rect.top)) rect = askEditor.value?.getBoundingClientRect()
  if (!rect) return
  kbAtMode.value = true
  kbSelector.value?.show({ left: rect.left, top: rect.top })
}

/** 消费触发用的 @：从后往前找最近一个 @/＠ 删掉（只在文本节点里找，不碰芯片） */
function eatAt() {
  const el = askEditor.value
  if (!el) return
  const nodes = Array.prototype.filter.call(el.childNodes, (n) => n.nodeType === 3)
  for (let i = nodes.length - 1; i >= 0; i--) {
    const t = nodes[i].textContent || ''
    const idx = Math.max(t.lastIndexOf('@'), t.lastIndexOf('＠'))
    if (idx >= 0) {
      nodes[i].textContent = t.slice(0, idx) + t.slice(idx + 1)
      text.value = askText()
      return
    }
  }
}

/** 知识库选中回调：@ 唤起时吃掉触发的 @；芯片本身由 kbs 的 watch 统一重画 */
function onKbPick({ atMode }) {
  if (atMode) eatAt()
  kbAtMode.value = false
}

function onInput() {
  text.value = askText()
  const lim = effectiveMaxLength.value
  if (lim && text.value.length > lim) {
    setBody(text.value.slice(0, lim))
    toast(`当前技能单次最多 ${lim} 字`)
    return
  }
  syncAskPh()
  checkAt()
}

/** 找光标紧邻（前/后）的知识库芯片。芯片是 contentEditable=false，浏览器按键会把
 *  它整块从 DOM 里删掉但不会通知 Vue —— kbs 状态和芯片显示会错位。
 *  所以这里先探出芯片，交给 removeKb 走统一出口，再阻止浏览器的默认删除。 */
function findAdjacentChip(dir) {
  const el = askEditor.value
  const sel = window.getSelection()
  if (!el || !sel || !sel.rangeCount) return null
  const r = sel.getRangeAt(0)
  if (!r.collapsed) return null
  const { startContainer: node, startOffset: offset } = r
  const isChip = (n) => n?.nodeType === 1 && n.classList?.contains('cf-kb-tag')
  /* 芯片后紧跟的 NBSP 分隔符是空节点；contenteditable 有时还会在光标处
     多留一个真正的空文本节点（textContent === ''），两种都跳过 */
  const isSkippable = (n) => n?.nodeType === 3 && (n.textContent === '' || n.textContent === NBSP)

  let cur
  if (dir === 'back') {
    if (node.nodeType === 3 && offset === 0) cur = node.previousSibling
    else if (node === el) cur = el.childNodes[offset - 1]
    else return null
    while (isSkippable(cur)) cur = cur.previousSibling
  } else {
    if (node.nodeType === 3 && offset === (node.textContent || '').length) cur = node.nextSibling
    else if (node === el) cur = el.childNodes[offset]
    else return null
    while (isSkippable(cur)) cur = cur.nextSibling
  }
  return isChip(cur) ? cur : null
}

/** 非折叠选区（鼠标拖选、Ctrl+A 全选）里可能整块吞掉知识库芯片——
 *  浏览器默认删除只会动 DOM，同样不会通知 kbs。先摘出选区覆盖到的芯片 id，
 *  从 kbs 里过滤掉，再手动删除选区内容，替浏览器默认行为收尾。 */
function deleteSelectionWithChips(r) {
  const el = askEditor.value
  if (!el) return false
  const chips = el.querySelectorAll('.cf-kb-tag')
  const removedIds = Array.prototype.filter
    .call(chips, (chip) => r.intersectsNode(chip))
    .map((chip) => chip.dataset.kbId)
  if (!removedIds.length) return false
  r.deleteContents()
  kbs.value = kbs.value.filter((k) => !removedIds.includes(k.id))
  text.value = askText()
  syncAskPh()
  return true
}

function onKeydown(e) {
  /* Enter 发送，Shift+Enter 手动插入换行（contenteditable 不会自动处理）。
     输入法组合中的 Enter（isComposing）不能当发送，否则中文选词就发出去了 */
  if (e.key === 'Enter') {
    e.preventDefault()
    if (e.shiftKey) {
      document.execCommand('insertLineBreak')
      text.value = askText()
      syncAskPh()
    } else if (!e.isComposing) {
      send()
    }
    return
  }
  if (e.key === 'Backspace' || e.key === 'Delete') {
    const sel = window.getSelection()
    const r = sel && sel.rangeCount ? sel.getRangeAt(0) : null
    if (r && !r.collapsed) {
      if (deleteSelectionWithChips(r)) e.preventDefault()
      return
    }
    const chip = findAdjacentChip(e.key === 'Backspace' ? 'back' : 'forward')
    if (chip) {
      e.preventDefault()
      removeKb(chip.dataset.kbId)
    }
  }
}

/** 粘贴只取纯文本，避免带进外部样式或结构 */
function onPaste(e) {
  e.preventDefault()
  const t = (e.clipboardData || window.clipboardData).getData('text') || ''
  document.execCommand('insertText', false, t.replace(/\r/g, ''))
  text.value = askText()
  syncAskPh()
}

const count = computed(() => text.value.length)
const overLimit = computed(() =>
  effectiveMaxLength.value > 0 && count.value > effectiveMaxLength.value)

/* 技能带字数上限时，超出的部分截断（如切到文字转语音时正文已经超过 250 字） */
watch(effectiveMaxLength, (lim) => {
  if (lim && text.value.length > lim) {
    setBody(text.value.slice(0, lim))
    toast(`当前技能单次最多 ${lim} 字`)
  }
})

/* ---------- 语音输入 ----------
   使用真实的 ASR（语音识别）服务，通过 AssistantChat 工具类连接科大讯飞语音识别。
   录音中逐字把转写结果落进输入框，实时显示；
   再次点击或松开空格停止。按住空格仅在焦点不在输入框时生效。 */

// 创建 AssistantChat 实例（懒加载）
let assistantChat = null
async function getAssistantChat() {
  if (!assistantChat) {
    const AssistantChatClass = await loadAssistantChat()
    if (!AssistantChatClass) {
      return null
    }
    const Authorization = sessionStorage.getItem('Authorization') ?? ''
    const EncryptCode = sessionStorage.getItem('encryptCode') ?? ''
    const CurEnv = getConfig('pluginPath')
    const SendMsgWebscroketUrL = getConfig('wssPath')
    assistantChat = new AssistantChatClass({ Authorization, EncryptCode, CurEnv, SendMsgWebscroketUrL })
  }
  return assistantChat
}

const micGranted = ref(false)
const micPermOpen = ref(false)
const recording = ref(false)
const recSeconds = ref(0)
let recClockTimer = null
let spaceHeld = false
let recBaseText = '' // 录音开始时的初始文本

function recFmt(s) {
  const m = Math.floor(s / 60)
  const ss = s % 60
  return `${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}
const recTimeLabel = computed(() => recFmt(recSeconds.value))

function clearRecTimers() {
  clearInterval(recClockTimer); recClockTimer = null
}

// 语音识别事件处理函数
function handleSoundTextChange(asrText) {
  if (!recording.value) return

  // 将转写文字追加到初始文本后
  const v = recBaseText + asrText
  const lim = effectiveMaxLength.value

  /* 超上限：截断并停录。这里传 stopRec(true, false) 抑制它自己的「转写完成」提示——
     两条 toast 连发时单例会互相顶掉，用户只看到一闪，且「转写完成」会盖住
     真正需要知道的「超字数」原因。 */
  if (lim && v.length > lim) {
    setBody(v.slice(0, lim))
    stopRec(true, false)
    toast(`当前技能单次最多 ${lim} 字`)
    return
  }

  setBody(v)
}

function handleSoundStateChange(data) {
  console.log('语音识别状态:', data)
  if (data.text === '已关闭' && recording.value) {
    stopRec(false)
  }
}

async function startRec() {
  if (recording.value) return

  // 检查语音 SDK 是否可用
  const chat = await getAssistantChat()
  if (!chat) {
    toast('语音功能不可用，请检查配置')
    return
  }

  // 注册事件监听器（如果还没注册）
  if (chat.on && !chat._listenersRegistered) {
    chat.on('soundTextChange', handleSoundTextChange)
    chat.on('soundStateChange', handleSoundStateChange)
    chat._listenersRegistered = true
  }

  recording.value = true
  recSeconds.value = 0
  recClockTimer = setInterval(() => { recSeconds.value++ }, 1000)

  // 保存录音开始时的初始文本
  recBaseText = text.value ? `${text.value.replace(/\s+$/, '')} ` : ''

  toast('麦克风已开启，正在实时转写…')

  try {
    // 手动调用接口获取语音识别配置
    const { default: APIF } = await import('@/api/chatflow.js').catch(() => ({ default: null }))

    if (!APIF) {
      throw new Error('API 模块未找到')
    }

    const res = await APIF.getConfigInfo({ data: { abilityType: 1 } })

    if (res?.data) {
      // 使用获取到的配置启动 ASR
      const abilityUrl = res.data.abilityUrl || res.data.url
      const abilityAppId = res.data.abilityAppId || res.data.appId
      chat.asrObj.start(abilityUrl, abilityAppId)
    } else {
      throw new Error('获取语音识别配置失败')
    }
  } catch (error) {
    console.error('启动语音识别失败:', error)
    toast('语音识别服务启动失败，请稍后重试')
    stopRec(false)
  }
}

/* notify=false：由调用方自己给提示（如超字数），这里不再弹「转写完成」把它顶掉 */
async function stopRec(done, notify = true) {
  if (!recording.value) return

  // 停止语音识别
  try {
    const chat = await getAssistantChat()
    if (chat) {
      chat.asrObj.stop()
    }
  } catch (error) {
    console.error('停止语音识别失败:', error)
  }

  clearRecTimers()
  recording.value = false
  if (notify) toast(done ? '转写完成，可继续编辑或直接发送' : '已停止语音输入')
  askEditor.value?.focus()
}

function requestMic() {
  if (micGranted.value) { startRec(); return }
  micPermOpen.value = true
}
function allowMic() {
  micGranted.value = true
  micPermOpen.value = false
  startRec()
}
function denyMic() {
  micPermOpen.value = false
  toast('未获得麦克风权限，语音输入不可用；可在浏览器地址栏重新授权')
}
function toggleVoice() {
  if (recording.value) { stopRec(false); return }
  requestMic()
}

/** 按住空格：仅在焦点不在输入框时生效，避免影响正常打字 */
function onGlobalKeydown(e) {
  if (e.key !== ' ' && e.code !== 'Space') return
  const tag = e.target?.tagName || ''
  if (tag === 'TEXTAREA' || tag === 'INPUT' || e.target?.isContentEditable) return
  e.preventDefault()
  if (spaceHeld || recording.value) return
  spaceHeld = true
  requestMic()
}
function onGlobalKeyup(e) {
  if (e.key !== ' ' && e.code !== 'Space') return
  if (!spaceHeld) return
  spaceHeld = false
  stopRec(false)
}

onMounted(() => {
  /* 挂载时先画一遍：这时 kbs 还是空数组，主要是把初始的空文本节点铺好，
     让 :empty 占位样式和后续 renderAsk 的「找旧文本节点」逻辑有东西可读 */
  renderAsk()
  if (!props.features.voiceInput) return
  window.addEventListener('keydown', onGlobalKeydown)
  window.addEventListener('keyup', onGlobalKeyup)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
  window.removeEventListener('keyup', onGlobalKeyup)
  clearRecTimers()
  clearUploadTimers()
  /* 未发送就卸载：回收 blobURL。
     已发送过的不回收 —— 消息气泡还在用同一个 URL（send 后附件刻意保留，
     所以这里仍拿得到它）。新建对话会卸载重建输入框，无条件回收会让
     刚发出那条消息的图片变成破图。与 removeAttachment 的口径一致。 */
  if (attachment.value?.url && !attachment.value.urlShared) {
    URL.revokeObjectURL(attachment.value.url)
  }
})

/** 供父级注入文本（点推荐问、点追问） */
defineExpose({
  fill(q, autoSend = true) {
    setBody(q)
    if (autoSend) send()
    else askEditor.value?.focus()
  },
  focus: () => askEditor.value?.focus(),
  /**
   * 清空输入框（正文 + 附件槽，知识库芯片与技能态保留）。
   *
   * 配 clearOnSend=false 用：那种场景下发送不清空，接入方在确认真的要跳走时
   * 再调这个。附件的 blobURL 不回收 —— 与 send() 内的清空口径一致，
   * 可能已被消息气泡引用。
   */
  clear() {
    setBody('')
    attachment.value = null
  },
  /**
   * 选中一个知识库（供 ChatFlow 从空态知识库卡片调用，等同于 @ 唤起选中）。
   * 与 KbSelector.toggle 同口径：已选则忽略、超上限提示、否则追加 {id,name}。
   * kbs 的 watch 会统一把芯片重画进输入框。
   * @param {{id:string,name:string}} kb
   */
  selectKb(kb) {
    if (!kb || !kb.id) return
    if (kbs.value.some((k) => k.id === kb.id)) return
    if (kbs.value.length >= KB_MAX) {
      toast(`最多选择 ${KB_MAX} 个知识库`)
      return
    }
    kbs.value = [...kbs.value, { id: kb.id, name: kb.name }]
  },
  /**
   * 只选中模型、不发送。
   * 模型广场「立即体验」跳转 /qa（只带 modelId、没有 question）时，输入框默认渲染该模型。
   * @param {string} modelId
   */
  selectModel(modelId) {
    if (!modelId) return
    const idx = models.value.findIndex((m) => m.id === modelId)
    if (idx !== -1 && idx !== modelIdx.value) modelIdx.value = idx
  },
  /**
   * 读取当前联网搜索开关状态。
   * 供 ChatFlow 重新生成时使用：重出答案要按输入区当前的开关状态取检索，
   * 而不是沿用上一轮发送时的快照（否则「关了联网再重新生成」仍会联网、
   * 「开了联网再重新生成」仍不联网）。
   * @returns {boolean}
   */
  getWebSearch() {
    return webSearch.value
  },
  /**
   * 从外部恢复完整的发送参数并立即发送（首页 hero 输入框选好模式/模型/知识库/附件后，
   * 经智能体弹窗跳转到 /qa 时用）。一次性把每个参数落到 composer 的响应式状态，再走 send()，
   * 使这一轮以对应模式（文生图/图生文/文字转语音/普通）触发。
   * @param {{text?, model?, knowledgeBases?, webSearch?, skill?, skillParams?, attachment?}} params
   */
  fillAndSendWithParams(params = {}) {
    // 文本
    if (params.text) setBody(params.text)

    // 模型：按 id 定位下拉项
    if (params.model?.id) {
      const idx = models.value.findIndex((m) => m.id === params.model.id)
      if (idx !== -1 && idx !== modelIdx.value) modelIdx.value = idx
    }

    // 知识库：直接替换选中数组（watch 会把芯片重画进输入框）
    if (Array.isArray(params.knowledgeBases) && params.knowledgeBases.length) {
      kbs.value = normalizeKbs(params.knowledgeBases)
    }

    // 联网搜索
    if (params.webSearch !== undefined) webSearch.value = !!params.webSearch

    // 技能 + 技能参数：技能存在才激活，参数并进该技能的 skillParams
    if (params.skill && skills.value[params.skill]) {
      activeSkillKey.value = params.skill
      if (params.skillParams && typeof params.skillParams === 'object') {
        // paramsOf 确保该技能有一份默认参数对象，再用传入值覆盖已知字段
        const cur = paramsOf(params.skill)
        Object.keys(params.skillParams).forEach((k) => {
          if (k in cur) cur[k] = params.skillParams[k]
        })
      }
    }

    // 附件
    if (params.attachment) attachment.value = normalizeRestoredAttachment(params.attachment)

    /* 跨页快捷动作（首页点「总结」跳 /qa）：action 是「待执行」的意图，
       写到附件上，send() 里 payload.action 才会带上，ChatFlow 据此走 docSummary。
       action 只作用这一轮，send() 内部 emit 后会清掉。 */
    if (params.action && attachment.value) attachment.value.action = params.action

    // 立即发送：send() 读取上面所有响应式状态，按当前模式触发这一轮
    send()
  },
  /**
   * 只恢复选择态、不发送、不填文本。
   * 用于空态 composer 发送后切到底部 composer：两个是独立实例，v-if 切换会让
   * 底部这个全新挂载、本地状态回默认，靠这个把上一轮的模型/联网/知识库/技能同步过来，
   * 让底部输入框和新建对话页选好的状态一致。
   * @param {{model?, knowledgeBases?, webSearch?, skill?, skillParams?, attachment?}} state
   */
  applyState(state = {}) {
    // 模型：按 id 定位下拉项
    if (state.model?.id) {
      const idx = models.value.findIndex((m) => m.id === state.model.id)
      if (idx !== -1 && idx !== modelIdx.value) modelIdx.value = idx
    }

    // 知识库：替换选中数组（watch 会把芯片重画进输入框）
    if (Array.isArray(state.knowledgeBases)) {
      kbs.value = normalizeKbs(state.knowledgeBases)
    }

    // 联网搜索
    if (state.webSearch !== undefined) webSearch.value = !!state.webSearch

    // 技能 + 技能参数：技能存在才激活，参数并进该技能的 skillParams
    if (state.skill && skills.value[state.skill]) {
      activeSkillKey.value = state.skill
      if (state.skillParams && typeof state.skillParams === 'object') {
        const cur = paramsOf(state.skill)
        Object.keys(state.skillParams).forEach((k) => {
          if (k in cur) cur[k] = state.skillParams[k]
        })
      }
    }

    /* 附件：空态 composer → 底部 composer 是换了实例，不接过来就丢了。
       与 restore() 同口径，只是这条路不发送。
       但 action 要剥掉 —— 这是「发送之后」的状态同步，action 是已消费的
       一次性意图（尤其 'summarize'），带过去会让下一轮手动输入被误判成
       「又点了一次总结」。restore() 是「发送之前」的意图恢复，那才要保留。 */
    if (state.attachment) {
      attachment.value = {
        ...normalizeRestoredAttachment(state.attachment),
        action: undefined,
      }
    }
  },
})
</script>

<template>
  <div class="cf-composer-wrap">
    <!-- 图标雪碧：CfIcon 引用 #cf-i-*，本组件自带注入 so 独立/散件挂载也有图标 -->
    <IconSprite />
    <!-- 能力舌头：选中技能后贴在输入卡上方 -->
    <SkillTray
      v-if="features.skills && activeSkill"
      :skill="activeSkill"
      @close="exitSkill"
    />

    <!-- 输入卡上方扩展点（技能托盘同层）：接入方放快捷开关/场景切换等，通常要读写动态入参。
         不订阅则不出现，不影响输入卡布局。 -->
    <slot name="composer-above" :params="params" :set-params="setParams" />

    <div class="cf-composer" :class="{ 'is-rec': recording }">
      <!-- 录音态：编辑区上方加一条波形 + 计时，编辑区仍在，实时转写文字照样可见 -->
      <div v-if="recording" class="cf-rec-strip" aria-hidden="true">
        <span class="cf-rec-wave">
          <i v-for="n in 28" :key="n" :style="{
            animationDelay: `${-(n % 7) * 0.12}s`,
            animationDuration: `${0.72 + (n % 5) * 0.09}s`,
          }" />
        </span>
        <span class="cf-rec-time">{{ recTimeLabel }}</span>
        <span class="cf-rec-tip">正在聆听…</span>
      </div>

      <div class="cf-ask-wrapper">
        <div
          ref="askEditor"
          class="cf-ask"
          contenteditable="true"
          role="textbox"
          aria-multiline="true"
          :data-ph="busy ? '正在生成回答中…' : (attPlaceholderMsg || activeSkill?.ph || placeholder)"
          :aria-label="placeholder"
          @input="onInput"
          @keydown="onKeydown"
          @paste="onPaste"
          @focus="onAskFocus"
          @blur="onAskBlur"
        />

        <!-- 右下角字数计数隐藏，仅保留超限校验（截断 + toast） -->
        <span
          v-if="false"
          class="cf-ask-count" :class="{ 'is-over': overLimit }"
        >{{ count }} / {{ effectiveMaxLength }}</span>
      </div>

      <div class="cf-bar">
        <!-- ---------- 附件 ---------- -->
        <span v-if="hasAttachments" class="cf-plus">
          <button
            ref="plusBtnRef"
            class="cf-plus-btn cf-tap40"
            :class="{ 'is-open': plusOpen, 'is-disabled': busy || attachBlockedBySkill }" type="button"
            :disabled="busy"
            :title="attachBlockedTip || undefined"
            :aria-disabled="attachBlockedBySkill || undefined"
            :aria-expanded="plusOpen" aria-haspopup="true" aria-label="添加图片、视频或文件"
            @click="togglePlusMenu"
          ><CfIcon name="plus" :size="18" /></button>

          <span v-if="plusOpen" class="cf-catch" @click="plusOpen = false" />
          <span v-if="plusOpen" class="cf-plus-menu" :style="plusMenuStyle" role="menu">
            <!-- 非多模态模型：菜单顶部红色提示，说明为何图片/视频置灰（对齐接入方 /qa） -->
            <div v-if="!supportsMultimodal && multimodalTip" class="cf-plus-tip">
              {{ multimodalTip }}
            </div>
            <button
              v-for="(rule, kind) in upload" :key="kind"
              v-show="attachmentConfig[kind]"
              class="cf-plus-item"
              :class="{ 'is-disabled': !supportsMultimodal }"
              type="button"
              role="menuitem"
              @click="pickUpload(kind)"
            >
              <i><CfIcon :name="kind === 'file' ? 'clip' : kind" :size="17" /></i>
              <span><b>{{ rule.label }}</b><span>{{ rule.hint }}</span></span>
            </button>
          </span>

          <input ref="upImage" type="file" hidden
                 :accept="upload.image?.accept" @change="onFile('image', $event)">
          <input ref="upVideo" type="file" hidden
                 :accept="upload.video?.accept" @change="onFile('video', $event)">
          <input ref="upFile" type="file" hidden
                 :accept="upload.file?.accept" @change="onFile('file', $event)">

          <span class="cf-bar-sep" aria-hidden="true" />
        </span>

        <!-- 中段：恒为单行，放不下由这里的文字省略让位。
             基础态显示模型 + 知识库 + 联网；技能态/挂附件时模型与联网让位给参数下拉 -->
        <span class="cf-bar-mid">
          <ModelSelector
            v-if="features.modelSelect && inBaseMode && models.length"
            :models="models"
            v-model:index="modelIdx"
            :before-interact="beforeInteract"
          />

          <KbSelector
            v-if="features.knowledgeBase && inBaseMode && kbAllowed"
            ref="kbSelector"
            :disabled="busy"
            :tree="meta.knowledgeBases ?? {}"
            :categories="kbCategoriesAllowed"
            :selected="kbs"
            :before-interact="beforeInteract"
            @update:selected="kbs = $event"
            @over-max="(n) => toast(`最多选择 ${n} 个知识库`)"
            @kb-pick="onKbPick"
          />

          <button
            v-if="showWebSearch"
            class="cf-tool-btn" :class="{ 'is-active': webSearch, 'is-disabled': busy }"
            type="button" role="switch" :aria-checked="webSearch"
            :disabled="busy"
            @click="busy ? null : (webSearch = !webSearch)"
          >
            <CfIcon name="globe" :size="16" />联网搜索
          </button>

          <!-- 附件 chip：与能力胶囊同行，跟在联网搜索后面（对齐原型 #attSlot 位置）。
               三种阶段：上传中（进度条）→ 解析中（仅视频）→ 就绪（图标/缩略图 + 名称 + 快捷动作 + 删除） -->
          <span v-if="attachment" class="cf-att">
            <!-- 上传中/解析中：不管什么类型都转圈，缩略图只在就绪后才出现（与原型一致，
                 renderLoading 全走 att-spin，只有 renderReady 才区分图片给缩略图） -->
            <span v-if="attachment.stage !== 'ready'" class="cf-att-spin" aria-hidden="true" />
            <img
              v-else-if="attachment.kind === 'image' && attachment.url && !thumbFailed"
              class="cf-att-thumb" :src="attachment.url" alt=""
              @error="thumbFailed = true"
            >
            <span v-else class="cf-att-ico"><CfIcon :name="attIcon(attachment.kind)" :size="17" /></span>

            <!-- size 可能缺失（跨页恢复的附件没有它）：缺了就只显示文件名，
                 不留「a.pdf · 」这种尾巴 -->
            <span
              class="cf-att-name"
              :title="fmtSize(attachment.size) ? `${attachment.name} · ${fmtSize(attachment.size)}` : attachment.name"
            >{{ attachment.name }}</span>

            <span v-if="attachment.stage === 'uploading'" class="cf-att-meta">上传中 {{ attachment.progress }}%</span>
            <span v-else-if="attachment.stage === 'parsing'" class="cf-att-meta">解析中…</span>
            <span v-if="attachment.stage === 'uploading'" class="cf-att-bar">
              <i :style="{ width: `${attachment.progress}%` }" />
            </span>

            <!-- 就绪后才出快捷动作：图片→内容总结/文字提取，视频/文件→总结 -->
            <template v-if="attachment.stage === 'ready'">
              <button
                v-for="act in (upload[attachment.kind]?.acts ?? [])" :key="act.label"
                class="cf-att-act" type="button"
                @click="runAttAction(act)"
              >{{ act.label }}</button>
            </template>

            <span class="cf-att-sep" aria-hidden="true" />
            <button class="cf-att-x cf-tap40" type="button" aria-label="移除附件" @click="removeAttachment">
              <CfIcon name="x" :size="13" />
            </button>
          </span>

          <!-- 技能参数：选中技能后内联展开，跟随该技能的字段定义 -->
          <template v-if="activeSkill">
            <SkillParam
              v-for="f in activeSkill.fields" :key="f.key"
              :field="f" :value="paramsOf(activeSkillKey)[f.key]"
              @update:value="updateSkillParam(f, $event)"
            />
          </template>

          <!-- 技能菜单：只在未挂附件时可用；
               挂附件后技能入口收起（附件与技能功能互斥）
               技能按钮显示条件：模型的 abilityList 不为空且有可用技能 -->
          <span
            v-if="skillsAvailable && !attachment && !activeSkillKey"
            class="cf-skill-menu"
          >
            <!-- 选了知识库时置灰：不加原生 disabled，否则点击事件被吞掉、
                 用户看到灰色但不知道为什么（与加号按钮的处理同口径） -->
            <button
              ref="skillBtnRef"
              class="cf-tool-btn"
              :class="{ 'is-open': skillMenuOpen, 'is-disabled': skillBlockedByKb }"
              type="button" :aria-expanded="skillMenuOpen" aria-haspopup="menu"
              :title="skillBlockedTip || undefined"
              :aria-disabled="skillBlockedByKb || undefined"
              @click="toggleSkillMenu"
            >
              <CfIcon name="grid" :size="16" />技能
            </button>
            <span v-if="skillMenuOpen" class="cf-catch" @click="skillMenuOpen = false" />
            <span v-if="skillMenuOpen" class="cf-skill-list" :style="skillMenuStyle" role="menu">
              <button
                v-for="key in filteredSkillOrder" :key="key"
                class="cf-skill-item" type="button" role="menuitem"
                @click="pickSkill(key)"
              >
                <CfIcon :name="skills[key]?.icon" :size="16" />{{ skills[key]?.name }}
              </button>
            </span>
          </span>

          <!-- 工具条末尾扩展点：技能菜单之后、右侧动作组之前。
               作用域比 composer-above 多一个 busy——工具条里的模式按钮生成中通常要禁用。
               不订阅则不出现，工具条布局不变。 -->
          <slot name="composer-tools" :params="params" :set-params="setParams" :busy="busy" />
        </span>

        <!-- ---------- 右侧动作组 ---------- -->
        <span class="cf-bar-acts">
          <button
            v-if="features.voiceInput"
            v-vtip="recording ? '正在聆听，点击停止' : '点击或按住空格开启语音输入'"
            class="cf-icon-btn cf-tap40" :class="{ 'is-rec': recording }"
            type="button" :aria-pressed="recording"
            :aria-label="recording ? '停止语音输入' : '语音输入'"
            :title="recording ? '正在聆听，点击停止' : '点击或按住空格开启语音输入'"
            @click="toggleVoice"
          >
            <CfIcon v-if="!recording" name="mic" :size="20" />
            <span v-else class="cf-icon-stop" aria-hidden="true" />
          </button>

          <span v-if="features.voiceInput" class="cf-bar-sep" aria-hidden="true" />

          <!-- 生成中变停止按钮：同一个位置，避免用户找不到出口 -->
          <button
            v-if="busy" class="cf-send cf-tap40 is-stop" type="button"
            aria-label="停止生成" @click="emit('stop')"
          ><CfIcon name="x" :size="18" /></button>
          <!-- 短请求进行中：转圈 + 禁用。不给停止入口（不可中止），
               也不复用上面的 is-stop —— ✕ 会被读成「取消」，语义不对。 -->
          <button
            v-else-if="loading" class="cf-send cf-tap40 is-loading" type="button"
            disabled aria-label="处理中"
          ><span class="cf-send-spinner" aria-hidden="true"></span></button>
          <button
            v-else class="cf-send cf-tap40" type="button"
            :disabled="!canSend" aria-label="发送提问" @click="send"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 19V5" /><path d="m5 12 7-7 7 7" />
            </svg>
          </button>
        </span>
      </div>
    </div>
    <p v-if="showDisclaimer" class="cf-composer-foot">内容均由AI生成，请注意辨别</p>

    <MicPermission
      :open="micPermOpen"
      @allow="allowMic"
      @deny="denyMic"
    />

    <!-- 独立使用输入框时自带 toast 接入方；被 ChatFlow 包裹时由外层统一渲染，这里不重复 -->
    <ToastHost v-if="renderOwnToastHost" />
  </div>
</template>

<style scoped>
/* 外层铺页面底色并占满宽度：输入区是固定在底部的，
   消息滚到下面时要被这层挡住，透明的话文字会从卡片缝隙里透出来 */
.cf-composer-wrap{
  flex:none;width:100%;
  /* background:var(--cf-page); */
}
/* 卡片自身限宽居中（与消息流同 860），不是外层限宽。
   position+z-index 让卡片盖住能力舌头塞进来的那 12px，
   舌头才是「压在背面」而不是浮在卡片上 */
.cf-composer{
  width:auto;max-width:var(--cf-stream-max);margin:0 auto;
  position:relative;z-index:1;
  background:#ffffff;
  border:1px solid #e4e7ed;border-radius:16px;
  padding:16px;
  color:var(--cf-text-1);
  box-shadow:0 2px 12px rgba(0,0,0,0.08);
  transition:border-color var(--cf-transition),box-shadow var(--cf-transition);
}
/* 输入区域包装器：为字符计数器提供定位参考 */
.cf-ask-wrapper{
  position:relative;
  padding:0 0 var(--cf-space-2);
}
/* 聚焦态沿用卡片阴影的扩散参数，只把颜色换成主色 */
.cf-composer:focus-within{
  border-color:#409eff;
  box-shadow:0 2px 12px rgba(64,158,255,0.2);
}

/* ---------- 录音条 ---------- */
.cf-rec-strip{
  display:flex;align-items:center;gap:var(--cf-space-3);height:40px;
  margin-bottom:4px;padding:var(--cf-space-2) 0;
}
.cf-rec-wave{display:flex;align-items:center;gap:3px;height:32px;flex:1;min-width:0;overflow:hidden}
.cf-rec-wave i{
  flex:1;max-width:4px;min-width:2px;height:15%;border-radius:2px;
  background:var(--cf-primary);animation:cfRecBounce .9s ease-in-out infinite;
}
@keyframes cfRecBounce{0%,100%{height:15%;opacity:.5}50%{height:90%;opacity:1}}
.cf-rec-time{flex:none;font-size:var(--cf-fs-sm);color:var(--cf-text-1);font-variant-numeric:tabular-nums}
.cf-rec-tip{flex:none;font-size:13px;color:var(--cf-text-3)}

/* min-height 72：三行的量。输入框比单行高，是要让人敢往里写长问题。
   contenteditable 没有原生 placeholder，靠 data-ph + ::after 模拟：
   正文为空（不论有没有知识库芯片）就显示，跟在已有子节点（芯片）后面。
   不用 :empty::before——删空后浏览器常残留一个空文本节点，:empty 就不再命中，
   占位会跟着消失；data-show-ph 由 JS 按 text.value 判断，不受这个影响 */
.cf-ask{
  display:block;width:100%;cursor:text;
  min-height:72px;max-height:224px;overflow-y:auto;
  outline:none;background:transparent;
  font-family:inherit;font-size:var(--cf-fs-base);line-height:var(--cf-lh-body);
  color:var(--cf-text-1);
  word-break:break-word;white-space:pre-wrap;
}
/* 卡片自身已经给了聚焦反馈（边框转主色 + 投影），contenteditable 再叠一层键盘焦点环
   是重复的双框。全局 :focus-visible 规则的特异性刚好和这里的 outline:none 打平，
   打包顺序让它赢，所以要单独用 :focus-visible 覆盖回去，而不是指望上面那行生效。 */
.cf-ask:focus-visible{outline:none}
.cf-ask[data-show-ph="true"]::after{
  content:attr(data-ph);color:var(--cf-text-3);pointer-events:none;
}
.cf-ask-count{
  position:absolute;right:4px;bottom:4px;
  font-size:var(--cf-fs-xs);color:var(--cf-text-3);
  pointer-events:none;
  padding:2px 6px;
  background:rgba(255, 255, 255, 0.9);
  border-radius:4px;
  z-index:1;
}
.cf-ask-count.is-over{color:var(--cf-danger)}

/* ---------- 知识库标签（输入框内的芯片）----------
   与正文同字号，常态只加粗不加底色；hover 出删除线示意「点一下移除」
   （对齐原型 .kb-tag/.kb-tag-t，颜色全部走 token，数值与原型一一对应） */
.cf-kb-tag{
  display:inline;font-size:var(--cf-fs-base);font-weight:600;
  color:var(--cf-primary);padding:2px 6px;border-radius:4px;cursor:pointer;
  background:var(--cf-user-bubble);transition:var(--cf-transition);
}
/* 内层文字吃渐变，与发送后气泡里的 .cf-user-kb 同一套色；
   background-clip:text 与外层的底色不能共用一个元素，必须拆成两层 */
.cf-kb-tag-t{
  color:var(--cf-kb-fallback);background:var(--cf-kb-gradient);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;
}
/* hover 移除态：撤掉渐变回落到中性灰，否则 text-fill 透明会盖掉删除线的颜色 */
@media (hover:hover){
  .cf-kb-tag:hover{background:var(--cf-ink-06)}
  .cf-kb-tag:hover .cf-kb-tag-t{
    background:none;color:var(--cf-text-3);
    -webkit-text-fill-color:currentColor;text-decoration:line-through;
  }
}

/* ---------- 附件 chip ----------
   高度锁 36px，给缩略图留呼吸位；左内边距收到 4px，让缩略图贴近左缘 */
.cf-att{
  display:inline-flex;align-items:center;gap:var(--cf-space-2);max-width:100%;min-width:0;
  flex:0 999 auto;height:36px;padding:0 6px 0 4px;
  background:var(--cf-ink-03);border:.5px solid var(--cf-ink-10);
  border-radius:var(--cf-radius-md);
  font-size:13px;line-height:20px;color:var(--cf-text-2);
  transition:var(--cf-transition);
}
@media (hover:hover){
  .cf-att:hover{background:var(--cf-ink-04);border-color:var(--cf-ink-15)}
}
.cf-att-thumb{width:28px;height:28px;flex:none;border-radius:var(--cf-radius-sm);object-fit:cover;border:.5px solid var(--cf-ink-08)}
.cf-att-ico{
  width:28px;height:28px;flex:none;border-radius:var(--cf-radius-sm);
  display:grid;place-items:center;background:var(--cf-primary-soft);color:var(--cf-primary);
}
.cf-att-spin{
  width:14px;height:14px;flex:none;border-radius:50%;margin:0 7px;
  border:2px solid var(--cf-ink-10);border-top-color:var(--cf-primary);
  animation:cfAttSpin .7s linear infinite;
}
@keyframes cfAttSpin{to{transform:rotate(360deg)}}
/* 文件名降到 13px：主角是操作按钮，文件名只需可读可辨 */
.cf-att-name{
  flex:0 1 auto;min-width:0;max-width:190px;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;color:var(--cf-text-1);font-weight:500;
}
.cf-att-meta{flex:none;font-size:var(--cf-fs-xs);color:var(--cf-text-3)}
.cf-att-bar{width:56px;height:4px;flex:none;border-radius:var(--cf-radius-pill);background:var(--cf-ink-10);overflow:hidden}
.cf-att-bar i{display:block;height:100%;width:0;border-radius:var(--cf-radius-pill);background:var(--cf-primary);transition:width .24s var(--cf-ease-out)}
/* 快捷动作（内容总结 / 文字提取 / 总结）：半透明白底从灰底 chip 上浮起一层 */
.cf-att-act{
  display:inline-flex;align-items:center;gap:4px;height:26px;flex:none;
  padding:0 var(--cf-space-2);border-radius:var(--cf-radius-xs);cursor:pointer;
  background:rgba(255,255,255,.6);color:var(--cf-text-2);
  font-size:13px;line-height:18px;font-weight:500;transition:var(--cf-transition);
}
@media (hover:hover){
  .cf-att-act:hover{background:var(--cf-primary-soft);color:var(--cf-primary)}
}
.cf-att-act:active{background:var(--cf-primary-soft);color:var(--cf-primary)}
.cf-att-sep{width:1px;height:18px;flex:none;background:var(--cf-line-strong)}
.cf-att-x{
  flex:none;width:22px;height:22px;border-radius:50%;
  display:grid;place-items:center;cursor:pointer;color:var(--cf-text-3);
}
@media (hover:hover){
  .cf-att-x:hover{background:var(--cf-line-strong);color:var(--cf-text-1)}
}
.cf-att-x:active{background:var(--cf-line-strong);color:var(--cf-text-1)}

/* ---------- 工具条 ---------- */
/* 恒为单行：三段式布局，左侧固定（+按钮），中段自适应，右侧固定（操作按钮） */
.cf-bar{
  display:flex;align-items:center;gap:8px;
  flex-wrap:nowrap;margin-top:var(--cf-space-2);
}
/* 中段可以横向滚动，但不会与左右两侧重叠 */
.cf-bar-mid{
  display:flex;align-items:center;gap:6px;
  flex:1 1 0;min-width:0;
  overflow-x:auto;overflow-y:hidden;
  /* 隐藏滚动条但保持滚动功能 */
  scrollbar-width:none;
  -ms-overflow-style:none;
}
.cf-bar-mid::-webkit-scrollbar{
  display:none;
}
.cf-bar-acts{
  display:flex;align-items:center;gap:var(--cf-space-3);
  flex:none;
}
.cf-bar-sep{width:1px;height:18px;background:var(--cf-line);flex:none}
.cf-plus{position:relative;display:inline-flex;align-items:center;gap:var(--cf-space-2);flex:none}

/* 加号：34×34 带描边的方形，与右侧的圆形语音键有意区分开——
   一个是「添加内容」，一个是「输入方式」，不是同一类动作 */
.cf-plus-btn{
  width:34px;height:34px;flex:none;border-radius:var(--cf-radius-md);
  display:grid;place-items:center;
  border:1px solid var(--cf-line);background:#ffffff;
  color:var(--cf-text-2);cursor:pointer;transition:var(--cf-transition);
}
.cf-plus-btn.is-open{
  background:var(--cf-page);border-color:var(--cf-primary-edge);color:var(--cf-primary);
}
/* 生成中禁用：置灰不可点，对齐接入方 /qa */
.cf-plus-btn:disabled,
.cf-plus-btn.is-disabled{opacity:.45;cursor:not-allowed}
@media (hover:hover){
  .cf-plus-btn:hover:not(:disabled){
    background:var(--cf-page);border-color:var(--cf-primary-edge);color:var(--cf-primary);
  }
}
/* 展开时加号转 45° 成叉，暗示「再点一下收起」 */
.cf-plus-btn :deep(svg){transition:transform var(--cf-transition)}
.cf-plus-btn.is-open :deep(svg){transform:rotate(45deg)}

/* 语音键：与发送键同尺寸的 32px 圆形，常态无底色。
   录音中：一级文字色实底 + 白色图标，权重高于 hover 的中性浅底 */
.cf-icon-btn{
  width:32px;height:32px;flex:none;border-radius:var(--cf-radius-pill);
  display:inline-flex;align-items:center;justify-content:center;
  color:var(--cf-text-2);cursor:pointer;transition:var(--cf-transition);
}
.cf-icon-btn.is-rec{background:var(--cf-text-1);color:#fff}
@media (hover:hover){
  .cf-icon-btn:hover{background:var(--cf-fill);color:var(--cf-text-1)}
  .cf-icon-btn.is-rec:hover{background:var(--cf-text-1)}
}
/* 停止符号：按钮本身已是深色圆底，只留一个方块，不再套外圆 */
.cf-icon-stop{width:8px;height:8px;border-radius:1.5px;background:currentColor}

.cf-send{
  width:32px;height:32px;flex:none;border-radius:var(--cf-radius-pill);
  display:grid;place-items:center;
  background:var(--cf-primary);color:#fff;cursor:pointer;
  transition:var(--cf-transition);
}
@media (hover:hover){
  .cf-send:hover:not(:disabled){background:var(--cf-primary-deep)}
}
/* 无内容时置灰：底色用中性描边色，图标退到三级文字色，
   不是把主色调浅——那样看着像「可点但加载中」 */
.cf-send:disabled{
  background:var(--cf-ink-10);color:var(--cf-text-3);cursor:not-allowed;
}
.cf-send.is-stop{background:var(--cf-text-1)}

/* 短请求进行中：保持主色底（区别于 :disabled 的置灰——那是「不能点」，
   这里是「已经在处理」），光标不用 not-allowed，避免读成出错。 */
.cf-send.is-loading{
  background:var(--cf-primary);color:#fff;cursor:default;
}
/* 转圈：3/4 圈描边。用 border 而非 svg，省一个图标依赖。
   颜色用 currentColor 的半透明 + 一段实色，天然跟着按钮前景色走。 */
.cf-send-spinner{
  width:16px;height:16px;border-radius:50%;
  border:2px solid rgba(255,255,255,.35);
  border-top-color:#fff;
  animation:cf-send-spin .7s linear infinite;
}
@keyframes cf-send-spin{to{transform:rotate(360deg)}}
/* 降低动效偏好：停掉旋转，留一个静态环表示状态，不做闪烁 */
@media (prefers-reduced-motion:reduce){
  .cf-send-spinner{animation:none}
}

/* ---------- 浮层：加号菜单、技能菜单 ---------- */
.cf-skill-menu{position:relative;display:inline-flex;flex:none}
.cf-plus-menu,.cf-skill-list{
  position:fixed;z-index:9999;
  width:250px;padding:6px;
  background:#ffffff;
  border:1px solid var(--cf-line);border-radius:var(--cf-radius-md);
  box-shadow:var(--cf-shadow-float);
}
.cf-skill-list{width:max-content;min-width:156px}
/* 非多模态模型：附件菜单顶部红色提示（对齐接入方 /qa .cf-plus-tip） */
.cf-plus-tip{
  padding:var(--cf-space-2) var(--cf-space-3);
  margin-bottom:var(--cf-space-1);
  font-size:var(--cf-fs-xs);
  color:#f56c6c;
  background:#fef0f0;
  border-radius:var(--cf-radius-sm);
  line-height:1.4;
}
.cf-plus-item{
  display:flex;align-items:center;gap:var(--cf-space-3);width:100%;
  padding:var(--cf-space-2) var(--cf-space-3);border-radius:var(--cf-radius-sm);
  cursor:pointer;text-align:left;transition:var(--cf-transition);
}
/* 多模态门禁：非多模态模型（模型名不含"鼎安"）时图片/视频/文件置灰不可点 */
.cf-plus-item:disabled,
.cf-plus-item.is-disabled{opacity:.45;cursor:not-allowed;pointer-events:none}
@media (hover:hover){
  .cf-plus-item:disabled:hover,
  .cf-plus-item.is-disabled:hover{background:transparent}
}
/* 技能菜单项：与加号菜单项分开——原型的 .more-item 用 8px gap，不是 12px */
.cf-skill-item{
  display:flex;align-items:center;gap:var(--cf-space-2);width:100%;
  padding:var(--cf-space-2) var(--cf-space-3);border-radius:var(--cf-radius-sm);
  cursor:pointer;text-align:left;transition:var(--cf-transition);
}
@media (hover:hover){
  .cf-plus-item:hover,.cf-skill-item:hover{background:var(--cf-page)}
}
.cf-plus-item>i{
  flex:none;width:30px;height:30px;border-radius:var(--cf-radius-sm);
  display:grid;place-items:center;
  background:var(--cf-primary-soft);color:var(--cf-primary);
}
.cf-plus-item>span{min-width:0}
.cf-plus-item b{
  display:block;font-size:var(--cf-fs-sm);font-weight:600;color:var(--cf-text-1);
}
/* 第二行说明：12px 三级色，与标题差一档 */
.cf-plus-item>span>span{
  display:block;font-size:var(--cf-fs-xs);color:var(--cf-text-3);margin-top:2px;
}
.cf-skill-item{
  font-size:var(--cf-fs-sm);color:var(--cf-text-2);white-space:nowrap;
}
.cf-skill-item :deep(svg){color:var(--cf-text-3)}
@media (hover:hover){
  .cf-skill-item:hover{color:var(--cf-text-1)}
  .cf-skill-item:hover :deep(svg){color:var(--cf-primary)}
}

.cf-composer-foot{
  max-width:var(--cf-stream-max);margin:0 auto;
  text-align:center;
  font-size:12px;color:#c0c4cc;
  padding:12px 0 8px;
  line-height:1.5;
}

/* H5 响应式适配 */
@media (max-width:767.98px){

  /* 小屏收窄：联网搜索与技能按钮只保留图标 */
  .cf-bar-mid .cf-tool-btn[role="switch"],
  .cf-bar-mid .cf-tool-btn[aria-haspopup="menu"]{
    width:34px;min-width:34px;flex:none;
    padding:0;justify-content:center;font-size:0;gap:0;
  }

  /* 附件卡片：窄屏下文件名适度缩短 */
  .cf-att-name{
    max-width: 120px;
  }

  /* 工具栏按钮触屏命中区补偿 */
  .cf-bar-l button,
  .cf-bar-mid button,
  .cf-bar-r button{
    position: relative;
  }
}

/* 触屏设备：增大命中区 */
@media (pointer: coarse) {
  .cf-bar-l button::before,
  .cf-bar-mid button::before,
  .cf-bar-r button::before{
    content: "";
    position: absolute;
    left: 50%;
    top: 50%;
    width: 40px;
    height: 40px;
    transform: translate(-50%, -50%);
  }
}

/* ---------- 暗色主题适配 ---------- */
html[data-theme="dark"] .cf-ask-count{
  /* 字符计数器：暗色下使用深色半透明背景 */
  background:rgba(0,0,0,.5);
  color:var(--cf-text-3);
}

</style>

