<!-- ============================================================
     ChatFlow · 主对话流 v1.0
     ------------------------------------------------------------
     中国矿业大学学科大模型 · 通用智能体对话组件。
     消息流 + 输入区 + 参考资料抽屉 + 反馈弹窗，一个标签接入。

     最小用法：
       <ChatFlow :agent="{name:'学科问答', description:'…'}" />

     数据源默认走 mock；接真实接口传 adapter（见 README「接真实接口」）。
     功能增删传 features；换肤覆盖 --cf-* 变量。
     ============================================================ -->
<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, provide, nextTick } from 'vue'
import IconSprite from '../icons/IconSprite.vue'
import MessageStream from './MessageStream.vue'
import ChatComposer from './ChatComposer.vue'
import RefDrawer from './RefDrawer.vue'
import FeedbackModal from './FeedbackModal.vue'
import Aurora from './Aurora.vue'
import ToastHost from './ToastHost.vue'
import { useChatFlow } from '../composables/useChatFlow.js'
import { useTypewriter } from '../composables/useTypewriter.js'
import { useToast } from '../composables/useToast.js'
import { mergeFeatures, DEFAULT_UPLOAD, DEFAULT_STREAM } from '../utils/config.js'
import { mockAdapter } from '../mock/index.js'
import { htmlToText } from '../utils/html.js'
import { buildAttachmentParams } from '../utils/buildAttachmentParams.js'
import { getHumanId } from '../utils/humanId.js'
import { submitVote } from '../services/feedbackService.js'
import { generateUuid } from '../services/chatService.js'

const props = defineProps({
  /** 智能体标识：{name, description, icon} —— 空态与占位文案用它 */
  agent: {
    type: Object,
    default: () => ({
      name: '',
      description: '',
    }),
  },
  /** 功能开关，只写要改的项。见 utils/config.js */
  features: { type: Object, default: () => ({}) },
  /** 数据适配器。默认 mock，接真实接口时替换 */
  adapter: { type: Object, default: () => mockAdapter },
  /** 流式输出节奏 */
  stream: { type: Object, default: () => DEFAULT_STREAM },
  /** 附件规则 */
  upload: { type: Object, default: () => DEFAULT_UPLOAD },
  /** 输入框占位文案 */
  placeholder: { type: String, default: '' },
  /** 输入字数上限，不传默认 250，0 为不限 */
  maxLength: { type: Number, default: 250 },
  /** 是否显示免责声明 */
  showDisclaimer: { type: Boolean, default: false },
  /** IP 形象立绘 URL（用于 split 布局） */
  illustrationUrl: { type: String, default: '' },
  /** 动态 chat 入参（配 v-model:chatParams）：发送时作为 extraParams 并进 SSE body。
      不传默认 {}，合并为 no-op，body 与不接入时逐字节一致。 */
  chatParams: { type: Object, default: () => ({}) },
  /** 游客功能权限，直传后端 /visitor/access/config/query 的返回对象
      （{ personalKb, teamKb, schoolKb, ... }，0-关闭 1-开启）。
      不传 = 不限制（非游客接入方无需传）；原样下传给两个 ChatComposer。 */
  permissions: { type: Object, default: null },
  /** 交互前置守卫：返回 false 则中止本次交互（发送 / 上传 / 知识库）。
      典型用途是未登录时跳登录页。不传 = 不拦；原样下传给两个 ChatComposer。 */
  beforeInteract: { type: Function, default: null },
  /** 短请求进行中：发送按钮转圈并禁用，不变成停止按钮（区别于内部的生成中态）。
      接入方在 @send 里做前置异步（如意图识别）时用。原样下传给两个 ChatComposer。 */
  loading: { type: Boolean, default: false },
})

