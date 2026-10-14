# 适配器开发指南

## 什么是适配器？

适配器（Adapter）是 ChatFlow 组件与后端 API 之间的桥梁，它定义了一套标准接口，让组件能够适配不同的后端服务。

通过实现适配器接口，你可以将 ChatFlow 组件接入任何 AI 对话服务，无需修改组件代码。

## 适配器接口定义

```typescript
interface Adapter {
  // 发送消息并获取 AI 回复
  sendMessage(params: SendMessageParams): Promise<SendMessageResponse>
  
  // 获取历史会话列表
  getHistory(params: GetHistoryParams): Promise<GetHistoryResponse>
  
  // 删除会话（支持单个或批量）
  deleteSession(sessionId: string | string[]): Promise<void>
  
  // 置顶/取消置顶会话
  pinSession(sessionId: string, pin: boolean): Promise<void>
  
  // 重命名会话
  renameSession(sessionId: string, title: string): Promise<void>
}
```

### 1. sendMessage - 发送消息

这是最核心的方法，负责将用户消息发送给 AI，并返回回复。

**参数：**

```typescript
interface SendMessageParams {
  content: string           // 用户输入的文本
  files?: File[]           // 上传的文件列表
  sessionId?: string       // 会话 ID（续接对话）
  kbIds?: string[]         // 选中的知识库 ID 列表
  modelId?: string         // 选中的模型 ID
  skills?: any[]           // 选中的技能列表
}
```

**返回值：**

```typescript
interface SendMessageResponse {
  sessionId: string        // 会话 ID（新会话或续接）
  message: string          // AI 回复内容
  isStreaming?: boolean    // 是否为流式输出
  sources?: Source[]       // 引用来源（可选）
  thinking?: string        // 思维过程（可选）
}

interface Source {
  title: string
  url?: string
  kbName?: string
  score?: number
}
```

**实现示例：**

```javascript
async sendMessage(params) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  })
  
  const data = await response.json()
  
  return {
    sessionId: data.sessionId,
    message: data.answer,
    sources: data.sources,
    thinking: data.thinking
  }
}
```

**流式输出支持：**

如果你的后端支持 SSE（Server-Sent Events）流式输出，可以这样实现：

```javascript
async sendMessage(params) {
  return new Promise((resolve, reject) => {
    const eventSource = new EventSource(`/api/chat?content=${encodeURIComponent(params.content)}`)
    
    let fullMessage = ''
    let sessionId = ''
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data)
      
      if (data.sessionId) {
        sessionId = data.sessionId
      }
      
      if (data.delta) {
        fullMessage += data.delta
        // 组件会监听 message 的变化来实现流式显示
      }
      
      if (data.done) {
        eventSource.close()
        resolve({
          sessionId,
          message: fullMessage,
          isStreaming: true
        })
      }
    }
    
    eventSource.onerror = (error) => {
      eventSource.close()
      reject(error)
    }
  })
}
```

### 2. getHistory - 获取历史记录

获取用户的历史会话列表，支持分页、搜索和时间筛选。

**参数：**

```typescript
interface GetHistoryParams {
  page: number             // 页码（从 1 开始）
  pageSize: number         // 每页数量
  keyword?: string         // 搜索关键词
  dayNum?: number          // 时间筛选（0=今天, 1-6=近7天, 7-29=近30天, 30-364=近一年, 365+=更多）
}
```

**返回值：**

```typescript
interface GetHistoryResponse {
  list: HistoryItem[]
  totalCount: number
  totalPage: number
  currentPage: number
}

interface HistoryItem {
  sessionId: string        // 会话 ID
  title: string            // 会话标题
  answer: string           // 最后一条 AI 回复（用于预览）
  createTime: number       // 创建时间戳（毫秒）
  updateTime: number       // 更新时间戳（毫秒）
  topFlag: number          // 置顶标志（1=未置顶, 2=已置顶）
  isPinned: boolean        // 是否置顶（便于使用）
  dayNum: number           // 时间分组标识（组件自动分组用）
}
```

**实现示例：**