const emit = defineEmits([
  /** 用户发出一轮提问：{text, model, knowledgeBases, webSearch, attachment} */
  'send',
  /** 用户点了停止生成 */
  'stop',
  /** 一轮回答完成：ai 消息对象 */
  'answer',
  /**
   * 重新生成：{question, requestId, sessionId, message}
   * 组件只把占位打回 thinking 态，真正的重发请求由接入方发 ——
   * 组件不认识 SSE，也不该认识。
   */
  'regenerate',
  /**
   * 投票：{message, vote, prev, revert}
   * vote 为 'up'|'down'|''（取消），prev 为点击前的值。
   * 本地态已乐观更新；接入方调接口失败时调 revert() 回滚，
   * 否则会出现界面点亮了但后端没落库
   */
  'vote',
  /** 提交反馈或举报：{mode, tags, text, message} */
  'feedback',
  /** 复制回答：纯文本 */
  'copy',
  /** 打开知识库文档：{title, kbName} */
  'open-doc',
  /** 动态入参回写（配 v-model:chatParams）：composer 扩展点里 setParams(patch) 触发 */
  'update:chatParams',
])

const feat = computed(() => mergeFeatures(props.features))
const { toast } = useToast()

/** 动态入参回写：浅合并 patch 到 chatParams 后 emit。
    配 v-model:chatParams 用；接入方未用 v-model 时 emit 无监听者，也不报错。
    透传给两个 ChatComposer 的扩展点作用域（composer-above / composer-tools）。 */
function setParams(patch) {
  emit('update:chatParams', { ...props.chatParams, ...(patch || {}) })
}

// 本组件模板末尾已渲染 <ToastHost/>，向后代（ChatComposer）声明：无需再自渲染一份，
// 避免嵌套导致 toast 接入方重复。单独用 ChatComposer 时无此 provide，它会自带一份。
provide('cf-has-toast-host', true)

/* ---------- 会话与流式输出 ---------- */
const typewriter = useTypewriter(props.stream)
const chat = useChatFlow(props.adapter, {
  onTurnEnd: (ai) => emit('answer', ai),
  /* 重新生成时沿用最后一轮的检索条件；
     但联网开关以输入区当前状态为准：用户开关变化后点重新生成，
     应按最新开关取检索，而不是沿用上一轮发送时的 webSearch 快照 */
  currentContext: () => ({
    ...lastContext.value,
    webSearch: composer.value?.getWebSearch?.() ?? lastContext.value.webSearch,
  }),
  /* 追问建议获取函数：传给 useChatFlow，在回答完成后调用 */
  fetchSuggestions: props.adapter.fetchSuggestions,
})
chat.bindTypewriter(typewriter)

/* 文字转语音·历史现合成：AudioPlayer 无 src 的历史消息首次播放时 inject 调用。
   adapter 提供 ttsSynthesize 才注入（真实服务适配器/接入方注入），否则 AudioPlayer 走 mock 假进度。 */
provide('ttsSynthesize', (text, params) => {
  if (typeof props.adapter?.ttsSynthesize === 'function') {
    return props.adapter.ttsSynthesize(text, params)
  }
  return Promise.reject(new Error('未提供 ttsSynthesize 能力'))
})

/** 最后一轮的检索条件，重新生成与依据抬头都要用 */
const lastContext = ref({ model: null, modelId: '', knowledgeBases: [], webSearch: false, parallelSourcing: false })
/* 名称可能还没反查到（接入方只给了 id）：滤掉空值，
   否则 undefined 会顺着 kb-names 流到依据抬头里显示出来 */
const kbNames = computed(() =>
  lastContext.value.knowledgeBases
    .map((k) => (typeof k === 'string' ? k : k?.name))
    .filter(Boolean)
)

/** 流式期间交给消息流的实时 HTML */
const streamingHtml = computed(() => {
  const msgs = chat.messages.value
  if (msgs.length === 0) return ''
  const lastMsg = msgs[msgs.length - 1]
  if (lastMsg.role !== 'ai') return ''
  /* 打字机播放优先：文档总结这类「一次性返回、逐字播放」的路径，phase 是
     'streaming' 但 html 不在 message.html 上（还没播完），内容全在 typewriter 里。
     放最前面判断，否则会走下面「读 message.html」拿到空串。 */
  if (typewriter.isStreaming.value) return typewriter.currentHtml()
  // 普通 SSE 流式：读最后一条 AI 消息实时累积的 html
  if (lastMsg.phase === 'streaming') {
    return lastMsg.html || ''
  }
  return ''
})

/** 流式期间交给消息流的实时思考过程 */
const streamingThoughts = computed(() => {
  const msgs = chat.messages.value
  if (msgs.length === 0) return ''
  const lastMsg = msgs[msgs.length - 1]
  if (lastMsg.role !== 'ai') return ''
  return lastMsg.thoughts || ''
})

const composer = ref(null)
const presetQuestions = computed(() => props.adapter.meta?.presetQuestions ?? [])

/* ---------- 发送 ---------- */
function onSend(p) {
  lastContext.value = {
    model: p.model,
    /* 显式记住本轮实际发出的 modelId：重新生成要和前一轮用同一个模型。
       只存 model 对象不够 —— 没有模型胶囊时 p.model 为 null，而
       normalizePayload 是 `p.modelId ?? p.model?.id ?? ''`，
       modelId 这一层缺失就会退到空串，后端重新选默认模型，
       可能和第一轮不是同一个。 */
    modelId: p.modelId ?? p.model?.id ?? '',
    knowledgeBases: p.knowledgeBases,
    webSearch: p.webSearch,
    /* 全局开关，不是逐轮控件：跟着当前 features 取值，不从 composer 的
       payload 里读（composer 不知道也不需要知道这项功能） */
    parallelSourcing: feat.value.parallelSourcing,
    /* 技能态沿用到重新生成：用户点「重新生成」时应该用同一个技能重问一次 */
    skill: p.skill,
    skillConfSummary: p.skillConfSummary,
    /* 技能结构化参数：文字转语音/文生图分支要用 */
    skillParams: p.skillParams,
  }

  /* 文档总结：文件点「总结」→ 走 docSummary 轮询（独立路径，不碰 chat）。
     else 里是原有的 chat 逻辑，一字未动。 */
  if (p.action === 'summarize' && p.attachment?.kind === 'file') {
    runDocSummary(p)
  } else {
    /* 文字转语音（tts）不走普通对话 SSE：接入方对接时 emit('send') 会让接入方 POST /dialog/chat，
       后端会拒（"回答生成失败"）。TTS 只经 chat.ask → adapter.ask 的合成分支。
       对齐接入方 /qa ChatFlow.vue 的 isTts 处理。 */
    const isTts = p.skill === 'tts'
    if (!isTts) {
      // 构建附件参数：将 payload.attachment 和 payload.files 转换为 SSE 请求参数
      const attachmentParams = buildAttachmentParams(p)

      // 合并原始 payload 和转换后的附件参数；动态入参一并带上，接入方自建请求时也拿得到
      const enrichedPayload = {
        ...p,
        ...attachmentParams,
        extraParams: props.chatParams,
      }

      emit('send', enrichedPayload)
    }

    /* 图生文这类图片附件也是随技能走的：quiet 那条只发用户消息，
       技能信息要留给紧随其后触发回答的那条 */
    if (p.isMedia) {
      chat.ask({ attachment: p.attachment, quiet: !!p.text, ...lastContext.value, extraParams: props.chatParams })
    }
    /* 有文字就正常问；纯媒体（没配文字）时上一句已经把消息发出去了，
       这里补一轮不带附件的提问让模型作答。
       注意：图生文时仍要把 attachment 传给这一轮 —— 组件里 adapter 就是真实服务，
       要靠它把附件映射成 imageFiles + action 发给后端；而 useChatFlow.ask 在有 text 时
       只渲染文字气泡（图片气泡已由上面 quiet 那条画过），不会重复出图。
       接入方 chatflow 这里传 null 无碍，是因为真实请求走页面 emit('send')→buildAttachmentParams。 */
    if (p.text || !p.isMedia) {
      chat.ask({
        text: p.text,
        files: p.files,
        attachment: p.attachment,
        ...lastContext.value,
        extraParams: props.chatParams,
      })
    }
  }

  /* 状态延续：空态 composer 与底部 composer 是两个独立实例（v-if 切换），
     发送后空态那个卸载、底部那个全新挂载、本地选择态回默认。这里把本轮选好的
     模型/联网/知识库/技能同步给新挂载的底部 composer，让底部输入框保持一致。
     nextTick 等底部 composer 挂载完（此时 messages.length>0，模板已切到底部那个）。 */
  nextTick(() => {
    composer.value?.applyState({
      model: p.model,
      knowledgeBases: p.knowledgeBases,
      webSearch: p.webSearch,
      skill: p.skill,
      skillParams: p.skillParams,
      /* 附件也要带过去：send() 之后附件是保留的（同一份文档常要连着追问几轮），
         但那是「同一个实例内保留」。空态→底部是换了实例，不传就丢了，
         表现为「首页上传发送进来后，底部输入框的附件 chip 不见了」。 */
      attachment: p.attachment,
    })
  })
}