```javascript
async getHistory(params) {
  const response = await fetch('/api/history', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  })
  
  const data = await response.json()
  
  return {
    list: data.records.map(item => ({
      sessionId: item.id,
      title: item.title,
      answer: item.lastAnswer,
      createTime: item.createTime,
      updateTime: item.updateTime,
      topFlag: item.topFlag,
      isPinned: item.topFlag === 2,
      dayNum: calculateDayNum(item.updateTime)
    })),
    totalCount: data.total,
    totalPage: data.pages,
    currentPage: data.current
  }
}

// 计算 dayNum 的辅助函数
function calculateDayNum(timestamp) {
  const now = Date.now()
  const diff = now - timestamp
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  
  if (days === 0) return 0           // 今天
  if (days <= 6) return days         // 近7天
  if (days <= 29) return days        // 近30天
  if (days <= 364) return days       // 近一年
  return 365                          // 更多
}
```

### 3. deleteSession - 删除会话

删除一个或多个会话。

**参数：**

```typescript
sessionId: string | string[]  // 单个会话 ID 或 ID 数组
```

**实现示例：**

```javascript
async deleteSession(sessionId) {
  const ids = Array.isArray(sessionId) ? sessionId : [sessionId]
  
  await fetch('/api/session/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids })
  })
}
```

### 4. pinSession - 置顶会话

置顶或取消置顶一个会话。

**参数：**

```typescript
sessionId: string   // 会话 ID
pin: boolean        // true=置顶, false=取消置顶
```

**实现示例：**

```javascript
async pinSession(sessionId, pin) {
  await fetch('/api/session/pin', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sessionId,
      topFlag: pin ? 2 : 1
    })
  })
}
```

### 5. renameSession - 重命名会话

修改会话标题。

**参数：**

```typescript
sessionId: string   // 会话 ID
title: string       // 新标题
```

**实现示例：**

```javascript
async renameSession(sessionId, title) {
  await fetch('/api/session/rename', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId, title })
  })
}
```

## 完整示例：基于 Axios 的适配器

```javascript
import axios from 'axios'

class MyAdapter {
  constructor(config = {}) {
    this.baseURL = config.baseURL || '/api'
    this.timeout = config.timeout || 30000
    
    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: this.timeout,
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    // 添加请求拦截器（如 token）
    this.client.interceptors.request.use(config => {
      const token = localStorage.getItem('token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    })
  }
  
  async sendMessage(params) {
    const { data } = await this.client.post('/chat', {
      content: params.content,
      sessionId: params.sessionId,
      kbIds: params.kbIds,
      modelId: params.modelId,
      skills: params.skills
    })
    
    return {
      sessionId: data.sessionId,
      message: data.answer,
      sources: data.sources,
      thinking: data.thinking
    }
  }
  
  async getHistory(params) {
    const { data } = await this.client.post('/history/list', params)
    
    return {
      list: data.records.map(item => ({
        sessionId: item.id,
        title: item.title,
        answer: item.lastAnswer,
        createTime: item.createTime,
        updateTime: item.updateTime,
        topFlag: item.topFlag,
        isPinned: item.topFlag === 2,
        dayNum: this.calculateDayNum(item.updateTime)
      })),
      totalCount: data.total,
      totalPage: data.pages,
      currentPage: data.current
    }
  }
  
  async deleteSession(sessionId) {
    const ids = Array.isArray(sessionId) ? sessionId : [sessionId]
    await this.client.post('/session/delete', { ids })
  }
  
  async pinSession(sessionId, pin) {
    await this.client.post('/session/pin', {
      sessionId,
      topFlag: pin ? 2 : 1
    })
  }
  
  async renameSession(sessionId, title) {
    await this.client.post('/session/rename', { sessionId, title })
  }
  
  calculateDayNum(timestamp) {
    const now = Date.now()
    const diff = now - timestamp
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    
    if (days === 0) return 0
    if (days <= 6) return days
    if (days <= 29) return days
    if (days <= 364) return days
    return 365
  }
}

export default MyAdapter
```

## 使用自定义适配器

```vue
<template>
  <ChatFlow :adapter="adapter" />
</template>

<script setup>
import { ChatFlow } from 'fif-chatflow'
import MyAdapter from './adapters/MyAdapter'

const adapter = new MyAdapter({
  baseURL: 'https://api.example.com',
  timeout: 60000
})
</script>
```

## 错误处理

建议在适配器中统一处理错误：

```javascript
class MyAdapter {
  async sendMessage(params) {
    try {
      const { data } = await this.client.post('/chat', params)
      return data
    } catch (error) {
      console.error('发送消息失败:', error)
      
      // 返回错误消息给用户
      return {
        sessionId: params.sessionId || '',
        message: '抱歉，服务暂时不可用，请稍后重试。',
        error: true
      }
    }
  }
}
```

## Mock 适配器源码参考

组件内置的 `mockAdapter` 是一个很好的参考实现，位于 `src/mock/index.js`：

```javascript
import { mockAdapter } from 'fif-chatflow'

// 查看源码了解完整实现
console.log(mockAdapter.toString())
```

## 最佳实践

1. **统一错误处理** - 在适配器层捕获并处理所有 API 错误
2. **超时设置** - 为长时间的 AI 生成设置合理的超时时间
3. **重试机制** - 对网络错误实现自动重试
4. **日志记录** - 记录关键操作日志便于调试
5. **类型安全** - 使用 TypeScript 定义完整的类型
6. **缓存策略** - 对历史记录等数据实现合理的缓存
7. **权限控制** - 在请求拦截器中统一处理认证和授权
8. **数据转换** - 在适配器层完成后端数据到组件格式的转换，保持组件纯净

## 进阶功能

### 支持多种 AI 服务

```javascript
class MultiModelAdapter {
  constructor(config) {
    this.providers = {
      'openai': new OpenAIAdapter(config.openai),
      'anthropic': new AnthropicAdapter(config.anthropic),
      'local': new LocalAdapter(config.local)
    }
  }
  
  async sendMessage(params) {
    const provider = this.providers[params.modelId] || this.providers.local
    return provider.sendMessage(params)
  }
}
```

### WebSocket 实时通信

```javascript
class WebSocketAdapter {
  constructor() {
    this.ws = new WebSocket('wss://api.example.com/chat')
    this.messageQueue = new Map()
  }
  
  async sendMessage(params) {
    return new Promise((resolve, reject) => {
      const messageId = Date.now().toString()
      
      this.messageQueue.set(messageId, { resolve, reject })
      
      this.ws.send(JSON.stringify({
        id: messageId,
        type: 'chat',
        data: params
      }))
    })
  }
  
  // 监听 WebSocket 消息
  handleMessage(event) {
    const { id, data } = JSON.parse(event.data)
    const handler = this.messageQueue.get(id)
    
    if (handler) {
      handler.resolve(data)
      this.messageQueue.delete(id)
    }
  }
}
```

## 常见问题

### Q: 如何支持文件上传？

A: 在 `sendMessage` 方法中处理 `files` 参数，可以先上传文件获取 URL，再发送给 AI：

```javascript
async sendMessage(params) {
  let fileUrls = []
  
  if (params.files?.length) {
    fileUrls = await Promise.all(
      params.files.map(file => this.uploadFile(file))
    )
  }
  
  return this.client.post('/chat', {
    content: params.content,
    files: fileUrls
  })
}
```

### Q: 如何实现断点续传？

A: 保存 `sessionId`，在后续消息中传递：

```javascript
let currentSessionId = null

async sendMessage(params) {
  const response = await this.client.post('/chat', {
    ...params,
    sessionId: currentSessionId || params.sessionId
  })
  
  currentSessionId = response.sessionId
  return response
}
```

### Q: 如何限制消息长度？

A: 在适配器中做前置校验：

```javascript
async sendMessage(params) {
  if (params.content.length > 10000) {
    throw new Error('消息长度不能超过 10000 字符')
  }
  // ... 发送消息
}
```