/* ---------- 文档总结（独立于 chat 的消息路径）---------- */

/** 文件点「总结」按钮：轮询 docSummary → 打字机播放 summary → saveChat 落库。
    不碰 emit('send') 也不走 chat.ask —— 总结走的是 ChatDoc 官方摘要接口，
    与问答的向量检索是两套机制。 */
function runDocSummary(p) {
  const att = p.attachment
  const file = p.files?.[0]
  const resourceId = att?.fileId || file?.fileIds || ''

  if (!resourceId) {
    toast('文件信息缺失，无法总结')
    return
  }

  chat.askDocSummary(p, {
    /* 轮询 docSummary：adapter 内部先确保 sessionId（建会话的 query 用预设问题），
       再轮询到 done 返回 summary */
    poll: () => props.adapter.docSummary?.(resourceId, p.text)
      ?? Promise.reject(new Error('当前适配器不支持文档总结')),
    /* 轮询完成即落库，不等打字机播完（后端拿到 summary 就能存） */
    onDone: (ai, summary) => saveDocSummary(p, summary, resourceId),
  })
}

/** 文档总结的 saveChat 落库。入参与 chat 路径的 doSave 对齐（type=0 普通文本），
    附件四字段齐全（后端据此反查或历史恢复）。 */
function saveDocSummary(p, summary, resourceId) {
  if (typeof props.adapter.saveDialogue !== 'function') return
  const att = p.attachment
  const file = p.files?.[0]

  props.adapter.saveDialogue({
    sessionId: props.adapter.sessionId,
    requestId: generateUuid(),
    question: p.text || '',
    output: summary,
    thoughts: '',
    modelId: p.model?.id ?? '',
    knowledgeId: p.knowledgeBases?.[0]?.id ?? '',
    resourceId,
    resourceName: att?.name || file?.name || '',
    resourceType: '2',  // 文档
    resourceUrl: att?.resourceUrl || att?.url || file?.url || '',
    reason: 'done',
    type: 0,
  }).catch((e) => {
    console.error('[ChatFlow] 文档总结 saveChat 失败:', e)
  })
}

function onStop() {
  chat.stop()
  emit('stop')
  toast('已停止生成')
}

/** 推荐问与追问：直接填进输入框并发送 */
function askQuestion(q) {
  composer.value?.fill(q, true)
}

/** 知识库卡片：选中该知识库（等同于 @ 唤起选中），不发送 */
function onSelectKb(kb) {
  composer.value?.selectKb(kb)
}

/* ---------- 消息操作 ---------- */
async function onCopy(message) {
  const text = htmlToText(message.html)
  try {
    await navigator.clipboard.writeText(text)
    toast('已复制回答内容')
  } catch {
    toast('当前环境不支持自动复制，请手动选中')
  }
  emit('copy', text)
}

function onRegenerate(message) {
  /* 先把旧回答换成 thinking 占位（拿到这一轮的 question 与后端 ID），
     再让接入方去发真正的重发请求 —— 顺序反了的话接入方清掉旧回答时
     组件这边还挂着上一轮的内容，会闪一下旧答案。
     历史回答点「重新生成」时 message 带上该轮消息，regenerate 按它定位轮次。 */
  const ai = chat.regenerate(message)
  if (!ai) return
  emit('regenerate', {
    question: ai.question,
    requestId: ai.requestId,
    sessionId: ai.sessionId,
    /* 模型信息带出去：接入方自己重发时要用同一个模型，
       否则拿不到本轮用的是哪个（组件内部走 lastContext，接入方没有这个）。 */
    modelId: lastContext.value.modelId,
    model: lastContext.value.model,
    message: ai,
  })
  toast('正在重新生成回答…')
}

/**
 * 从消息上取 /dialog/report 需要的问答对定位信息。
 * answerId/questionId 由后端 saveChat 回包填上，sessionId 优先取消息自己的
 * （历史消息属于旧会话），回落 adapter 当前会话。
 */
function reportIds(message) {
  if (!message) return null
  return {
    answerId: message.answerId || '',
    questionId: message.questionId || '',
    sessionId: message.sessionId || props.adapter?.sessionId || '',
    humanId: getHumanId(props.agent?.humanId),
  }
}

function onVote({ message, vote }) {
  /* 记住原值：接口失败要回滚到这里 */
  const before = message.vote
  const applied = chat.setVote(message.id, vote)

  /* answerId 为空说明这轮还没落库，跳过上报，只把事件抛给接入方 */
  if (message.answerId) {
    /* 根据 before 和 applied 决定 action：
       1=点赞, 2=点踩, 3=取消点赞, 4=取消点踩 */
    let action = null
    if (vote === 'up' && applied === 'up') action = 1       // 点赞
    else if (vote === 'down' && applied === 'down') action = 2  // 点踩
    else if (vote === 'up' && applied === '') action = 3    // 取消点赞
    else if (vote === 'down' && applied === '') action = 4  // 取消点踩

    if (action !== null) {
      submitVote({
        chatId: message.answerId,       // chatId 就是 answerId
        sessionId: message.sessionId || '',
        questionId: message.questionId || '',
        answerId: message.answerId,
        action,
      }).then((ok) => {
        if (!ok) {
          chat.revertVote(message.id, before)
          toast('操作失败，请稍后重试')
        }
      })
    }
  }

  emit('vote', {
    message,
    vote: applied,
    /* 上一个状态：接入方要靠它区分「取消点赞」和「取消点踩」——
       applied 为 '' 时只知道被取消了，不知道取消的是哪一个 */
    prev: before,
    revert: () => chat.revertVote(message.id, before),
  })
}

/* ---------- 反馈弹窗 ---------- */
const fbOpen = ref(false)
const fbMode = ref('vote')
const fbMessage = ref(null)
/** 传给弹窗的问答对 ID，弹窗内部调 /dialog/report 用 */
const fbIds = computed(() => reportIds(fbMessage.value))
/** 未提交关闭时的回滚回调；点踩入口才有，举报入口为 null */
const fbRevert = ref(null)

function openFeedback(mode, message, revert = null) {
  fbMode.value = mode
  fbMessage.value = message ?? null
  fbRevert.value = revert
  fbOpen.value = true
}

/* 统一的关闭出口（取消/关闭/遮罩/Esc 都走这里）。
   未提交就关闭时执行回滚回调，把点踩临时置上的投票态还原。 */
function closeFeedback() {
  fbOpen.value = false
  if (fbRevert.value) fbRevert.value()
  fbRevert.value = null
}

function onFeedback(payload) {
  /* 提交即认可这次点踩，清掉回滚回调，随后的 close 便不再还原投票态 */
  fbRevert.value = null
  /* 反馈已提交，抛出事件。点踩和反馈已解耦——举报按钮独立触发反馈弹窗，
     与投票无关，不再锁死投票态。 */
  emit('feedback', { ...payload, message: fbMessage.value })
  toast('反馈已提交,感谢你的建议')
}

/* ---------- 参考资料抽屉 ---------- */
const drawerOpen = ref(false)
const drawerMode = ref('list')
const drawerWeb = ref([])
const drawerDoc = ref(null)
/** 从列表点进文档时记住回列表的路；null 表示没有可回的列表 */
const backSources = ref(null)

async function openWeb(message) {
  drawerMode.value = 'list'
  drawerWeb.value = message.webSources ?? []
  backSources.value = null
  drawerOpen.value = true
}

async function openDoc(payload, fromList = false) {
  /* fromList 决定返回按钮是否出现。用 backSources 而非布尔量，
     这样返回时不必重新请求列表数据 */
  backSources.value = fromList ? drawerWeb.value : null

  /* payload 有两种来源：
     1) 知识库依据 SourceList 点击：带真实 doc（含 contents/resourceUrl/responsitoryId 等）
     2) 联网资料列表里点知识库卡片：只有 { title, kbName }，无真实原文数据
     只要 payload 带了 contents 或 resourceUrl，就认定是真实 doc，直接用；
     否则回落到接入方 adapter.fetchDoc（真实实现缺失时才是 mock）。 */
  const hasRealDoc = payload && (payload.contents?.length || payload.resourceUrl)
  if (hasRealDoc) {
    drawerDoc.value = {
      ...payload,
      /* RefDrawer 切片视图读 doc.chunks {title,text}，把真实 contents 映射过去。
         后端 contents 每项 {pageNumber,id,sort,content}，无 title，用页码兜底。 */
      chunks: (payload.contents || []).map((c, i) => ({
        loc: c.loc || (c.pageNumber ? `第 ${c.pageNumber} 页` : `片段 ${i + 1}`),
        text: c.content || c.text || '',
      })),
    }
  } else {
    drawerDoc.value = await props.adapter.fetchDoc(payload.title, payload.kbName)
  }

  drawerMode.value = 'doc'
  drawerOpen.value = true
  emit('open-doc', payload)
}

function backToList() {
  drawerMode.value = 'list'
  drawerWeb.value = backSources.value ?? []
  backSources.value = null
  drawerDoc.value = null
}

/* Esc 出口。宽屏抽屉没有遮罩，所以键盘出口必须留着。
   监听挂 window 而不是根节点：焦点常常在 body 上，事件从 body 往上冒，
   到不了根节点这个后代。只在有浮层打开时挂，关掉即摘。 */
function onEsc(e) {
  if (e.key !== 'Escape') return
  /* 弹窗层级高于抽屉，先关它。走 closeFeedback 以便回滚未提交的点踩 */
  if (fbOpen.value) { closeFeedback(); return }
  if (drawerOpen.value) drawerOpen.value = false
}

const escOn = computed(() => drawerOpen.value || fbOpen.value)
watch(escOn, (on) => {
  if (on) window.addEventListener('keydown', onEsc)
  else window.removeEventListener('keydown', onEsc)
})
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))

/* 关掉参考资料抽屉这项功能时，把已打开的收起来，避免留一块死面板 */
watch(() => feat.value.refDrawer, (on) => { if (!on) drawerOpen.value = false })

/* iOS Safari 的 :active 反馈需要有一个真实的 touch 监听才会生效，
   否则触屏按压不会有任何视觉反馈。空函数即可，只是为了激活它。 */
function noop() {}
onMounted(() => document.addEventListener('touchstart', noop, { passive: true }))
onBeforeUnmount(() => document.removeEventListener('touchstart', noop))

/* ---------- 对外方法 ---------- */
defineExpose({
  /** 以编程方式提问 */
  ask: askQuestion,
  /**
   * 填入输入框并立即发送。
   * 与 ask 同一实现，保留这个名字是因为接入方页面（NewChatPC）按这个名字调用；
   * 之前没暴露，点首页推荐问会直接 TypeError。
   */
  fillAndSend: askQuestion,
  /** 填入完整参数（模型/知识库/联网/技能+参数/附件）并发送。首页 hero 跳转 /qa 带模式时用 */
  fillAndSendWithParams: (params) => composer.value?.fillAndSendWithParams(params),
  /** 只选中模型不发送（模型广场「立即体验」跳转时用） */
  selectModel: (modelId) => composer.value?.selectModel(modelId),
  /** 仅应用状态参数（如 webSearch/knowledgeBases）到输入区，不发送。
      接入方 URL 带 webSearch=1 跳入时用于默认选中联网搜索。 */
  applyComposerState: (state) => composer.value?.applyState(state),
  /** 清空会话回到空态（同时清掉 adapter 的 sessionId + URL，若 adapter 支持） */
  reset: () => { chat.reset(); props.adapter?.reset?.(); drawerOpen.value = false },
  /** 加载历史消息 */
  loadHistory: (historyMessages) => chat.loadHistory(historyMessages),
  /** 只读消息列表 */
  messages: chat.messages,
  /** 是否生成中 */
  busy: chat.busy,
})
</script>

<template>
  <div class="cf-root">
    <IconSprite />

    <div class="cf-layout">
      <!-- Aurora 背景层 - 仅在空状态时显示 -->
      <div v-if="feat.emptyState && chat.messages.value.length === 0" class="cf-layout-aurora">
        <Aurora
          :color-stops="['#f0f8ff', '#c7dcff', '#ffebeb']"
          :blend="0.5"
          :amplitude="0.8"
          :speed="0.9"
        />
      </div>

      <section class="cf-pane">
        <MessageStream
          :messages="chat.messages.value"
          :features="feat"
          :agent="agent"
          :preset-questions="presetQuestions"
          :kb-names="kbNames"
          :streaming-html="streamingHtml"
          :streaming-thoughts="streamingThoughts"
          :layout="feat.emptyStateLayout"
          :illustration-url="illustrationUrl"
          :is-empty="chat.isEmpty.value"
          @pick-question="askQuestion"
          @select-kb="onSelectKb"
          @follow="askQuestion"
          @stop="onStop"
          @copy="onCopy"
          @regenerate="onRegenerate"
          @vote="onVote"
          @report="openFeedback('report', $event)"
          @open-web="openWeb"
          @open-doc="openDoc($event, false)"
        >
          <template #composer>
            <ChatComposer
              ref="composer"
              :features="feat"
              :meta="adapter.meta ?? {}"
              :busy="chat.busy.value"
              :loading="loading"
              :placeholder="placeholder || `向${agent.name || '智能体'}提问，输入 @ 选择知识库`"
              :max-length="maxLength"
              :upload="upload"
              :params="chatParams"
              :set-params="setParams"
              :permissions="permissions"
              :before-interact="beforeInteract"
              @send="onSend"
              @stop="onStop"
            >
              <!-- composer 扩展点透传给空态输入框：作用域 {params,setParams(,busy)}，与底部输入框绑同一 chatParams。
                   守卫透传，未订阅不渲染，SSE body 与原来一致。 -->
              <template v-if="$slots['composer-above']" #composer-above="s">
                <slot name="composer-above" v-bind="s"></slot>
              </template>
              <template v-if="$slots['composer-tools']" #composer-tools="s">
                <slot name="composer-tools" v-bind="s"></slot>
              </template>
            </ChatComposer>
          </template>
          <!-- 空态品牌区/附加区插槽透传给 MessageStream→EmptyState（接入方定制空态用）。
               v-if 守卫：未传则走默认空态，其它页面不受影响。 -->
          <template v-if="$slots['empty-brand']" #empty-brand="s">
            <slot name="empty-brand" v-bind="s"></slot>
          </template>
          <template v-if="$slots['empty-extra']" #empty-extra="s">
            <slot name="empty-extra" v-bind="s"></slot>
          </template>
          <!-- ai-card 守卫透传给 MessageStream→AiMessage：作用域是整条 message（含 SSE 原始 raw）。
               未订阅则不出现，链路上任一层插槽都不渲染，DOM 与原来逐字节一致。 -->
          <template v-if="$slots['ai-card']" #ai-card="s">
            <slot name="ai-card" v-bind="s"></slot>
          </template>
        </MessageStream>

        <!-- ============================================================
             输入框显示逻辑说明（底部输入框）
             ------------------------------------------------------------
             ChatFlow 组件中有两个输入框（ChatComposer）：

             1. 插槽输入框（在 MessageStream 的 EmptyState 中）
                - 显示条件：features.emptyState && !messages.length
                - 位置：居中，在"猜你想问"上方
                - 场景：新建对话且没有消息时

             2. 底部输入框（当前这个）
                - 显示条件：!features.hideComposer && (!features.emptyState || messages.length > 0)
                - 位置：底部固定
                - 场景：非空状态 或 已有消息数据

             各场景表现：
             | 场景                 | emptyState | messages.length | hideComposer | 插槽输入框 | 底部输入框 | 结果           |
             |---------------------|-----------|----------------|--------------|----------|----------|---------------|
             | 新建对话（刚进入）     | true      | 0              | false        | ✅ 显示   | ❌ 隐藏   | 只有居中输入框   |
             | 发送消息后           | true      | >0             | false        | ❌ 隐藏   | ✅ 显示   | 只有底部输入框   |
             | 点击历史详情         | false     | 0或>0          | false        | ❌ 隐藏   | ✅ 显示   | 只有底部输入框   |
             | 历史记录列表         | -         | -              | true         | ❌ 隐藏   | ❌ 隐藏   | 都不显示       |

             核心规则：
             - 新建对话时，插槽输入框居中显示，用户体验更好
             - 有消息后，切换到底部输入框，符合对话习惯
             - 历史记录列表时，通过 hideComposer=true 隐藏所有输入框
             - 两个输入框不会同时显示，避免重复
             ============================================================ -->
        <ChatComposer
          v-if="!features.hideComposer && (!features.emptyState || chat.messages.value.length > 0)"
          ref="composer"
          :features="feat"
          :meta="adapter.meta ?? {}"
          :busy="chat.busy.value"
          :loading="loading"
          :placeholder="placeholder || `向${agent.name || '智能体'}提问，输入 @ 选择知识库`"
          :max-length="maxLength"
          :upload="upload"
          :show-disclaimer="showDisclaimer"
          :params="chatParams"
          :set-params="setParams"
          :permissions="permissions"
          @send="onSend"
          @stop="onStop"
        >
          <!-- composer 扩展点透传给底部输入框：与空态输入框绑同一 chatParams，两处表现一致。
               守卫透传，未订阅不渲染。 -->
          <template v-if="$slots['composer-above']" #composer-above="s">
            <slot name="composer-above" v-bind="s"></slot>
          </template>
          <template v-if="$slots['composer-tools']" #composer-tools="s">
            <slot name="composer-tools" v-bind="s"></slot>
          </template>
        </ChatComposer>
      </section>

      <RefDrawer
        v-if="feat.refDrawer"
        :open="drawerOpen"
        :mode="drawerMode"
        :web-sources="drawerWeb"
        :doc="drawerDoc"
        :can-back="backSources !== null"
        @close="drawerOpen = false"
        @back="backToList"
        @open-doc="openDoc($event, true)"
      />
    </div>

    <FeedbackModal
      :open="fbOpen"
      :mode="fbMode"
      :ids="fbIds"
      @close="closeFeedback"
      @submit="onFeedback"
    />
    <ToastHost />
  </div>
</template>

<style scoped>
.cf-root{
  display:flex;flex-direction:column;
  height:100%;min-height:0;
  overflow:hidden;
}
/* 抽屉与消息区并排：抽屉展开时把正文挤窄。
   overflow 不挂在这里 —— 会裁掉输入区的下拉浮层 */
.cf-layout{
  position: relative;
  flex:1;
  min-height:0;
  display:flex;
}

/* Aurora 背景层 - 固定在 cf-layout 底部 */
.cf-layout-aurora {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 40vh;
  max-height: 400px;
  pointer-events: none;
  z-index: 0;
}

.cf-pane{
  position: relative;
  z-index: 1;
  flex:1;min-width:0;min-height:0;
  display:flex;flex-direction:column;
  padding: 0 24px;
}

/* 确保内容在 Aurora 之上 */
.cf-pane > :not(.cf-pane-aurora) {
  position: relative;
  z-index: 1;
}

/* H5 响应式布局 */
@media (max-width: 767.98px) {
  .cf-pane {
    padding: 0 calc(16px + env(safe-area-inset-left, 0px)) 0 calc(16px + env(safe-area-inset-right, 0px));
  }

  /* Aurora 背景层在 H5 上调整高度 */
  .cf-layout-aurora {
    height: 30vh;
    max-height: 300px;
  }
}
</style>
